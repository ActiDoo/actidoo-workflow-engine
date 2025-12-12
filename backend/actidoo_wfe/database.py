import datetime
import json
import logging
import uuid
from contextlib import contextmanager
from typing import Any, Generator
from urllib import parse
import zlib

import alembic.config
from asgi_correlation_id.context import correlation_id
from sqlalchemy import TIMESTAMP, MetaData, NullPool, TypeDecorator, literal, text
from sqlalchemy.dialects.mysql import LONGTEXT, LONGBLOB
from sqlalchemy.engine import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session
from sqlalchemy.orm.session import sessionmaker

from actidoo_wfe.constants import ALEMBIC_PATH

# load_all_models() is only used dynamically by CLI function, so there's no static dependency to actidoo_wfe.database_models
from actidoo_wfe.database_models import load_all_models
from actidoo_wfe.helpers.wait_for_server import wait_for_server
from actidoo_wfe.settings import Settings

log = logging.getLogger(__name__)


### Setup and Connection
def get_mysql_options(settings: Settings) -> dict:
    if settings.db_ssl_ca:
        return  {
            "connect_timeout": 20,
            "ssl": {
                "ca": settings.db_ssl_ca
            },
            "init_command": "SET SESSION time_zone='+00:00', innodb_lock_wait_timeout=3"
        }
    else:
        return {
            "connect_timeout": 20,
            "init_command": "SET SESSION time_zone='+00:00', innodb_lock_wait_timeout=3"
        }


def setup_db(settings: Settings) -> Engine:
    """Creates the database connection pool and configures the ORM Session"""

    db_uri = get_uri(settings)
    wait(settings)

    # starlette seems to have a threadpool for 50 requests concurrently. we need at least 50 connections for http requests!
    # futhermore, we have a thread executor for background tasks with max 50 threads. each uses at most 1 connection
    # there is also a scheduler worker in the background (currently only 1)
    # max connections = pool_size + max_overflow

    engine = create_engine(
        db_uri,
        pool_size=10,
        max_overflow=150,
        echo=settings.db_echo,
        #echo_pool="debug",
        pool_pre_ping=True,
        pool_recycle=60 * 5,
        pool_timeout=300,
        isolation_level="REPEATABLE READ",
        connect_args=get_mysql_options(settings),
    )

    setup_db_session(engine)

    return engine

def create_null_pool_engine(settings: Settings, isolation_level="REPEATABLE READ"):
    db_uri = get_uri(settings)

    engine = create_engine(
        db_uri,
        echo=settings.db_echo,
        poolclass=NullPool,
        isolation_level=isolation_level,
        connect_args=get_mysql_options(settings),
    )

    return engine

def get_uri(settings: Settings):
    """Composes the database connection string based on the application settings"""
    encoded_password = parse.quote_plus(settings.db_password)
    db_uri = f"{settings.db_driver}://{settings.db_user}:{encoded_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    if settings.db_query:
        db_uri += "?" + settings.db_query
    return db_uri

def get_dsn(settings: Settings):
    encoded_password = parse.quote_plus(settings.db_password)
    db_uri = f'dbname={settings.db_name} user={settings.db_user} password={encoded_password} host={settings.db_host} port={settings.db_port}'
    return db_uri

def wait(settings: Settings):
    """Waits synchronously for the configured database server to be available (reachable via socket)"""
    wait_for_server(settings.db_host, settings.db_port)


### Settings, Metadata, ORM Session

# Recommended naming convention used by Alembic, as various different database
# providers will autogenerate vastly different names making migrations more
# difficult. See: http://alembic.zzzcomputing.com/en/latest/naming.html
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# The SQLAlchemy metadata is a collection of Table objects and their associated schema constructs.
metadata: MetaData = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """The declarative base for our ORM classes"""

    # All tables implicitly defined by our ORM classes should share this metadata
    metadata = metadata


def _session_local_scopefunc() -> str:
    """This function returns a string which identifies a database session scope. It uses the Correlection-ID of the Request or - if executed outside of a request - generates a random string.
    This leads to having a request-scopes database session (and thus transaction); and the possibility to use the database outside of a request, e.g. in a background task oder app initialization.
    """

    if correlation_id.get() is not None:
        #log.debug(
        #    f"SqlAlchemy SessionLocal scopefunc using Correlation-ID: {correlation_id.get()}"
        #)
        ret: str = str(correlation_id.get())
    else:
        random_id = uuid.uuid4()
        correlation_id.set(str(random_id))
        #log.debug(f"SqlAlchemy SessionLocal scopefunc using RANDOM-ID: {random_id}")
        ret: str = str(random_id)
    return ret


# Factory for creating database sessions
SessionMaker: sessionmaker = sessionmaker(autocommit=False, autoflush=True)

# Factory for creating a new session or returning an active session for the currently active scope. Scope is defined by _session_local_scopefunc.
SessionLocal: scoped_session = scoped_session(
    SessionMaker, scopefunc=_session_local_scopefunc
)


def setup_db_session(engine) -> None:
    """The database sessions, created by SessionMaker, are configured to use the given engine"""
    SessionMaker.configure(bind=engine)


### Access the database in the application


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for providing a database session. Usage is enclosed in a transaction!"""
    db: Session = SessionLocal()
    if db.in_transaction():
        #raise Exception("already in transaction")
        with db.begin_nested():
            yield db
    else:
        try:
            with db.begin():
                yield db
        finally:
            try:
                SessionLocal.remove()
            except Exception:
                log.exception("Error calling SessionLocal.remove()")


get_db_contextmanager = contextmanager(get_db)
"""The database dependency can also be used as a contextmanager, e.g. in background tasks."""


### Helpers


def exists_by_expr(db: Session, expr) -> bool:
    """Short-Hand function to find out whether a row exists in the database"""
    result: Any | None = db.query(literal(True)).filter(expr).first()
    return result is not None


ESCAPE_CHAR = "*"


def elike(column, string, prefix_wildcard=True, suffix_wildcard=True):
    return column.like(
        ("%" if prefix_wildcard else "")
        + escape_like(string, escape_char=ESCAPE_CHAR)
        + ("%" if suffix_wildcard else ""),
        escape=ESCAPE_CHAR,
    )


def eilike(column, string, prefix_wildcard=True, suffix_wildcard=True):
    return column.ilike(
        ("%" if prefix_wildcard else "")
        + escape_like(string, escape_char=ESCAPE_CHAR)
        + ("%" if suffix_wildcard else ""),
        escape=ESCAPE_CHAR,
    )


def escape_like(string, escape_char=ESCAPE_CHAR):
    return (
        string.replace(escape_char, escape_char * 2)
        .replace("%", escape_char + "%")
        .replace("_", escape_char + "_")
    )


def search_uuid_by_prefix(column, prefix):
    lower, upper = generate_uuid_bounds(uuid_prefix=prefix)
    return column.between(lower, upper)


def generate_uuid_bounds(uuid_prefix):
    lower = "00000000-0000-0000-0000-000000000000"
    upper = "ffffffff-ffff-ffff-ffff-ffffffffffff"

    for i in range(len(uuid_prefix)):
        lower = lower[:i] + uuid_prefix[i] + lower[i + 1 :]
        upper = upper[:i] + uuid_prefix[i] + upper[i + 1 :]

    try:
        return uuid.UUID(lower), uuid.UUID(upper)
    except Exception:
        return uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"), uuid.UUID(
            "ffffffff-ffff-ffff-ffff-ffffffffffff"
        )


def run_migrations(settings: Settings):
    """ only used by the cli app """
    engine = create_engine(
        get_uri(settings),
        poolclass=NullPool,
        connect_args=get_mysql_options(settings),
    )

    with engine.connect() as conn:
        initialized = conn.execute(
            text(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '{settings.db_name}' AND table_name = 'alembic_version'")
        ).scalar()

    alembic_cfg = alembic.config.Config(attributes={"engine": engine})

    if ALEMBIC_PATH.exists():
        alembic_cfg.set_main_option("script_location", str(ALEMBIC_PATH))

        if not initialized:
            load_all_models()
            metadata.create_all(engine)
            from alembic.command import stamp

            stamp(config=alembic_cfg, revision="head")
        else:
            from alembic.command import upgrade

            upgrade(config=alembic_cfg, revision="head")
    else:
        raise Exception("Alembic Path not existing")

    engine.dispose()


def create_revision(settings: Settings, message: str):
    """ only used by the cli app """
    engine = create_engine(
        get_uri(settings),
        poolclass=NullPool,
        connect_args=get_mysql_options(settings),
    )

    alembic_cfg = alembic.config.Config(attributes={"engine": engine})

    if ALEMBIC_PATH.exists():
        alembic_cfg.set_main_option("script_location", str(ALEMBIC_PATH))

        load_all_models()
        from alembic.command import revision

        revision(alembic_cfg, message, True)

    engine.dispose()


def drop_all(settings: Settings):
    engine = create_engine(
        get_uri(settings),
        poolclass=NullPool,
        connect_args=get_mysql_options(settings),
    )

    with engine.connect() as conn:
        conn.execute(text("ROLLBACK"))
        conn.execute(text(f"DROP DATABASE IF EXISTS `{settings.db_name}`"))
        conn.execute(text(f"CREATE DATABASE `{settings.db_name}`"))
    engine.dispose()


class UTCDateTime(TypeDecorator):
    impl = TIMESTAMP
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            # Convert to UTC and store as timezone-unaware
            value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            # Treat as UTC and make it timezone-aware
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value

class JSONBlob(TypeDecorator):
    impl = LONGTEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            # Convert Python object to JSON string and then encode as bytes
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            # Decode bytes to JSON string and then convert to Python object
            value = json.loads(value)
        return value
    
class ZlibJSONBlob(TypeDecorator):
    """
    SQLAlchemy type for storing JSON as zlib-compressed binary data.
    On load it falls back to plain JSON if decompression fails.
    """
    impl = LONGBLOB
    cache_ok = True

    def __init__(self, max_decompress_size: int = 10 * 1024 * 1024, *args, **kwargs):
        """
        :param max_decompress_size: Maximum bytes allowed after decompression (default: 10 MB)
        """
        super().__init__(*args, **kwargs)
        self.max_decompress_size = max_decompress_size

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        try:
            json_str = json.dumps(value)
            return zlib.compress(json_str.encode("utf-8"))
        except Exception as e:
            raise ValueError(f"Error compressing JSON data: {e}") from e

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        # 1) Fallback for uncompressed JSON str
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception as e:
                raise ValueError(f"Error parsing plain JSON string: {e}") from e

        # 2) If Bytes, decompress
        if isinstance(value, (bytes, bytearray)):
            decompressor = zlib.decompressobj()
            try:
                data = decompressor.decompress(value, self.max_decompress_size)
                if decompressor.unconsumed_tail:
                    raise ValueError("Decompressed data exceeds allowed size limit.")
                return json.loads(data.decode("utf-8"))
            except zlib.error:
                # Fallback: Decode Bytes as UTF-8 and parse as JSON
                try:
                    text = value.decode("utf-8")
                    return json.loads(text)
                except Exception as e2:
                    raise ValueError(f"Error parsing fallback JSON from bytes: {e2}") from e2

        # 3) Unhandled type
        raise ValueError(f"Unsupported type for ZlibJSONBlob: {type(value)}")
