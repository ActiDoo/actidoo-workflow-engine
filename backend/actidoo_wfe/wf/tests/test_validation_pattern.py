# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Regex validation of text fields (the Modeler's ``validate.pattern``) and the custom
property ``pattern_message`` that replaces the raw regex in the error shown to the user."""

from pathlib import Path

from actidoo_wfe.wf import service_i18n
from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import validate_task_data

OPTIONS_FOLDER = Path(__file__).parent / "options"

PLATE_PATTERN = r"^[A-Z]{1,3}-[A-Z]{1,2} \d{1,4}$"
PLATE_MESSAGE = "Enter a plate like B-AB 1234"

FORM = {
    "components": [
        {
            "type": "textfield",
            "key": "plate",
            "validate": {"required": True, "pattern": PLATE_PATTERN},
            "properties": {"pattern_message": PLATE_MESSAGE},
        },
        {"type": "textfield", "key": "code", "validate": {"pattern": r"^\d{3}$"}},
        {
            "type": "dynamiclist",
            "path": "rows",
            "components": [
                {
                    "type": "textfield",
                    "key": "zip",
                    "validate": {"pattern": r"^\d{5}$"},
                    "properties": {"pattern_message": "Five digits"},
                },
            ],
        },
    ],
}


def _validate(form, data):
    return validate_task_data(form=form, task_data=data, options_folder=OPTIONS_FOLDER, functions_env={}).error_schema


def test_transformation_carries_pattern_and_message():
    form = transform_camunda_form(FORM)

    assert form.jsonschema["properties"]["plate"]["pattern"] == PLATE_PATTERN
    assert form.uischema["plate"]["ui:patternMessage"] == PLATE_MESSAGE
    assert "ui:patternMessage" not in form.uischema["code"]
    assert form.jsonschema["properties"]["rows"]["items"]["properties"]["zip"]["pattern"] == r"^\d{5}$"
    assert form.uischema["rows"]["items"]["zip"]["ui:patternMessage"] == "Five digits"


def test_matching_values_pass():
    form = transform_camunda_form(FORM)

    assert _validate(form, {"plate": "B-AB 1234", "code": "123", "rows": [{"zip": "12345"}]}) is None


def test_mismatch_reports_custom_message_else_default():
    form = transform_camunda_form(FORM)

    errors = _validate(form, {"plate": "foo", "code": "12", "rows": [{"zip": "12345"}, {"zip": "1"}]})

    assert errors["plate"]["__errors"] == [PLATE_MESSAGE]
    assert errors["code"]["__errors"] == ["'12' does not match '^\\\\d{3}$'"]
    assert errors["rows"] == [{}, {"zip": {"__errors": ["Five digits"]}}]


def test_pattern_message_is_extracted_for_translation():
    entries = service_i18n.extract_strings_from_form(FORM["components"])

    assert (PLATE_MESSAGE, "plate.pattern_message") in entries
    assert ("Five digits", "rows.zip.pattern_message") in entries
