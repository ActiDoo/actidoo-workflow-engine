# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import asyncio
import datetime
import uuid
import threading
import time

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from actidoo_wfe import async_scheduling
from actidoo_wfe.async_scheduling import (
    CronRetryPolicy,
    CronTask,
    TaskResult,
    register_task,
    run_scheduler,
    schedule_cleanup,
    clear_task_registry,
    schedule_task,
    task_registry,
    t_task_queue,
    t_task_results,
)
from actidoo_wfe.database import SessionMaker, create_null_pool_engine
from actidoo_wfe.settings import settings


@pytest.mark.asyncio
async def test_scheduler(db_engine_ctx):
    with db_engine_ctx():
        async_scheduling._schedule_every = 1
        async_scheduling._lease_duration = 4
        async_scheduling._refresh_lease = 2
        async_scheduling._worker_idle_sleep_seconds = 1

        # Create the scheduler
        scheduler = run_scheduler(settings=settings)

        # Start the scheduler
        scheduler_task = asyncio.create_task(scheduler)

        # Schedule a task
        task_completed = asyncio.Event()

        def task_function(db: Session):
            # Task logic here
            # Signal completion
            task_completed.set()

        task_registry["test_task"] = CronTask(cron="* * * * * */10", name="test_task", func=task_function)

        while not task_completed.is_set():
            await asyncio.sleep(1)

        # Wait for the task to complete
        scheduler_task.cancel()
        await scheduler_task


@pytest.mark.asyncio
async def test_cleanupAfterRunFindsNoResults(db_engine_ctx):
    with db_engine_ctx():
        async_scheduling._schedule_every = 1
        async_scheduling._lease_duration = 4
        async_scheduling._refresh_lease = 2
        async_scheduling._worker_idle_sleep_seconds = 1
        async_scheduling._keep_task_results = dict(seconds=1)


        # Modify cleanup cron
        del task_registry["ts_schedule_cleanup"]
        task_registry["ts_schedule_cleanup"] = CronTask(cron="* * * * * */3", name="ts_schedule_cleanup", func=schedule_cleanup)

        # Create the scheduler
        scheduler = run_scheduler(settings=settings)

        # Start the scheduler
        scheduler_task = asyncio.create_task(scheduler)

        # Schedule a task
        task_completed = asyncio.Event()

        def task_function(db: Session):
            assert "test_task" in task_registry

            # Task logic here
            # Signal completion
            task_completed.set()

            # delete from registry, such that it wont run again
            del task_registry["test_task"]

        task_registry["test_task"] = CronTask(cron="* * * * * */10", name="test_task", func=task_function)

        while not task_completed.is_set():
            await asyncio.sleep(1)

        await asyncio.sleep(3) # Wait for cleanup to run

        # Wait for the task to complete
        scheduler_task.cancel()
        await scheduler_task


        db: Session = SessionMaker()

        ts_results = [x for x in db.execute(
            select(TaskResult).where(TaskResult.name == "test_task")
        ).scalars()]

        db.close()

        assert len(ts_results) == 0


def test_cron_task_reschedules_if_interval_not_elapsed(db_engine_ctx):
    with db_engine_ctx():
        db: Session = SessionMaker()

        runs: list[str] = []

        def guarded_task(db: Session):
            runs.append("executed")

        task_name = "weekly_status_task"
        task_registry[task_name] = CronTask(cron="0 10 * * tue", name=task_name, func=guarded_task)

        # Step 1: record a previous successful execution to establish the minimum interval baseline
        last_execution = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        db.execute(
            t_task_results.insert().values(
                {
                    "id": uuid.uuid4(),
                    "name": task_name,
                    "executed_at": last_execution,
                    "params": {},
                    "result": {},
                    "error_log": "",
                    "is_error": False,
                }
            )
        )

        # Step 2: enqueue a task that claims to be due now
        task_id = uuid.uuid4()
        db.execute(
            t_task_queue.insert().values(
                {
                    "id": task_id,
                    "execute_after": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1),
                    "name": task_name,
                    "params": {},
                }
            )
        )
        db.commit()

        try:
            # Step 3: run the worker so it evaluates the overdue entry
            async_scheduling.run_worker(settings, db)

            queued_task = db.execute(
                t_task_queue.select().where(t_task_queue.c.id == task_id)
            ).fetchone()

            # Step 4: verify the task was re-enqueued rather than executed
            assert queued_task is not None, "Task should have been re-enqueued"
            assert runs == [], "Task must not execute before minimum interval elapsed"

            min_interval = task_registry[task_name].minimum_interval
            assert min_interval is not None

            # Step 5: confirm the new schedule obeys the next allowed execution time
            persisted_last_execution = (
                db.execute(
                    select(t_task_results.c.executed_at)
                    .where(t_task_results.c.name == task_name)
                    .order_by(t_task_results.c.executed_at.desc())
                )
                .scalars()
                .first()
            )
            assert persisted_last_execution is not None

            expected_next = persisted_last_execution + min_interval
            assert queued_task.execute_after >= expected_next
        finally:
            db.close()
            del task_registry[task_name]


def test_next_allowed_execution_is_none_without_history(db_engine_ctx):
    with db_engine_ctx():
        db: Session = SessionMaker()
        task_name = "ad_hoc_task"
        cron_task = CronTask(cron="0 9 * * mon", name=task_name, func=lambda db: None)
        try:
            assert async_scheduling._next_allowed_execution(db=db, task=cron_task) is None
        finally:
            db.close()


def test_failed_task_does_not_rerun_immediately(db_engine_ctx):
    with db_engine_ctx():
        db: Session = SessionMaker()
        run_count = {"count": 0}

        def failing_task(db: Session):
            run_count["count"] += 1
            raise RuntimeError("boom")

        task_name = "failing_weekly_task"
        task_registry[task_name] = CronTask(cron="0 10 * * tue", name=task_name, func=failing_task)

        try:
            # Step 1: enqueue the first execution that will fail
            failing_task_id = uuid.uuid4()
            db.execute(
                t_task_queue.insert().values(
                    {
                        "id": failing_task_id,
                        "execute_after": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=10),
                        "name": task_name,
                        "params": {},
                    }
                )
            )
            db.commit()

            # Step 2: execute the failing task once
            async_scheduling.run_worker(settings, db)

            assert run_count["count"] == 1

            last_result = db.execute(
                t_task_results.select()
                .where(t_task_results.c.name == task_name)
                .order_by(t_task_results.c.executed_at.desc())
            ).fetchone()

            assert last_result is not None
            assert last_result.is_error

            # Step 3: enqueue another immediate run to verify throttling
            new_task_id = uuid.uuid4()
            db.execute(
                t_task_queue.insert().values(
                    {
                        "id": new_task_id,
                        "execute_after": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=10),
                        "name": task_name,
                        "params": {},
                    }
                )
            )
            db.commit()

            # Step 4: run the worker again; it should just requeue the task
            async_scheduling.run_worker(settings, db)

            queued_task = (
                db.execute(t_task_queue.select().where(t_task_queue.c.id == new_task_id))
                .fetchone()
            )

            assert queued_task is not None, "Failed task should be postponed before rerunning"
            assert run_count["count"] == 1

            min_interval = task_registry[task_name].minimum_interval
            assert min_interval is not None
            expected_next = last_result.executed_at + min_interval
            assert queued_task.execute_after >= expected_next
        finally:
            db.close()
            del task_registry[task_name]


def test_task_runs_do_not_overlap(db_engine_ctx):
    with db_engine_ctx():
        task_name = "non_overlapping_task"
        runs: list[str] = []
        previous_tasks = dict(task_registry)
        clear_task_registry()

        def slow_task(db: Session):
            runs.append("executed")

        task_registry[task_name] = CronTask(cron=None, name=task_name, func=slow_task)

        try:
            # Simulate an existing run by holding an advisory lock for this task
            lock_name = f"cron:{task_name}"
            lock_engine = create_null_pool_engine(settings=settings, isolation_level="READ COMMITTED")
            lock_conn = lock_engine.connect()
            lock_conn.execute(text("SELECT GET_LOCK(:lock_name, 0)"), {"lock_name": lock_name})

            # Enqueue another execution for the same task that becomes immediately due
            db = SessionMaker()
            db.execute(
                t_task_queue.insert().values(
                    {
                        "id": uuid.uuid4(),
                        "execute_after": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1),
                        "name": task_name,
                        "params": {},
                    }
                )
            )
            db.commit()
            db.close()

            # Run the worker while the first run is still in progress
            worker_session = SessionMaker()
            async_scheduling.run_worker(settings, worker_session)
            worker_session.close()

            # Release the advisory lock
            lock_conn.execute(text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": lock_name})
            lock_conn.close()
            lock_engine.dispose()

            assert runs == [], "Task should not run while an advisory lock is held"
        finally:
            clear_task_registry()
            task_registry.update(previous_tasks)


def test_schedule_task_persists_keys(db_engine_ctx):
    with db_engine_ctx():
        task_name = "keyed_task"
        previous_tasks = dict(task_registry)
        clear_task_registry()

        def noop(db: Session, params: dict):
            pass

        task_registry[task_name] = CronTask(cron=None, name=task_name, func=noop)

        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            schedule_task(
                task_name=task_name,
                execute_after=now - datetime.timedelta(seconds=1),
                params={"foo": "bar"},
                key_concurrent="group-1",
                key_dedup="dedup-1",
                settings=settings,
            )

            session = SessionMaker()
            async_scheduling.run_worker(settings, session)

            result = (
                session.execute(
                    t_task_results.select().where(t_task_results.c.name == task_name)
                )
                .fetchone()
            )
            session.close()

            assert result is not None
            assert result.key_concurrent == "group-1"
            assert result.key_dedup == "dedup-1"
            assert result.params.get("foo") == "bar"
        finally:
            clear_task_registry()
            task_registry.update(previous_tasks)


def test_concurrency_lock_defers_same_key(db_engine_ctx):
    with db_engine_ctx():
        task_name = "locked_task"
        runs: list[str] = []
        previous_tasks = dict(task_registry)
        clear_task_registry()

        def recorder(db: Session, params: dict):
            runs.append("ran")

        task_registry[task_name] = CronTask(cron=None, name=task_name, func=recorder)

        lock_engine = None
        lock_conn = None
        try:
            lock_engine = create_null_pool_engine(settings=settings, isolation_level="READ COMMITTED")
            lock_conn = lock_engine.connect()
            lock_conn.execute(text("SELECT GET_LOCK(:lock_name, 0)"), {"lock_name": "cron:locked_task:user-1"})

            now = datetime.datetime.now(datetime.timezone.utc)
            task_id = uuid.uuid4()
            db = SessionMaker()
            db.execute(
                t_task_queue.insert().values(
                    {
                        "id": task_id,
                        "execute_after": now - datetime.timedelta(seconds=1),
                        "name": task_name,
                        "params": {},
                        "key_concurrent": "user-1",
                        "key_dedup": "user-1",
                    }
                )
            )
            db.commit()
            db.close()

            worker_session = SessionMaker()
            async_scheduling.run_worker(settings, worker_session)
            worker_session.close()

            db_check = SessionMaker()
            queued = db_check.execute(
                t_task_queue.select().where(t_task_queue.c.id == task_id)
            ).fetchone()
            db_check.close()

            assert runs == []
            assert queued is not None
            assert queued.execute_after > now
        finally:
            if lock_conn is not None:
                lock_conn.execute(text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": "cron:locked_task:user-1"})
                lock_conn.close()
            if lock_engine is not None:
                lock_engine.dispose()
            clear_task_registry()
            task_registry.update(previous_tasks)


def test_dedup_reschedules_latest(db_engine_ctx):
    with db_engine_ctx():
        task_name = "dedup_task"
        runs: list[str] = []
        previous_tasks = dict(task_registry)
        clear_task_registry()

        def run_once(db: Session, params: dict):
            runs.append(params["version"])

        task_registry[task_name] = CronTask(
            cron=None, name=task_name, func=run_once
        )

        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            schedule_task(
                task_name=task_name,
                execute_after=now - datetime.timedelta(seconds=2),
                params={"version": 1},
                key_dedup="user-42",
                key_concurrent="user-42",
                settings=settings,
            )
            schedule_task(
                task_name=task_name,
                execute_after=now - datetime.timedelta(seconds=1),
                params={"version": 2},
                key_dedup="user-42",
                key_concurrent="user-42",
                settings=settings,
            )

            session = SessionMaker()
            async_scheduling.run_worker(settings, session)
            session.close()

            assert runs == [2], "Only the latest deduped task should execute"
        finally:
            clear_task_registry()
            task_registry.update(previous_tasks)


def test_concurrent_keys_allow_parallel(db_engine_ctx):
    with db_engine_ctx():
        task_name = "partitioned_task"
        runs: list[str] = []
        previous_tasks = dict(task_registry)
        clear_task_registry()

        def record(db: Session, params: dict):
            runs.append(params["user"])

        task_registry[task_name] = CronTask(
            cron=None, name=task_name, func=record
        )

        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            schedule_task(
                task_name=task_name,
                execute_after=now - datetime.timedelta(seconds=2),
                params={"user": "A"},
                key_dedup="A",
                key_concurrent="A",
                settings=settings,
            )
            schedule_task(
                task_name=task_name,
                execute_after=now - datetime.timedelta(seconds=2),
                params={"user": "B"},
                key_dedup="B",
                key_concurrent="B",
                settings=settings,
            )

            session1 = SessionMaker()
            session2 = SessionMaker()

            t1 = threading.Thread(target=async_scheduling.run_worker, args=(settings, session1))
            t2 = threading.Thread(target=async_scheduling.run_worker, args=(settings, session2))

            t1.start()
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)

            # In case a task remained queued, drain once more
            drain_session = SessionMaker()
            async_scheduling.run_worker(settings, drain_session)
            drain_session.close()

            session1.close()
            session2.close()

            assert set(runs) == {"A", "B"}, "Tasks with different concurrency keys should both run"
        finally:
            clear_task_registry()
            task_registry.update(previous_tasks)
def test_retry_policy_reschedules_after_failure(db_engine_ctx):
    with db_engine_ctx():
        db: Session = SessionMaker()
        run_count = {"count": 0}

        def flaky_task(db: Session, params: dict):
            assert params == {"foo": "bar"}
            run_count["count"] += 1
            if run_count["count"] == 1:
                raise RuntimeError("fail once")

        # Step 1: register a retry-enabled task that will fail once
        task_name = "retry_task"
        task_registry[task_name] = CronTask(
            cron="0 10 * * tue",
            name=task_name,
            func=flaky_task,
            retry_policy=CronRetryPolicy(retry_delay_seconds=1, max_retries=2),
        )

        try:
            # Step 2: enqueue the initial execution with user params
            first_id = uuid.uuid4()
            db.execute(
                t_task_queue.insert().values(
                    {
                        "id": first_id,
                        "execute_after": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5),
                        "name": task_name,
                        "params": {"foo": "bar"},
                    }
                )
            )
            db.commit()

            # Step 3: run once to capture the failure and schedule a retry
            async_scheduling.run_worker(settings, db)

            assert run_count["count"] == 1

            # Step 4: fetch the retry entry and ensure internal metadata is set
            retry_entry = db.execute(
                t_task_queue.select().where(t_task_queue.c.name == task_name)
            ).fetchone()

            assert retry_entry is not None
            assert retry_entry.params.get("_cron_retry_count") == 1

            db.execute(
                t_task_queue.update()
                .where(t_task_queue.c.id == retry_entry.id)
                .values(execute_after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1))
            )
            db.commit()

            # Step 5: force the retry to execute and clear the queue afterwards
            async_scheduling.run_worker(settings, db)

            assert run_count["count"] == 2

            still_queued = db.execute(
                t_task_queue.select().where(t_task_queue.c.name == task_name)
            ).fetchone()
            assert still_queued is None
        finally:
            db.close()
            del task_registry[task_name]


def test_retry_policy_respects_max_retries(db_engine_ctx):
    with db_engine_ctx():
        db: Session = SessionMaker()

        run_count = {"value": 0}

        def always_fails(db: Session):
            run_count["value"] += 1
            raise RuntimeError("boom")

        # Step 1: register a task allowed to retry only once
        task_name = "limited_retry_task"
        task_registry[task_name] = CronTask(
            cron="0 11 * * tue",
            name=task_name,
            func=always_fails,
            retry_policy=CronRetryPolicy(retry_delay_seconds=1, max_retries=1),
        )

        try:
            # Step 2: run the task once and trigger the single retry
            db.execute(
                t_task_queue.insert().values(
                    {
                        "id": uuid.uuid4(),
                        "execute_after": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5),
                        "name": task_name,
                        "params": {},
                    }
                )
            )
            db.commit()

            # Step 3: execute the first attempt so a retry gets queued
            async_scheduling.run_worker(settings, db)
            assert run_count["value"] == 1

            retry_entry = db.execute(
                t_task_queue.select().where(t_task_queue.c.name == task_name)
            ).fetchone()
            assert retry_entry is not None

            db.execute(
                t_task_queue.update()
                .where(t_task_queue.c.id == retry_entry.id)
                .values(execute_after=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1))
            )
            db.commit()

            # Step 4: execute the retry; no further retries should be scheduled
            async_scheduling.run_worker(settings, db)
            assert run_count["value"] == 2

            final_entry = db.execute(
                t_task_queue.select().where(t_task_queue.c.name == task_name)
            ).fetchone()
            assert final_entry is None
        finally:
            db.close()
            del task_registry[task_name]
