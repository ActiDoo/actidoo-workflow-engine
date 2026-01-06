# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging

from fastapi.requests import Request

log = logging.getLogger(__name__)


class HTTPAccessLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        else:
            request = Request(scope)

        if request.url.path.endswith("/docs") or request.url.path.endswith(
            "/openapi.json"
        ):
            await self.app(scope, receive, send)
            return

        async def receive_request_body():
            message = await receive()
            return message

        async def send_response(message):
            if message["type"] == "http.response.start":
                if request.client is not None:
                    log.info(
                        f"{request.client.host}:{request.client.port} - {request.method} {request.url} {message['status']}"
                    )

            await send(message)

        await self.app(scope, receive_request_body, send_response)
