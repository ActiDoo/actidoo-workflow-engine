# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Submitted task data is validated against hide-if conditions that reference
``disabled`` fields. The client cannot be trusted for disabled values (and used
to have them stripped before validation, which made such hide-if conditions
evaluate vacuously) — so ``validate_task_data`` merges the authoritative values
in, evaluates the conditions like the frontend's FEEL engine would, and strips
the disabled fields from the result again."""

from pathlib import Path

from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import validate_task_data
from actidoo_wfe.wf.types import ReactJsonSchemaFormData

OPTIONS_FOLDER = Path(__file__).parent / "options"

FORM = {
    "components": [
        {
            "type": "radio",
            "key": "testclass",
            "label": "test class",
            "disabled": True,
            "values": [
                {"label": "A", "value": "a"},
                {"label": "B", "value": "b"},
            ],
        },
        {
            "type": "select",
            "key": "approval",
            "label": "Release",
            "validate": {"required": True},
            "conditional": {"hide": '=testclass != "b"'},
            "values": [
                {"label": "Release", "value": "approved"},
                {"label": "Reject", "value": "rejected"},
            ],
        },
        {
            "type": "textfield",
            "key": "comment",
            "label": "Comment",
        },
    ],
}


def _validate(task_data: dict, stored: dict):
    form = transform_camunda_form(FORM)
    return validate_task_data(
        form=form,
        task_data=task_data,
        options_folder=OPTIONS_FOLDER,
        functions_env={},
        authoritative_disabled_values=stored,
    )


def test__hidden_required_field_may_be_absent():
    result = _validate(task_data={"comment": "x"}, stored={"testclass": "a"})

    assert not result.error_schema
    assert "approval" not in result.task_data


def test__visible_required_field_is_still_required():
    result = _validate(task_data={"comment": "x"}, stored={"testclass": "b"})

    assert "approval" in result.error_schema


def test__visible_required_field_value_is_kept():
    result = _validate(task_data={"approval": "approved"}, stored={"testclass": "b"})

    assert not result.error_schema
    assert result.task_data["approval"] == "approved"


def test__value_submitted_for_hidden_field_is_stripped_without_error():
    result = _validate(task_data={"approval": "approved"}, stored={"testclass": "a"})

    assert not result.error_schema
    assert "approval" not in result.task_data


def test__submitted_disabled_value_cannot_override_stored_one():
    # The client claims testclass "a" to dodge the approval, but the stored value is "b".
    result = _validate(task_data={"testclass": "a"}, stored={"testclass": "b"})

    assert "approval" in result.error_schema


def test__garbage_in_disabled_field_is_ignored():
    result = _validate(
        task_data={"testclass": "NOT_A_VALID_OPTION", "approval": "approved"},
        stored={"testclass": "b"},
    )

    assert not result.error_schema
    assert "testclass" not in result.task_data


def test__unset_disabled_reference_behaves_like_feel_null():
    # FEEL: null != "b" is true, so the approval is hidden and may be absent.
    result = _validate(task_data={"comment": "x"}, stored={})

    assert not result.error_schema
    assert "approval" not in result.task_data
