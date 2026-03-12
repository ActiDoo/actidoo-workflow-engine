# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging

from fastapi import APIRouter

import actidoo_wfe.wf.api.routes as api_routes
import actidoo_wfe.wf.bff.bff_admin as api_bff_admin
import actidoo_wfe.wf.bff.bff_user as api_bff_user
from actidoo_wfe.wf.bff.bff_user_data_model import workflow_data_router

router = APIRouter()

# Initialize the Logger
log = logging.getLogger(__name__)

router.include_router(router=api_bff_user.router, prefix="/bff/user")
router.include_router(router=api_bff_admin.router, prefix="/bff/admin")
router.include_router(router=api_routes.router, prefix="/api/v1")
router.include_router(router=workflow_data_router, prefix="/bff/user")

