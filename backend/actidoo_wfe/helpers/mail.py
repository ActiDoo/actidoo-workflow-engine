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

def _normalize_recipients(recipient_or_recipients_list: list[str] | str) -> list[str]:
    if isinstance(recipient_or_recipients_list, str):
        return [recipient_or_recipients_list]
    return recipient_or_recipients_list

def _send_via_graph(subject: str, content: str, recipients_list: list[str], attachments: Dict[str, io.BytesIO]) -> None:
    token_endpoint_with_key = build_url(
        settings.email_token_endpoint,
        {"Subscription-Key": settings.email_subscription_key},
    )

    scope = "https://graph.microsoft.com/.default"
    client_id = settings.email_client_id
    client_secret = settings.email_client_secret

    with OAuth2Session(
        client_id=client_id, client_secret=client_secret, scope=scope
    ) as client:
        # Fetch token
        client.fetch_token(token_endpoint_with_key, grant_type="client_credentials")

        send_endpoint_with_key = build_url(
            settings.email_send_endpoint,
            {"Subscription-Key": settings.email_subscription_key},
        )

        for recipient in recipients_list:
            # Create payload for sending email
            payload = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "Text", "content": content},
                    "toRecipients": [{"emailAddress": {"address": recipient}}],
                    "ccRecipients": [],
                },
                "saveToSentItems": False,
            }

            # Add attachments to payload
            attachments_payload = []
            for name, attachment in attachments.items():
                attachment.seek(0)
                content_bytes = base64.b64encode(attachment.read()).decode("utf-8")
                attachment.seek(0)

                attachment_payload = {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": name,
                    "contentBytes": content_bytes,
                }

                attachments_payload.append(attachment_payload)

            payload["message"]["attachments"] = attachments_payload

            # Send email
            response = client.post(url=send_endpoint_with_key, json=payload)
            response.raise_for_status() # raises an exception for status_code >=400

def _send_via_smtp(subject: str, content: str, recipients_list: list[str], attachments: Dict[str, io.BytesIO]) -> None:
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
    if settings.email_smtp_use_ssl:
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            if username or password:
                server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            if settings.email_smtp_use_tls:
                server.starttls(context=context)
                server.ehlo()
            if username or password:
                server.login(username, password)
            server.send_message(message)

def send_text_mail(
    subject: str,
    content: str,
    recipient_or_recipients_list: list[str] | str,
    attachments: Dict[str, io.BytesIO],
):
    """Sends a text email via Microsoft Graph API or SMTP.

    Args:
        subject (str): The subject of the email.
        content (str): The content of the email.
        recipient_or_recipients_list (list[str] | str): The recipient(s) of the email.
        attachments (list[io.BytesIO]): The file-like objects to be attached to the email.

    Raises:
        Exception: If sending the email fails with an exception.
    """

    # Prepend email subject prefix if it exists
    if settings.email_subject_prefix is not None and isinstance(
        settings.email_subject_prefix, str
    ):
        subject = settings.email_subject_prefix + " " + subject

    # Append email subject suffix if it exists
    if settings.email_subject_suffix is not None and isinstance(
        settings.email_subject_suffix, str
    ):
        subject = subject + " " + settings.email_subject_suffix

    override_recipients_list = settings.email_override_recipients_list
    override_recipients_enable = settings.email_override_recipients_enable
    recipients_list = _normalize_recipients(recipient_or_recipients_list)

    if override_recipients_enable or len(override_recipients_list) > 0:
        recipients_list = override_recipients_list

    # Skip sending email in test mode
    if in_test() or is_debugger_active():
        rec_str = ", ".join(recipients_list)
        
        log.warning(
            "Skipping mail during test:\n"
            + get_boxed_text(subject + "\n\n" + content)
        )
        return

    transport = (settings.email_transport or "GRAPH").upper()
    if transport == "SMTP":
        _send_via_smtp(subject, content, recipients_list, attachments)
    elif transport == "GRAPH":
        _send_via_graph(subject, content, recipients_list, attachments)
    else:
        raise ValueError(f"Unsupported email transport configured: {settings.email_transport}")
