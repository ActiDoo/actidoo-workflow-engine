# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""End-to-end row identity across several user tasks sharing one dynamic list
(ADR 010).

The three steps of this process are what makes these scenarios expressible at
all: values are captured in step 1, edited in step 2 (where ``backend_value``
is disabled and ``hidden_note`` may be hidden per item), and read back in
step 3. Every assertion below therefore runs through the real engine path -
two submissions with a merge in between - instead of a hand-built stored state.
"""

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import repository, service_application, service_workflow
from actidoo_wfe.wf.constants import ROW_ID_KEY
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_RowIdentity"

STEP_1 = "Form010_Capture"
STEP_2 = "Form020_Review"
STEP_3 = "Form030_Confirm"


def _start_workflow():
    return WorkflowDummy(
        db_session=SessionLocal(),
        users_with_roles={"initiator": ["wf-user"]},
        workflow_name=WF_NAME,
        start_user="initiator",
    )


def _ready_task(workflow, name):
    tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id)
    matching = [t for t in tasks if t.name == name]
    assert len(matching) == 1, f"expected exactly one ready task {name!r}, got {[t.name for t in tasks]}"
    return matching[0]


def _rows_by_id(rows):
    return {row[ROW_ID_KEY]: row for row in rows}


def _capture_three_rows(workflow):
    """Step 1: three rows, each with its own hidden_note and backend_value."""
    workflow.user("initiator").submit(
        task_data={
            "header_text": "outer",
            "my_list": [
                {ROW_ID_KEY: "row-1", "text_a": "first", "number_a": 1, "backend_value": "value_2", "hidden_note": "note-1"},
                {ROW_ID_KEY: "row-2", "text_a": "second", "number_a": 2, "backend_value": "value_3", "hidden_note": "note-2"},
                {ROW_ID_KEY: "row-3", "text_a": "third", "number_a": 3, "backend_value": "value_2", "hidden_note": "note-3"},
            ],
        },
        workflow_instance_id=workflow.workflow_instance_id,
        task_name=STEP_1,
    )


def test_deleting_a_middle_row_keeps_hidden_values_on_their_own_rows(db_engine_ctx, mock_send_text_mail):
    """Deleting a row must not shift another row's restored values onto its
    neighbour. Setting number_a to 9 hides hidden_note, so it is stripped from
    the submission and restored from stored data - matched by row ID, never by
    index."""
    with db_engine_ctx():
        workflow = _start_workflow()
        _capture_three_rows(workflow)

        # Step 2: delete the middle row and hide the notes of the remaining ones.
        workflow.user("initiator").submit(
            task_data={
                "header_text": "outer",
                "my_list": [
                    {ROW_ID_KEY: "row-1", "text_a": "first", "number_a": 9},
                    {ROW_ID_KEY: "row-3", "text_a": "third", "number_a": 9},
                ],
            },
            workflow_instance_id=workflow.workflow_instance_id,
            task_name=STEP_2,
        )

        rows = _rows_by_id(_ready_task(workflow, STEP_3).data["my_list"])
        assert set(rows) == {"row-1", "row-3"}
        # Index alignment would have restored row-2's note onto row-3.
        assert rows["row-1"]["hidden_note"] == "note-1"
        assert rows["row-3"]["hidden_note"] == "note-3"
        assert rows["row-3"]["backend_value"] == "value_2"


def test_reordering_rows_keeps_every_row_with_its_own_values(db_engine_ctx, mock_send_text_mail):
    """Row identity makes reordering legal: the result order follows the
    submission while each row keeps the values restored for itself."""
    with db_engine_ctx():
        workflow = _start_workflow()
        _capture_three_rows(workflow)

        workflow.user("initiator").submit(
            task_data={
                "header_text": "outer",
                "my_list": [
                    {ROW_ID_KEY: "row-3", "text_a": "third", "number_a": 9},
                    {ROW_ID_KEY: "row-1", "text_a": "first", "number_a": 9},
                    {ROW_ID_KEY: "row-2", "text_a": "second", "number_a": 9},
                ],
            },
            workflow_instance_id=workflow.workflow_instance_id,
            task_name=STEP_2,
        )

        result = _ready_task(workflow, STEP_3).data["my_list"]
        assert [row[ROW_ID_KEY] for row in result] == ["row-3", "row-1", "row-2"]
        assert [row["hidden_note"] for row in result] == ["note-3", "note-1", "note-2"]


def test_row_added_in_a_later_step_gets_the_declared_default(db_engine_ctx, mock_send_text_mail):
    """A row added where ``backend_value`` is disabled has no stored value for
    it. The default declared in that form is the forced assignment and must be
    persisted - otherwise the new row would silently stay incomplete."""
    with db_engine_ctx():
        workflow = _start_workflow()
        _capture_three_rows(workflow)

        workflow.user("initiator").submit(
            task_data={
                "header_text": "outer",
                "my_list": [
                    {ROW_ID_KEY: "row-1", "text_a": "first", "number_a": 1, "hidden_note": "note-1"},
                    {ROW_ID_KEY: "row-new", "text_a": "added later", "number_a": 4, "hidden_note": "note-new"},
                ],
            },
            workflow_instance_id=workflow.workflow_instance_id,
            task_name=STEP_2,
        )

        rows = _rows_by_id(_ready_task(workflow, STEP_3).data["my_list"])
        # Existing row keeps its captured value ...
        assert rows["row-1"]["backend_value"] == "value_2"
        # ... the added row is filled with the declared default.
        assert rows["row-new"]["backend_value"] == "value_1"
        assert rows["row-new"]["hidden_note"] == "note-new"


def test_rows_submitted_without_ids_are_stamped_and_schemas_stay_clean(db_engine_ctx, mock_send_text_mail):
    """Lazy migration: a client that sends no row IDs still gets identities -
    stamped by the engine when it advances. The persisted form schemas never
    contain the technical field."""
    with db_engine_ctx():
        workflow = _start_workflow()

        workflow.user("initiator").submit(
            task_data={
                "header_text": "outer",
                "my_list": [
                    {"text_a": "first", "number_a": 1, "backend_value": "value_2", "hidden_note": "note-1"},
                    {"text_a": "second", "number_a": 2, "backend_value": "value_3", "hidden_note": "note-2"},
                ],
            },
            workflow_instance_id=workflow.workflow_instance_id,
            task_name=STEP_1,
        )

        task = _ready_task(workflow, STEP_2)
        row_ids = [row.get(ROW_ID_KEY) for row in task.data["my_list"]]
        assert all(isinstance(row_id, str) and row_id for row_id in row_ids)
        assert len(set(row_ids)) == 2

        # The delivered schema stays free of the technical field.
        assert ROW_ID_KEY not in task.jsonschema["properties"]["my_list"]["items"]["properties"]
        assert ROW_ID_KEY not in task.uischema["my_list"]["items"]


def _strip_stored_row_ids(workflow):
    """Turn the instance into what it looked like before row identity existed."""
    stored_workflow = repository.load_workflow_instance(
        db=workflow.db,
        workflow_id=workflow.workflow_instance_id,
    )
    for task in service_workflow.get_ready_and_waiting_usertasks(workflow=stored_workflow):
        for row in task.data.get("my_list", []):
            row.pop(ROW_ID_KEY, None)
    repository.store_workflow_instance(db=workflow.db, workflow=stored_workflow)
    workflow.db.commit()


def test_handing_out_a_task_stamps_and_persists_row_ids(db_engine_ctx, mock_send_text_mail):
    """Rows an instance carries from before row identity existed get their ids
    when the task is handed out - and keep them, so the next request and the
    frontend see the same identities."""
    with db_engine_ctx():
        workflow = _start_workflow()
        _capture_three_rows(workflow)
        _strip_stored_row_ids(workflow)

        delivered = [row[ROW_ID_KEY] for row in _ready_task(workflow, STEP_2).data["my_list"]]
        assert len(set(delivered)) == 3

        reloaded = repository.load_workflow_instance(db=workflow.db, workflow_id=workflow.workflow_instance_id)
        stored_task = next(t for t in service_workflow.get_ready_and_waiting_usertasks(workflow=reloaded) if t.task_spec.name == STEP_2)
        assert [row[ROW_ID_KEY] for row in stored_task.data["my_list"]] == delivered


def test_handing_out_a_stamped_task_again_writes_nothing(db_engine_ctx, mock_send_text_mail, monkeypatch):
    """Stamping writes, so it must happen once and then never again - a read
    path that keeps writing would compete with concurrent submissions."""
    with db_engine_ctx():
        workflow = _start_workflow()
        _capture_three_rows(workflow)
        _strip_stored_row_ids(workflow)

        _ready_task(workflow, STEP_2)  # stamps

        calls = []
        original = repository.store_workflow_instance
        monkeypatch.setattr(repository, "store_workflow_instance", lambda **kwargs: calls.append(kwargs) or original(**kwargs))

        _ready_task(workflow, STEP_2)

        assert calls == []


def test_handing_out_a_task_notifies_nobody(db_engine_ctx, mock_send_text_mail, monkeypatch):
    """Storing an instance is what fires the assignment mails. The stamping
    write must not look like a task becoming ready."""
    with db_engine_ctx():
        workflow = _start_workflow()
        _capture_three_rows(workflow)
        _strip_stored_row_ids(workflow)

        published = []
        monkeypatch.setattr(repository.events, "publish_event", lambda event: published.append(event))

        _ready_task(workflow, STEP_2)

        assert published == []


def test_admin_replace_stamps_replaced_rows(db_engine_ctx, mock_send_text_mail):
    """Admin replace writes task data wholesale, bypassing submission validation.
    Its rows must come out stamped like any other write - otherwise the replaced
    task would be the one path left that hands out rows without identity."""
    with db_engine_ctx():
        workflow = WorkflowDummy(
            db_session=SessionLocal(),
            users_with_roles={"initiator": ["wf-user"], "admin": ["wf-user", "wf-admin"]},
            workflow_name=WF_NAME,
            start_user="initiator",
        )
        _capture_three_rows(workflow)
        task = _ready_task(workflow, STEP_2)

        service_application.admin_replace_task_data(
            db=workflow.db,
            user_id=workflow.user("admin").user.id,
            task_id=task.id,
            task_data={"header_text": "replaced", "my_list": [{"text_a": "first"}, {"text_a": "second"}]},
        )
        workflow.db.commit()

        reloaded = repository.load_workflow_instance(db=workflow.db, workflow_id=workflow.workflow_instance_id)
        stored_task = next(t for t in service_workflow.get_ready_and_waiting_usertasks(workflow=reloaded) if t.task_spec.name == STEP_2)
        row_ids = [row.get(ROW_ID_KEY) for row in stored_task.data["my_list"]]
        assert all(isinstance(row_id, str) and row_id for row_id in row_ids)
        assert len(set(row_ids)) == 2


def test_deleting_a_middle_row_of_a_legacy_instance_keeps_values_in_place(db_engine_ctx, mock_send_text_mail):
    """The regression this is all about: rows without identity, the user deletes
    the middle one. Because the task was stamped when it was handed out, both
    sides share the same ids and every remaining row keeps its own values."""
    with db_engine_ctx():
        workflow = _start_workflow()
        _capture_three_rows(workflow)
        _strip_stored_row_ids(workflow)

        rows = _ready_task(workflow, STEP_2).data["my_list"]
        first, _middle, third = (row[ROW_ID_KEY] for row in rows)

        workflow.user("initiator").submit(
            task_data={
                "header_text": "outer",
                "my_list": [
                    {ROW_ID_KEY: first, "text_a": "first", "number_a": 9},
                    {ROW_ID_KEY: third, "text_a": "third", "number_a": 9},
                ],
            },
            workflow_instance_id=workflow.workflow_instance_id,
            task_name=STEP_2,
        )

        result = _rows_by_id(_ready_task(workflow, STEP_3).data["my_list"])
        assert set(result) == {first, third}
        # Index alignment would have restored the deleted row's note onto the third.
        assert result[first]["hidden_note"] == "note-1"
        assert result[third]["hidden_note"] == "note-3"
