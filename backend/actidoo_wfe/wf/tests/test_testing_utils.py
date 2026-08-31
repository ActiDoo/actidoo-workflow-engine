# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Row-id support for hand-written test payloads.

Since ADR 010 the engine rejects a dynamic list that arrives without the row
ids it was handed out with. Test suites, however, submit hand-written payload
literals - often the same literal across several steps. ``UserDummy.submit``
therefore adopts the stored ids by position, like a browser resubmitting the
loaded form, and ``strip_row_ids`` removes the technical key before comparing
task data against expectations. No concrete ids ever appear in test code.
"""

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.testing.utils import RowIdCarryError, _adopt_row_ids, strip_row_ids
from actidoo_wfe.wf.constants import ROW_ID_KEY
from actidoo_wfe.wf.exceptions import ValidationResultContainsErrors
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_RowIdentity"

STEP_1 = "Form010_Capture"
STEP_2 = "Form020_Review"
STEP_3 = "Form030_Confirm"


# --- adoption and stripping (unit) ----------------------------------------------


def test__ids_are_adopted_by_position_and_into_nested_lists():
    """An id-less payload adopts the stored ids row by row - also for lists
    nested inside rows - so it looks exactly like a browser submission of the
    loaded form."""
    stored = {"rows": [{ROW_ID_KEY: "a", "inner": [{ROW_ID_KEY: "i", "n": 1}]}, {ROW_ID_KEY: "b"}]}
    payload = {"rows": [{"x": 10, "inner": [{"n": 5}]}, {"x": 20}]}

    _adopt_row_ids(stored, payload)

    assert payload["rows"][0][ROW_ID_KEY] == "a"
    assert payload["rows"][0]["inner"][0][ROW_ID_KEY] == "i"
    assert payload["rows"][1] == {ROW_ID_KEY: "b", "x": 20}


def test__payload_that_already_carries_ids_is_left_alone_including_below():
    """A test that manages ids itself (e.g. to delete or reorder rows) stays in
    control - adoption touches neither those rows nor the lists inside them,
    because positions are not trustworthy under a reordered or shrunk list."""
    stored = {"rows": [{ROW_ID_KEY: "a"}, {ROW_ID_KEY: "b", "inner": [{ROW_ID_KEY: "i"}]}]}
    payload = {"rows": [{ROW_ID_KEY: "b", "x": 2, "inner": [{"n": 1}]}]}

    _adopt_row_ids(stored, payload)

    assert payload["rows"] == [{ROW_ID_KEY: "b", "x": 2, "inner": [{"n": 1}]}]


def test__grown_or_shrunk_lists_raise_with_guidance():
    """When the id-less payload has a different row count, positions cannot say
    which stored row is meant - adoption refuses and names the ways out."""
    stored = {"rows": [{ROW_ID_KEY: "a"}, {ROW_ID_KEY: "b"}]}

    with pytest.raises(RowIdCarryError) as excinfo:
        _adopt_row_ids(stored, {"rows": [{"x": 1}]})

    assert "rows" in str(excinfo.value)
    assert "carry_row_ids=False" in str(excinfo.value)


def test__an_empty_payload_list_is_a_legal_clear():
    """Submitting an empty list clears it - that must not trip the length
    check, and there is nothing to adopt."""
    stored = {"rows": [{ROW_ID_KEY: "a"}]}
    payload = {"rows": []}

    _adopt_row_ids(stored, payload)

    assert payload == {"rows": []}


def test__strip_removes_the_technical_key_everywhere():
    """Comparing task data against a hand-written expectation must not fail on
    the stamped ``_row_id`` keys - strip removes them at every depth."""
    data = {"rows": [{ROW_ID_KEY: "a", "x": 1, "inner": [{ROW_ID_KEY: "i", "y": 2}]}]}

    assert strip_row_ids(data) == {"rows": [{"x": 1, "inner": [{"y": 2}]}]}
    assert ROW_ID_KEY in data["rows"][0]  # the input stays untouched


# --- UserDummy.submit (integration) ---------------------------------------------


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


LITERAL = {
    "header_text": "t",
    "my_list": [
        {"text_a": "first", "number_a": 1},
        {"text_a": "second", "number_a": 2},
    ],
}


def test__resubmitting_the_same_id_less_literal_keeps_working(db_engine_ctx, mock_send_text_mail):
    """The customer-suite pattern: the same hand-written list literal is
    submitted in consecutive steps. The dummy adopts the stamped ids by
    position, so the second submission passes and every row keeps exactly one
    identity."""
    with db_engine_ctx():
        workflow = _start_workflow()

        workflow.user("initiator").submit(
            task_data=LITERAL, workflow_instance_id=workflow.workflow_instance_id, task_name=STEP_1
        )
        handed_out = [row[ROW_ID_KEY] for row in _ready_task(workflow, STEP_2).data["my_list"]]

        workflow.user("initiator").submit(
            task_data=LITERAL, workflow_instance_id=workflow.workflow_instance_id, task_name=STEP_2
        )

        rows = _ready_task(workflow, STEP_3).data["my_list"]
        assert [row[ROW_ID_KEY] for row in rows] == handed_out
        assert [row["text_a"] for row in rows] == ["first", "second"]


def test__opting_out_sends_the_payload_untouched(db_engine_ctx, mock_send_text_mail):
    """``carry_row_ids=False`` bypasses the adoption, so the engine-side
    rejection of id-less lists stays testable."""
    with db_engine_ctx():
        workflow = _start_workflow()
        workflow.user("initiator").submit(
            task_data=LITERAL, workflow_instance_id=workflow.workflow_instance_id, task_name=STEP_1
        )

        with pytest.raises(ValidationResultContainsErrors):
            workflow.user("initiator").submit(
                task_data=LITERAL,
                workflow_instance_id=workflow.workflow_instance_id,
                task_name=STEP_2,
                carry_row_ids=False,
            )
