# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import contextlib
import logging
import pathlib
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, TypeAlias
from unittest.mock import MagicMock, patch

import pytest
from libcloud.storage.drivers.local import LocalStorageDriver
from sqlalchemy import create_engine, text
from sqlalchemy_file.storage import StorageManager

from actidoo_wfe.database import drop_all, get_uri, run_migrations, setup_db, wait
from actidoo_wfe.helpers.concurrency import wait_for_background_tasks
from actidoo_wfe.settings import settings

log = logging.getLogger(__name__)


def setup_test_db() -> None:
    """Import demo data and schema into a clean test database."""
    teardown_test_db()
    run_migrations(settings)


def teardown_test_db() -> None:
    """Drop all tables from the test database."""
    drop_all(settings)


def create_test_db_if_not_exists() -> None:
    """Make sure the dedicated test database exists."""
    settings.db_name = "app"
    db_uri = get_uri(settings)
    wait(settings)

    engine = create_engine(db_uri)
    with engine.connect() as conn:
        conn.execute(text("ROLLBACK"))
        conn.execute(text("DROP DATABASE IF EXISTS app_test"))
        conn.execute(text("CREATE DATABASE app_test"))
    engine.dispose()


def configure_test_db() -> None:
    """Configure the application to point to the test database."""
    create_test_db_if_not_exists()

    settings.db_name = "app_test"
    setup_db(settings=settings)


@pytest.fixture(scope="session")
def db_engine_ctx():
    """Fixture to run tests inside an isolated database context."""
    configure_test_db()

    @contextlib.contextmanager
    def _db_engine_ctx():
        setup_test_db()

        from actidoo_wfe.database import SessionLocal

        SessionLocal.remove()
        try:
            yield
        except Exception as error:  # pragma: no cover - best effort logging
            log.exception(f"{type(error).__name__}: {error.args}.")
            raise
        finally:
            # Drain async event handlers (run_background_task / commit_db_and_run_background_task)
            # before dropping the DB - otherwise their queries race the teardown and surface as
            # "Unknown database 'app_test'" errors in the log.
            if not wait_for_background_tasks(timeout=10.0):
                log.warning("Background tasks did not finish within timeout before db teardown")
            SessionLocal.remove()
            teardown_test_db()

    return _db_engine_ctx


@pytest.fixture(scope="session", autouse=True)
def _tmp_file_storage(tmp_path_factory):
    """Provide a local tmp directory as default file storage for tests."""
    try:
        StorageManager.get_default()
        return  # already configured
    except RuntimeError:
        pass

    storage_path = tmp_path_factory.mktemp("storage")
    driver = LocalStorageDriver(storage_path)
    container = driver.create_container("attachment")
    StorageManager.add_storage("default", container)

    yield

    StorageManager._clear()


@pytest.fixture(scope="function", autouse=True)
def clear_cache():
    """Automatically clear cached Namespace instances between tests."""
    from actidoo_wfe.cache import Namespace

    Namespace.clear_instances()


@pytest.fixture
def mock_send_text_mail():
    """Capture outbound text mails for assertions."""
    from actidoo_wfe.helpers.mail import log_email

    emails = []

    def mock_send(subject, content, recipient_or_recipients_list, attachments):
        email = {
            "subject": subject,
            "content": content,
            "recipients": recipient_or_recipients_list,
            "attachments": attachments,
        }
        emails.append(email)
        log_email(subject, content, recipient_or_recipients_list, attachments)

    with patch("actidoo_wfe.helpers.mail.send_text_mail", new=mock_send):
        yield emails


ConnectorMockSetup: TypeAlias = Callable[[MagicMock], None]
"""Callable hook to seed a connector's MagicMock with default behavior."""

ConnectorMockDefaults: TypeAlias = ConnectorMockSetup | dict[str, Any]
"""Shorthand for default mock behavior — a dict of ``{method_name: return_value}``
or a callable that mutates the MagicMock directly."""

InstanceMocks: TypeAlias = dict[tuple[str, str], MagicMock]
"""Mapping of ``(type_name, instance_name)`` to its per-test MagicMock instance."""


@dataclass(frozen=True)
class _InstanceSpec:
    type_name: str
    instance_name: str
    defaults: ConnectorMockDefaults | None = None


_specs: list[_InstanceSpec] = []


def _apply_defaults(mock: MagicMock, defaults: ConnectorMockDefaults) -> None:
    if callable(defaults):
        defaults(mock)
        return
    for method_name, return_value in defaults.items():
        getattr(mock, method_name).return_value = return_value


@contextlib.contextmanager
def patch_connectors(specs: list[_InstanceSpec]) -> Iterator[InstanceMocks]:
    """Replace ``actidoo_wfe.connectors.get_connector`` with a stub that yields
    per-instance MagicMocks for every spec. Unknown ``(type, instance)`` lookups
    raise ``ConnectorInstanceNotFoundError`` to surface accidental calls.
    """
    from actidoo_wfe.connectors import ConnectorInstanceNotFoundError

    mocks: InstanceMocks = {}
    for spec in specs:
        mock = MagicMock(name=f"{spec.type_name}_{spec.instance_name}_mock")
        if spec.defaults is not None:
            _apply_defaults(mock, spec.defaults)
        mocks[(spec.type_name, spec.instance_name)] = mock

    @contextlib.contextmanager
    def fake_get_connector(type_name: str, instance_name: str):
        key = (type_name, instance_name)
        if key not in mocks:
            raise ConnectorInstanceNotFoundError(
                f"No mock registered for connector {type_name}/{instance_name}. Add `mock_connector_instance({type_name!r}, {instance_name!r}, ...)` to your conftest.",
            )
        yield mocks[key]

    with patch("actidoo_wfe.connectors.get_connector", new=fake_get_connector):
        yield mocks


def mock_connector_instance(
    type_name: str,
    instance_name: str,
    *,
    defaults: ConnectorMockDefaults | None = None,
) -> Callable[..., MagicMock]:
    """Declare a mocked connector instance and return a pytest fixture for it.

    Assign the result at module scope in your conftest::

        mock_jira_abc = mock_connector_instance(
            "jira", "abc",
            defaults={"create_issue": {"id": "10001", "key": "TEST-1"}},
        )

    Tests then depend on it directly: ``def test_x(mock_jira_abc): ...``
    """
    for existing in _specs:
        if existing.type_name == type_name and existing.instance_name == instance_name:
            raise ValueError(
                f"Connector instance {type_name}/{instance_name} is already mocked",
            )
    _specs.append(_InstanceSpec(type_name, instance_name, defaults))

    @pytest.fixture
    def fixture(mocked_connectors: InstanceMocks) -> MagicMock:
        return mocked_connectors[(type_name, instance_name)]

    return fixture


@pytest.fixture(autouse=True)
def mocked_connectors() -> Iterator[InstanceMocks]:
    """Patch ``get_connector`` with stubs for all declared connector instances.

    Inactive (real ``get_connector`` runs) when no specs are registered — this lets
    the engine's own connector tests exercise the real resolver without interference.
    """
    if not _specs:
        yield {}
        return
    with patch_connectors(_specs) as mocks:
        yield mocks
