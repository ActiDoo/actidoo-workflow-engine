# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""What a field holds stays while a later step hides it.

The three steps share the optional text field ``text_a`` and the optional multi select
``tags_a``, both with a default. Step 1 shows them, step 2 hides them while ``flag_a``
is true, step 3 shows them again. Whatever step 1 stores - a value, or the null and the
empty list of fields the user emptied - survives step 2, its hand-out and its submit,
so step 3 receives it. The browser fills in a default only for a missing key, not for
null or an empty list.
"""

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_HiddenInBetween"

STEP_1 = "Form010_Clear"
STEP_2 = "Form020_Hide"
STEP_3 = "Form030_Show"


def _start_workflow():
    return WorkflowDummy(
        db_session=SessionLocal(),
        users_with_roles={"initiator": ["wf-user"]},
        workflow_name=WF_NAME,
        start_user="initiator",
    )


def _submit(workflow, task_name, task_data):
    workflow.user("initiator").submit(
        task_data=task_data,
        workflow_instance_id=workflow.workflow_instance_id,
        task_name=task_name,
    )


def _ready_task(workflow):
    return workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0]


def test_a_cleared_field_stays_cleared_while_a_later_step_hides_it(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow = _start_workflow()
        _submit(workflow, STEP_1, {"text_a": None, "tags_a": [], "flag_a": True})

        hidden = _ready_task(workflow)
        assert hidden.name == STEP_2
        assert "text_a" in hidden.data and hidden.data["text_a"] is None
        assert hidden.data["tags_a"] == []

        # The browser sends the hidden fields' empty values along; the submit writes nothing into them.
        _submit(workflow, STEP_2, {"flag_a": True, "text_a": None, "tags_a": []})

        shown = _ready_task(workflow)
        assert shown.name == STEP_3
        assert "text_a" in shown.data and shown.data["text_a"] is None
        assert shown.data["tags_a"] == []


def test_a_value_of_a_hidden_field_stays_while_a_later_step_hides_it(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow = _start_workflow()
        _submit(workflow, STEP_1, {"text_a": "typed", "tags_a": ["b"], "flag_a": True})

        hidden = _ready_task(workflow)
        assert hidden.name == STEP_2
        assert hidden.data["text_a"] == "typed"
        assert hidden.data["tags_a"] == ["b"]

        # Whatever the browser sends for the hidden fields is ignored.
        _submit(workflow, STEP_2, {"flag_a": True, "text_a": "changed", "tags_a": ["a"]})

        shown = _ready_task(workflow)
        assert shown.name == STEP_3
        assert shown.data["text_a"] == "typed"
        assert shown.data["tags_a"] == ["b"]


def test_a_field_the_user_shows_again_takes_the_submitted_value(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow = _start_workflow()
        _submit(workflow, STEP_1, {"text_a": "typed", "tags_a": ["b"], "flag_a": True})

        # The user unticks the flag in step 2: the fields are visible when the form is sent.
        _submit(workflow, STEP_2, {"flag_a": False, "text_a": "changed", "tags_a": ["a"]})

        shown = _ready_task(workflow)
        assert shown.data["text_a"] == "changed"
        assert shown.data["tags_a"] == ["a"]
