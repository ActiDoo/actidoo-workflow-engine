import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from actidoo_wfe import async_scheduling
from actidoo_wfe.async_scheduling import CronTask, TaskResult, run_scheduler, schedule_cleanup, task_registry
from actidoo_wfe.database import SessionMaker
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