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

import io
import socketserver
import threading
import time
from unittest.mock import MagicMock, patch

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


@pytest.fixture
def real_sending(monkeypatch):
    monkeypatch.setattr(mail, "shall_skip_sending_email", lambda: False)
    monkeypatch.setattr(settings, "email_override_recipients_enable", False)
    monkeypatch.setattr(settings, "email_override_recipients_list", [])
    monkeypatch.setattr(settings, "email_subject_prefix", "")
    monkeypatch.setattr(settings, "email_subject_suffix", "")


@pytest.fixture
def smtp_server(monkeypatch, real_sending):
    monkeypatch.setattr(settings, "email_transport", "SMTP")
    monkeypatch.setattr(settings, "email_smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "email_smtp_use_ssl", False)
    monkeypatch.setattr(settings, "email_smtp_use_tls", False)
    monkeypatch.setattr(settings, "email_smtp_username", "")
    monkeypatch.setattr(settings, "email_smtp_password", "")
    monkeypatch.setattr(settings, "email_from_address", "wf@example.com")
    server = MagicMock()
    with patch("actidoo_wfe.helpers.mail.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = server
        yield server


@pytest.fixture
def graph_client(monkeypatch, real_sending):
    monkeypatch.setattr(settings, "email_transport", "GRAPH")
    monkeypatch.setattr(settings, "email_token_endpoint", "https://login.example.com/token")
    monkeypatch.setattr(settings, "email_send_endpoint", "https://graph.example.com/sendMail")
    monkeypatch.setattr(settings, "email_subscription_key", "key")
    client = MagicMock()
    client.post.return_value.raise_for_status.return_value = None
    with patch("actidoo_wfe.helpers.mail.OAuth2Session") as session_cls:
        session_cls.return_value.__enter__.return_value = client
        yield client


def _sent_message(server):
    server.send_message.assert_called_once()
    return server.send_message.call_args.args[0]


def test_smtp_sets_cc_header(smtp_server):
    sent = mail.send_text_mail(
        subject="Hi",
        content="Body",
        recipient_or_recipients_list=["to@example.com"],
        attachments={},
        cc_recipient_or_recipients_list=["cc1@example.com", "cc2@example.com"],
    )

    assert sent is True
    message = _sent_message(smtp_server)
    assert message["To"] == "to@example.com"
    assert message["Cc"] == "cc1@example.com, cc2@example.com"


def test_smtp_accepts_single_cc_string_and_omits_header_without_cc(smtp_server):
    mail.send_text_mail("Hi", "Body", "to@example.com", {}, cc_recipient_or_recipients_list="cc@example.com")
    assert _sent_message(smtp_server)["Cc"] == "cc@example.com"

    smtp_server.reset_mock()
    mail.send_text_mail("Hi", "Body", "to@example.com", {})
    assert _sent_message(smtp_server)["Cc"] is None


def test_override_recipients_drop_cc(smtp_server, monkeypatch):
    monkeypatch.setattr(settings, "email_override_recipients_list", ["dev@example.com"])

    mail.send_text_mail("Hi", "Body", ["to@example.com"], {}, cc_recipient_or_recipients_list=["cc@example.com"])

    message = _sent_message(smtp_server)
    assert message["To"] == "dev@example.com"
    assert message["Cc"] is None


def test_graph_without_cc_sends_one_mail_per_recipient(graph_client):
    mail.send_text_mail("Hi", "Body", ["a@example.com", "b@example.com"], {})

    payloads = [call.kwargs["json"]["message"] for call in graph_client.post.call_args_list]
    assert [p["toRecipients"] for p in payloads] == [
        [{"emailAddress": {"address": "a@example.com"}}],
        [{"emailAddress": {"address": "b@example.com"}}],
    ]
    assert all(p["ccRecipients"] == [] for p in payloads)


def test_graph_with_cc_sends_single_mail_with_all_recipients(graph_client):
    mail.send_text_mail(
        "Hi",
        "Body",
        ["a@example.com", "b@example.com"],
        {"file.txt": io.BytesIO(b"data")},
        cc_recipient_or_recipients_list="cc@example.com",
    )

    graph_client.post.assert_called_once()
    message = graph_client.post.call_args.kwargs["json"]["message"]
    assert message["toRecipients"] == [
        {"emailAddress": {"address": "a@example.com"}},
        {"emailAddress": {"address": "b@example.com"}},
    ]
    assert message["ccRecipients"] == [{"emailAddress": {"address": "cc@example.com"}}]
    assert message["attachments"][0]["name"] == "file.txt"


def test_skipped_sending_logs_cc(monkeypatch, caplog):
    monkeypatch.setattr(mail, "shall_skip_sending_email", lambda: True)
    monkeypatch.setattr(settings, "email_override_recipients_enable", False)
    monkeypatch.setattr(settings, "email_override_recipients_list", [])

    with caplog.at_level("INFO", logger="actidoo_wfe.helpers.mail"):
        sent = mail.send_text_mail("Hi", "Body", "to@example.com", {}, cc_recipient_or_recipients_list=["cc@example.com"])

    assert sent is False
    assert "cc: 'cc@example.com'" in caplog.text
