# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Request schemas for the workflow-data API.

The response side lives in ``wf/types_data_model.py`` (neutral, shared with the
views/service layers); only the HTTP request contract is BFF-specific.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class StartWorkflowForExistingDataModelRequest(BaseModel):
    """Start a follow-up workflow (declared as an action) from an existing row.

    The client only picks the row and the action; the workflow seed is built
    server-side from the row, so no free-form data is accepted here.
    """

    model_name: str
    id: uuid.UUID  # the stable record id of the source row
    action: str
