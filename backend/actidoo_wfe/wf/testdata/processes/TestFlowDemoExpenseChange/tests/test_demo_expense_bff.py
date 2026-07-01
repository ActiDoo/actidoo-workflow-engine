# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Reference BFF integration test for the workflow-data feature.

Exercises the full feature set end-to-end against the data API:
- a Create workflow writes a DemoExpense record (incl. a receipt upload),
- the row + typed schema + per-row action are visible via the data API,
- read permission (viewer ok, outsider forbidden),
- the receipt attachment downloads through the read-access-authorized endpoint,
- a Change workflow (started via the "edit" action) appends a new version sharing
  the record's stable id,
- modify permission (a viewer may not start the change workflow).
"""

import base64
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from actidoo_wfe.database import SessionLocal, SessionMaker, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.registry_data_model import data_model_registry
from actidoo_wfe.wf.testdata.datamodels.demo_expense_model import DemoExpense, register_demo_expense
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

setup_db(settings=settings)

_PNG_BYTES = (Path(__file__).parent / "test.png").read_bytes()
_PNG_B64 = base64.b64encode(_PNG_BYTES).decode("utf-8")
_RECEIPT = {"datauri": f"data:image/png;name=receipt.png;base64,{_PNG_B64}"}


@pytest.fixture(autouse=True)
def _isolate_registry():
    data_model_registry.clear()
    yield
    data_model_registry.clear()


def _setup(db):
    """Create the ext table, register the model, start the create workflow."""
    register_demo_expense()
    DemoExpense.__table__.create(bind=SessionMaker.kw["bind"], checkfirst=True)
    return WorkflowDummy(
        db_session=db,
        users_with_roles={
            "editor": ["wf-user", "demo-editor"],
            "viewer": ["wf-user", "demo-viewer"],
            "outsider": ["wf-user"],
        },
        workflow_name="TestFlowDemoExpenseCreate",
        start_user="editor",
    )


def _create_record(wf, *, title="Lunch", amount=42.5, category="Food", with_receipt=True):
    data = {"title": title, "amount": amount, "category": category}
    if with_receipt:
        data["receipt"] = _RECEIPT
    wf.user("editor").submit(task_data=data, workflow_instance_id=wf.workflow_instance_id)


# --- BFF URL helpers (mirroring the data-model test) -----------------------


def _base(client):
    return client.root_client.app.url_path_for("list_models")


def _list_models(client):
    return client.root_client.get(_base(client))


def _list_rows(client):
    return client.root_client.get(f"{_base(client)}/DemoExpense")


def _head_item(client):
    """The current (head) row of the only DemoExpense record, via the API."""
    return _list_rows(client).json()["ITEMS"][0]


def _version_chain(client, record_id):
    return client.root_client.get(f"{_base(client)}/DemoExpense/{record_id}")


def _download(client, record_id, version, file_hash):
    return client.root_client.get(
        f"{_base(client)}/DemoExpense/{record_id}/versions/{version}/attachments/{file_hash}"
    )


def _export_csv(client):
    return client.root_client.get(f"{_base(client)}/DemoExpense/export.csv")


def _start_edit(client, record_id):
    url = client.root_client.app.url_path_for("start_workflow_for_existing_data_model")
    return client.root_client.post(url, json={"model_name": "DemoExpense", "id": record_id, "action": "edit"})


def _drop_read_snapshot(db):
    """Release the long-lived test session's REPEATABLE READ snapshot.

    The action endpoint commits the new (change) workflow instance in its own
    request session; this test session opened its snapshot earlier and would not
    see that commit, so a later ``wf.submit`` on it 404s. Ending the read
    transaction lets the next query start a fresh snapshot. The real app is
    unaffected — every HTTP request runs in its own session.
    """
    db.commit()


def _list_processes(client):
    return client.root_client.get(f"{_base(client)}/DemoExpense/processes")


# ---------------------------------------------------------------------------


def test_create_persists_row_and_typed_schema(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        wf = _setup(db)
        _create_record(wf, title="Lunch", amount=42.5, category="Food")

        client = Client()
        with override_get_user(client=client, user=wf.user("editor").user), disable_role_check(client):
            models = _list_models(client).json()
            rows = _list_rows(client).json()

        model = next(m for m in models if m["name"] == "DemoExpense")
        assert model["label"] == "Demo Expenses"
        by_name = {f["name"]: f for f in model["fields"]}
        assert by_name["amount"]["type"] == "decimal" and by_name["amount"]["format"] == "currency:EUR"
        assert by_name["created_at"]["type"] == "datetime"
        assert by_name["receipt"]["type"] == "file"

        assert rows["COUNT"] == 1
        item = rows["ITEMS"][0]
        # The stable id is a fresh surrogate (not the producing workflow instance).
        assert uuid.UUID(item["data"]["id"])  # parses as a uuid
        assert item["data"]["version"] == 1
        assert item["data"]["title"] == "Lunch"
        assert item["data"]["amount"] == 42.5
        assert item["data"]["status"] == "open"
        assert item["data"]["receipt"][0]["filename"] == "receipt.png"
        assert {a["key"] for a in item["actions"]} == {"edit"}


def test_labels_resolve_via_committed_catalog(db_engine_ctx):
    """A German user gets the labels from datamodels/i18n/.../DemoExpense.mo."""
    with db_engine_ctx():
        db = SessionLocal()
        wf = _setup(db)
        _create_record(wf)

        # Switch the viewer to German — the services load the user fresh by id.
        from actidoo_wfe.wf.models import WorkflowUser

        with SessionMaker() as s, s.begin():
            user_row = s.get(WorkflowUser, wf.user("viewer").user.id)
            user_row.locale = "de-DE"

        client = Client()
        with override_get_user(client=client, user=wf.user("viewer").user), disable_role_check(client):
            models = _list_models(client).json()
            rows = _list_rows(client).json()

        model = next(m for m in models if m["name"] == "DemoExpense")
        assert model["label"] == "Demo-Ausgaben"
        by_name = {f["name"]: f for f in rows["model"]["fields"]}
        assert by_name["title"]["label"] == "Titel"
        assert by_name["amount"]["label"] == "Betrag"


def test_description_detail_only_and_receipt_excluded_from_csv(db_engine_ctx):
    """Reference for per-context field visibility (FieldDef include_in_* flags):

    - ``description`` is verbose, so it is declared detail-only
      (``include_in_table=False``): absent from the table schema + row payload,
      present in full on the detail (version-chain) page.
    - ``receipt`` is a file field with no meaningful CSV cell, so it is excluded
      from the export (``include_in_csv=False``), while ``description`` (default on)
      is exported.
    """
    with db_engine_ctx():
        db = SessionLocal()
        wf = _setup(db)
        notes = "Client dinner with the whole team; itemised receipt attached."
        wf.user("editor").submit(
            task_data={"title": "Dinner", "amount": 80.0, "category": "Food",
                       "description": notes, "receipt": _RECEIPT},
            workflow_instance_id=wf.workflow_instance_id,
        )

        client = Client()
        with override_get_user(client=client, user=wf.user("editor").user), disable_role_check(client):
            rows = _list_rows(client).json()
            record_id = rows["ITEMS"][0]["data"]["id"]
            chain = _version_chain(client, record_id).json()
            csv_body = _export_csv(client).text

        # Table: the verbose field is gone from both the schema and the row payload.
        assert "description" not in {f["name"] for f in rows["model"]["fields"]}
        assert "description" not in rows["ITEMS"][0]["data"]
        # Detail page: the full description is present.
        assert "description" in {f["name"] for f in chain["model"]["fields"]}
        assert chain["versions"][0]["data"]["description"] == notes
        # CSV: no receipt column (include_in_csv=False), but description is exported.
        header = csv_body.splitlines()[0]
        assert "Receipt" not in header and "Beleg" not in header
        assert notes in csv_body


def test_read_permission(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        wf = _setup(db)
        _create_record(wf)

        client = Client()
        with override_get_user(client=client, user=wf.user("viewer").user), disable_role_check(client):
            viewer_rows = _list_rows(client)
        with override_get_user(client=client, user=wf.user("outsider").user), disable_role_check(client):
            outsider_rows = _list_rows(client)
            outsider_models = _list_models(client).json()

        assert viewer_rows.status_code == 200 and viewer_rows.json()["COUNT"] == 1
        assert outsider_rows.status_code == 403
        assert all(m["name"] != "DemoExpense" for m in outsider_models)


def test_receipt_attachment_downloads(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        wf = _setup(db)
        _create_record(wf)

        client = Client()
        with override_get_user(client=client, user=wf.user("editor").user), disable_role_check(client):
            row = _head_item(client)
            record_id, version = row["data"]["id"], row["data"]["version"]
            file_hash = row["data"]["receipt"][0]["hash"]
            resp = _download(client, record_id, version, file_hash)
            wrong = _download(client, record_id, version, "does-not-belong")

        assert resp.status_code == 200
        assert resp.content == _PNG_BYTES
        assert "receipt.png" in resp.headers.get("content-disposition", "")
        assert wrong.status_code == 404


def test_change_creates_new_version(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        wf = _setup(db)
        _create_record(wf, amount=42.5)

        client = Client()
        with override_get_user(client=client, user=wf.user("editor").user), disable_role_check(client):
            record_id = _head_item(client)["data"]["id"]
            start = _start_edit(client, record_id)
            change_id = start.json()["workflow_instance_id"]  # the new workflow instance

        _drop_read_snapshot(db)  # see the change instance the action endpoint just committed
        # Editor completes the (prefilled) change form with a new amount. The source
        # id is a server-set technical variable carried by the engine — not a form
        # field — so the submission carries only the user-editable fields.
        wf.user("editor").submit(
            task_data={"title": "Lunch", "amount": 99.0, "category": "Food"},
            workflow_instance_id=uuid.UUID(change_id),
        )

        with override_get_user(client=client, user=wf.user("editor").user), disable_role_check(client):
            rows = _list_rows(client).json()
            chain = _version_chain(client, record_id).json()

        assert start.status_code == 200
        # list_rows returns only the head (latest) version — same id, new version.
        assert rows["COUNT"] == 1
        head = rows["ITEMS"][0]["data"]
        assert head["id"] == record_id
        assert head["version"] == 2
        assert head["amount"] == 99.0
        # The version chain holds both versions of the one record, oldest first.
        assert [v["data"]["version"] for v in chain["versions"]] == [1, 2]
        assert {v["data"]["id"] for v in chain["versions"]} == {record_id}
        assert [v["data"]["amount"] for v in chain["versions"]] == [42.5, 99.0]
        # Per-version metadata: each version records what its workflow did.
        assert [v["action"] for v in chain["versions"]] == ["CREATE", "UPDATE"]
        # The chain carries the head's available follow-up actions (editor, open row).
        assert {a["key"] for a in chain["actions"]} == {"edit"}


def test_change_prefills_from_source_before_first_user_task(db_engine_ctx):
    """A service task before the first user task already sees the action's ``source_id``.

    The "edit" action seeds ``source_id`` (a server-set technical variable) into the
    engine task data *before* ``run_workflow``, so the ``PrefillFromSource`` service
    task — which runs before the first user task — can load the source row by
    ``source_id`` and prefill ``category``, a field the action payload does not carry.
    The edit form is therefore pre-populated with the record's current category.
    """
    with db_engine_ctx():
        db = SessionLocal()
        wf = _setup(db)
        _create_record(wf, title="Lunch", amount=42.5, category="Food")

        client = Client()
        with override_get_user(client=client, user=wf.user("editor").user), disable_role_check(client):
            record_id = _head_item(client)["data"]["id"]
            change_id = _start_edit(client, record_id).json()["workflow_instance_id"]

        _drop_read_snapshot(db)  # see the change instance the action endpoint just committed
        ready = wf.user("editor").get_usertasks(uuid.UUID(change_id), 1)
        data = ready[0].data
        # The early service task saw the technical source_id in task_data ...
        assert data["source_id"] == record_id
        # ... and used it to prefill `category` from the source row (the payload omits it).
        assert data["category"] == "Food"
        # The action payload's own prefill still applies to the first form unchanged.
        assert data["title"] == "Lunch"
        assert data["amount"] == 42.5


def test_change_ignores_injected_source_id(db_engine_ctx):
    """An injected ``source_id`` in the submission has no effect.

    The source id is a server-set technical variable, not a form field, so a client
    that smuggles it into the user-task submission has it stripped as an unknown
    field — the new version is appended to the real (server-seeded) record, never
    to the injected id.
    """
    with db_engine_ctx():
        db = SessionLocal()
        wf = _setup(db)
        _create_record(wf, amount=42.5)

        client = Client()
        with override_get_user(client=client, user=wf.user("editor").user), disable_role_check(client):
            record_id = _head_item(client)["data"]["id"]
            change_id = _start_edit(client, record_id).json()["workflow_instance_id"]

        _drop_read_snapshot(db)  # see the change instance the action endpoint just committed
        # Smuggle a foreign source id into the submission.
        injected = str(uuid.uuid4())
        wf.user("editor").submit(
            task_data={"title": "X", "amount": 1.0, "category": "Y", "source_id": injected},
            workflow_instance_id=uuid.UUID(change_id),
        )

        with SessionMaker() as s:
            real_versions = s.scalars(select(DemoExpense).where(DemoExpense.id == uuid.UUID(record_id))).all()
            injected_rows = s.scalars(select(DemoExpense).where(DemoExpense.id == uuid.UUID(injected))).all()
        # The new version was appended to the real record (v1 + v2), not the injected id.
        assert sorted(r.version for r in real_versions) == [1, 2]
        assert injected_rows == []


def test_modify_permission_viewer_forbidden(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        wf = _setup(db)
        _create_record(wf)

        client = Client()
        with override_get_user(client=client, user=wf.user("viewer").user), disable_role_check(client):
            rows = _list_rows(client).json()
            record_id = rows["ITEMS"][0]["data"]["id"]
            resp = _start_edit(client, record_id)

        # The "edit" action row_filter requires demo-editor → the viewer gets no
        # edit action on the row, and triggering it anyway is forbidden.
        assert rows["ITEMS"][0]["actions"] == []
        assert resp.status_code == 403


def test_list_models_row_count_and_hides_empty(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        wf = _setup(db)  # model registered + table created, but no rows yet

        client = Client()
        with override_get_user(client=client, user=wf.user("editor").user), disable_role_check(client):
            empty = _list_models(client).json()
        # No visible rows yet → the model is hidden from the overview.
        assert all(m["name"] != "DemoExpense" for m in empty)

        _create_record(wf, title="Lunch")

        with override_get_user(client=client, user=wf.user("editor").user), disable_role_check(client):
            models = _list_models(client).json()
        model = next(m for m in models if m["name"] == "DemoExpense")
        assert model["row_count"] == 1


def test_processes_filtered_by_execute_permission(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        wf = _setup(db)
        _create_record(wf)

        client = Client()
        with override_get_user(client=client, user=wf.user("editor").user), disable_role_check(client):
            editor = _list_processes(client)
        with override_get_user(client=client, user=wf.user("viewer").user), disable_role_check(client):
            viewer = _list_processes(client)
        with override_get_user(client=client, user=wf.user("outsider").user), disable_role_check(client):
            outsider = _list_processes(client)

        # Both demo workflows declare DemoExpense in DATA_MODELS; the editor may
        # start both (demo-editor initiator).
        assert editor.status_code == 200
        assert {p["name"] for p in editor.json()} == {
            "TestFlowDemoExpenseCreate",
            "TestFlowDemoExpenseChange",
        }
        # The viewer may read the model but may start neither workflow.
        assert viewer.status_code == 200 and viewer.json() == []
        # The outsider has no read access to the model at all.
        assert outsider.status_code == 403
