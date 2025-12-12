import threading
from datetime import datetime, timedelta

import pytest

from actidoo_wfe.cache import Cache, Namespace, get_or_compute
from actidoo_wfe.database import SessionLocal

DEFAULT_NAMESPACE = Namespace("default", timedelta(minutes=10))

def test_cache_retrieval(db_engine_ctx):
    with db_engine_ctx():
        session=SessionLocal()
        key = "test_key"
        value = "test_value"
        cache_item = Cache(namespace=DEFAULT_NAMESPACE.name, key=key, value=value, created_at=datetime.utcnow())
        session.add(cache_item)
        session.commit()

        result = get_or_compute(session, DEFAULT_NAMESPACE, key, lambda: "new_value")
        assert result == value

def test_cache_expiration(db_engine_ctx):
    with db_engine_ctx():
        session=SessionLocal()
        key = "test_key"
        value = "old_value"
        expired_time = datetime.utcnow() - timedelta(minutes=11)
        cache_item = Cache(namespace=DEFAULT_NAMESPACE.name, key=key, value=value, created_at=expired_time)
        session.add(cache_item)
        session.commit()

        result = get_or_compute(session, DEFAULT_NAMESPACE, key, lambda: "new_value")
        assert result == "new_value"

def test_concurrent_cache_access(db_engine_ctx):
    with db_engine_ctx():
        key = "test_key"
        value = "concurrent_value"
        results = []

        def worker():
            session=SessionLocal()
            try:
                result = get_or_compute(session, DEFAULT_NAMESPACE, key, lambda: value)
                results.append(result)
            finally:
                SessionLocal.remove()

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert all(result == value for result in results)
        assert len(results) == 50

def test_concurrent_access_different_keys(db_engine_ctx):
    with db_engine_ctx():
        num_threads = 20
        results = {}
        threads = []
        compute_calls = dict()

        def compute(key, value):
            compute_calls[key] += 1
            return value

        def worker(key, value):
            session=SessionLocal()
            try:
                result = get_or_compute(session, DEFAULT_NAMESPACE, key, lambda: compute(key, value))
                results[key].append(result)
            finally:
                SessionLocal.remove()

        for i in range(num_threads):
            key = f"test_key_{i}"
            value = f"value_{i}"
            results[key] = []
            compute_calls[key]=0
            thread = threading.Thread(target=worker, args=(key, value))
            threads.append(thread)

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        for i in range(num_threads):
            key = f"test_key_{i}"
            value = f"value_{i}"
            assert all(result == value for result in results[key])
            assert compute_calls[key] == 1
    assert len(results) == num_threads


def test_namespace_uniqueness():
    namespace_name = "unique_namespace"
    
    # Create the first namespace object
    namespace1 = Namespace(namespace_name, timedelta(minutes=10))
    
    # Try to create a second namespace object with the same name
    with pytest.raises(ValueError):
        namespace2 = Namespace(namespace_name, timedelta(minutes=20))
    
    