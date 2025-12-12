import time
import uuid

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.helpers.tests import wait_for_results
from actidoo_wfe.wf import events


@pytest.fixture(scope='function')
def clean_handlers():
    old_handlers = events.handlers
    events.handlers = {}
    events.session_events = {}
    try:
        yield
    finally:
        events.handlers = old_handlers

def test_publish_event_collects_event(db_engine_ctx, clean_handlers):
    with db_engine_ctx():
        session = SessionLocal()
        session.begin()
        event_instance = events.UserAssignedToReadyTaskEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
        events.publish_event(event_instance, session)
        
        assert session in events.session_events
        assert events.session_events[session][0] == event_instance

def test_handler_registration_and_execution(db_engine_ctx, clean_handlers):
    with db_engine_ctx():
        session = SessionLocal()
        results = []

        events.handlers[events.UserAssignedToReadyTaskEvent]=[]

        @events.event_handler(events.UserAssignedToReadyTaskEvent)
        def handle_event(event: events.UserAssignedToReadyTaskEvent):
            results.append(event)
        
        event_instance = events.UserAssignedToReadyTaskEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
        events.publish_event(event_instance, session)
        
        events.handle_pending_events(session)
        
        wait_for_results(results, 1, 2)

        assert len(results) == 1
        assert results[0] == event_instance

def test_event_handling_no_transaction(db_engine_ctx, clean_handlers):
    with db_engine_ctx():
        session = SessionLocal()
        results = []

        events.handlers[events.UserAssignedToReadyTaskEvent]=[]

        @events.event_handler(events.UserAssignedToReadyTaskEvent)
        def handle_event(event: events.UserAssignedToReadyTaskEvent):
            results.append(event)
        
        assert not session.in_transaction()

        event_instance = events.UserAssignedToReadyTaskEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
        events.publish_event(event_instance, session)

        wait_for_results(results, 1, 2)

        assert len(results) == 1
        assert results[0] == event_instance

def test_event_handling_in_transaction(db_engine_ctx, clean_handlers):
    with db_engine_ctx():
        session = SessionLocal()
        session.begin()
        results = []

        events.handlers[events.UserAssignedToReadyTaskEvent]=[]

        @events.event_handler(events.UserAssignedToReadyTaskEvent)
        def handle_event(event: events.UserAssignedToReadyTaskEvent):
            time.sleep(0.5)
            results.append(event)
        
        assert session.in_transaction()

        event_instance = events.UserAssignedToReadyTaskEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
        events.publish_event(event_instance, session)

        session.commit()

        wait_for_results(results, 1, 2)

        assert len(results) == 1
        assert results[0] == event_instance

def test_cleanup_session_events(db_engine_ctx, clean_handlers):
    with db_engine_ctx():
        session = SessionLocal()
        event_instance = events.UserAssignedToReadyTaskEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
        events.publish_event(event_instance, session)
        
        events.cleanup_session_events(session, None)
        
        assert session not in events.session_events

def test_cleanup_after_transaction_end(db_engine_ctx, clean_handlers):
    with db_engine_ctx():
        session = SessionLocal()
        event_instance = events.UserAssignedToReadyTaskEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
        events.publish_event(event_instance, session)
        
        session.rollback()
        
        assert session not in events.session_events


def test_user_assigned_to_task_event(db_engine_ctx):
    with db_engine_ctx():
        session = SessionLocal()
        event_instance = events.UserAssignedToReadyTaskEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
        events.publish_event(event_instance, session)
        
        session.rollback()
        
        assert session not in events.session_events
