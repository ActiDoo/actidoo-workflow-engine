# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import copy
from pathlib import Path

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.bff.bff_user_schema import FormChangeResponse
from actidoo_wfe.wf.constants import ROW_ID_KEY
from actidoo_wfe.wf.exceptions import ChangeFunctionNotFound
from actidoo_wfe.wf.form_transformation import transform_camunda_form_from_file
from actidoo_wfe.wf.service_form import get_form_changes, validate_task_data
from actidoo_wfe.wf.testdata.processes.TestFlowDemoChangeFunction import update_contacts, update_gift, update_prices
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.overrides import disable_role_check, override_get_user
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

FUNCTIONS = {"update_prices": update_prices, "update_gift": update_gift, "update_contacts": update_contacts}


def _form():
    return copy.deepcopy(transform_camunda_form_from_file(Path(__file__).parents[1] / "EnterGifts.form"))


def _start_workflow():
    workflow = WorkflowDummy(
        db_session=SessionLocal(),
        users_with_roles={"initiator": ["wf-user"]},
        workflow_name="TestFlowDemoChangeFunction",
        start_user="initiator",
    )
    user = workflow.user("initiator")
    task = user.get_usertasks(workflow.workflow_instance_id, 1)[0]
    return workflow, user, task


def test_transformation_marks_fields_with_a_change_function():
    uischema = _form().uischema
    assert uischema["company"]["ui:changeFunction"] is True
    assert uischema["gifts"]["items"]["product"]["ui:changeFunction"] is True
    assert "ui:changeFunction" not in uischema["gifts"]["items"]["price"]


def test_change_in_a_row_changes_only_that_row():
    data = {"company": "subsidiary", "gifts": [{"product": "pen", "price": 2.2, "remark": "mine"}, {"product": "mug"}]}
    changes = get_form_changes(_form(), ["gifts", 1, "product"], data, FUNCTIONS)
    assert changes == [
        {"path": ["gifts", 1, "price"], "value": 11.0},
        {"path": ["gifts", 1, "remark"], "value": "dishwasher safe"},
    ]


def test_change_at_the_top_level_changes_all_rows():
    data = {"company": "subsidiary", "gifts": [{"product": "pen", "price": 2}, {"product": "mug", "price": 10}, {}]}
    changes = get_form_changes(_form(), ["company"], data, FUNCTIONS)
    assert changes == [
        {"path": ["gifts", 0, "price"], "value": 2.2},
        {"path": ["gifts", 1, "price"], "value": 11.0},
    ]


def test_change_at_the_top_level_changes_top_level_fields():
    changes = get_form_changes(_form(), ["sales_product"], {"sales_product": "wine"}, FUNCTIONS)
    assert changes == [
        {"path": ["product_manager"], "value": "Matias Soto"},
        {"path": ["ccc_group"], "value": "CCC Wine"},
    ]


@pytest.mark.parametrize("path", [["gifts", 0, "price"], ["gifts", 5, "product"], ["unknown"], []])
def test_fields_without_a_change_function_change_nothing(path):
    assert get_form_changes(_form(), path, {"gifts": [{"product": "pen"}]}, FUNCTIONS) == []


def test_missing_change_function_raises():
    with pytest.raises(ChangeFunctionNotFound):
        get_form_changes(_form(), ["company"], {"company": "parent"}, {})


def test_changed_rows_are_discarded():
    def add_row(cth):
        cth.form_data["gifts"].append({"product": "pen"})

    data = {"company": "parent", "gifts": [{"product": "pen", ROW_ID_KEY: "a"}]}
    assert get_form_changes(_form(), ["company"], data, {"update_prices": add_row}) == []


def test_submit_derives_disabled_values_and_keeps_editable_ones():
    form = _form()
    stored = {"gifts": [{ROW_ID_KEY: "a"}, {ROW_ID_KEY: "b"}]}
    submitted = {
        "company": "subsidiary",
        "gifts": [
            {ROW_ID_KEY: "a", "product": "pen", "price": 0.01, "remark": "mine"},
            {ROW_ID_KEY: "b", "product": "mug"},
        ],
    }
    result = validate_task_data(form, submitted, Path("."), FUNCTIONS, authoritative_disabled_values=stored)
    assert result.error_schema is None
    assert result.task_data["gifts"] == [
        {ROW_ID_KEY: "a", "product": "pen", "price": 2.2, "remark": "mine"},
        {ROW_ID_KEY: "b", "product": "mug", "price": 11.0},
    ]


def test_failing_change_function_fails_the_submit_unless_skipped():
    def fail(cth):
        raise RuntimeError("boom")

    functions = {**FUNCTIONS, "update_prices": fail}
    data = {"company": "parent", "gifts": [{ROW_ID_KEY: "a", "product": "pen"}]}
    with pytest.raises(RuntimeError):
        validate_task_data(_form(), copy.deepcopy(data), Path("."), functions, authoritative_disabled_values={})

    result = validate_task_data(
        _form(), copy.deepcopy(data), Path("."), functions, authoritative_disabled_values={}, skip_failing_change_functions=True
    )
    assert result.task_data["gifts"][0]["price"] == 2.0


def test__demo_workflow_stores_the_derived_values(db_engine_ctx, mock_send_text_mail):
    with db_engine_ctx():
        workflow, user, _task = _start_workflow()
        user.submit(
            task_data={
                "company": "subsidiary",
                "gifts": [{ROW_ID_KEY: "a", "product": "mug", "price": 1, "remark": "mine"}],
                "sales_product": "wine",
                "product_manager": "Somebody else",
            },
            workflow_instance_id=workflow.workflow_instance_id,
        )

        review = user.get_usertasks(workflow.workflow_instance_id, 1)[0]
        assert review.data["gifts"][0]["price"] == 11.0
        assert review.data["gifts"][0]["remark"] == "mine"
        assert review.data["product_manager"] == "Matias Soto"
        assert review.data["ccc_group"] == "CCC Wine"

        user.submit(task_data={}, workflow_instance_id=workflow.workflow_instance_id)
        workflow.assert_completed()


def test_form_change_endpoint(db_engine_ctx):
    with db_engine_ctx():
        _workflow, user, task = _start_workflow()

        client = Client()
        with override_get_user(client=client, user=user.user), disable_role_check(client):
            status, response = client.post(
                name="form_change",
                json={
                    "task_id": str(task.id),
                    "property_path": ["gifts", 0, "product"],
                    "form_data": {"company": "parent", "gifts": [{"product": "pen"}]},
                },
                cls=FormChangeResponse,
            )

        assert status == 200
        assert [(change.path, change.value) for change in response.changes] == [
            (["gifts", 0, "price"], 2.0),
            (["gifts", 0, "remark"], "blue ink"),
        ]
