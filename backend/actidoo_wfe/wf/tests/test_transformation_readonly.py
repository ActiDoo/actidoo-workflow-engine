# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH
"""readonly and disabled mean the same to the engine: the user cannot change the value,
so the server owns it - it is not required of the user, and a submission cannot
change or clear it. A list can carry both flags too."""

from pathlib import Path

from actidoo_wfe.wf.constants import ROW_ID_KEY
from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import validate_task_data

OPTIONS_FOLDER = Path(__file__).parent / "options"

FORM = {
    "components": [
        {"type": "textfield", "key": "owned", "readonly": True, "validate": {"required": True}},
        {"type": "textfield", "key": "note"},
        {
            "type": "dynamiclist",
            "path": "rows",
            "disabled": True,
            "components": [{"type": "textfield", "key": "label"}],
        },
        {
            "type": "dynamiclist",
            "path": "needed",
            "validate": {"required": True},
            "components": [{"type": "textfield", "key": "label"}],
        },
    ],
}


def test__readonly_is_disabled_and_not_required_of_the_user():
    form = transform_camunda_form(FORM)

    assert form.uischema["owned"]["ui:disabled"] is True
    assert "owned" not in form.jsonschema.get("required", [])


def test__a_disabled_list_is_disabled_as_a_whole():
    form = transform_camunda_form(FORM)

    assert form.uischema["rows"]["ui:disabled"] is True


def test__a_required_list_needs_at_least_one_row():
    form = transform_camunda_form(FORM)

    assert form.jsonschema["properties"]["needed"]["minItems"] == 1


def test__submissions_do_not_change_readonly_values():
    form = transform_camunda_form(FORM)
    stored = {"owned": "server", "note": "n"}

    result = validate_task_data(
        form=form,
        task_data={"owned": "tampered", "note": "n", "needed": [{ROW_ID_KEY: "n1"}]},
        options_folder=OPTIONS_FOLDER,
        functions_env={},
        authoritative_disabled_values=stored,
    )

    assert not result.error_schema
    assert result.task_data["owned"] == "server"
