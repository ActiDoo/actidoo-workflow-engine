# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Tests for the Workflow Data BFF endpoints.

End-to-end via the FastAPI TestClient. The read routes resolve the model from the
data-model registry at request time, so tests only need to register a model — no
route (re)mounting.
"""

import uuid

import pytest
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from actidoo_wfe.database import FlexibleUuid, SessionLocal, SessionMaker, get_db_contextmanager, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import repository, service_user
from actidoo_wfe.wf.config_data_model import (
    READ_ALL_WORKFLOW_USERS,
    ActionDef,
    FieldDef,
    WorkflowDataApiConfig,
    add_workflow_participant_filter,
)
from actidoo_wfe.wf.models import DataModelFile, WorkflowInstance, WorkflowManagedMixin, extension_model_base
from actidoo_wfe.wf.registry_data_model import DataModelDescriptor, data_model_registry
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

setup_db(settings=settings)


_WF_NS = uuid.UUID("00000000-0000-0000-0000-0000000000aa")


def _wf_id(label: str) -> str:
    """Deterministic UUID string for a human-readable label."""
    return str(uuid.uuid5(_WF_NS, label))


_ApiTestBase = extension_model_base("apitest")


class ApiTestModel(_ApiTestBase, WorkflowManagedMixin):
    _ext_table = "ate"
    __abstract__ = False
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    value: Mapped[int | None] = mapped_column(nullable=True)
    # ``data_upload`` is a framework-managed file field (registered with
    # type="file"); its references live in the data_model_files side table, not a
    # column. Tests seed them via ``_seed_file``.


@pytest.fixture(autouse=True)
def _clean_registry():
    data_model_registry.clear()
    yield
    data_model_registry.clear()


def _create_extension_table():
    engine = SessionMaker.kw["bind"]
    ApiTestModel.__table__.create(bind=engine, checkfirst=True)


def _make_detached_user(idp_user_id, email, role_name=None, locale="en-US"):
    """Mirror bff/deps.get_user: a detached user with loaded scalar attributes.

    Relationships (``roles``) are deliberately NOT loaded: routes only read
    ``user.id`` and the services load the ORM user freshly by id, so a test
    failing on a lazy load of this instance marks a contract violation.
    """
    with get_db_contextmanager() as db:
        service_user.upsert_user(
            db=db, idp_user_id=idp_user_id, username=email, email=email,
            first_name="X", last_name="Y", is_service_user=False, initial_locale=locale,
        )
    if role_name:
        with get_db_contextmanager() as db:
            user = service_user.upsert_user(
                db=db, idp_user_id=idp_user_id, username=email, email=email,
                first_name="X", last_name="Y", is_service_user=False, initial_locale=locale,
            )
            service_user.assign_roles(db=db, user_id=user.id, role_names=[role_name])
    with get_db_contextmanager() as db:
        user = service_user.upsert_user(
            db=db, idp_user_id=idp_user_id, username=email, email=email,
            first_name="X", last_name="Y", is_service_user=False, initial_locale=locale,
        )
        db.refresh(user)
        db.expunge(user)  # detach with loaded scalars; commit no longer expires it
    return user


def _register(name, *, read_roles=None, fields=None, row_filter=None, actions=None, i18n_dir=None):
    data_model_registry.register(
        DataModelDescriptor(
            name=name,
            model_class=ApiTestModel,
            namespace="apitest",
            is_versioned=True,
            i18n_dir=i18n_dir,
            api=WorkflowDataApiConfig(
                # read access is deny-by-default; tests default to the explicit wildcard
                read_roles=read_roles or [READ_ALL_WORKFLOW_USERS],
                fields=fields,
                row_filter=row_filter,
                actions=actions or [],
            ),
        ),
    )


def _register_non_api(name):
    data_model_registry.register(
        DataModelDescriptor(name=name, model_class=ApiTestModel, namespace="apitest", is_versioned=True, api=None),
    )


def _seed_row(row_id, *, name="Row", value=1, version=1, is_current=True, workflow_instance_id=None, title=None):
    """Seed an ApiTestModel version row. ``version``/``is_current`` are set explicitly
    so the ``before_flush`` versioning hook leaves the seeded values untouched.
    ``workflow_instance_id`` is mandatory (WorkflowManagedMixin) — a fresh provenance
    id is generated when the caller does not pin one."""
    with SessionMaker() as db, db.begin():
        db.add(ApiTestModel(
            id=row_id,
            version=version,
            is_current=is_current,
            workflow_instance_id=workflow_instance_id or uuid.uuid4(),  # provenance, distinct from id
            title=title,  # reserved record title from WorkflowManagedMixin
            name=name,
            value=value,
        ))


def _store_attachment(file_hash, *, filename="doc.pdf", mimetype="application/pdf", content=b"BYTES"):
    """Create a real WorkflowAttachment (stored via the tmp file storage fixture)."""
    with SessionMaker() as db, db.begin():
        att = repository.store_attachment(db=db, filename=filename, mimetype=mimetype, data=content, hash=file_hash)
        return att.id


def _seed_file(row_id, attachment_id, *, model_name="Files", row_version=1, field_name="data_upload", filename="doc.pdf", mimetype="application/pdf", position=0):
    """Seed a data_model_files side row linking a row version to an attachment."""
    with SessionMaker() as db, db.begin():
        db.add(DataModelFile(
            model_name=model_name,
            row_id=row_id,
            row_version=row_version,
            field_name=field_name,
            workflow_attachment_id=attachment_id,
            filename=filename,
            mimetype=mimetype,
            position=position,
        ))


def _seed_wf_instance(instance_id, created_by_id=None):
    with SessionMaker() as db, db.begin():
        db.add(WorkflowInstance(
            id=instance_id, name="participant-test", lane_mapping={}, data={}, created_by_id=created_by_id,
        ))


def _models_base(client) -> str:
    """The catalog path; per-model routes hang off it as ``<base>/<model_name>``."""
    return client.root_client.app.url_path_for("list_models")


def _list_models(client):
    return client.root_client.get(_models_base(client))


def _list_rows(client, model_name, **params):
    return client.root_client.get(f"{_models_base(client)}/{model_name}", params=params)


def _get_version_chain(client, model_name, record_id):
    return client.root_client.get(f"{_models_base(client)}/{model_name}/{record_id}")


# ---------------------------------------------------------------------------
# Display-type inference (unit)
# ---------------------------------------------------------------------------


class TestDisplayTypeInference:
    @pytest.mark.parametrize(
        "col_type, expected",
        [
            (FlexibleUuid(), "string"),
            (String(50), "string"),
            (Integer(), "number"),
            (Numeric(10, 2), "decimal"),
            (Boolean(), "boolean"),
            (DateTime(), "datetime"),
        ],
    )
    def test_maps_column_types(self, col_type, expected):
        from actidoo_wfe.wf import views_data_model

        assert views_data_model.display_type(col_type) == expected


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
            _seed_row(_wf_id("seed"))  # list_models hides models with zero visible rows

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_models(client)

            assert response.status_code == 200
            assert [m["name"] for m in response.json()] == ["Exposed"]

    def test_excludes_models_user_cannot_read(self, db_engine_ctx):
        with db_engine_ctx():
            user = _make_detached_user("lm2", "lm2@example.com", role_name="viewer")
            _register("OpenToAll")  # helper defaults to READ_ALL_WORKFLOW_USERS
            _register("ViewerOnly", read_roles=["viewer"])
            _register("AdminOnly", read_roles=["admin"])
            _seed_row(_wf_id("seed"))  # list_models hides models with zero visible rows

            client = Client()
            with override_get_user(client=client, user=user), disable_role_check(client):
                response = _list_models(client)

            assert response.status_code == 200
            assert {m["name"] for m in response.json()} == {"OpenToAll", "ViewerOnly"}

    def test_has_actions_reflects_declared_actions(self, db_engine_ctx):
        """``has_actions`` is stable per model (declared actions), independent of rows."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("WithActions", actions=[ActionDef(key="go", label="Go", target="Wf")])
            _register("WithoutActions")
            _seed_row(_wf_id("seed"))  # list_models hides models with zero visible rows

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                models = {m["name"]: m for m in _list_models(client).json()}

            assert models["WithActions"]["has_actions"] is True
            assert models["WithoutActions"]["has_actions"] is False

    def test_fields_metadata_excludes_mixin_system_columns(self, db_engine_ctx):
        with db_engine_ctx():
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Cols")
            _seed_row(_wf_id("seed"))  # list_models hides models with zero visible rows

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_models(client)

            assert response.status_code == 200
            fields = response.json()[0]["fields"]
            names = {f["name"] for f in fields}
            # The reserved record title is a regular display field, like id.
            assert {"id", "title", "name", "value"} <= names
            # Versioning/provenance plumbing is hidden from the inferred schema.
            assert names.isdisjoint({"version", "is_current", "workflow_instance_id", "action", "created_at"})
            id_field = next(f for f in fields if f["name"] == "id")
            assert id_field["primary_key"] is True
            assert id_field["type"] == "string"
            assert id_field["sortable"] is True and id_field["filterable"] is True
            assert next(f for f in fields if f["name"] == "value")["type"] == "number"

    def test_exposes_file_field_filterable_false(self, db_engine_ctx):
        with db_engine_ctx():
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register(
                "Meta",
                fields=[FieldDef("name"), FieldDef("data_upload", type="file")],
            )
            _seed_row(_wf_id("seed"))  # list_models hides models with zero visible rows

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                model = _list_models(client).json()[0]

            file_field = next(f for f in model["fields"] if f["name"] == "data_upload")
            # File fields are framework-managed virtual fields (no backing column).
            assert file_field["filterable"] is False and file_field["sortable"] is False
            assert file_field["virtual"] is True and file_field["type"] == "file"

    def test_respects_explicit_fields_config_with_computed_field(self, db_engine_ctx):
        with db_engine_ctx():
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register(
                "Restricted",
                fields=[
                    FieldDef("name"),
                    FieldDef("is_high", type="boolean", compute=lambda row: (row.value or 0) > 10),
                ],
            )
            _seed_row(_wf_id("seed"))  # list_models hides models with zero visible rows

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_models(client)

            assert response.status_code == 200
            fields = response.json()[0]["fields"]
            assert [f["name"] for f in fields] == ["name", "is_high"]
            assert fields[1] == {
                "name": "is_high", "label": "is_high", "type": "boolean", "format": None,
                "nullable": True, "primary_key": False, "virtual": True,
                "sortable": False, "filterable": False,
            }


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
                _seed_row(_wf_id(f"wf-{i}"), name=f"Row{i}", value=i)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                page1 = _list_rows(client, "Paginated", limit=2, offset=0).json()
                page2 = _list_rows(client, "Paginated", limit=2, offset=2).json()

            assert page1["COUNT"] == 5
            assert len(page1["ITEMS"]) == 2
            assert len(page2["ITEMS"]) == 2
            assert page1["model"]["has_actions"] is False  # stable per model, not per page
            ids = [i["data"]["id"] for i in page1["ITEMS"] + page2["ITEMS"]]
            assert ids == sorted(ids)

    def test_returns_only_head_of_version_chain(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Chained")
            rec_id = _wf_id("record")
            _seed_row(rec_id, name="OldVersion", version=1, is_current=False)
            _seed_row(rec_id, name="LatestVersion", version=2, is_current=True)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_rows(client, "Chained")

            assert response.status_code == 200
            data = response.json()
            assert data["COUNT"] == 1
            assert data["ITEMS"][0]["data"]["id"] == rec_id
            assert data["ITEMS"][0]["data"]["version"] == 2
            assert data["ITEMS"][0]["data"]["name"] == "LatestVersion"

    def test_items_use_computed_fields_and_exclude_system_columns(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            doubled = FieldDef("doubled", type="number", compute=lambda r: (r.value or 0) * 2)
            _register("Virt", fields=[FieldDef("name"), FieldDef("value"), doubled])
            _seed_row(_wf_id("wf-vf"), name="Item", value=21)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_rows(client, "Virt")

            assert response.status_code == 200
            # The stable id, the record title (and version, for versioned models) are
            # always projected (for action/download/version URLs and the record name)
            # even though they are not declared fields.
            assert response.json()["ITEMS"] == [
                {
                    "data": {"name": "Item", "value": 21, "doubled": 42, "id": _wf_id("wf-vf"), "title": None, "version": 1},
                    "actions": [],
                },
            ]

    def test_title_always_projected_without_fielddef(self, db_engine_ctx):
        """The reserved record title rides along in the row data even when the model
        declares display fields that do not include it."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Titled", fields=[FieldDef("name")])
            _seed_row(_wf_id("t1"), name="Row", title="Lunch receipt")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                body = _list_rows(client, "Titled").json()

            assert body["ITEMS"][0]["data"]["title"] == "Lunch receipt"
            # ...but it is not part of the declared display fields.
            assert [f["name"] for f in body["model"]["fields"]] == ["name"]

    def test_global_search_matches_title_without_fielddef(self, db_engine_ctx):
        """Records stay findable by their human-readable name via the global search."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Titled", fields=[FieldDef("name")])
            _seed_row(_wf_id("t1"), name="A", title="Lunch receipt")
            _seed_row(_wf_id("t2"), name="B", title="Hotel invoice")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                found = _list_rows(client, "Titled", search="Lunch").json()

            assert found["COUNT"] == 1
            assert found["ITEMS"][0]["data"]["title"] == "Lunch receipt"

    def test_title_filter_and_sort(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Titled", fields=[FieldDef("name")])
            _seed_row(_wf_id("t1"), name="A", title="Alpha")
            _seed_row(_wf_id("t2"), name="B", title="Beta")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                filtered = _list_rows(client, "Titled", f_title="Beta").json()
                ordered = _list_rows(client, "Titled", sort="title.desc").json()

            assert filtered["COUNT"] == 1 and filtered["ITEMS"][0]["data"]["title"] == "Beta"
            assert [i["data"]["title"] for i in ordered["ITEMS"]] == ["Beta", "Alpha"]

    def test_failing_compute_serializes_as_none_not_500(self, db_engine_ctx):
        """A raising compute callable must not 500 the page; the cell becomes None."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            boom = FieldDef("boom", type="number", compute=lambda r: 1 / 0)
            _register("Broken", fields=[FieldDef("name"), boom])
            _seed_row(_wf_id("wf-boom"), name="Item", value=1)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_rows(client, "Broken")

            assert response.status_code == 200
            assert response.json()["ITEMS"][0]["data"]["boom"] is None

    def test_file_field_serializes_to_refs(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Files", fields=[FieldDef("name"), FieldDef("data_upload", type="file")])
            row_id = _wf_id("wf-file")
            _seed_row(row_id, name="WithFile")
            att_id = _store_attachment("h1", filename="a.pdf", mimetype="application/pdf")
            _seed_file(row_id, att_id, filename="a.pdf", mimetype="application/pdf")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _list_rows(client, "Files")

            assert response.status_code == 200
            item = response.json()["ITEMS"][0]["data"]
            assert item["data_upload"] == [
                {"id": str(att_id), "hash": "h1", "filename": "a.pdf", "mimetype": "application/pdf"},
            ]

    def test_filter_and_sort_via_bff_table(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Filterable")
            _seed_row(_wf_id("a"), name="Apple", value=1)
            _seed_row(_wf_id("b"), name="Banana", value=3)
            _seed_row(_wf_id("c"), name="Cherry", value=2)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                filtered = _list_rows(client, "Filterable", f_name="Banana").json()
                ordered = _list_rows(client, "Filterable", sort="value.desc").json()
                invalid_sort = _list_rows(client, "Filterable", sort="nope.asc")

            assert filtered["COUNT"] == 1
            assert filtered["ITEMS"][0]["data"]["name"] == "Banana"
            assert [i["data"]["value"] for i in ordered["ITEMS"]] == [3, 2, 1]
            # Undeclared sort fields are rejected with FastAPI's structured 422 body
            # (the dynamic route binds query params via FastAPI internals — this
            # assertion guards that reuse against FastAPI upgrades).
            assert invalid_sort.status_code == 422
            assert invalid_sort.json()["detail"][0]["loc"][:2] == ["query", "sort"]

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
        """Regression: row_filter used to receive a detached user."""
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
            assert response.json()["COUNT"] == 0


# ---------------------------------------------------------------------------
# Label localization (LocalizableLabel)
# ---------------------------------------------------------------------------


class TestLabelResolution:
    """Labels are gettext msgids, resolved against the model's Babel catalog
    (``i18n/locales/<locale>/LC_MESSAGES/<name>.mo``) — the same toolchain as the
    per-workflow catalogs."""

    def _catalog_dir(self, tmp_path, model_name, translations, locale="de"):
        """Write + compile a catalog under tmp_path (the model's i18n_dir)."""
        from babel.messages.catalog import Catalog
        from babel.messages.pofile import write_po

        from actidoo_wfe.i18n import compile_po_to_mo

        po = tmp_path / "i18n" / "locales" / locale / "LC_MESSAGES" / f"{model_name}.po"
        po.parent.mkdir(parents=True)
        catalog = Catalog(locale=locale)
        for msgid, msgstr in translations.items():
            catalog.add(id=msgid, string=msgstr)
        with open(po, "wb") as f:
            write_po(f, catalog)
        compile_po_to_mo(po)
        return tmp_path

    def test_resolver_fallbacks(self):
        from actidoo_wfe.wf.views_data_model import resolve_label

        no_catalog = DataModelDescriptor(name="X", model_class=ApiTestModel, namespace="apitest")
        # without a catalog the msgid passes through; None falls back to the field name
        assert resolve_label(no_catalog, "Amount", "de-DE", "x") == "Amount"
        assert resolve_label(no_catalog, None, "de-DE", "amount") == "amount"

    def test_labels_resolve_via_catalog(self, db_engine_ctx, tmp_path):
        """Model/field/action labels arrive in the requesting user's language."""
        with db_engine_ctx():
            _create_extension_table()
            user = _make_detached_user("loc1", "loc1@example.com", role_name="wf-user", locale="de-DE")
            i18n_dir = self._catalog_dir(tmp_path, "Localized", {"Name": "Bezeichnung", "Go": "Los"})
            _register(
                "Localized",
                fields=[FieldDef("name", label="Name")],
                actions=[ActionDef(key="go", label="Go", target="Wf")],
                i18n_dir=i18n_dir,
            )
            _seed_row(_wf_id("l1"), name="Row")

            client = Client()
            with override_get_user(client=client, user=user), disable_role_check(client):
                rows = _list_rows(client, "Localized").json()

            assert rows["model"]["fields"][0]["label"] == "Bezeichnung"
            assert rows["ITEMS"][0]["actions"][0]["label"] == "Los"

    def test_csv_header_resolves_via_catalog(self, db_engine_ctx, tmp_path):
        with db_engine_ctx():
            _create_extension_table()
            user = _make_detached_user("loc2", "loc2@example.com", role_name="wf-user", locale="de-DE")
            i18n_dir = self._catalog_dir(tmp_path, "Localized", {"Name": "Bezeichnung"})
            _register("Localized", fields=[FieldDef("name", label="Name")], i18n_dir=i18n_dir)
            _seed_row(_wf_id("l1"), name="Row")

            client = Client()
            with override_get_user(client=client, user=user), disable_role_check(client):
                body = client.root_client.get(f"{_models_base(client)}/Localized/export.csv").text

            assert "Bezeichnung" in body

    def test_extraction_writes_declared_labels(self, tmp_path):
        """The CLI extraction reads the registered declaration, not source files."""
        from actidoo_wfe.wf import service_i18n

        descriptor = DataModelDescriptor(
            name="Extracted",
            model_class=ApiTestModel,
            namespace="apitest",
            i18n_dir=tmp_path,
            api=WorkflowDataApiConfig(
                label="My Model",
                read_roles=[READ_ALL_WORKFLOW_USERS],
                fields=[FieldDef("name", label="Name")],
                actions=[ActionDef(key="go", label="Go", target="Wf")],
            ),
        )
        pot = service_i18n.extract_messages_for_datamodel(descriptor)
        content = pot.read_text()
        assert pot == tmp_path / "i18n" / "Extracted.pot"
        for msgid in ("My Model", "Name", "Go"):
            assert f'msgid "{msgid}"' in content


# ---------------------------------------------------------------------------
# Per-row actions
# ---------------------------------------------------------------------------


class TestRowActions:
    def test_actions_delivered_per_row_and_filtered_by_allowed(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            actions = [
                ActionDef(key="approve", label="Approve", target="ApprovalWf"),
                ActionDef(key="escalate", label="Escalate", target="EscalateWf",
                          row_filter=lambda q, db, user: q.where(ApiTestModel.value > 5)),
            ]
            _register("WithActions", actions=actions)
            _seed_row(_wf_id("low"), name="Low", value=1)
            _seed_row(_wf_id("high"), name="High", value=10)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                rows = _list_rows(client, "WithActions").json()["ITEMS"]

            by_name = {r["data"]["name"]: {a["key"] for a in r["actions"]} for r in rows}
            assert by_name["Low"] == {"approve"}
            assert by_name["High"] == {"approve", "escalate"}


# ---------------------------------------------------------------------------
# get_version_chain endpoint
# ---------------------------------------------------------------------------


class TestGetVersionChainEndpoint:
    def test_returns_all_versions_for_record_id(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Chain")
            rec = _wf_id("record")
            _seed_row(rec, name="v1", version=1, is_current=False)
            _seed_row(rec, name="v2", version=2, is_current=False)
            _seed_row(rec, name="v3", version=3, is_current=True)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                response = _get_version_chain(client, "Chain", record_id=rec)

            assert response.status_code == 200
            versions = response.json()["versions"]
            assert [v["data"]["version"] for v in versions] == [1, 2, 3]
            assert {v["data"]["id"] for v in versions} == {rec}
            assert [v["data"]["name"] for v in versions] == ["v1", "v2", "v3"]
            # Each entry carries metadata independent of the declared fields,
            # including the historical record title per version.
            assert all(v["created_at"] is not None for v in versions)
            assert all("title" in v["data"] for v in versions)

    def test_returns_404_for_unknown_row(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Chain")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                absent = _get_version_chain(client, "Chain", record_id=_wf_id("nope"))
                malformed = _get_version_chain(client, "Chain", record_id="not-a-uuid")

            assert absent.status_code == 404
            assert malformed.status_code == 422

    def test_row_filter_receives_attached_user(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            user = _make_detached_user("gvc3", "gvc3@example.com", role_name="rf-role-2")
            xyz = _wf_id("wf-xyz")
            _seed_row(xyz, name="Seed", value=1)

            captured = []

            def row_filter(query, db, user):
                captured.append({r.role.name for r in user.roles})
                return query

            _register("WithFilter", read_roles=["rf-role-2"], row_filter=row_filter)

            client = Client()
            with override_get_user(client=client, user=user), disable_role_check(client):
                response = _get_version_chain(client, "WithFilter", record_id=xyz)

            assert response.status_code == 200
            assert captured == [{"rf-role-2"}]
            assert len(response.json()["versions"]) == 1


# ---------------------------------------------------------------------------
# Per-context field visibility (include_in_table / include_in_detail / include_in_csv)
# ---------------------------------------------------------------------------


class TestPerContextFieldVisibility:
    """The three include_in_* flags gate a field per presentation context (default
    on), filtered server-side so the schema and the row data agree for each context."""

    def _register_mixed(self):
        _register(
            "Visible",
            fields=[
                FieldDef("name"),  # default: shown everywhere
                FieldDef("value", include_in_table=False),  # verbose detail-only column
                FieldDef("tbl", type="string", compute=lambda r: "T", include_in_detail=False),
                FieldDef("nocsv", type="string", compute=lambda r: "X", include_in_csv=False),
            ],
        )

    def test_detail_only_field_absent_from_table_present_in_detail(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            self._register_mixed()
            rec = _wf_id("v1")
            _seed_row(rec, name="Row", value=42)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                listed = _list_rows(client, "Visible").json()
                chain = _get_version_chain(client, "Visible", record_id=rec).json()

            # Table: ``value`` is dropped from both the schema and the row payload, so a
            # verbose field never bloats the list response...
            assert "value" not in {f["name"] for f in listed["model"]["fields"]}
            assert "value" not in listed["ITEMS"][0]["data"]
            # ...but the detail page (schema + data) carries it in full.
            assert "value" in {f["name"] for f in chain["model"]["fields"]}
            assert chain["versions"][0]["data"]["value"] == 42

    def test_table_only_field_absent_from_detail(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            self._register_mixed()
            rec = _wf_id("v2")
            _seed_row(rec, name="Row", value=1)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                listed = _list_rows(client, "Visible").json()
                chain = _get_version_chain(client, "Visible", record_id=rec).json()

            assert "tbl" in {f["name"] for f in listed["model"]["fields"]}
            assert listed["ITEMS"][0]["data"]["tbl"] == "T"
            assert "tbl" not in {f["name"] for f in chain["model"]["fields"]}
            assert "tbl" not in chain["versions"][0]["data"]

    def test_csv_excludes_opted_out_field_keeps_detail_only(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            self._register_mixed()
            _seed_row(_wf_id("v3"), name="Row", value=42)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                body = client.root_client.get(f"{_models_base(client)}/Visible/export.csv").text

            header = body.splitlines()[0]
            # include_in_csv=False keeps ``nocsv`` out of the export entirely...
            assert "nocsv" not in header
            # ...while a detail-only field (default include_in_csv=True) is still exported.
            assert "value" in header
            assert "42" in body


# ---------------------------------------------------------------------------
# start_workflow_for_existing_data_model
# ---------------------------------------------------------------------------


class TestStartWorkflowForExistingDataModel:
    def _post(self, client, model_name, row_id, action, data=None):
        url = client.root_client.app.url_path_for("start_workflow_for_existing_data_model")
        body = {"model_name": model_name, "id": str(row_id), "action": action}
        if data is not None:
            body["data"] = data
        return client.root_client.post(url, json=body)

    def test_unknown_action_returns_404(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Acts", actions=[ActionDef(key="go", label="Go", target="Wf")])
            _seed_row(_wf_id("r1"), name="R", value=1)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._post(client, "Acts", _wf_id("r1"), action="missing")

            assert resp.status_code == 404

    def test_action_not_allowed_returns_403(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Acts", actions=[
                ActionDef(key="go", label="Go", target="Wf",
                          row_filter=lambda q, db, user: q.where(false())),
            ])
            _seed_row(_wf_id("r1"), name="R", value=1)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._post(client, "Acts", _wf_id("r1"), action="go")

            assert resp.status_code == 403

    def test_no_current_version_returns_404(self, db_engine_ctx):
        """An action on a record with no current (head) version is rejected."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Acts", actions=[ActionDef(key="go", label="Go", target="Wf")])
            rec = _wf_id("rec")
            # Only a superseded version exists; there is no is_current head to act on.
            _seed_row(rec, name="R", value=1, version=1, is_current=False)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._post(client, "Acts", rec, action="go")

            assert resp.status_code == 404

    def test_happy_path_starts_workflow_with_payload(self, db_engine_ctx, monkeypatch):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Acts", actions=[ActionDef(key="go", label="Go", target="TargetWf")])
            row_id = _wf_id("r1")
            _seed_row(row_id, name="R", value=1)

            started = uuid.uuid4()
            captured = {}

            def fake_start_workflow(db, name, user_id, initial_task_data=None, trusted_seed=False):
                captured["name"] = name
                captured["data"] = initial_task_data
                captured["trusted_seed"] = trusted_seed
                return started

            import actidoo_wfe.wf.service_application as service_application
            monkeypatch.setattr(service_application, "start_workflow", fake_start_workflow)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                # Client-supplied free-form data is no longer accepted/merged.
                resp = self._post(client, "Acts", row_id, action="go", data={"extra": 1})

            assert resp.status_code == 200
            assert resp.json()["workflow_instance_id"] == str(started)
            assert captured["name"] == "TargetWf"
            # Only the server-built payload is seeded; the injected ``data`` is ignored.
            assert captured["data"] == {"source_id": row_id}
            # The trusted seed preserves technical fields through the target's first form.
            assert captured["trusted_seed"] is True


# ---------------------------------------------------------------------------
# Attachment download (read-access authorized)
# ---------------------------------------------------------------------------


class TestAttachmentDownload:
    def _download(self, client, model_name, record_id, version, file_hash):
        return client.root_client.get(
            f"{_models_base(client)}/{model_name}/{record_id}/versions/{version}/attachments/{file_hash}"
        )

    def test_happy_path_streams_attachment(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            file_hash = "hash-abc"
            _register("Files", fields=[FieldDef("name"), FieldDef("data_upload", type="file")])
            row_id = _wf_id("f1")
            _seed_row(row_id, name="R")
            att_id = _store_attachment(file_hash, filename="doc.pdf", content=b"PDFDATA")
            _seed_file(row_id, att_id, filename="doc.pdf")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._download(client, "Files", row_id, 1, file_hash)

            assert resp.status_code == 200
            assert resp.content == b"PDFDATA"
            assert "doc.pdf" in resp.headers.get("content-disposition", "")

    def test_serves_per_row_filename_under_hash_dedup(self, db_engine_ctx):
        """The download name is the row's context filename, not the attachment's
        first_filename (which, under hash dedup, is the first uploader's name)."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            file_hash = "shared-bytes"
            _register("Files", fields=[FieldDef("name"), FieldDef("data_upload", type="file")])
            # One attachment (first_filename "first.pdf"), referenced by two rows
            # under different context names.
            att_id = _store_attachment(file_hash, filename="first.pdf", content=b"DATA")
            row_a, row_b = _wf_id("fa"), _wf_id("fb")
            _seed_row(row_a, name="A")
            _seed_row(row_b, name="B")
            _seed_file(row_a, att_id, filename="invoice-a.pdf")
            _seed_file(row_b, att_id, filename="invoice-b.pdf")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp_a = self._download(client, "Files", row_a, 1, file_hash)
                resp_b = self._download(client, "Files", row_b, 1, file_hash)

            assert "invoice-a.pdf" in resp_a.headers.get("content-disposition", "")
            assert "invoice-b.pdf" in resp_b.headers.get("content-disposition", "")

    def test_ownership_unreferenced_hash_returns_404(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Files", fields=[FieldDef("name"), FieldDef("data_upload", type="file")])
            row_id = _wf_id("f2")
            _seed_row(row_id, name="R")
            att_id = _store_attachment("referenced", filename="a.pdf")
            _seed_file(row_id, att_id, filename="a.pdf")
            # An unrelated attachment exists globally, but the row does not reference it.
            _store_attachment("other-hash", filename="b.pdf")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._download(client, "Files", row_id, 1, "other-hash")

            assert resp.status_code == 404

    def test_no_read_access_returns_403(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            user = _make_detached_user("dl3", "dl3@example.com", role_name="viewer")
            _register("Files", read_roles=["admin"], fields=[FieldDef("data_upload", type="file")])
            row_id = _wf_id("f3")
            _seed_row(row_id, name="R")
            att_id = _store_attachment("h", filename="a.pdf")
            _seed_file(row_id, att_id, filename="a.pdf")

            client = Client()
            with override_get_user(client=client, user=user), disable_role_check(client):
                resp = self._download(client, "Files", row_id, 1, "h")

            assert resp.status_code == 403

    def test_row_filter_hides_row_returns_404(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})

            def hide_all(query, db, user):
                return query.where(ApiTestModel.value == 999999)

            _register("Files", fields=[FieldDef("data_upload", type="file")], row_filter=hide_all)
            row_id = _wf_id("f4")
            _seed_row(row_id, name="R", value=1)
            att_id = _store_attachment("h", filename="a.pdf")
            _seed_file(row_id, att_id, filename="a.pdf")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._download(client, "Files", row_id, 1, "h")

            assert resp.status_code == 404

    def test_unknown_model_returns_404(self, db_engine_ctx):
        with db_engine_ctx():
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._download(client, "Nope", _wf_id("x"), 1, "h")

            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


class TestCsvExport:
    def _export(self, client, model_name, **params):
        return client.root_client.get(f"{_models_base(client)}/{model_name}/export.csv", params=params)

    def test_exports_all_rows_as_csv(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Export", fields=[FieldDef("name", label="Name"), FieldDef("value", label="Wert")])
            _seed_row(_wf_id("e1"), name="Alpha", value=1)
            _seed_row(_wf_id("e2"), name="Beta", value=2)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._export(client, "Export")

            assert resp.status_code == 200
            assert "text/csv" in resp.headers.get("content-type", "")
            assert "Export.csv" in resp.headers.get("content-disposition", "")
            body = resp.text
            assert "Name;Wert" in body
            assert "Alpha;1" in body
            assert "Beta;2" in body

    def test_export_respects_filter(self, db_engine_ctx):
        """The export matches the visible table view: column filters apply."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Export", fields=[FieldDef("name", label="Name"), FieldDef("value", label="Wert")])
            _seed_row(_wf_id("e1"), name="Alpha", value=1)
            _seed_row(_wf_id("e2"), name="Beta", value=2)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                body = self._export(client, "Export", f_name="Beta").text

            assert "Beta;2" in body
            assert "Alpha" not in body

    def test_export_respects_global_search(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Export", fields=[FieldDef("name", label="Name")])
            _seed_row(_wf_id("e1"), name="Alpha")
            _seed_row(_wf_id("e2"), name="Beta")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                body = self._export(client, "Export", search="Bet").text

            assert "Beta" in body
            assert "Alpha" not in body

    def test_export_respects_sort(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Export", fields=[FieldDef("name", label="Name"), FieldDef("value", label="Wert")])
            _seed_row(_wf_id("e1"), name="Low", value=1)
            _seed_row(_wf_id("e2"), name="High", value=9)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                body = self._export(client, "Export", sort="value.desc").text

            assert body.index("High") < body.index("Low")

    def test_export_ignores_pagination_params(self, db_engine_ctx):
        """Pagination must never truncate an export — limit/offset are ignored."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Export", fields=[FieldDef("name", label="Name")])
            for i in range(3):
                _seed_row(_wf_id(f"e{i}"), name=f"Row{i}")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                body = self._export(client, "Export", limit=1, offset=1).text

            assert all(f"Row{i}" in body for i in range(3))

    def test_export_invalid_sort_returns_422(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Export", fields=[FieldDef("name", label="Name")])

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._export(client, "Export", sort="nope.asc")

            assert resp.status_code == 422

    def test_export_row_filter_still_applies_with_filters(self, db_engine_ctx):
        """Read scope wins: a row hidden by ``row_filter`` never exports, even if
        the requested column filter would match it."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})

            def only_low_values(query, db, user):
                return query.where(ApiTestModel.value < 5)

            _register("Export", fields=[FieldDef("name", label="Name")], row_filter=only_low_values)
            _seed_row(_wf_id("e1"), name="Visible", value=1)
            _seed_row(_wf_id("e2"), name="Hidden", value=9)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                body = self._export(client, "Export", f_name="Hidden").text

            assert "Hidden" not in body

    def test_neutralizes_formula_injection(self, db_engine_ctx):
        """A cell that a spreadsheet would evaluate as a formula is prefixed with `'`."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Export", fields=[FieldDef("name", label="Name"), FieldDef("value", label="Wert")])
            _seed_row(_wf_id("e1"), name="=1+2", value=1)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._export(client, "Export")

            assert resp.status_code == 200
            # neutralized to a literal, not left as a leading-`=` formula cell
            assert "'=1+2" in resp.text

    def test_neutralizes_whitespace_and_all_formula_prefixes(self, db_engine_ctx):
        """`= + - @` are defanged, including behind leading whitespace (`\\t=`)."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Export", fields=[FieldDef("name", label="Name")])
            vectors = ["\t=cmd", "+1+2", "-2+3", "@SUM(A1)"]
            for i, payload in enumerate(vectors):
                _seed_row(_wf_id(f"e{i}"), name=payload)

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                body = self._export(client, "Export").text

            for payload in vectors:
                assert "'" + payload in body

    def test_export_is_utf8_with_bom(self, db_engine_ctx):
        """Excel (de-DE, `;` delimiter) needs a BOM to read the file as UTF-8."""
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})
            _register("Export", fields=[FieldDef("name", label="Name")])
            _seed_row(_wf_id("e1"), name="Ümläut")

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._export(client, "Export")

            assert resp.content[:3] == b"\xef\xbb\xbf"

    def test_no_read_access_returns_403(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            user = _make_detached_user("ex2", "ex2@example.com", role_name="viewer")
            _register("Export", read_roles=["admin"])

            client = Client()
            with override_get_user(client=client, user=user), disable_role_check(client):
                resp = self._export(client, "Export")

            assert resp.status_code == 403

    def test_unknown_model_returns_404(self, db_engine_ctx):
        with db_engine_ctx():
            db = SessionLocal()
            dummy = WorkflowDummy(db_session=db, users_with_roles={"u": ["wf-user"]})

            client = Client()
            with override_get_user(client=client, user=dummy.user("u").user), disable_role_check(client):
                resp = self._export(client, "Nope")

            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# add_workflow_participant_filter
# ---------------------------------------------------------------------------


class TestParticipantRowFilter:
    def test_creator_sees_row_non_participant_does_not(self, db_engine_ctx):
        with db_engine_ctx():
            _create_extension_table()
            db = SessionLocal()
            dummy = WorkflowDummy(
                db_session=db,
                users_with_roles={"creator": ["pf-role"], "outsider": ["pf-role"]},
            )
            creator = dummy.user("creator").user
            outsider = dummy.user("outsider").user

            wf_id = uuid.uuid4()
            _seed_wf_instance(wf_id, created_by_id=creator.id)
            # The row's stable id is its own surrogate; participation is matched on the
            # provenance column (which workflow instance produced the version).
            record_id = str(uuid.uuid4())
            _seed_row(record_id, name="Owned", value=1, workflow_instance_id=str(wf_id))

            def row_filter(query, db, user):
                return add_workflow_participant_filter(query, ApiTestModel.workflow_instance_id, user)

            _register("Owned", read_roles=["pf-role"], row_filter=row_filter)

            client = Client()
            with override_get_user(client=client, user=creator), disable_role_check(client):
                creator_resp = _list_rows(client, "Owned")
            with override_get_user(client=client, user=outsider), disable_role_check(client):
                outsider_resp = _list_rows(client, "Owned")

            assert creator_resp.status_code == 200
            assert [r["data"]["id"] for r in creator_resp.json()["ITEMS"]] == [record_id]

            assert outsider_resp.status_code == 200
            assert outsider_resp.json()["ITEMS"] == []


# ---------------------------------------------------------------------------
# Reverse-scan cache (workflows_using_model)
# ---------------------------------------------------------------------------


class TestReverseScanCache:
    def test_rebuilds_only_when_workflow_set_changes(self, monkeypatch):
        """The cache is keyed on the workflow *set*: a new workflow set rebuilds it,
        the same set reuses it."""
        import types

        import actidoo_wfe.wf.service_data_model as svc

        # start from a clean cache
        svc._model_to_workflows.cache_clear()

        names = ["wf-a"]

        def fake_import(module_path):
            module = types.ModuleType(module_path)
            module.DATA_MODELS = ["M"]
            return module

        monkeypatch.setattr(svc.workflow_providers, "iter_workflow_names", lambda: list(names))
        monkeypatch.setattr(svc.workflow_providers, "get_workflow_module_path", lambda name: f"fake.{name}")
        monkeypatch.setattr(svc.importlib, "import_module", fake_import)

        assert svc.workflows_using_model("M") == ["wf-a"]
        # same set -> served from cache, no rebuild
        assert svc.workflows_using_model("M") == ["wf-a"]
        assert svc._model_to_workflows.cache_info().misses == 1

        # the workflow set changes -> different cache key -> rebuild
        names.append("wf-b")
        assert sorted(svc.workflows_using_model("M")) == ["wf-a", "wf-b"]
        assert svc._model_to_workflows.cache_info().misses == 2

        # reset so later tests recompute against the real provider
        svc._model_to_workflows.cache_clear()


class TestActionTargetValidation:
    """Post-scan validation of ``ActionDef.target`` against loadable workflows."""

    def test_unknown_target_is_reported(self):
        from actidoo_wfe.wf.service_workflow import can_load_workflow

        _register("Acts", actions=[ActionDef(key="go", label="Go", target="DoesNotExist")])
        errors = data_model_registry.validate_action_targets(workflow_exists=can_load_workflow)
        assert any("Acts" in e and "DoesNotExist" in e for e in errors)

    def test_real_target_passes(self):
        from actidoo_wfe.wf.service_workflow import can_load_workflow

        _register("Acts", actions=[ActionDef(key="go", label="Go", target="TestFlowBasicStart")])
        assert data_model_registry.validate_action_targets(workflow_exists=can_load_workflow) == []
