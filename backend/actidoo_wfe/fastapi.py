# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""
FastAPI Entrypoint
"""

import asyncio
import logging
import pathlib
import re
import sys
from contextlib import asynccontextmanager
from ipaddress import ip_network
from typing import Any, Callable

import orjson
import sentry_sdk
import venusian
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from actidoo_wfe.async_scheduling import clear_task_registry, run_scheduler
from actidoo_wfe.auth.fastapi import router as router_auth
from actidoo_wfe.database import run_migrations, setup_db
from actidoo_wfe.helpers.logging import HTTPAccessLogMiddleware
from actidoo_wfe.helpers.proxy_middleware import ProxyHeadersNetworkMiddleware
from actidoo_wfe.testing.utils import in_test
from actidoo_wfe.session import SessionMiddleware
from actidoo_wfe.settings import settings
from actidoo_wfe.storage import setup_storage
from actidoo_wfe.wf.fastapi import router as router_wf
from actidoo_wfe.venusian_scan import discover_venusian_scan_targets

print(f"Setting Log-Level to {settings.log_level}")
logging.basicConfig(
    stream=sys.stderr,
    level=settings.log_level,
    format="%(asctime)s\t[%(levelname)s]\t%(message)s",
)
log: logging.Logger = logging.getLogger(__name__)
log.info("FastAPI starting up....")

# Setup Sentry
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )

# Run migrations
run_migrations(settings=settings)

# Create engine and setup DB Session
db_engine = setup_db(settings=settings)

# Configure Storage
setup_storage(settings)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """This function allows to execute before and after the app lifetime. It can be used for initialization and proper shutdown."""

    # before app start
    import actidoo_wfe as pyapp

    clear_task_registry()

    scanner = venusian.Scanner()
    for target in discover_venusian_scan_targets(default_modules=[pyapp]):
        scanner.scan(target, ignore=[re.compile("test_").search])

    task_future = None
    if not in_test():
        task_future = asyncio.create_task(run_scheduler(settings=settings))

    yield

    if task_future is not None:
        task_future.cancel()

    # after app stop
    from actidoo_wfe.helpers.concurrency import stop_executor

    await stop_executor()
       
class ORJSONRequest(Request):
    async def json(self) -> Any:
        body = await self.body()
        return orjson.loads(body)

class ORJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return orjson.dumps(content)

class ORJSONRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            request = ORJSONRequest(request.scope, request.receive)
            return await original_route_handler(request)

        return custom_route_handler

app: FastAPI = FastAPI(
    lifespan=lifespan,
    debug=True,
    title="Workflow Engine",
    version="0.1.0",
    docs_url ="/api/docs",
    redoc_url = "/api/redoc",
    openapi_url = "/api/openapi.json",
    default_response_class = ORJSONResponse
)

app.router.route_class = ORJSONRoute

# For local develoment, we need to support CORS. CORS settings can be made in the application settings.
if settings.cors_origins is not None and len(settings.cors_origins) > 0:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=("Content-Disposition",),
    )

# Initialize the ProxyHeadersNetworkMiddleware for accepting X-Forwarded headers
trusted_proxy_networks = []
for network in settings.proxy_trusted_networks:
    try:
        trusted_proxy_networks.append(ip_network(network))
    except ValueError:
        log.warning("Ignoring invalid proxy trusted network '%s'", network)

if trusted_proxy_networks:
    app.add_middleware(
        ProxyHeadersNetworkMiddleware,
        trusted_networks=trusted_proxy_networks,
    )
else:
    log.warning("No valid proxy trusted networks configured; Proxy headers middleware disabled.")

# We need sessions to track the auth status.
app.add_middleware(SessionMiddleware, session_cookie="wfesess")

# The CorrelationIdMiddleware adds a unique ID to each request. If an ID is given in X-Request-ID, it is used, otherwise one is created. It can be used for inter-service tracability.
# We also use it for DBSession handling (SessionLocal)
app.add_middleware(CorrelationIdMiddleware)

# Add our custom access log middleware
app.add_middleware(HTTPAccessLogMiddleware)

# All endpoints should be reachable under settings.api_path + ...
PATH_PREFIX = "" if settings.api_path == "/" else settings.api_path
app.include_router(prefix=PATH_PREFIX + "/auth", router=router_auth)
app.include_router(prefix=PATH_PREFIX + "/wfe", router=router_wf)

# Output Build Version


class VersionResponse(BaseModel):
    git_commit_sha: str


@app.router.get(PATH_PREFIX + "/version", name="app_version", response_model=VersionResponse)
def api_version_endpoint(request: Request):
    """The endpoint outputs the git commit of the server build."""
    import os

    git_commit_sha = os.environ.get("CI_COMMIT_SHA", "-")
    return VersionResponse(git_commit_sha=git_commit_sha)
