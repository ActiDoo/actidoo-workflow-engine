# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

from pathlib import Path

import pytest

from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import validate_task_data

OPTIONS_FOLDER = Path(__file__).parent / "options"


def _form(type_, **validate):
    return {"components": [{"type": type_, "id": "Field_1", "key": "value", "label": "Value", "layout": {"row": "Row_1"}, "validate": validate}]}


def _schema(type_, **validate):
    return transform_camunda_form(_form(type_, **validate)).jsonschema["properties"]["value"]


def _errors(type_, value, **validate):
    return validate_task_data(
        form=transform_camunda_form(_form(type_, **validate)),
        task_data={"value": value},
        options_folder=OPTIONS_FOLDER,
        functions_env={},
    ).error_schema


def test__number_min_max_become_minimum_maximum():
    schema = _schema("number", min=1, max=10.5)
    assert schema["minimum"] == 1
    assert schema["maximum"] == 10.5


@pytest.mark.parametrize("type_", ["textfield", "textarea"])
def test__text_min_max_length_are_kept(type_):
    schema = _schema(type_, minLength=2, maxLength=5)
    assert schema["minLength"] == 2
    assert schema["maxLength"] == 5


@pytest.mark.parametrize(
    "type_, validate, value, valid",
    [
        ("number", {"min": 1, "max": 10}, 1, True),
        ("number", {"min": 1, "max": 10}, 10, True),
        ("number", {"min": 1, "max": 10}, 0, False),
        ("number", {"min": 1, "max": 10}, 11, False),
        ("textfield", {"minLength": 2, "maxLength": 3}, "ab", True),
        ("textfield", {"minLength": 2, "maxLength": 3}, "a", False),
        ("textarea", {"minLength": 2, "maxLength": 3}, "abcd", False),
    ],
)
def test__backend_validation_enforces_the_limits(type_, validate, value, valid):
    assert (_errors(type_, value, **validate) is None) is valid


@pytest.mark.parametrize("keyword", ["min", "max", "minLength", "maxLength"])
def test__feel_expressions_are_rejected(keyword):
    with pytest.raises(ValueError, match="FEEL expressions are not supported"):
        _schema("number", **{keyword: "=limit"})
