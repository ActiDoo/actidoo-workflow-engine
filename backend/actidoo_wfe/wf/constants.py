# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from enum import StrEnum
from pathlib import Path

BPMN_DIRECTORY = Path(__file__).parent / "testdata" / "processes"
FORM_DIRECTORY = Path(__file__).parent / "testdata" / "processes" / "forms"
MAIL_TEMPLATE_DIR = Path(__file__).parent / "templates" / "mails"

# set_internal_data in tasks
INTERNAL_DATA_KEY_ASSIGNED_USER = "assigned_user_id"
INTERNAL_DATA_KEY_ASSIGNED_DELEGATE_USER = "assigned_delegate_user_id"
INTERNAL_DATA_KEY_ALLOW_UNASSIGN = "allow_unassign"
INTERNAL_DATA_KEY_ASSIGNED_ROLES = "assigned_roles"
INTERNAL_DATA_KEY_STACKTRACE = "stacktrace"
INTERNAL_DATA_KEY_COMPLETED_BY_USER = "completed_by_user_id"
INTERNAL_DATA_KEY_COMPLETED_BY_DELEGATE_USER = "completed_by_delegate_user_id"
INTERNAL_DATA_KEY_DELEGATE_COMMENT = "delegate_submit_comment"

# set_data in workflow instances
DATA_KEY_CREATED_BY = "_created_by_id"
DATA_KEY_WORKFLOW_INSTANCE_SUBTITLE = "_subtitle"

# Technical row identity of dynamic-list items (ADR 010). Part of the task data
# contract: exposed to service tasks and API consumers, survives workflow completion.
ROW_ID_KEY = "_row_id"

# The ui:field renderer of layouted containers. Items rendered with it are the
# signature by which dynamic lists are recognized (form_transformation produces
# it, service_form detects it, the frontend mirrors it in models.ts).
UI_FIELD_LAYOUT = "layout"

# Wire contract between this backend and the SPA bundle. Every BFF request has to
# carry the client's contract version; the backend serves only an exact match.
#
# Bump this together with BFF_CONTRACT_VERSION in frontend/src/models/models.ts
# IN THE SAME COMMIT whenever a change makes an already-loaded bundle unsafe -
# row identity (ADR 010) was such a change: a bundle that predates it submits
# dynamic lists without _row_id, which falls back to the index merge and moves
# backend-owned values onto the wrong rows.
#
# Exact match rather than a minimum, so a bundle that is *newer* than the backend
# is refused too - that is the rollback case. The bump deliberately locks out every
# tab that is still open, which is the whole point (see ADR 011).
BFF_CONTRACT_VERSION = 1

# Hyphens, never underscores: nginx drops request headers containing underscores
# by default (underscores_in_headers off), which would lock out every client that
# reaches the backend through the proxy.
BFF_CLIENT_VERSION_HEADER = "X-WFE-Client-Version"

# Form template modes (see ADR-008). Single source for transform, services and BFF schema.
class TemplateMode(StrEnum):
    OFF = "off"
    BLACKLIST = "blacklist"
    WHITELIST = "whitelist"


DEFAULT_TEMPLATE_MODE = TemplateMode.BLACKLIST

# uischema root key carrying the form-level template mode to client and server.
TEMPLATE_MODE_UISCHEMA_KEY = "ui:templateMode"
