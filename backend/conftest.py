import contextlib
import logging
import os
import re
from unittest.mock import patch

from actidoo_wfe.storage import _unsetup_storage, setup_storage
import pytest
import venusian
from sqlalchemy import create_engine, text

from actidoo_wfe.database import drop_all, get_uri, run_migrations, setup_db, wait
from actidoo_wfe.settings import settings

# Do not test third-party code.
collect_ignore_glob = [
    "**/node_modules/*",
    "**/web_modules/*",
]

log = logging.getLogger(__name__)

# Configure Logging
if os.path.exists("log-unittest.log"):
    os.remove("log-unittest.log")
# logging.basicConfig(filename="log-unittest.log", level=logging.DEBUG, format="%(asctime)s\t[%(levelname)s]\t%(message)s")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("faker.factory").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("spiff.metrics").setLevel(logging.INFO)
# logging.getLogger("fontTools.subset").setLevel(logging.WARNING)
# logging.getLogger("fpdf").setLevel(logging.WARNING)
# from http.client import HTTPConnection  # py3
# HTTPConnection.debuglevel = 1


def pytest_configure(config):
    """This hook is called after command line options have been parsed"""
    config.option.log_cli = True
    config.option.log_cli_level = "DEBUG"
    import sys

    # We are setting a global flag, so we can trace whether we are currently inside a test.
    # This is read in actidoo_wfe.helpers.test
    sys._called_from_test = True  # type: ignore

    if os.getenv("AUTH_TEST_SKIP_APP_INIT") == "1":
        return

    import actidoo_wfe as pyapp

    scanner = venusian.Scanner()
    scanner.scan(pyapp, ignore=[re.compile("test_").search])


def pytest_unconfigure(config):
    """This hook is called before the test process is exited"""
    import sys

    del sys._called_from_test  # type: ignore

    _unsetup_storage()


@pytest.fixture(scope="function", autouse=True)
def clear_cache():
    from actidoo_wfe.cache import Namespace
    Namespace.clear_instances()

def setup_test_db() -> None:
    """Sets up the test database. Imports all demo_data/schema_* files into a cleaned test database."""
    teardown_test_db()
    run_migrations(settings)


def teardown_test_db() -> None:
    """Drops all tables from the test database"""

    drop_all(settings)


def create_test_db_if_not_exists() -> None:
    # Create the database engine
    # We are overriding the database which is used for tests.
    # This might have to be created first.

    # At first we still have to use "app" to make a connection with engine.connect() as conn (we know "app" exists).
    # Only then we can use conn.execute() to create a new, additional database.
    # You can not use the engine object to create a new database
    settings.db_name = "app"
    db_uri = get_uri(settings)
    wait(settings)

    engine = create_engine(db_uri)
    with engine.connect() as conn:
        conn.execute(text("ROLLBACK"))
        conn.execute(text("DROP DATABASE IF EXISTS app_test"))
        conn.execute(text("CREATE DATABASE app_test"))
    engine.dispose()


def configure_test_db():
    create_test_db_if_not_exists()

    settings.db_name = "app_test"

    setup_db(settings=settings)


@pytest.fixture(scope="session")
def db_engine_ctx():
    """
    The fixture for running and turning down database.
    """

    configure_test_db()

    @contextlib.contextmanager
    def db_engine_ctx():
        setup_test_db()

        from actidoo_wfe.database import SessionLocal

        SessionLocal.remove()
        try:
            yield
        except Exception as error:
            log.exception(f'{type(error).__name__}: {error.args}.')
            raise
        finally:
            SessionLocal.remove()
            teardown_test_db()

    return db_engine_ctx


@pytest.fixture
def mock_send_text_mail():
    emails = []

    def mock_send(subject, content, recipient_or_recipients_list, attachments):
        email = {"subject": subject, "content": content, "recipients": recipient_or_recipients_list, "attachments": attachments}
        emails.append(email)

    with patch("actidoo_wfe.helpers.mail.send_text_mail", new=mock_send):
        yield emails
