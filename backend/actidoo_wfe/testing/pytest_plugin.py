# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import contextlib
import logging
import pathlib
import tempfile
from unittest.mock import patch

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
