# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import contextlib
import logging
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text

from actidoo_wfe.database import drop_all, get_uri, run_migrations, setup_db, wait
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
            SessionLocal.remove()
            teardown_test_db()

    return _db_engine_ctx


@pytest.fixture(scope="function", autouse=True)
def clear_cache():
    """Automatically clear cached Namespace instances between tests."""
    from actidoo_wfe.cache import Namespace

    Namespace.clear_instances()


@pytest.fixture
def mock_send_text_mail():
    """Capture outbound text mails for assertions."""
    emails = []

    def mock_send(subject, content, recipient_or_recipients_list, attachments):
        email = {
            "subject": subject,
            "content": content,
            "recipients": recipient_or_recipients_list,
            "attachments": attachments,
        }
        emails.append(email)

    with patch("actidoo_wfe.helpers.mail.send_text_mail", new=mock_send):
        yield emails
