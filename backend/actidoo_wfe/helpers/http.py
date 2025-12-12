import typing
import unicodedata
import urllib.parse
from typing import Any, Callable, Dict, Optional

import requests
from fastapi import FastAPI, Request
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from starlette.datastructures import URL
from starlette.routing import Router

from actidoo_wfe.settings import settings


def install_request_and_response_hooks_into_session(
    session: TestClient | requests.Session,
    request_hook: Optional[Callable],
    response_hook: Optional[Callable],
):
    """This method patches the session for hooking the request object before sending"""

    original_session_send = session.send

    def send(*args, **kwargs):
        if len(args) > 0:
            request = args[0]
            args = args[1:]
        else:
            request = kwargs["request"]

        if request_hook is not None:
            request = request_hook(request)

        return original_session_send(*args, request=request, **kwargs)

    session.send = send
    if response_hook is not None:
        if isinstance(session, TestClient):
            session.event_hooks["response"].append(response_hook)
        else:
            session.hooks["response"].append(response_hook)

    return session


class HTTPSession(object):
    """A HTTP Session with extras: Request/Response Hooks, Support for Tests, Advanced Settings"""

    def __init__(
        self,
        testclient_fastapi_app: FastAPI|None=None,
        request_hook: Optional[Callable] = None,
        response_hook: Optional[Callable] = None,
    ):
        self.testclient_fastapi_app: FastAPI|None = testclient_fastapi_app
        self.request_hook: Optional[Callable] = request_hook
        self.response_hook: Optional[Callable] = response_hook

    def __enter__(self):
        from actidoo_wfe.helpers.tests import in_test

        if in_test() and self.testclient_fastapi_app is not None:
            self.http_client = TestClient(self.testclient_fastapi_app)
        else:
            self.http_client = requests.Session()
            self.http_client.verify = settings.oidc_verify_ssl

        self.http_client = install_request_and_response_hooks_into_session(
            self.http_client,
            request_hook=self.request_hook,
            response_hook=self.response_hook,
        )

        return self.http_client.__enter__()

    def __exit__(self, type, value, traceback):
        self.http_client.__exit__(type, value, traceback)


def build_url(url: str, params: dict[str, str]) -> str:
    """Sets get parameters for a given url. Existing parameters are not removed."""
    r = requests.Request(url=url, params=params)
    prepared = r.prepare()
    assert prepared.url is not None
    return prepared.url


def rfc5987_content_disposition(filename):
    """Generates a Content-Disposition Header for the given filename (triggers download in the browser)"""
    ascii_name = (
        unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    )
    header = 'attachment; filename="{}"'.format(ascii_name)
    if ascii_name != filename:
        quoted_name = urllib.parse.quote(filename)
        header += "; filename*=UTF-8''{}".format(quoted_name)

    return header


def streaming_response_with_filecontent(
    binary, filename, mimetype
) -> StreamingResponse:
    """Streams a given binary as download"""

    def it():
        yield binary

    headers = {
        "Content-Disposition": rfc5987_content_disposition(filename),
        #'Access-Control-Expose-Headers': 'Content-Disposition'
    }

    return StreamingResponse(it(), media_type=mimetype, headers=headers)


class UrlBuilderFromFastAPIRequest:
    """When running a background task (not FastAPI, ours), the request object cannot be passed. Nevertheless, we sometimes need to build an absolute URL and do not have the active router and base URL.
    This class mimics the url-building behaviour of the FastAPI Request object.
    """

    def __init__(self, request: Request) -> None:
        self.router: Router = request.scope["router"]
        self.base_url = request.base_url

    def url_for(self, __name: str, **path_params: typing.Any) -> URL:
        url_path = self.router.url_path_for(__name, **path_params)
        return url_path.make_absolute_url(base_url=self.base_url)


class HTTPException(FastAPIHTTPException):
    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        headers: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code, detail, headers)
