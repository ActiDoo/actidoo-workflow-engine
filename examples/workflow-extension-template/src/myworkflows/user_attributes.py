# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Example user attribute provider registration for the Workflow Engine."""

from __future__ import annotations

from actidoo_wfe.wf.user_attributes import register_user_attribute_provider


@register_user_attribute_provider(
    keys=["manager_upn"],
    needs=["access_token"],  # signals on-behalf-of using the user's OIDC access token
    source_name="demo_graph_on_behalf_of",
)
def fetch_manager(ctx):
    # In a real project, use ctx.access_token to call Graph/REST and return real data.
    # Here we just return a static demo value to show the shape.
    return {"manager_upn": "boss@example.com"}
