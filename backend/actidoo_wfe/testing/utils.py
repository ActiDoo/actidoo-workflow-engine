# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Shared testing helpers used by application code and test suites."""

import json
import logging
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

from sqlalchemy.orm import Session

from actidoo_wfe.database import SessionLocal

log = logging.getLogger(__name__)


def in_test() -> bool:
    """Return True if we are currently inside a test (set by conftest)."""
    return getattr(sys, "_called_from_test", False)


@dataclass
class CollectedBackgroundTasks:
    """Hold background tasks scheduled during a request so tests can run them synchronously."""

    list_of_tasks: List[Tuple[Callable, Tuple, Dict]]

    def commit_current_db_session_and_execute_tasks(self, db: Session):
        # db is the session used during the request
        db.commit()

        SessionLocal.remove()

        log.debug("Running collected background tasks")
        log.debug(str(self.list_of_tasks))

        for task in self.list_of_tasks:
            from asgi_correlation_id.context import correlation_id

            old_id = correlation_id.get()
            correlation_id.set(None)

            task[0](*task[1], **task[2])

            correlation_id.set(old_id)

        self.list_of_tasks = []

        SessionLocal.remove()


class MockResponse:
    """Create mocked response for tests (aligned with the requests library)."""

    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    @property
    def text(self):
        return json.dumps(self.json_data)


def wait_for_results(results, awaited_result_count, timeout_sec):
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        if len(results) >= awaited_result_count:
            return True
        time.sleep(0.01)  # Sleep for a short interval to avoid busy-waiting
    return False


__all__ = [
    "in_test",
    "CollectedBackgroundTasks",
    "MockResponse",
    "wait_for_results",
]

