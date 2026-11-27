# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

"""An options file missing in the workflow's ``options`` folder is taken from the
shared ``options`` folder of all workflows; the workflow's own file wins."""

from pathlib import Path

import pytest

from actidoo_wfe.wf.exceptions import OptionsFileNotExistsException
from actidoo_wfe.wf.service_form import get_file_options, get_options, get_options_detailed, validate_task_data
from actidoo_wfe.wf.tests.helpers.dicts import read_and_transform

PATH_FORM = Path(__file__).parent / "../SimpleForm.form"
OPTIONS_FOLDER = Path(__file__).parents[1] / "options"


def test_missing_file_is_taken_from_the_shared_folder():
    form = read_and_transform(PATH_FORM)

    options = get_options(form.jsonschema, ["select_dynamic"], OPTIONS_FOLDER, {}, {})
    assert options == [("shared01", "Shared Eins"), ("shared02", "Shared Zwei")]

    detailed = get_options_detailed(form.jsonschema, ["select_dynamic"], OPTIONS_FOLDER, {}, {})
    assert detailed["shared01"] == {"value": "shared01", "label": "Shared Eins", "my_option": "shared01", "my_value": "Shared Eins"}


def test_workflow_file_wins_over_the_shared_file():
    form = read_and_transform(PATH_FORM)

    options = get_options(form.jsonschema, ["select_dynamic_required"], OPTIONS_FOLDER, {}, {})
    assert ("option01", "Option Eins") in options
    assert ("shadowed01", "Shadowed Eins") not in options


def test_submit_validates_against_the_shared_file():
    form = read_and_transform(PATH_FORM)
    data = {"select_static_required": "value1", "select_dynamic_required": "option01"}

    valid = validate_task_data(form, {**data, "select_dynamic": "shared01"}, OPTIONS_FOLDER, {}, log_validation_errors=False)
    assert not valid.error_schema

    invalid = validate_task_data(form, {**data, "select_dynamic": "option01"}, OPTIONS_FOLDER, {}, log_validation_errors=False)
    assert invalid.error_schema["select_dynamic"]["__errors"]


def test_file_in_neither_folder_is_reported_as_missing():
    with pytest.raises(OptionsFileNotExistsException):
        get_file_options(OPTIONS_FOLDER, "unknown.csv")
