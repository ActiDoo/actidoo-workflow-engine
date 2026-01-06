# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from pathlib import Path

BPMN_DIRECTORY = Path(__file__).parent / "processes"
FORM_DIRECTORY = Path(__file__).parent / "processes" / "forms"
MAIL_TEMPLATE_DIR = Path(__file__).parent / "templates" / "mails"

# set_internal_data in tasks
INTERNAL_DATA_KEY_ASSIGNED_USER = "assigned_user_id"
INTERNAL_DATA_KEY_ALLOW_UNASSIGN = "allow_unassign"
INTERNAL_DATA_KEY_ASSIGNED_ROLES = "assigned_roles"
INTERNAL_DATA_KEY_STACKTRACE = "stacktrace"

# set_data in workflow instances
DATA_KEY_CREATED_BY = "_created_by_id"
DATA_KEY_WORKFLOW_INSTANCE_SUBTITLE = "_subtitle"

DEFAULT_LOCALE= "en"