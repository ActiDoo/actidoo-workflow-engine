import asyncio
import logging
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from sqlalchemy.orm import Session

from actidoo_wfe.database import SessionLocal

log = logging.getLogger(__name__)


class MyThreadPoolExecutor(ThreadPoolExecutor):
    """This is a custom ThreadPoolExecutor which uses a Queue instead of SimpleQueue. This is needed to safely determine whether there are items left in the queue."""

    def __init__(
        self,
        max_workers: int | None = None,
        thread_name_prefix: str = "",
        initializer: Callable[..., object] | None = None,
        initargs: tuple[Any, ...] = ...,
    ) -> None:
        super().__init__(max_workers, thread_name_prefix, initializer, initargs)
        self._work_queue: queue.Queue = queue.Queue()  # type: ignore

    def is_empty_filter_none(self):
        return len([x for x in self._work_queue.queue if x is not None]) == 0


background_task_executor = MyThreadPoolExecutor(max_workers=50)
"""A global executor instance for running background tasks. Note that this needs to be considered when defining the sqlalchemy pool."""


async def stop_executor():
    """Stops the background task executor. At first it does not accept any new items. After a timeout, all queued(not started) items will be canceled as well. Started items cannot be cancelled."""

    if not background_task_executor._work_queue.empty():
        log.info(
            "Waiting for up to 5 minutes to finish pending and queued background tasks"
        )

    WAIT_FOR_QUEUED = 5 * 60

    background_task_executor.shutdown(wait=False, cancel_futures=False)
    wait_start = time.time()

    while not background_task_executor.is_empty_filter_none():
        await asyncio.sleep(5)
        if time.time() - wait_start > WAIT_FOR_QUEUED:
            log.error(
                "Waited 5 minutes for pending + queued tasks; clearing queue now and finish pending tasks..."
            )
            break

    background_task_executor.shutdown(wait=True, cancel_futures=True)

def commit_db_and_run_background_task(db: Session, task, *args, **kwargs):
    """Commits and queues the task."""
    db.commit()
    SessionLocal.remove()

    def background_task():
        try:
            task(*args, **kwargs)
        except Exception:
            log.exception("Unexpected error during background_task")
        finally:
            SessionLocal.remove()

    background_task_executor.submit(background_task)

def run_background_task(task, *args, **kwargs):
    def background_task():
        try:
            task(*args, **kwargs)
        except Exception:
            log.exception("Unexpected error during background_task")
    # kein Event-Loop nötig
    background_task_executor.submit(background_task)
