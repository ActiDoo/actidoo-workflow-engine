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
from actidoo_wfe.wf import repository, service_workflow
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


def test_rollout_window_fresh_ids_over_id_less_stored_rows(db_engine_ctx, mock_send_text_mail):
    """Rollout window: rows stored before the feature existed carry no IDs,
    while the updated frontend stamps fresh ones at load. Matching must fall
    back to index alignment - treating every row as new would drop the values
    the merge is supposed to restore."""
    with db_engine_ctx():
        workflow = _start_workflow()
        _capture_three_rows(workflow)

        # Simulate data written before the rollout: strip the stored identities.
        stored_workflow = repository.load_workflow_instance(
            db=workflow.db,
            workflow_id=workflow.workflow_instance_id,
        )
        for task in service_workflow.get_ready_and_waiting_usertasks(workflow=stored_workflow):
            for row in task.data.get("my_list", []):
                row.pop(ROW_ID_KEY, None)
        repository.store_workflow_instance(db=workflow.db, workflow=stored_workflow)
        workflow.db.commit()

        # Updated frontend: same rows in the same order, freshly stamped IDs,
        # notes hidden because number_a is 9.
        workflow.user("initiator").submit(
            task_data={
                "header_text": "outer",
                "my_list": [
                    {ROW_ID_KEY: "fresh-1", "text_a": "first", "number_a": 9},
                    {ROW_ID_KEY: "fresh-2", "text_a": "second", "number_a": 9},
                    {ROW_ID_KEY: "fresh-3", "text_a": "third", "number_a": 9},
                ],
            },
            workflow_instance_id=workflow.workflow_instance_id,
            task_name=STEP_2,
        )

        result = _ready_task(workflow, STEP_3).data["my_list"]
        assert [row["hidden_note"] for row in result] == ["note-1", "note-2", "note-3"]
        assert [row["backend_value"] for row in result] == ["value_2", "value_3", "value_2"]
