# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging
import random
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Index, delete, func
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.types import DateTime, String

from actidoo_wfe.database import Base, JSONBlob, create_null_pool_engine
from actidoo_wfe.settings import settings

logger = logging.getLogger(__name__)

class Namespace:
    _instances:dict = {}

    def __new__(cls, name: str, ttl: timedelta):
        if name in cls._instances:
            raise ValueError(f"Namespace with name '{name}' already exists")
        
        instance = super().__new__(cls)
        cls._instances[name] = instance
        return instance

    def __init__(self, name: str, ttl: timedelta):
        self.name = name
        self.ttl = ttl

    @classmethod
    def get(cls, name: str) -> 'Namespace':
        return cls._instances.get(name)
    
    @classmethod
    def clear_instances(cls):
        """ This must only be used for testing!! """
        cls._instances.clear()

    def __repr__(self) -> str:
        return f"<Namespace(name={self.name}, ttl={self.ttl})>"
    
LOCK_TIMEOUT = timedelta(minutes=30)
RETRY_INTERVAL_MIN = 0.5  # minimum wait time in seconds
RETRY_INTERVAL_MAX = 2.0  # maximum wait time in seconds
MAX_RETRIES = 10

class Cache(Base):
    __tablename__ = 'cache_data'

    namespace: Mapped[str] = mapped_column(String(255), primary_key=True)
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(JSONBlob, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index('ix_cache_namespace_key', 'namespace', 'key', unique=True),
        Index('ix_cache_created_at', 'created_at'),
    )


class Lock(Base):
    __tablename__ = 'cache_lock'

    namespace: Mapped[str] = mapped_column(String(255), primary_key=True)
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index('ix_lock_namespace_key', 'namespace', 'key', unique=True),
        Index('ix_lock_created_at', 'created_at'),
    )


class CouldNotLockException(Exception):
    pass


@contextmanager
def acquire_lock(session: Session, namespace: Namespace, key: str, lock_timeout=LOCK_TIMEOUT, retries=10):
    try:
        _acquire_lock(session, namespace, key, lock_timeout)
        yield
    except CouldNotLockException as e:
        if retries > 0:
            time.sleep(random.uniform(RETRY_INTERVAL_MIN, RETRY_INTERVAL_MAX))
            acquire_lock(session, namespace, key, lock_timeout, retries - 1)
        else:
            raise e

def _acquire_lock(session: Session, namespace: Namespace, key: str, lock_timeout=LOCK_TIMEOUT):
    now = datetime.utcnow()
    locked = False
    try:
        # Try to acquire the lock
        lock = session.query(Lock).filter_by(namespace=namespace.name, key=key).one_or_none()
        if lock:
            # If the lock exists and is not expired, raise an exception
            if now - lock.created_at < lock_timeout:
                raise CouldNotLockException("Lock already acquired and not expired")
            else:
                # If the lock is expired, delete it
                session.delete(lock)
                session.commit()

        # Create a new lock
        lock = Lock(namespace=namespace.name, key=key, created_at=now)
        session.add(lock)
        session.commit()
        locked = True
        yield
    except (IntegrityError, OperationalError) as e:
        session.rollback()
        raise CouldNotLockException()
    finally:
        if locked:
            try:
                session.execute(delete(Lock).filter_by(namespace=namespace.name, key=key))
                session.commit()
            except Exception as e:
                logger.error(f"Failed to delete lock for {namespace.name}:{key}.", exc_info=e)
                session.rollback()


def get_or_compute(session: Session, namespace: Namespace, key: str, creator) -> Any:
    now = datetime.utcnow()
    ttl = namespace.ttl
    retries = 0

    # first try with existing session (REPEATABLE READ, might get old data)
    cache_item = session.query(Cache).filter_by(namespace=namespace.name, key=key).one_or_none()

    if cache_item and now - cache_item.created_at < ttl:
        return cache_item.value

    # if no valid value was found, we will try the search-or-compute loop in a new session in READ COMMITTED mode
    while retries < MAX_RETRIES:        
        try:
            engine = create_null_pool_engine(settings=settings, isolation_level="READ COMMITTED")
            new_session: Session = Session(bind=engine)
            cache_item = new_session.query(Cache).filter_by(namespace=namespace.name, key=key).one_or_none()

            if cache_item and now - cache_item.created_at < ttl:
                return cache_item.value
            
            with acquire_lock(new_session, namespace, key): #commit in acquire_lock
                value = creator()
                new_session.query(Cache).filter_by(namespace=namespace.name, key=key).delete()
                
                new_cache_item = Cache(namespace=namespace.name, key=key, value=value)
                new_session.add(new_cache_item)
                return value
        except CouldNotLockException as e:
            logger.warning(f"Could not acquire lock for {namespace.name}:{key} due to {repr(e)}, retrying... ({retries + 1}/{MAX_RETRIES})")
            retries += 1
        finally:
            new_session.close()
            engine.dispose()
        
        sleep_time = random.uniform(RETRY_INTERVAL_MIN, RETRY_INTERVAL_MAX)
        time.sleep(sleep_time)
            
    
    raise Exception(f"Failed to acquire lock for {namespace.name}:{key} after {MAX_RETRIES} retries")
