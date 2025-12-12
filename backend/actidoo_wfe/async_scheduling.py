import asyncio
import datetime
import inspect
import logging
import time
import traceback
import uuid
from typing import Callable

import asyncer
import croniter
import pytz
import sqlalchemy.types as ty
import venusian
from sqlalchemy import Connection, func, literal_column, select, text
from sqlalchemy.dialects.mysql import JSON, insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.schema import Table

from actidoo_wfe.constants import CRON_TIMEZONE, INSTANCE_NAME
from actidoo_wfe.database import Base, SessionLocal, UTCDateTime, create_null_pool_engine
from actidoo_wfe.helpers.time import (
    dt_ago_naive,
    dt_in_aware,
    dt_now_naive,
    to_timezone_naive_in_utc,
)
from actidoo_wfe.settings import Settings

_log = logging.getLogger(__name__)

# When does a master-lock timeout?
_lease_duration = 30

# How often do we refresh the master-lock?
_refresh_lease = 5

# How often do we want to compute the schedule for cron tasks?
_schedule_every = 30

# When do we want to delete task results?
_keep_task_results = dict(days=10)

# If a worker has not tasks, how long should it wait for polling?
_worker_idle_sleep_seconds = 5

# Assertion that the master-lock refresh time is not too big
assert _refresh_lease < _lease_duration / 2

class MasterInstance(Base):
    __tablename__ = "master_instance"

    id: Mapped[int] = mapped_column(ty.Integer, primary_key=True)
    instance_name: Mapped[str] = mapped_column(ty.String(255), nullable=False, unique=True)
    last_updated: Mapped[datetime.datetime] = mapped_column(UTCDateTime(),server_default=func.now())

class TaskQueue(Base):
    __tablename__ = "ts_queue"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    execute_after: Mapped[datetime.datetime] = mapped_column(UTCDateTime(), nullable=True, default=None)
    name: Mapped[str] = mapped_column(ty.String(255), nullable=False)
    params: Mapped[dict] = mapped_column(JSON(), nullable=False, default={})
 
class TaskResult(Base):
    __tablename__ = "ts_results"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(ty.String(255), nullable=False, index=True)
    executed_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    params: Mapped[dict] = mapped_column(JSON(), nullable=False, default={})
    result: Mapped[dict] = mapped_column(JSON(), nullable=False, default={})
    error_log: Mapped[str] = mapped_column(ty.Text, nullable=False, default="")
    is_error: Mapped[bool] = mapped_column(ty.Boolean, nullable=False, default=False)

t_master_instance: Table = MasterInstance.__table__ # type: ignore
t_task_queue: Table = TaskQueue.__table__ # type: ignore
t_task_results: Table = TaskResult.__table__ # type: ignore


class CancelledStatus:
    def __init__(self):
        self.is_cancelled = False


async def run_scheduler(settings: Settings):
    cancelled_status = CancelledStatus()
    try:
        _log.info("Starting scheduler")
        await asyncio.gather(
            asyncer.asyncify(loop_elect_master_instance, abandon_on_cancel=True)(settings=settings, instance_name=INSTANCE_NAME, cancelled_status=cancelled_status),
            asyncer.asyncify(loop_schedule_next_executions, abandon_on_cancel=True)(settings=settings, instance_name=INSTANCE_NAME, cancelled_status=cancelled_status),
            asyncer.asyncify(loop_worker, abandon_on_cancel=True)(settings=settings, cancelled_status=cancelled_status),
        )
    except asyncio.CancelledError:
        cancelled_status.is_cancelled = True
        _log.info("Stopping scheduler")


def loop_elect_master_instance(settings: Settings, instance_name:str, cancelled_status: CancelledStatus):
    while True:
        if cancelled_status.is_cancelled:
            break
    
        engine = None
        try:
            engine = create_null_pool_engine(settings=settings, isolation_level="READ COMMITTED")
            # we use read committed with "for update" selects to achieve consistency
            # (https://vladmihalcea.com/a-beginners-guide-to-database-locking-and-the-lost-update-phenomena/)
            with engine.connect() as conn:
                elect_master_instance(conn, instance_name=instance_name)
        except Exception:
            _log.exception("error during master election")
        finally:
            if engine is not None:
                engine.dispose()
 
        for i in range(0, _refresh_lease):
            if not cancelled_status.is_cancelled:
                time.sleep(1.0)


def elect_master_instance(conn: Connection, instance_name):
    try:

        conn.execute(text("LOCK TABLES master_instance WRITE;"))
        
        row = conn.execute(
            select(
                t_master_instance.c.id,
                t_master_instance.c.instance_name,
                t_master_instance.c.last_updated,
                literal_column(f"DATE_SUB(CURRENT_TIMESTAMP, INTERVAL {_lease_duration} SECOND)", UTCDateTime).label("mintime")
            ).select_from(t_master_instance).with_for_update()
        ).fetchone()
        
        if row is None:
            conn.execute(
                insert(t_master_instance).values(
                    id=1,
                    instance_name = instance_name,
                    last_updated = text("CURRENT_TIMESTAMP")
                )
            )
        elif row.instance_name == instance_name or row.last_updated < row.mintime:
            conn.execute(
                t_master_instance.update().values(
                    id=1,
                    instance_name = instance_name,
                    last_updated = text("CURRENT_TIMESTAMP")
                )
            )
        else:
            conn.rollback()
            return None
        
        conn.commit()
        return instance_name
    except OperationalError:
        _log.exception("Error during master election")
        conn.rollback()
        return None
    except Exception:
        _log.exception("Error during master election")
        conn.rollback()
        return None
    finally:
        conn.execute(text("UNLOCK TABLES"))

def is_master_instance(conn: Connection, instance_name):
    try:
        row = conn.execute(
            select(
                t_master_instance.c.id,
                t_master_instance.c.instance_name,
                t_master_instance.c.last_updated,
                literal_column(f"DATE_SUB(CURRENT_TIMESTAMP, INTERVAL {_lease_duration} SECOND)", UTCDateTime).label("mintime")
            ).select_from(t_master_instance)
        ).fetchone()
        if row is not None and row.instance_name == instance_name and row.last_updated >= row.mintime:
            return True
        return False
    except OperationalError:
        _log.exception("Error during master check")
        return False
    except Exception:
        _log.exception("Error during master check")
        return False
    finally:
        conn.rollback()


class CronTask:
    def __init__(self, name:str, cron: str, func: Callable):
        self.croniter = croniter.croniter(cron, start_time=dt_now_naive().astimezone(pytz.timezone(CRON_TIMEZONE)), day_or=False)
        self.func = func
        self.name = name
    
    def next(self):
        return self.croniter.get_next(ret_type=datetime.datetime, start_time=dt_now_naive().astimezone(pytz.timezone(CRON_TIMEZONE)))
    
task_registry: dict[str, CronTask] = dict()

def clear_task_registry():
    task_registry.clear()

def cron_task(task_name: str, cron: str):
    """
        Use with 
            @cron_task("* * * * *")
            def mytask(db: Session):
                pass
    """
    def decorator(
        wrapped: Callable[
            [
                Session
            ],
            None,
        ],
    ):
        def callback(scanner, name, ob):
            if task_name in task_registry:
                raise Exception(f"Duplicate cron task definition {task_name}")
            task_registry[task_name] = CronTask(cron=cron, name=task_name, func=wrapped)
        venusian.attach(wrapped, callback)
        return wrapped
    return decorator

def loop_schedule_next_executions(settings: Settings, instance_name:str, cancelled_status: CancelledStatus):
    while True:
        if cancelled_status.is_cancelled:
            break
    
        engine = None
        try:
            engine = create_null_pool_engine(settings=settings, isolation_level="READ COMMITTED")
            with engine.connect() as conn:
                if is_master_instance(conn=conn, instance_name=instance_name):
                    schedule_next_executions(conn)
        except Exception:
            _log.exception("error during master election")
        finally:
            if engine is not None:
                engine.dispose()
 
        for i in range(0, _schedule_every):
            if not cancelled_status.is_cancelled:
                time.sleep(1.0)

def schedule_next_executions(conn: Connection):
    for task in list(task_registry.values()):
        task_next = task.next()
        task_next_utc = to_timezone_naive_in_utc(task_next)

        db_next_run = conn.execute(
            t_task_queue.select().where(
                t_task_queue.c.name == task.name
            )
        ).fetchone()
        if db_next_run is None:
            _log.debug(f"Scheduling task {task.name} at {str(task_next_utc)}")
            conn.execute(
                t_task_queue.insert().values({
                    "execute_after": task_next_utc,
                    "name": task.name,
                    "params": dict()
                })
            )
        elif db_next_run.execute_after >= dt_in_aware(minutes=5) and to_timezone_naive_in_utc(db_next_run.execute_after) != task_next_utc:
            _log.debug(f"Update existing task schedule {task.name} at {str(task_next_utc)}")
            conn.execute(t_task_queue.update().values({
                    "execute_after": task_next_utc,
                    "name": task.name,
                    "params": dict()
            }).where(
                t_task_queue.c.name == task.name
            ))
        conn.commit()


@cron_task(task_name="ts_schedule_cleanup", cron="1 * * * *")
def schedule_cleanup(db: Session):
    db.execute(t_task_results.delete().where(
        t_task_results.c.executed_at <= dt_ago_naive(**_keep_task_results)
    ))
    db.commit()


def loop_worker(settings: Settings, cancelled_status: CancelledStatus):
    while True:
        if cancelled_status.is_cancelled:
            break
    
        
        try_again = True
        while try_again:
            engine = None

            if cancelled_status.is_cancelled:
                break

            try:
                engine = create_null_pool_engine(settings=settings, isolation_level="READ COMMITTED")
                # we use read committed with "for update" selects to achieve consistency;
                # REPEATABLE_READ would also work, but leads to a lot of logged errors (which are okay)
                # (https://vladmihalcea.com/a-beginners-guide-to-database-locking-and-the-lost-update-phenomena/)
                with engine.connect() as conn:
                    db = Session(bind=conn)
                    try_again = run_worker(settings, db)
                    
            except OperationalError:
                _log.exception("Error while running worker")
                try_again = True
            except Exception:
                _log.exception("Error while running worker")
                try_again = False
            finally:
                if engine is not None:
                    engine.dispose()

        for i in range(0, _worker_idle_sleep_seconds):
            if not cancelled_status.is_cancelled:
                time.sleep(1.0)
        

def run_worker(settings, db: Session):
    has_found_task = False

    db_next_run = db.execute(
        t_task_queue.select().with_for_update().where(
            t_task_queue.c.execute_after <= text("CURRENT_TIMESTAMP"),   
        ).order_by(text("rand()")).limit(1)
    ).fetchone()

    if db_next_run is not None:
        has_found_task = True
        db.execute(
            t_task_queue.delete().where(t_task_queue.c.id == db_next_run.id)
        )

        if db_next_run.name not in task_registry:
            _log.error(f"Scheduled task {db_next_run.name} not found in task_registry; Removing schedule.")
            db.commit()
            return True
        else:
            task: CronTask = task_registry[db_next_run.name]
            
            kw = dict()

            if "db" in inspect.signature(task.func).parameters:
                task_db_session = SessionLocal()
                kw["db"] = SessionLocal()

            if "params" in inspect.signature(task.func).parameters:
                kw["params"] = db_next_run.params

            error_log = None

            result = {}
            try:
                result = task.func(**kw)
            except Exception:
                _log.exception(f"Executing task failed (name: {task.name})")
                error_log = traceback.format_exc()
            finally:
                if task_db_session is not None:
                    task_db_session.close()

                db.execute(
                    t_task_results.insert().values({
                        "id": db_next_run.id,
                        "name": db_next_run.name,
                        "executed_at": text("CURRENT_TIMESTAMP"),
                        "params": db_next_run.params,
                        "result": result,
                        "error_log": error_log or "",
                        "is_error": error_log is not None
                    })
                )
    
    db.commit()

    return has_found_task

