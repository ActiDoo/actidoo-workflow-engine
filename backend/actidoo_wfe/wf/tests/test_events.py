# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import time
import uuid

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.testing.utils import wait_for_results
from actidoo_wfe.wf import events


@pytest.fixture(scope="function")
def clean_handlers():
    old_handlers = events.handlers
    events.handlers = {}
    try:
        yield
    finally:
        events.handlers = old_handlers


def test_handler_registration_and_execution(db_engine_ctx, clean_handlers):
    with db_engine_ctx():
        session = SessionLocal()
        results = []

        events.handlers[events.TaskReadyForUserNotificationEvent] = []

        @events.event_handler(events.TaskReadyForUserNotificationEvent)
        def handle_event(event: events.TaskReadyForUserNotificationEvent):
            results.append(event)

        event_instance = events.TaskReadyForUserNotificationEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
        events.publish_event(event_instance, session)

        wait_for_results(results, 1, 2)

        assert len(results) == 1
        assert results[0] == event_instance


def test_event_handling_no_transaction(db_engine_ctx, clean_handlers):
    with db_engine_ctx():
        session = SessionLocal()
        results = []

        events.handlers[events.TaskReadyForUserNotificationEvent] = []

        @events.event_handler(events.TaskReadyForUserNotificationEvent)
        def handle_event(event: events.TaskReadyForUserNotificationEvent):
            results.append(event)

        assert not session.in_transaction()

        event_instance = events.TaskReadyForUserNotificationEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
        events.publish_event(event_instance, session)

        wait_for_results(results, 1, 2)

        assert len(results) == 1
        assert results[0] == event_instance


def test_event_handling_in_transaction(db_engine_ctx, clean_handlers):
    with db_engine_ctx():
        session = SessionLocal()
        session.begin()
        results = []

        events.handlers[events.TaskReadyForUserNotificationEvent] = []

        @events.event_handler(events.TaskReadyForUserNotificationEvent)
        def handle_event(event: events.TaskReadyForUserNotificationEvent):
            time.sleep(0.5)
            results.append(event)

        assert session.in_transaction()

        event_instance = events.TaskReadyForUserNotificationEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
        events.publish_event(event_instance, session)

        session.commit()

        wait_for_results(results, 1, 2)

        assert len(results) == 1
        assert results[0] == event_instance


def test_closing_an_uncommitted_session_discards_events(db_engine_ctx, monkeypatch):
    with db_engine_ctx():
        delivered = []
        monkeypatch.setattr(events, "_handle_event", delivered.append)
        db = SessionLocal()
        db.begin()
        events.publish_event(events.TaskBecameErroneousEvent(task_id=uuid.uuid4()), db)
        db.close()
        with db.begin():
            pass
        assert delivered == []


def test_savepoint_events_follow_their_transaction(db_engine_ctx, monkeypatch):
    with db_engine_ctx():
        delivered = []
        monkeypatch.setattr(events, "_handle_event", delivered.append)
        db = SessionLocal()
        outer, kept, discarded = [events.TaskBecameErroneousEvent(task_id=uuid.uuid4()) for _ in range(3)]
        with db.begin():
            events.publish_event(outer, db)
            with db.begin_nested():
                events.publish_event(kept, db)
            preview = db.begin_nested()
            with db.begin_nested():
                events.publish_event(discarded, db)
            preview.rollback()
            assert delivered == []
        assert delivered == [outer, kept]

        db.begin()
        with db.begin_nested():
            events.publish_event(discarded, db)
        db.rollback()
        assert delivered == [outer, kept]


def test_task_ready_for_role_notification_event_dispatches_handler(db_engine_ctx, clean_handlers):
    with db_engine_ctx():
        session = SessionLocal()
        results = []

        events.handlers[events.TaskReadyForRoleNotificationEvent] = []

        @events.event_handler(events.TaskReadyForRoleNotificationEvent)
        def handle_event(event: events.TaskReadyForRoleNotificationEvent):
            results.append(event)

        event_instance = events.TaskReadyForRoleNotificationEvent(task_id=uuid.uuid4())
        events.publish_event(event_instance, session)

        wait_for_results(results, 1, 2)

        assert len(results) == 1
        assert results[0] == event_instance
        assert results[0].task_id == event_instance.task_id
