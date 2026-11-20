# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""
Event System Module

This module provides a simple event system for handling events.
Events should be published from the service layer, and handlers can be attached to
specific event types using the @handler decorator.

Classes:
    Event: Base class for all events.
    Concrete Event Classes:
      e.g. TaskReadyForUserNotificationEvent: Event class for when a ready task should trigger a notification to its assigned user.

Functions:
    publish_event(event): Publishes an event to all registered handlers.
    handler(event_type): Decorator for registering event handlers.

Usage:
    To define a new event, create a subclass of the Event class and add the necessary attributes (in this module).
    Use the @handler decorator to register a function as an event handler for a specific event type.
    Use the publish_event function to publish events, triggering all registered handlers for that event type.

Example:
    class TaskReadyForUserNotificationEvent(Event):
        user_id: uuid.UUID
        task_id: uuid.UUID

    @handler(TaskReadyForUserNotificationEvent)
    def handle_task_ready_for_user_notification(event: TaskReadyForUserNotificationEvent):
        print(f"Handling event: notify user {event.user_id} about ready task {event.task_id}")

    event = TaskReadyForUserNotificationEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
    publish_event(event)
"""

import uuid
from functools import wraps

import pydantic
from sqlalchemy import event
from sqlalchemy.orm import Session, SessionTransaction

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.helpers.concurrency import run_background_task


class Event(pydantic.BaseModel):
    pass


class TaskReadyForUserNotificationEvent(Event):
    user_id: uuid.UUID
    task_id: uuid.UUID


class TaskReadyForRoleNotificationEvent(Event):
    task_id: uuid.UUID


class TaskBecameErroneousEvent(Event):
    task_id: uuid.UUID


handlers = {}
_EVENT_QUEUES = "workflow_event_queues"


def publish_event(event: Event, session: Session | None = None):
    """Collects an event to be published after transaction commit."""
    if session is None:
        session = SessionLocal()

    transaction = session.get_nested_transaction() or session.get_transaction()
    if transaction is None:
        _handle_event(event)
    else:
        queues = session.info.setdefault(_EVENT_QUEUES, {})
        queues.setdefault(transaction, []).append(event)


def event_handler(event_type):
    def decorator(func):
        if event_type not in handlers:
            handlers[event_type] = []
        handlers[event_type].append(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def _handle_event(event):
    event_type = type(event)
    if event_type in handlers:
        for handler in handlers[event_type]:
            run_background_task(handler, event=event)


def handle_pending_events(session: Session):
    """Dispatch events collected for the current transaction."""
    transaction = session.get_nested_transaction() or session.get_transaction()
    for entry in session.info.get(_EVENT_QUEUES, {}).pop(transaction, []):
        _handle_event(entry)


@event.listens_for(Session, "after_commit")
def after_commit(session: Session):
    nested = session.get_nested_transaction()
    if nested is None:
        handle_pending_events(session)
    else:
        # Releasing a savepoint moves its events to the parent. Only the outer
        # commit can publish them, since a surrounding savepoint may roll back.
        queues = session.info.get(_EVENT_QUEUES, {})
        pending = queues.pop(nested, [])
        if pending:
            queues.setdefault(nested.parent, []).extend(pending)


@event.listens_for(Session, "after_transaction_end")
def cleanup_session_events(session: Session, transaction: SessionTransaction | None = None):
    if transaction is None or transaction.parent is None:
        session.info.pop(_EVENT_QUEUES, None)
    else:
        # A commit already moved the queue. Rollback or close discards it.
        session.info.get(_EVENT_QUEUES, {}).pop(transaction, None)
