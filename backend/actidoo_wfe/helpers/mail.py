import base64
import io
import logging
import sys
import textwrap
from typing import Dict

from authlib.integrations.requests_client import OAuth2Session

from actidoo_wfe.helpers.http import build_url
from actidoo_wfe.helpers.string import get_boxed_text
from actidoo_wfe.helpers.tests import in_test
from actidoo_wfe.settings import settings

log = logging.getLogger(__name__)

def is_debugger_active() -> bool:
    """Return if the debugger is currently active, see https://stackoverflow.com/questions/38634988/check-if-program-runs-in-debug-mode"""
    # sys.monitoring is the new feature of Python 3.12 and newer versions of VSCode or PyCharm will use it.
    return hasattr(sys, "gettrace") and sys.gettrace() is not None or sys.monitoring.get_tool(sys.monitoring.DEBUGGER_ID) is not None 


def send_text_mail(
    subject: str,
    content: str,
    recipient_or_recipients_list: list[str] | str,
    attachments: Dict[str, io.BytesIO],
):
    """Sends a text email via Microsoft Graph API.

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

    # Skip sending email in test mode
    if in_test() or is_debugger_active():
        rec_str = (
            recipient_or_recipients_list
            if isinstance(recipient_or_recipients_list, str)
            else ", ".join(recipient_or_recipients_list)
        )
        
        log.warning(
            "Skipping mail during test:\n"
            + get_boxed_text(subject + "\n\n" + content)
        )
        return

    token_endpoint_with_key = build_url(
        settings.email_token_endpoint,
        {"Subscription-Key": settings.email_subscription_key},
    )

    scope = "https://graph.microsoft.com/.default"
    client_id = settings.email_client_id
    client_secret = settings.email_client_secret
    override_recipients_list = settings.email_override_recipients_list
    override_recipients_enable = settings.email_override_recipients_enable

    if override_recipients_enable or len(override_recipients_list) > 0:
        recipient_or_recipients_list = override_recipients_list

    with OAuth2Session(
        client_id=client_id, client_secret=client_secret, scope=scope
    ) as client:
        # Fetch token
        client.fetch_token(token_endpoint_with_key, grant_type="client_credentials")

        send_endpoint_with_key = build_url(
            settings.email_send_endpoint,
            {"Subscription-Key": settings.email_subscription_key},
        )

        recipients_list: list[str] = []
        if isinstance(recipient_or_recipients_list, str):
            recipients_list.append(recipient_or_recipients_list)
        else:
            recipients_list = recipient_or_recipients_list

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
                contentBytes = base64.b64encode(attachment.read()).decode("utf-8")
                attachment.seek(0)

                attachment_payload = {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": name,
                    "contentBytes": contentBytes,
                }

                attachments_payload.append(attachment_payload)

            payload["message"]["attachments"] = attachments_payload

            # Send email
            response = client.post(url=send_endpoint_with_key, json=payload)
            response.raise_for_status() # raises an exception for status_code >=400
