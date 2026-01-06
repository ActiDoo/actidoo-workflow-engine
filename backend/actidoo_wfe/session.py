# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import datetime
import random
import secrets
import string
import typing
import uuid

import sqlalchemy.types as ty
from itsdangerous.exc import BadSignature
from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from actidoo_wfe.database import Base, UTCDateTime, get_db_contextmanager
from actidoo_wfe.helpers.time import dt_ago_aware, dt_ago_naive, dt_now_naive


class SessionModel(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(
        ty.String(64), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(), default=dt_now_naive, nullable=False, index=True
    )
    data: Mapped[dict[str, str]] = mapped_column(JSON)


def generate_session_id():
    return "".join(
        secrets.choice(string.ascii_letters + string.digits) for x in range(64)
    )


def load_session(db, token):
    sess = db.execute(select(SessionModel).where(SessionModel.token == token)).scalar()
    if sess is not None:
        db.expunge(sess)
    return sess


def save_session(db, id, token, data):
    if id is None:
        session = SessionModel()
        session.token = token
        session.data = data
    else:
        session = load_session(db=db, token=token)
        if session is None:
            session = SessionModel()
            session.token = token
        session.data = data
    db.add(session)


def delete_session(db, id=id):
    db.execute(delete(SessionModel).where(SessionModel.id == id))


def session_cleanup(db, max_age_seconds):
    db.execute(
        delete(SessionModel).where(
            SessionModel.created_at <= dt_ago_naive(seconds=max_age_seconds)
        )
    )


class TrackChangesDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.changed = False

    def __setitem__(self, key, value):
        if key in self:
            old_value = self[key]
            if old_value != value:
                self.changed = True
        else:
            self.changed = True

        super().__setitem__(key, value)


class SessionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        session_cookie: str = "sess",
        server_max_age: typing.Optional[int] = 14 * 24 * 60 * 60,  # 14 days, in seconds
        path: str = "/",
        same_site: typing.Literal["lax", "strict", "none"] = "lax",
        https_only: bool = True,
    ) -> None:
        self.app = app
        self.session_cookie = session_cookie
        self.server_max_age = server_max_age
        self.path = path
        self.security_flags = "httponly; samesite=" + same_site
        if https_only:  # Secure flag can be used with HTTPS only
            self.security_flags += "; secure"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):  # pragma: no cover
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        initial_session_was_empty = True

        if self.session_cookie in connection.cookies:
            data = connection.cookies[self.session_cookie]  # .encode("utf-8")
            try:
                with get_db_contextmanager() as db:
                    # cleanup sessions every 100 requests
                    if random.randint(1, 100) == 50:
                        session_cleanup(db=db, max_age_seconds=self.server_max_age)
                    model = load_session(db=db, token=data)
                    if model is not None and model.created_at < dt_ago_aware(
                        seconds=self.server_max_age
                    ):
                        model = None

                if model is not None:
                    scope["session_id"] = model.id
                    scope["session_token"] = model.token
                    scope["session"] = TrackChangesDict(model.data)
                    if scope["session"]:
                        initial_session_was_empty = False
                else:
                    scope["session_id"] = None
                    scope["session_token"] = generate_session_id()
                    scope["session"] = TrackChangesDict()

            except BadSignature:
                scope["session_id"] = None
                scope["session_token"] = generate_session_id()
                scope["session"] = TrackChangesDict()
        else:
            scope["session_id"] = None
            scope["session_token"] = generate_session_id()
            scope["session"] = TrackChangesDict()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                if scope["session"]:
                    # We have session data to persist.
                    if scope["session"].changed:
                        with get_db_contextmanager() as db:
                            save_session(
                                db=db,
                                id=scope["session_id"],
                                token=scope["session_token"],
                                data=scope["session"],
                            )

                    headers = MutableHeaders(scope=message)
                    header_value = (
                        "{session_cookie}={data}; path={path}; {security_flags}".format(  # noqa E501
                            session_cookie=self.session_cookie,
                            data=scope["session_token"],
                            path=self.path,
                            security_flags=self.security_flags,
                        )
                    )
                    headers.append("Set-Cookie", header_value)
                elif not initial_session_was_empty:
                    # The session has been cleared.
                    if scope["session_id"] is not None:
                        with get_db_contextmanager() as db:
                            delete_session(db=db, id=scope["session_id"])

                    if self.session_cookie in connection.cookies:
                        headers = MutableHeaders(scope=message)
                        header_value = "{session_cookie}={data}; path={path}; {expires}{security_flags}".format(  # noqa E501
                            session_cookie=self.session_cookie,
                            data="null",
                            path=self.path,
                            expires="expires=Thu, 01 Jan 1970 00:00:00 GMT; ",
                            security_flags=self.security_flags,
                        )
                        headers.append("Set-Cookie", header_value)
            await send(message)

        await self.app(scope, receive, send_wrapper)
