# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import copy
from pathlib import Path

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.form_transformation import transform_camunda_form_from_file
from actidoo_wfe.wf.service_form import get_options, validate_task_data
from actidoo_wfe.wf.testdata.processes.TestFlow_DependsOn import get_car_sub_type_options
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy


def test_list_options_follow_the_rows_car_type(db_engine_ctx):
    with db_engine_ctx():
        workflow = WorkflowDummy(
            db_session=SessionLocal(),
            users_with_roles={"initiator": ["wf-user"]},
            workflow_name="TestFlow_DependsOn",
            start_user="initiator",
        )
        user = workflow.user("initiator")
        task = user.get_usertasks(workflow.workflow_instance_id, 1)[0]

        options = user.search_options(
            property_path=["vehicles", 0, "car_sub_type"],
            search="",
            task_id=task.id,
            form_data={"car_type": "car", "vehicles": [{"car_type": "truck"}]},
        )

        assert {value for value, _label in options} == {"pickup", "semi", "dump"}


@pytest.mark.parametrize("row", [{}, {"car_type": None}])
def test_empty_row_dependency_shadows_global_value_for_search_and_validation(row):
    form = copy.deepcopy(transform_camunda_form_from_file(Path(__file__).parents[1] / "Form010_Fill.form"))
    data = {"car_type": "car", "vehicles": [dict(row)]}
    functions = {"get_car_sub_type_options": get_car_sub_type_options}
    options = get_options(form.jsonschema, ["vehicles", 0, "car_sub_type"], Path("."), data, functions)
    assert options == []

    data["vehicles"][0]["car_sub_type"] = "sedan"
    result = validate_task_data(form, data, Path("."), functions, log_validation_errors=False)
    assert result.error_schema["vehicles"][0]["car_sub_type"]["__errors"]


def test_global_dependency_is_used_when_the_row_does_not_define_it():
    form = copy.deepcopy(transform_camunda_form_from_file(Path(__file__).parents[1] / "Form010_Fill.form"))
    del form.jsonschema["properties"]["vehicles"]["items"]["properties"]["car_type"]
    options = get_options(
        form.jsonschema, ["vehicles", 0, "car_sub_type"], Path("."),
        {"car_type": "truck", "vehicles": [{}]},
        {"get_car_sub_type_options": get_car_sub_type_options},
    )
    assert {value for value, _ in options} == {"pickup", "semi", "dump"}


def test_nested_row_shadows_its_parent_even_before_its_dependency_is_filled():
    form = copy.deepcopy(transform_camunda_form_from_file(Path(__file__).parents[1] / "Form010_Fill.form"))
    vehicles = form.jsonschema["properties"].pop("vehicles")
    form.jsonschema["properties"]["groups"] = {
        "type": "array", "items": {"type": "object", "properties": {
            "car_type": {"type": ["string", "null"]}, "vehicles": vehicles,
        }},
    }
    options = get_options(
        form.jsonschema, ["groups", 0, "vehicles", 0, "car_sub_type"], Path("."),
        {"car_type": "car", "groups": [{"car_type": "truck", "vehicles": [{}]}]},
        {"get_car_sub_type_options": get_car_sub_type_options},
    )
    assert options == []
