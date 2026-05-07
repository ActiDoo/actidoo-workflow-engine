import logging

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf import repository, service_application
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "FeelWorkflow"
WF_NAME_OLD_STYLE = "FeelWorkflowThisOnly"

log = logging.getLogger(__name__)

FORM_DATA = {}


def _start_workflow(workflow_name=WF_NAME):
    db_session = SessionLocal()

    workflow = WorkflowDummy(
        db_session=db_session,
        users_with_roles={  # keycloak-realm dummy
            "initiator": ["wf-user"],
        },
        workflow_name=workflow_name,
        start_user="initiator",
    )

    return workflow


def _clean_task_data(workflow, task_data):
    """Helper: validate+clean task_data via the public API."""
    stored_workflow = repository.load_workflow_instance(
        db=workflow.db,
        workflow_id=workflow.workflow_instance_id,
    )
    usertasks = workflow.user("initiator").get_usertasks(
        workflow.workflow_instance_id,
        1,
    )
    task = usertasks[0]
    return service_application._clean_submitted_task_data(
        workflow=stored_workflow,
        task=task,
        submitted_data=task_data,
    )


def test_feel_start(db_engine_ctx, mock_send_text_mail):
    """for 'db_engine_ctx' see conftest.py"""
    with db_engine_ctx():
        workflow = _start_workflow()

        workflow.user("initiator").submit(
            task_data=FORM_DATA,
            workflow_instance_id=workflow.workflow_instance_id,
        )


def test_hideif_parent_hidden_keeps_number_c_in_nested_list(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow = _start_workflow()
        task_data = {
            "globalA": 3,
            "globalB": 4,
            "my_list": [
                {
                    "number_a": 7,
                    "number_b": 1,
                    "my_list_B": [
                        {
                            "number_c": 32,
                            "number_d": 2,
                        },
                    ],
                },
            ],
        }

        cleaned_task_data = _clean_task_data(workflow, task_data)
        stored_list = cleaned_task_data["my_list"][0]
        assert "number_a" not in stored_list
        assert stored_list["my_list_B"][0]["number_c"] == 32

        workflow.user("initiator").submit(
            task_data=task_data,
            workflow_instance_id=workflow.workflow_instance_id,
        )


def test_hideif_globalA4_hides_number_c_keeps_number_a(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow = _start_workflow()
        task_data = {
            "globalA": 4,
            "globalB": 4,
            "my_list": [
                {
                    "number_a": 7,
                    "number_b": 1,
                    "my_list_B": [
                        {
                            "number_d": 2,
                        },
                    ],
                },
            ],
        }

        cleaned_task_data = _clean_task_data(workflow, task_data)
        stored_list = cleaned_task_data["my_list"][0]
        assert stored_list["number_a"] == 7
        assert "number_c" not in stored_list["my_list_B"][0]

        workflow.user("initiator").submit(
            task_data=task_data,
            workflow_instance_id=workflow.workflow_instance_id,
        )


# ==================== BACKWARDS COMPATIBILITY TESTS ====================
# Tests for old-style hide-if conditions (without explicit parent/this keywords)
# These tests ensure that forms using scope shadowing still work with new implementation


@pytest.mark.parametrize(
    "test_case",
    [
        {
            "name": "globalB hidden by root-level condition",
            "globalA": 1,
            "list_item": None,
            "expected_global_hidden": ["globalB"],
            "expected_list_hidden": [],
            "description": "hide='=globalA=1' (no parent prefix)",
        },
        {
            "name": "number_a hidden by parent scope reference in list",
            "globalA": 3,
            "list_item": {"number_a": 7, "number_b": 16},
            "expected_global_hidden": [],
            "expected_list_hidden": ["number_a"],
            "description": "hide='=globalA=3' (parent scope, no parent prefix)",
        },
        {
            "name": "number_b hidden by sibling field",
            "globalA": 2,
            "list_item": {"number_a": 9, "number_b": 16},
            "expected_global_hidden": [],
            "expected_list_hidden": ["number_b"],
            "description": "hide='=number_a=9' (sibling ref, no this. prefix)",
        },
        {
            "name": "all fields visible when conditions don't match",
            "globalA": 2,
            "list_item": {"number_a": 7, "number_b": 16},
            "expected_global_hidden": [],
            "expected_list_hidden": [],
            "description": "Positive case: no hide conditions met",
        },
    ],
)
def test_hideif_backwards_compat_scenarios(db_engine_ctx, mock_send_text_mail, test_case):
    """Test old-style hide-if conditions without explicit parent/this keywords"""
    with db_engine_ctx():
        workflow = _start_workflow(WF_NAME_OLD_STYLE)
        task_data = {
            "globalA": test_case["globalA"],
            "globalB": 4,
            "mylist": [test_case["list_item"]] if test_case["list_item"] else [],
        }

        cleaned_task_data = _clean_task_data(workflow, task_data)

        # Check global field visibility
        for field in test_case["expected_global_hidden"]:
            assert field not in cleaned_task_data, f"{field} should be hidden: {test_case['description']}"

        # Check list field visibility
        if test_case["list_item"]:
            stored_list = cleaned_task_data["mylist"][0]
            for field in test_case["expected_list_hidden"]:
                assert field not in stored_list, f"{field} should be hidden in list: {test_case['description']}"

        workflow.user("initiator").submit(task_data=task_data, workflow_instance_id=workflow.workflow_instance_id)


def test_hideif_backwards_compat_hidden_field_values_filtered(db_engine_ctx, mock_send_text_mail):
    """Test that values provided for hidden fields are removed from data.

    Hidden fields should not be in output even if user provides values.
    """
    with db_engine_ctx():
        workflow = _start_workflow(WF_NAME_OLD_STYLE)
        task_data = {
            "globalA": 1,
            "globalB": 99,  # User tries to provide value for hidden field
            "mylist": [],
        }

        cleaned_task_data = _clean_task_data(workflow, task_data)

        assert "globalB" not in cleaned_task_data, "Hidden field should be removed even with user value"
        workflow.user("initiator").submit(task_data=task_data, workflow_instance_id=workflow.workflow_instance_id)
