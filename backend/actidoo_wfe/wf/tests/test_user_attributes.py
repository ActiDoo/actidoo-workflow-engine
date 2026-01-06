# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import pytest
from sqlalchemy import select

from actidoo_wfe.database import SessionLocal, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.models import WorkflowUserClaim
from actidoo_wfe.wf.service_user import upsert_user
from actidoo_wfe.wf.user_attributes import clear_user_attribute_providers, register_user_attribute_provider, resolve_user_attributes_on_login

setup_db(settings=settings)


@pytest.fixture(autouse=True)
def _clear_registry():
    clear_user_attribute_providers()
    yield
    clear_user_attribute_providers()


def test_resolve_attributes_with_access_token(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        user = upsert_user(
            db=db,
            idp_user_id="id-abc",
            username="user@example.com",
            email="user@example.com",
            first_name="Workflow",
            last_name="User",
            is_service_user=False,
            initial_locale="en-US",
        )

        calls: list[dict] = []

        @register_user_attribute_provider(
            keys=["manager_upn"], needs=["access_token"], source_name="graph_on_behalf_of"
        )
        def _provider(ctx):
            calls.append(ctx.access_token or {})
            return {"manager_upn": "boss@example.com"}

        resolve_user_attributes_on_login(
            db=db,
            user=user,
            claims={"sub": "123"},
            access_token={"access_token": "token"},
        )

        stored_claims = {
            claim.claim_key: claim
            for claim in db.execute(
                select(WorkflowUserClaim).where(WorkflowUserClaim.user_id == user.id)
            ).scalars()
        }

        assert len(calls) == 1
        assert "manager_upn" in stored_claims
        assert stored_claims["manager_upn"].claim_value == "boss@example.com"
        assert stored_claims["manager_upn"].source_name == "graph_on_behalf_of"
        assert stored_claims["manager_upn"].fetched_at is not None


def test_provider_skipped_without_access_token(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        user = upsert_user(
            db=db,
            idp_user_id="id-def",
            username="user2@example.com",
            email="user2@example.com",
            first_name="Workflow",
            last_name="User",
            is_service_user=False,
            initial_locale="en-US",
        )

        called = False

        @register_user_attribute_provider(
            keys=["manager_upn"], needs=["access_token"], source_name="graph_on_behalf_of"
        )
        def _provider(ctx):
            nonlocal called
            called = True
            return {"manager_upn": "boss@example.com"}

        resolve_user_attributes_on_login(
            db=db,
            user=user,
            claims={"sub": "123"},
            access_token=None,
        )

        stored_claims = list(
            db.execute(
                select(WorkflowUserClaim).where(WorkflowUserClaim.user_id == user.id)
            ).scalars()
        )

        assert called is False
        assert stored_claims == []
