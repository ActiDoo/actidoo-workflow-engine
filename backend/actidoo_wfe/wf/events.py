"""
Event System Module

This module provides a simple event system for handling events.
Events should be published from the service layer, and handlers can be attached to 
specific event types using the @handler decorator.

Classes:
    Event: Base class for all events.
    Concrete Event Classes:
      e.g. UserAssignedToReadyTaskEvent: Event class for when a user is assigned to a ready task or an already assigned task becomes ready.

Functions:
    publish_event(event): Publishes an event to all registered handlers.
    handler(event_type): Decorator for registering event handlers.

Usage:
    To define a new event, create a subclass of the Event class and add the necessary attributes (in this module).
    Use the @handler decorator to register a function as an event handler for a specific event type.
    Use the publish_event function to publish events, triggering all registered handlers for that event type.

Example:
    class UserAssignedToTaskEvent(Event):
        user_id: uuid.UUID
        task_id: uuid.UUID
    
    @handler(UserAssignedToTaskEvent)
    def handle_user_assigned_to_task(event: UserAssignedToTaskEvent):
        print(f"Handling event: User {event.user_id} assigned to task {event.task_id}")

    event = UserAssignedToTaskEvent(user_id=uuid.uuid4(), task_id=uuid.uuid4())
    publish_event(event)
"""

import logging
import uuid
from functools import wraps

import pydantic
from sqlalchemy import event
from sqlalchemy.orm import Session

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.helpers.concurrency import run_background_task

log = logging.getLogger(__name__)


class Event(pydantic.BaseModel):
    pass


class UserAssignedToReadyTaskEvent(Event):
    user_id: uuid.UUID
    task_id: uuid.UUID

class TaskBecameErroneousEvent(Event):
    task_id: uuid.UUID

handlers = {}
session_events = {}

def publish_event(event: Event, session: Session|None = None):
    """Collects an event to be published after transaction commit."""
    if session is None:
        session = SessionLocal()

    if session is None or not session.in_transaction():
        _handle_event(event)
    else:
        if session not in session_events:
            session_events[session] = []
        session_events[session].append(event)

        
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

def handle_pending_events(session):
    """Handles all collected events for a given session."""
    if session in session_events:
        while session_events[session]:
            event = session_events[session].pop(0)
            _handle_event(event)
            

def _handle_event(event):
    event_type = type(event)
    if event_type in handlers:
        for handler in handlers[event_type]:
            run_background_task(handler, event=event)


def after_commit(session):
    handle_pending_events(session)
    cleanup_session_events(session, None)

def cleanup_session_events(session, transaction=None):
    """Cleans up session events to prevent memory leaks."""
    if transaction is None or (not transaction.nested and transaction.parent is None):
        if session in session_events:
            if len(session_events[session])>0:
                log.error("Cleaning non-empty session_events queue in cleanup_session_events")
            del session_events[session]

event.listen(Session, 'after_commit', after_commit)
event.listen(Session, 'after_transaction_end', cleanup_session_events)
event.listen(Session, 'after_rollback', cleanup_session_events)
