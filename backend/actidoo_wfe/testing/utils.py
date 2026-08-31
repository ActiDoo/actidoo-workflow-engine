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
from actidoo_wfe.wf.constants import ROW_ID_KEY

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


class RowIdCarryError(AssertionError):
    """A hand-written list payload cannot be mapped onto the stored rows."""


def strip_row_ids(data):
    """Return a deep copy of ``data`` without the technical row-id keys the
    engine stamps onto dynamic-list rows (ADR 010) - for comparing task data
    against hand-written expectations."""
    if isinstance(data, dict):
        return {key: strip_row_ids(value) for key, value in data.items() if key != ROW_ID_KEY}
    if isinstance(data, list):
        return [strip_row_ids(item) for item in data]
    return data


def _adopt_row_ids(stored, payload, where="task data"):
    """Give id-less list rows in ``payload`` (in place) the row ids ``stored``
    carries at the same position - what a browser sends when a user edits the
    loaded form without adding or removing rows. A list that brings any id of
    its own is author-managed: it stays untouched, including everything inside
    its rows - positions are not trustworthy there, and guessing would graft
    another row's nested identities onto it.

    Raises :class:`RowIdCarryError` when an id-less list changed its length:
    positions can then no longer say which stored row is meant."""
    if isinstance(stored, dict) and isinstance(payload, dict):
        for key, value in payload.items():
            if key in stored:
                _adopt_row_ids(stored[key], value, where=key)
        return
    if not (isinstance(stored, list) and isinstance(payload, list)):
        return

    # An empty payload list legally clears the list - only non-empty id-less
    # lists need (and can get) the stored identities.
    payload_rows = [row for row in payload if isinstance(row, dict)]
    adopt = (
        bool(payload_rows)
        and not any(row.get(ROW_ID_KEY) for row in payload_rows)
        and any(isinstance(row, dict) and row.get(ROW_ID_KEY) for row in stored)
    )
    if not adopt:
        return
    if len(payload) != len(stored):
        raise RowIdCarryError(
            f"dynamic list at '{where}' was handed out with {len(stored)} rows carrying row ids, "
            f"but the payload holds {len(payload)} id-less rows - positions cannot say which "
            f"stored row each payload row means. Start from the handed-out task data (or set "
            f"the row ids yourself) to express which rows remain, or pass carry_row_ids=False "
            f"to submit() to send the payload untouched."
        )
    for stored_row, payload_row in zip(stored, payload):
        if isinstance(stored_row, dict) and isinstance(payload_row, dict):
            if stored_row.get(ROW_ID_KEY):
                payload_row[ROW_ID_KEY] = stored_row[ROW_ID_KEY]
            _adopt_row_ids(stored_row, payload_row, where=where)


def wait_for_results(results, awaited_result_count, timeout_sec):
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        if len(results) >= awaited_result_count:
            return True
        time.sleep(0.01)  # Sleep for a short interval to avoid busy-waiting
    return False


__all__ = [
    "in_test",
    "RowIdCarryError",
    "strip_row_ids",
    "CollectedBackgroundTasks",
    "MockResponse",
    "wait_for_results",
]
