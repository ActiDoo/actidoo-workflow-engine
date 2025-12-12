from typing import Callable

import venusian
from fastapi import Request
from sqlalchemy.orm import Session

from actidoo_wfe.auth.core import (
    get_login_state as _get_login_state,
)
from actidoo_wfe.auth.schema import LoginStateSchema

__login_hooks = set()


def login_hook(
    wrapped: Callable[
        [
            Request,
            Session,
            LoginStateSchema,
        ],
        None,
    ],
):
    def callback(scanner, name, ob):
        __login_hooks.add(wrapped)

    venusian.attach(wrapped, callback)
    return wrapped


def call_login_hooks(request, db):
    login_state = get_login_state(request=request)

    if login_state.is_logged_in:
        for cb in __login_hooks:
            cb(request, db, login_state)

def get_login_state(request) -> LoginStateSchema:
    return _get_login_state(request=request)
