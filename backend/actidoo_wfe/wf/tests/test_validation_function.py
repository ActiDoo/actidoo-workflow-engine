# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from pathlib import Path

from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import validate_task_data

OPTIONS_FOLDER = Path(__file__).parent / "options"

GIFT_FORM = {
    "components": [
        {
            "type": "dynamiclist",
            "path": "gifts",
            "isRepeating": True,
            "components": [
                {"type": "textfield", "key": "choice"},
                {
                    "type": "textfield",
                    "key": "sap_number",
                    "conditional": {"hide": '=this.choice != "other"'},
                    "properties": {"validation_function": "check_sap_number"},
                },
            ],
        },
    ],
}


def _validate(task_data: dict, check_sap_number):
    return validate_task_data(
        form=transform_camunda_form(GIFT_FORM),
        task_data=task_data,
        options_folder=OPTIONS_FOLDER,
        functions_env={"check_sap_number": check_sap_number},
    )


def test__validation_function_gets_key_value_and_path_of_the_row():
    calls = []

    def check_sap_number(vth):
        calls.append((vth.key, vth.value, vth.path, vth.property_path))

    _validate({"gifts": [{"choice": "other", "sap_number": "1"}, {"choice": "other", "sap_number": "2"}]}, check_sap_number)

    assert ("sap_number", "1", ["gifts", 0, "sap_number"], ["gifts"]) in calls
    assert ("sap_number", "2", ["gifts", 1, "sap_number"], ["gifts"]) in calls


def test__error_marks_only_the_invalid_row():
    def check_sap_number(vth):
        if len(vth.value) != 8:
            vth.raise_error("8 digits")

    result = _validate(
        {"gifts": [{"choice": "other", "sap_number": "12345678"}, {"choice": "other", "sap_number": "123"}]},
        check_sap_number,
    )

    assert result.error_schema == {"gifts": [{}, {"sap_number": {"__errors": ["8 digits"]}}]}


def test__value_of_a_hidden_field_is_neither_validated_nor_seen_in_form_data():
    def check_sap_number(vth):
        for gift in vth.form_data["gifts"]:
            if "sap_number" in gift and len(gift["sap_number"]) != 8:
                vth.raise_error("8 digits")

    result = _validate(
        {"gifts": [{"choice": "other", "sap_number": "12345678"}, {"choice": "catalog", "sap_number": "123"}]},
        check_sap_number,
    )

    assert not result.error_schema
