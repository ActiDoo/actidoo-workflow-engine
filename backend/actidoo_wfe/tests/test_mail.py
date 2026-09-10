# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Sending mail must give up on a transport that does not answer.

A service task that sends mail runs inside a request and holds the instance
row lock while it does. Without a timeout on the HTTP calls behind the Graph
transport, an unresponsive gateway keeps the request and the lock open for as
long as the gateway likes. The test points the transport at a local server that
accepts the connection and never replies, and expects the send to fail within
the configured timeout.
"""

import socketserver
import threading
import time

import pytest

from actidoo_wfe.helpers import mail
from actidoo_wfe.settings import settings

#: The timeout the test configures for one HTTP call of the transport.
REQUEST_TIMEOUT_SECONDS = 1
#: Token fetch plus send, each with the timeout above, plus slack.
BUDGET_SECONDS = 5


class _SilentHandler(socketserver.BaseRequestHandler):
    """Reads the request and then keeps the connection open without answering."""

    def handle(self):
        self.request.recv(1)
        self.server.release.wait()


@pytest.fixture
def silent_server():
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _SilentHandler)
    server.daemon_threads = True
    server.release = threading.Event()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()


def test_graph_transport_gives_up_on_a_gateway_that_never_answers(silent_server, monkeypatch):
    monkeypatch.setattr(settings, "email_token_endpoint", f"{silent_server}/token")
    monkeypatch.setattr(settings, "email_send_endpoint", f"{silent_server}/send")
    monkeypatch.setattr(settings, "email_client_id", "client")
    monkeypatch.setattr(settings, "email_client_secret", "secret")
    monkeypatch.setattr(settings, "email_subscription_key", "key")
    # Written past pydantic on purpose: the field may not exist yet, and the
    # test should then show the hang, not a validation error.
    monkeypatch.setitem(settings.__dict__, "email_request_timeout_seconds", REQUEST_TIMEOUT_SECONDS)

    outcome: dict[str, BaseException | None] = {}

    def send() -> None:
        try:
            mail._send_via_graph("subject", "content", ["someone@example.com"], {})
            outcome["error"] = None
        except BaseException as error:  # noqa: BLE001 - inspected in the main thread
            outcome["error"] = error

    started = time.monotonic()
    worker = threading.Thread(target=send, daemon=True)
    worker.start()
    worker.join(timeout=BUDGET_SECONDS)

    assert not worker.is_alive(), f"the send is still waiting on the gateway after {BUDGET_SECONDS} s; the transport has no timeout on its HTTP calls"
    assert outcome["error"] is not None, "a gateway that never answers must make the send fail"
    assert time.monotonic() - started < BUDGET_SECONDS
