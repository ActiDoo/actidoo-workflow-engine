# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import base64
import io
import logging
import mimetypes
import smtplib
import ssl
import sys
from email.message import EmailMessage
from typing import Dict

from authlib.integrations.requests_client import OAuth2Session

from actidoo_wfe.helpers.http import build_url
from actidoo_wfe.helpers.string import get_boxed_text
from actidoo_wfe.testing.utils import in_test
from actidoo_wfe.settings import settings

log = logging.getLogger(__name__)


def is_debugger_active() -> bool:
    """Return if the debugger is currently active, see https://stackoverflow.com/questions/38634988/check-if-program-runs-in-debug-mode"""
    # sys.monitoring is the new feature of Python 3.12 and newer versions of VSCode or PyCharm will use it.
    return hasattr(sys, "gettrace") and sys.gettrace() is not None or sys.monitoring.get_tool(sys.monitoring.DEBUGGER_ID) is not None


def shall_skip_sending_email() -> bool:
    return in_test() or is_debugger_active() or settings.email_skip


def log_email(
    subject: str,
    content: str,
    recipient_or_recipients_list: list[str] | str,
    attachments: Dict[str, io.BytesIO],
    cc_recipient_or_recipients_list: list[str] | str | None = None,
):
    rec_str = ", ".join(_normalize_recipients(recipient_or_recipients_list))
    cc_list = _normalize_recipients(cc_recipient_or_recipients_list)
    cc_str = f" (cc: '{', '.join(cc_list)}')" if cc_list else ""
    attachment_list = "\n\nATTACH: " + ", ".join(attachments.keys()) if attachments.keys() else ""
    log.info(
        f"Printing email to '{rec_str}'{cc_str}:\n" + get_boxed_text(subject + "\n\n" + content + attachment_list) + "\n",
    )


def _normalize_recipients(recipient_or_recipients_list: list[str] | str | None) -> list[str]:
    if recipient_or_recipients_list is None:
        return []
    if isinstance(recipient_or_recipients_list, str):
        return [recipient_or_recipients_list]
    return list(recipient_or_recipients_list)


def _graph_attachments_payload(attachments: Dict[str, io.BytesIO]) -> list[dict]:
    attachments_payload = []
    for name, attachment in attachments.items():
        attachment.seek(0)
        content_bytes = base64.b64encode(attachment.read()).decode("utf-8")
        attachment.seek(0)

        attachments_payload.append(
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": name,
                "contentBytes": content_bytes,
            }
        )
    return attachments_payload


def _graph_payload(subject: str, content: str, to_list: list[str], cc_list: list[str], attachments: Dict[str, io.BytesIO]) -> dict:
    return {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": content},
            "toRecipients": [{"emailAddress": {"address": address}} for address in to_list],
            "ccRecipients": [{"emailAddress": {"address": address}} for address in cc_list],
            "attachments": _graph_attachments_payload(attachments),
        },
        "saveToSentItems": False,
    }


def _send_via_graph(subject: str, content: str, recipients_list: list[str], attachments: Dict[str, io.BytesIO], cc_list: list[str] | None = None) -> None:
    token_endpoint_with_key = build_url(
        settings.email_token_endpoint,
        {"Subscription-Key": settings.email_subscription_key},
    )

    scope = "https://graph.microsoft.com/.default"
    client_id = settings.email_client_id
    client_secret = settings.email_client_secret

    with OAuth2Session(
        client_id=client_id,
        client_secret=client_secret,
        scope=scope,
    ) as client:
        # Fetch token
        timeout = settings.email_request_timeout_seconds
        client.fetch_token(token_endpoint_with_key, grant_type="client_credentials", timeout=timeout)

        send_endpoint_with_key = build_url(
            settings.email_send_endpoint,
            {"Subscription-Key": settings.email_subscription_key},
        )

        cc_list = cc_list or []
        batches = [recipients_list] if cc_list else [[recipient] for recipient in recipients_list]

        successful_recipients: list[str] = []
        current_batch: list[str] = []
        try:
            for current_batch in batches:
                payload = _graph_payload(subject, content, current_batch, cc_list, attachments)
                response = client.post(url=send_endpoint_with_key, json=payload, timeout=timeout)
                response.raise_for_status()  # raises an exception for status_code >=400
                successful_recipients.extend(current_batch)
        except Exception as error:
            log.error(
                f"error while sending email to '{current_batch}' (cc: '{cc_list}'). Successful before was '{successful_recipients}'. All recipients are '{recipients_list}'. Attachments = {list(attachments.keys())}"
            )
            raise error


def _send_via_smtp(subject: str, content: str, recipients_list: list[str], attachments: Dict[str, io.BytesIO], cc_list: list[str] | None = None) -> None:
    host = settings.email_smtp_host
    port = settings.email_smtp_port
    username = settings.email_smtp_username
    password = settings.email_smtp_password
    from_address = settings.email_from_address or settings.email_smtp_username

    if not host:
        raise ValueError("SMTP host is not configured (email_smtp_host).")
    if not from_address:
        raise ValueError("No sender configured (email_from_address or email_smtp_username).")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = ", ".join(recipients_list)
    cc_list = cc_list or []
    if cc_list:
        message["Cc"] = ", ".join(cc_list)
    message.set_content(content)

    for name, attachment in attachments.items():
        attachment.seek(0)
        data = attachment.read()
        attachment.seek(0)

        mime_type, _ = mimetypes.guess_type(name)
        maintype, subtype = ("application", "octet-stream")
        if mime_type:
            maintype, subtype = mime_type.split("/", 1)

        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)

    context = ssl.create_default_context()
    timeout = settings.email_request_timeout_seconds
    try:
        if settings.email_smtp_use_ssl:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=timeout) as server:
                if username or password:
                    server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                server.ehlo()
                if settings.email_smtp_use_tls:
                    server.starttls(context=context)
                    server.ehlo()
                if username or password:
                    server.login(username, password)
                server.send_message(message)
    except Exception as error:
        log.error(f"error while sending email via SMTP. Recipients: '{recipients_list}', cc: '{cc_list}'. Attachments = {list(attachments.keys())}")
        raise error


def send_text_mail(
    subject: str,
    content: str,
    recipient_or_recipients_list: list[str] | str,
    attachments: Dict[str, io.BytesIO],
    cc_recipient_or_recipients_list: list[str] | str | None = None,
) -> bool:
    """Sends a text email via Microsoft Graph API or SMTP.

    Args:
        subject (str): The subject of the email.
        content (str): The content of the email.
        recipient_or_recipients_list (list[str] | str): The recipient(s) of the email.
        attachments (list[io.BytesIO]): The file-like objects to be attached to the email.
        cc_recipient_or_recipients_list (list[str] | str | None): Optional cc recipient(s) of the email.
            Dropped when the recipient override is active.

    Returns:
        bool: True if the mail was handed to a transport, False if sending was skipped
            (test/debug mode or email_skip).

    Raises:
        Exception: If sending the email fails with an exception.
    """

    # Prepend email subject prefix if it exists
    if settings.email_subject_prefix is not None and isinstance(
        settings.email_subject_prefix,
        str,
    ):
        subject = settings.email_subject_prefix + " " + subject

    # Append email subject suffix if it exists
    if settings.email_subject_suffix is not None and isinstance(
        settings.email_subject_suffix,
        str,
    ):
        subject = subject + " " + settings.email_subject_suffix

    override_recipients_list = settings.email_override_recipients_list
    override_recipients_enable = settings.email_override_recipients_enable
    recipients_list = _normalize_recipients(recipient_or_recipients_list)
    cc_list = _normalize_recipients(cc_recipient_or_recipients_list)

    if override_recipients_enable or len(override_recipients_list) > 0:
        recipients_list = override_recipients_list
        cc_list = []

    # Skip sending email in test/debug mode or when email_skip is set
    if shall_skip_sending_email():
        log_email(subject, content, recipients_list, attachments, cc_list)
        return False

    transport = (settings.email_transport or "GRAPH").upper()
    if transport == "SMTP":
        _send_via_smtp(subject, content, recipients_list, attachments, cc_list)
    elif transport == "GRAPH":
        _send_via_graph(subject, content, recipients_list, attachments, cc_list)
    else:
        raise ValueError(f"Unsupported email transport configured: {settings.email_transport}")

    return True
