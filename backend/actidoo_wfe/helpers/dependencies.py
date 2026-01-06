# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import json

from fastapi import Request


async def get_body(request: Request):
    """A FastAPI dependency which provides the decoded body as string"""
    s = await request.body()
    b = s.decode(json.detect_encoding(s), "surrogatepass")
    return b


async def get_json(request: Request):
    """A FastAPI dependency which provides the json-decoded body."""
    return await request.json()
