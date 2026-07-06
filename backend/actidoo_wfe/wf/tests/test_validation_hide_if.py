# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Server-side hide-if semantics of ``validate_task_data`` for submitted task data.

The validation must reach the same visibility verdict as the frontend's FEEL
evaluation:

- A missing reference value counts as null: ``null = x`` is false, ``null != x``
  is true, and comparisons against the ``null`` literal match exactly the unset
  case.
- Disabled references cannot be trusted from the client: their values come from
  ``authoritative_disabled_values`` (the task's stored data) and are stripped
  from the result again.
- Values submitted for hidden fields are dropped without raising errors, while
  visible required fields stay required.
"""

from pathlib import Path

from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import validate_task_data

OPTIONS_FOLDER = Path(__file__).parent / "options"

AB_OPTIONS = [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}]

DISABLED_REFERENCE_FORM = {
    "components": [
        {"type": "radio", "key": "testclass", "disabled": True, "values": AB_OPTIONS},
        {
            "type": "select",
            "key": "approval",
            "validate": {"required": True},
            "conditional": {"hide": '=testclass != "b"'},
            "values": [{"label": "Release", "value": "approved"}, {"label": "Reject", "value": "rejected"}],
        },
        {"type": "textfield", "key": "comment"},
    ],
}

UNSET_REFERENCE_FORM = {
    # The hide-if reference is a regular optional select the user may leave
    # empty — its key is then absent from the submission entirely.
    "components": [
        {"type": "select", "key": "category", "values": AB_OPTIONS},
        {
            "type": "select",
            "key": "detail",
            "validate": {"required": True},
            "conditional": {"hide": '=category != "a"'},
            "values": AB_OPTIONS,
        },
    ],
}

NULL_LITERAL_FORM = {
    # Real-world forms cover the unset case explicitly via '= null': the comparison
    # against the null literal must match exactly when the field is unset.
    "components": [
        {"type": "select", "key": "kind", "values": AB_OPTIONS},
        {
            "type": "textfield",
            "key": "company_name",
            "validate": {"required": True},
            "conditional": {"hide": '=kind = "a" or kind = null'},
        },
    ],
}

NOT_NULL_FORM = {
    # Real-world forms also use the inverse guard: '=somefield != null and somefield = "..."'.
    "components": [
        {"type": "select", "key": "kind", "values": AB_OPTIONS},
        {
            "type": "textfield",
            "key": "person_name",
            "validate": {"required": True},
            "conditional": {"hide": '=kind != null and kind = "b"'},
        },
    ],
}


def _validate(form: dict, task_data: dict, stored: dict | None = None):
    """Validate ``task_data`` as an untrusted submission; ``stored`` holds the
    task's authoritative data for disabled fields (default: nothing stored)."""
    return validate_task_data(
        form=transform_camunda_form(form),
        task_data=task_data,
        options_folder=OPTIONS_FOLDER,
        functions_env={},
        authoritative_disabled_values=stored if stored is not None else {},
    )


def test__hidden_required_field_may_be_absent():
    result = _validate(DISABLED_REFERENCE_FORM, {"comment": "x"}, stored={"testclass": "a"})

    assert not result.error_schema
    assert "approval" not in result.task_data


def test__visible_required_field_is_still_required():
    result = _validate(DISABLED_REFERENCE_FORM, {"comment": "x"}, stored={"testclass": "b"})

    assert "approval" in (result.error_schema or {})


def test__visible_required_field_value_is_kept():
    result = _validate(DISABLED_REFERENCE_FORM, {"approval": "approved"}, stored={"testclass": "b"})

    assert not result.error_schema
    assert result.task_data["approval"] == "approved"


def test__value_submitted_for_hidden_field_is_stripped_without_error():
    result = _validate(DISABLED_REFERENCE_FORM, {"approval": "approved"}, stored={"testclass": "a"})

    assert not result.error_schema
    assert "approval" not in result.task_data


def test__submitted_disabled_value_cannot_override_stored_one():
    # The client claims testclass "a" to dodge the approval, but the stored value is "b".
    result = _validate(DISABLED_REFERENCE_FORM, {"testclass": "a"}, stored={"testclass": "b"})

    assert "approval" in (result.error_schema or {})


def test__garbage_in_disabled_field_is_ignored():
    result = _validate(
        DISABLED_REFERENCE_FORM,
        {"testclass": "NOT_A_VALID_OPTION", "approval": "approved"},
        stored={"testclass": "b"},
    )

    assert not result.error_schema
    assert "testclass" not in result.task_data


def test__unset_disabled_reference_behaves_like_feel_null():
    # FEEL: null != "b" is true, so the approval is hidden and may be absent.
    result = _validate(DISABLED_REFERENCE_FORM, {"comment": "x"}, stored={})

    assert not result.error_schema
    assert "approval" not in result.task_data


def test__required_field_hidden_behind_unset_optional_reference_may_be_absent():
    result = _validate(UNSET_REFERENCE_FORM, {})

    assert not result.error_schema


def test__required_field_visible_behind_set_reference_is_required():
    result = _validate(UNSET_REFERENCE_FORM, {"category": "a"})

    assert "detail" in (result.error_schema or {})


def test__comparison_against_null_literal_matches_unset_reference():
    result = _validate(NULL_LITERAL_FORM, {})

    assert not result.error_schema


def test__comparison_against_null_literal_does_not_match_set_reference():
    result = _validate(NULL_LITERAL_FORM, {"kind": "b"})

    assert "company_name" in (result.error_schema or {})


def test__not_null_conjunction_leaves_field_visible_for_unset_reference():
    # FEEL: null != null is false, so the conjunction never matches an unset reference.
    result = _validate(NOT_NULL_FORM, {})

    assert "person_name" in (result.error_schema or {})


def test__not_null_conjunction_hides_field_for_matching_reference():
    result = _validate(NOT_NULL_FORM, {"kind": "b"})

    assert not result.error_schema


NONE_SPELLING_FORM = {
    # Some forms spell the null literal the Python way: '!= None'. It must behave
    # exactly like '!= null' (and must not crash the expression conversion).
    "components": [
        {"type": "select", "key": "kind", "values": AB_OPTIONS},
        {
            "type": "select",
            "key": "detail",
            "validate": {"required": True},
            "conditional": {"hide": "=kind != None"},
            "values": AB_OPTIONS,
        },
    ],
}


def test__none_spelling_behaves_like_null_literal():
    unset = _validate(NONE_SPELLING_FORM, {})
    hidden = _validate(NONE_SPELLING_FORM, {"kind": "a"})

    assert "detail" in (unset.error_schema or {})  # kind unset -> detail visible
    assert not hidden.error_schema  # kind set -> detail hidden, may be absent
