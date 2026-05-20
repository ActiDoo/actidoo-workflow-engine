# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Tests for the Workflow Data BFF endpoints (list_models, list_rows, get_version_chain).

End-to-end via the FastAPI TestClient. Helper functions (`_user_has_read_access`,
`_serialize_row`, `_fields_metadata`, ...) are exercised implicitly through the
endpoint responses.
"""

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from actidoo_wfe.database import SessionLocal, SessionMaker, get_db_contextmanager, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import service_user
from actidoo_wfe.wf.config_data_model import VirtualField, WorkflowDataApiConfig
from actidoo_wfe.wf.models import WorkflowManagedMixin, extension_model_base
from actidoo_wfe.wf.registry_data_model import DataModelDescriptor, data_model_registry
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

setup_db(settings=settings)


_ApiTestBase = extension_model_base("apitest")


class ApiTestModel(_ApiTestBase, WorkflowManagedMixin):
    _ext_table = "ate"
    __abstract__ = False
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    value: Mapped[int | None] = mapped_column(nullable=True)


@pytest.fixture(autouse=True)
def _clean_registry():
    data_model_registry.clear()
    yield
    data_model_registry.clear()


def _create_extension_table():
    engine = SessionMaker.kw["bind"]
    ApiTestModel.__table__.create(bind=engine, checkfirst=True)


def _make_detached_user(idp_user_id, email, role_name=None):
    """Mirror bff/deps.get_user: own context-manager, returns a detached + expired user."""
    with get_db_contextmanager() as db:
        service_user.upsert_user(
            db=db, idp_user_id=idp_user_id, username=email, email=email,
            first_name="X", last_name="Y", is_service_user=False, initial_locale="en-US",
        )
    if role_name:
        with get_db_contextmanager() as db:
            user = service_user.upsert_user(
                db=db, idp_user_id=idp_user_id, username=email, email=email,
                first_name="X", last_name="Y", is_service_user=False, initial_locale="en-US",
            )
            service_user.assign_roles(db=db, user_id=user.id, role_names=[role_name])
    with get_db_contextmanager() as db:
        user = service_user.upsert_user(
            db=db, idp_user_id=idp_user_id, username=email, email=email,
            first_name="X", last_name="Y", is_service_user=False, initial_locale="en-US",
        )
    return user


def _register(name, *, read_roles=None, fields=None, row_filter=None):
    data_model_registry.register(
        DataModelDescriptor(
            name=name,
            model_class=ApiTestModel,
            namespace="apitest",
            api=WorkflowDataApiConfig(
                read_roles=read_roles or [],
                fields=fields,
                row_filter=row_filter,
            ),
        ),
    )


def _register_non_api(name):
    data_model_registry.register(
        DataModelDescriptor(
            name=name,
            model_class=ApiTestModel,
            namespace="apitest",
            api=None,
        ),
    )


def _seed_row(workflow_instance_id, *, name="Row", value=1, parent=None, child=None):
    with SessionMaker() as db, db.begin():
        db.add(ApiTestModel(
            workflow_instance_id=workflow_instance_id,
            name=name,
            value=value,
            parent_workflow_instance_id=parent,
            child_workflow_instance_id=child,
        ))


def _list_models(client):
    url = client.root_client.app.url_path_for("list_models")
    return client.root_client.get(url)


def _list_rows(client, model_name, *, page=1, page_size=10):
    url = client.root_client.app.url_path_for("list_rows", model_name=model_name)
    return client.root_client.get(url, params={"page": page, "page_size": page_size})


def _get_version_chain(client, model_name, workflow_instance_id):
    url = client.root_client.app.url_path_for(
        "get_version_chain", model_name=model_name, workflow_instance_id=workflow_instance_id,
    )
    return client.root_client.get(url)


# ---------------------------------------------------------------------------
# list_models endpoint
# ---------------------------------------------------------------------------


class TestListModelsEndpoint:
    def test_returns_only_api_exposed_models(self, db_engine_ctx):
        with db_engine_ctx():
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Exposed")
            _register_non_api("Hidden")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_models(client)

            assert response.status_code == 200
            assert [m["name"] for m in response.json()] == ["Exposed"]

    def test_excludes_models_user_cannot_read(self, db_engine_ctx):

        with db_engine_ctx():
            user = _make_detached_user("lm2", "lm2@example.com", role_name="viewer")
            _register("OpenToAll")  # no read_roles → public
            _register("ViewerOnly", read_roles=["viewer"])
            _register("AdminOnly", read_roles=["admin"])

            client = Client()
            with override_get_user(client=client, user=user), disable_role_check(client):
                response = _list_models(client)

            assert response.status_code == 200
            assert {m["name"] for m in response.json()} == {"OpenToAll", "ViewerOnly"}

    def test_columns_metadata_excludes_mixin_system_columns(self, db_engine_ctx):
        with db_engine_ctx():
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Cols")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_models(client)

            assert response.status_code == 200
            cols = response.json()[0]["columns"]
            names = {c["name"] for c in cols}
            assert {"workflow_instance_id", "created_at", "name", "value"} <= names
            assert names.isdisjoint({"parent_workflow_instance_id", "child_workflow_instance_id", "action"})
            wf_col = next(c for c in cols if c["name"] == "workflow_instance_id")
            assert wf_col["primary_key"] is True

    def test_respects_explicit_fields_config_with_virtual_field(self, db_engine_ctx):
        with db_engine_ctx():
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            vf = VirtualField("is_high", type="boolean", value=lambda row: (row.value or 0) > 10)
            _register("Restricted", fields=["name", vf])

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_models(client)

            assert response.status_code == 200
            cols = response.json()[0]["columns"]
            assert [c["name"] for c in cols] == ["name", "is_high"]
            assert cols[1] == {"name": "is_high", "type": "boolean", "nullable": True, "primary_key": False, "virtual": True}


# ---------------------------------------------------------------------------
# list_rows endpoint
# ---------------------------------------------------------------------------


class TestListRowsEndpoint:
    def test_returns_paginated_rows(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Paginated")
            for i in range(5):
                _seed_row(f"wf-{i}", name=f"Row{i}", value=i)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                page1 = _list_rows(client, "Paginated", page=1, page_size=2).json()
                page2 = _list_rows(client, "Paginated", page=2, page_size=2).json()

            assert page1["total"] == 5
            assert page1["page"] == 1
            assert page1["page_size"] == 2
            assert len(page1["items"]) == 2
            assert len(page2["items"]) == 2
            ids = [i["workflow_instance_id"] for i in page1["items"] + page2["items"]]
            assert ids == sorted(ids)

    def test_returns_only_head_of_version_chain(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Chained")
            _seed_row("parent", name="OldVersion", child="child")
            _seed_row("child", name="LatestVersion", parent="parent")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_rows(client, "Chained")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["workflow_instance_id"] == "child"

    def test_items_use_virtual_fields_and_exclude_system_columns(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            doubled = VirtualField("doubled", type="integer", value=lambda r: (r.value or 0) * 2)
            _register("Virt", fields=["name", "value", doubled])
            _seed_row("wf-vf", name="Item", value=21)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_rows(client, "Virt")

            assert response.status_code == 200
            assert response.json()["items"] == [{"name": "Item", "value": 21, "doubled": 42}]

    def test_returns_403_for_user_without_role(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            user = _make_detached_user("lr4", "lr4@example.com", role_name="viewer")
            _register("Restricted", read_roles=["admin"])

            client = Client()
            with override_get_user(client=client, user=user), disable_role_check(client):
                response = _list_rows(client, "Restricted")

            assert response.status_code == 403

    def test_returns_404_for_unknown_model(self, db_engine_ctx):
        with db_engine_ctx():
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_rows(client, "DoesNotExist")

            assert response.status_code == 404

    def test_row_filter_receives_attached_user(self, db_engine_ctx):
        """Regression: row_filter used to receive a detached user; reading
        user.roles raised DetachedInstanceError."""
        with db_engine_ctx():
            _create_extension_table()
            user = _make_detached_user("lr6", "lr6@example.com", role_name="rf-role")

            captured = []

            def row_filter(query, db, user):
                captured.append({r.role.name for r in user.roles})
                return query

            _register("WithFilter", read_roles=["rf-role"], row_filter=row_filter)

            client = Client()
            with override_get_user(client=client, user=user), disable_role_check(client):
                response = _list_rows(client, "WithFilter")

            assert response.status_code == 200
            assert captured == [{"rf-role"}]
            assert response.json()["total"] == 0


# ---------------------------------------------------------------------------
# get_version_chain endpoint
# ---------------------------------------------------------------------------


class TestGetVersionChainEndpoint:
    def test_walks_full_chain_from_middle(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Chain")
            _seed_row("a", name="v1", child="b")
            _seed_row("b", name="v2", parent="a", child="c")
            _seed_row("c", name="v3", parent="b")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _get_version_chain(client, "Chain", workflow_instance_id="b")

            assert response.status_code == 200
            assert [v["workflow_instance_id"] for v in response.json()["versions"]] == ["a", "b", "c"]

    def test_returns_404_for_unknown_row(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Chain")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _get_version_chain(client, "Chain", workflow_instance_id="unknown")

            assert response.status_code == 404

    def test_row_filter_receives_attached_user(self, db_engine_ctx):
        """Regression: row_filter used to receive a detached user."""
        with db_engine_ctx():
            _create_extension_table()
            user = _make_detached_user("gvc3", "gvc3@example.com", role_name="rf-role-2")
            _seed_row("wf-xyz", name="Seed", value=1)

            captured = []

            def row_filter(query, db, user):
                captured.append({r.role.name for r in user.roles})
                return query

            _register("WithFilter", read_roles=["rf-role-2"], row_filter=row_filter)

            client = Client()
            with override_get_user(client=client, user=user), disable_role_check(client):
                response = _get_version_chain(client, "WithFilter", workflow_instance_id="wf-xyz")

            assert response.status_code == 200
            assert captured == [{"rf-role-2"}]
            assert len(response.json()["versions"]) == 1
