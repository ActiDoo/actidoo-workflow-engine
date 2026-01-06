# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import actidoo_wfe.wf.service_application as service_application
from actidoo_wfe.database import get_db
from actidoo_wfe.wf.api.api_schema import (
    SendMessageRequest,
    SendMessageResponse,
)
from actidoo_wfe.wf.api.deps import dep_require_service_user
from actidoo_wfe.wf.models import WorkflowUser

log = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[],
    tags=["wfe-api"]
)
 
@router.post("/send_message", name="api_v1_send_message")
def api_send_message(
    reqdata: SendMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[WorkflowUser, Depends(dep_require_service_user)],
) -> SendMessageResponse:
    
    service_application.receive_message(
        db=db,
        message_name=reqdata.message_name,
        correlation_key=reqdata.correlation_key,
        data=reqdata.data,
        user_id=user.id
    )

    return SendMessageResponse()

