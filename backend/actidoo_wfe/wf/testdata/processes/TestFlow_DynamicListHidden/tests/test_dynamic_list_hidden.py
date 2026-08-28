# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""A required field inside a hidden nested dynamic list must not block the
submission - only a visible one may."""

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.exceptions import ValidationResultContainsErrors
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlow_DynamicListHidden"


def _start_workflow():
    return WorkflowDummy(
        db_session=SessionLocal(),
        users_with_roles={"initiator": ["wf-user"]},
        workflow_name=WF_NAME,
        start_user="initiator",
    )


def _submit(workflow, task_data):
    workflow.user("initiator").submit(
        task_data=task_data,
        workflow_instance_id=workflow.workflow_instance_id,
    )


def test_hidden_inner_list_without_rows_does_not_block_submission(db_engine_ctx, mock_send_text_mail):
    """``yes`` hides the inner list. Submitted empty, its required field must not
    be validated."""
    with db_engine_ctx():
        workflow = _start_workflow()

        _submit(
            workflow,
            {
                "create_set": "yes",
                "outer_list": [{"outer_text": "some value", "inner_list": []}],
                "other_list": [{"other_text": "some value"}],
            },
        )

        workflow.assert_completed()


def test_hidden_inner_list_with_default_row_does_not_block_submission(db_engine_ctx, mock_send_text_mail):
    """The inner list starts with one default row, so a form submitted with
    ``yes`` carries an empty required field inside the hidden list - exactly
    what an untouched form produces. That must not be validated either."""
    with db_engine_ctx():
        workflow = _start_workflow()

        _submit(
            workflow,
            {
                "create_set": "yes",
                "outer_list": [{"outer_text": "some value", "inner_list": [{}]}],
                "other_list": [{"other_text": "some value"}],
            },
        )

        workflow.assert_completed()


def test_visible_inner_list_requires_its_field(db_engine_ctx, mock_send_text_mail):
    """``no`` shows the inner list; its required field left empty is rejected."""
    with db_engine_ctx():
        workflow = _start_workflow()

        with pytest.raises(ValidationResultContainsErrors):
            _submit(
                workflow,
                {
                    "create_set": "no",
                    "outer_list": [{"outer_text": "some value", "inner_list": [{}]}],
                    "other_list": [],
                },
            )

        workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)


def test_visible_inner_list_with_filled_field_completes(db_engine_ctx, mock_send_text_mail):
    """Control case: ``no`` with the required field filled passes."""
    with db_engine_ctx():
        workflow = _start_workflow()

        _submit(
            workflow,
            {
                "create_set": "no",
                "outer_list": [{"outer_text": "some value", "inner_list": [{"inner_required": "filled"}]}],
                "other_list": [],
            },
        )

        workflow.assert_completed()
