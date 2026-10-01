# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""How submitted form data behaves: hide-if visibility, empty values and required.

One module on purpose: every detail rule about what a submission means lives here,
next to its neighbours. Sections:

1. Hide-if - the server must reach the same visibility verdict as the browser's FEEL
   evaluation. A missing reference counts as null: ``null = x`` is false, ``null != x``
   is true, and only a comparison against the ``null`` literal matches the unset case.
   Disabled references take their effective value from the stored data (ADR 010).
   Values submitted for hidden fields are dropped without errors, while visible
   required fields stay required.
2. Empty values - an emptied field is null, a blank never satisfies ``required``,
   and values are never trimmed.

Forms used by a single test are defined inside it; only the widely shared ones are
module constants.
"""

import copy
import json
import re
from pathlib import Path

import pytest

from actidoo_wfe.wf.constants import ROW_ID_KEY
from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import normalize_blank_values, validate_task_data
from actidoo_wfe.wf.service_workflow import update

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

MIXED_OR_FORM = {
    # One operand lives on the row, the other on the root: each level gets its own
    # condition in the converted schema. Hidden as soon as either holds.
    "components": [
        {"type": "select", "key": "rootflag", "values": AB_OPTIONS},
        {
            "type": "dynamiclist",
            "path": "rows",
            "components": [
                {"type": "number", "key": "n"},
                {"type": "textfield", "key": "note", "validate": {"required": True}, "conditional": {"hide": '=this.n = 9 or rootflag = "a"'}},
            ],
        },
    ],
}

EQUALITY_REFERENCE_FORM = {
    "components": [
        {"type": "select", "key": "category", "values": AB_OPTIONS},
        {
            "type": "textfield",
            "key": "detail",
            "validate": {"required": True},
            "conditional": {"hide": '=category = "a"'},
        },
    ],
}

HIDDEN_LIST_FORM = {
    "components": [
        {"type": "select", "key": "variant", "values": AB_OPTIONS},
        {
            "type": "dynamiclist",
            "path": "positions",
            "properties": {"minItems": "1"},
            "conditional": {"hide": '=variant = "a"'},
            "components": [
                {"type": "textfield", "key": "name", "validate": {"required": True}},
            ],
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


def _required_errors(result) -> set[str]:
    """Names of the fields reported as missing (the error dict nests required errors)."""
    return set(re.findall(r"'([^']+)' is a required property", json.dumps(result.error_schema or {})))


def test__hidden_required_field_may_be_absent():
    """Stored testclass is "a", so ``testclass != "b"`` is true and approval is
    hidden. The user could not fill it, so leaving it out is no error."""
    result = _validate(DISABLED_REFERENCE_FORM, {"comment": "x"}, stored={"testclass": "a"})

    assert not result.error_schema
    assert "approval" not in result.task_data


def test__visible_required_field_is_still_required():
    """Stored testclass is "b", so the condition is false and approval is
    shown. It is required and missing, so there is an error."""
    result = _validate(DISABLED_REFERENCE_FORM, {"comment": "x"}, stored={"testclass": "b"})

    assert "approval" in (result.error_schema or {})


def test__visible_required_field_value_is_kept():
    """Stored testclass is "b", approval is shown and set to "approved".
    The value ends up in the result unchanged."""
    result = _validate(DISABLED_REFERENCE_FORM, {"approval": "approved"}, stored={"testclass": "b"})

    assert not result.error_schema
    assert result.task_data["approval"] == "approved"


def test__value_submitted_for_hidden_field_is_stripped_without_error():
    """Stored testclass is "a", so approval is hidden. The browser still sends
    a value for it. That value is dropped without an error."""
    result = _validate(DISABLED_REFERENCE_FORM, {"approval": "approved"}, stored={"testclass": "a"})

    assert not result.error_schema
    assert "approval" not in result.task_data


def test__submitted_disabled_value_cannot_override_stored_one():
    """The client sends testclass "a", but the stored value is "b". testclass is
    disabled, so the stored "b" wins: approval stays shown and required."""
    result = _validate(DISABLED_REFERENCE_FORM, {"testclass": "a"}, stored={"testclass": "b"})

    assert "approval" in (result.error_schema or {})


def test__garbage_in_disabled_field_is_replaced_by_the_stored_value():
    """The client sends an invalid option for the disabled testclass. That is no
    error: the stored "b" replaces it."""
    result = _validate(
        DISABLED_REFERENCE_FORM,
        {"testclass": "NOT_A_VALID_OPTION", "approval": "approved"},
        stored={"testclass": "b"},
    )

    assert not result.error_schema
    assert result.task_data["testclass"] == "b"


def test__unset_disabled_reference_behaves_like_feel_null():
    """Nothing is stored for testclass, so it reads as null. ``null != "b"`` is
    true, approval is hidden and may be absent."""
    result = _validate(DISABLED_REFERENCE_FORM, {"comment": "x"}, stored={})

    assert not result.error_schema
    assert "approval" not in result.task_data


def _unset_reference_form() -> dict:
    """An optional select guarding a required one via ``category != "a"``."""
    return {
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


def test__required_field_hidden_behind_unset_optional_reference_may_be_absent():
    """category was never filled, so ``null != "a"`` is true. detail is hidden
    and its required rule does not apply."""
    result = _validate(_unset_reference_form(), {})

    assert not result.error_schema


def test__required_field_visible_behind_set_reference_is_required():
    """category is "a", so ``category != "a"`` is false. detail is shown,
    required and missing, so there is an error."""
    result = _validate(_unset_reference_form(), {"category": "a"})

    assert "detail" in (result.error_schema or {})


def _null_literal_form() -> dict:
    """A guard that covers the unset case explicitly: ``kind = "a" or kind = null``."""
    return {
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


def test__comparison_against_null_literal_matches_unset_reference():
    """kind was never filled, so ``kind = null`` is true. company_name is hidden
    and may be absent."""
    result = _validate(_null_literal_form(), {})

    assert not result.error_schema


def test__comparison_against_null_literal_does_not_match_set_reference():
    """kind is "b", so neither ``kind = "a"`` nor ``kind = null`` is true.
    company_name is shown, required and missing, so there is an error."""
    result = _validate(_null_literal_form(), {"kind": "b"})

    assert "company_name" in (result.error_schema or {})


def _not_null_form() -> dict:
    """The inverse guard: ``kind != null and kind = "b"``."""
    return {
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


def test__not_null_conjunction_leaves_field_visible_for_unset_reference():
    """kind is unset, so ``kind != null`` is false and the whole condition is
    false. person_name stays shown and its required rule reports it."""
    result = _validate(_not_null_form(), {})

    assert "person_name" in (result.error_schema or {})


def test__not_null_conjunction_hides_field_for_matching_reference():
    """kind is "b", so both parts are true. person_name is hidden and may be
    absent."""
    result = _validate(_not_null_form(), {"kind": "b"})

    assert not result.error_schema


def test__none_spelling_behaves_like_null_literal():
    """Some forms spell the null literal the Python way, ``!= None``. It behaves
    exactly like ``!= null`` and must not crash the expression conversion."""
    form = {
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

    unset = _validate(form, {})
    hidden = _validate(form, {"kind": "a"})

    assert "detail" in (unset.error_schema or {})  # kind unset -> detail visible
    assert not hidden.error_schema  # kind set -> detail hidden, may be absent


def test__list_or_condition_is_evaluated_per_item():
    """A hide-if inside a dynamic list is decided row by row: the same condition
    hides the field in one row and shows it in the next."""
    form = {
        "components": [
            {
                "type": "dynamiclist",
                "path": "employees",
                "isRepeating": True,
                "components": [
                    {"type": "textfield", "key": "employee"},
                    {
                        "type": "textfield",
                        "key": "region",
                        "conditional": {"hide": '=this.employee="intern"\nor this.employee = null'},
                    },
                ],
            },
        ],
    }

    result = _validate(
        form,
        {
            "employees": [
                {"employee": "manager", "region": "west"},
                {"employee": "intern", "region": "ost"},
                {"region": "sued"},
            ]
        },
    )

    assert not result.error_schema
    assert result.task_data["employees"][0]["region"] == "west"
    assert "region" not in result.task_data["employees"][1]
    assert "region" not in result.task_data["employees"][2]


def test__missing_hide_if_reference_is_treated_as_unset_and_does_not_crash():
    """A hide-if pointing at a field that no longer exists in the form (it was
    removed from the modeler) counts as null instead of crashing the request:
    ``null = false`` is false, so the field stays visible and required."""
    form = {
        "components": [
            {
                "type": "select",
                "key": "subarea",
                "validate": {"required": True},
                "conditional": {"hide": "=missing_checkbox = false"},
                "values": AB_OPTIONS,
            },
        ],
    }

    result = _validate(form, {})

    assert "subarea" in (result.error_schema or {})


def test__this_reference_does_not_reach_into_an_outer_row():
    """``this.`` names the row the field itself lives in - nothing else. flag
    sits one level up, so ``this.flag`` is unset and the field stays visible."""
    form = {
        "components": [
            {
                "type": "dynamiclist",
                "path": "outer",
                "components": [
                    {"type": "checkbox", "key": "flag"},
                    {
                        "type": "dynamiclist",
                        "path": "inner",
                        "components": [
                            {"type": "textfield", "key": "note", "conditional": {"hide": "=this.flag = false"}},
                        ],
                    },
                ],
            },
        ],
    }

    result = _validate(form, {"outer": [{"flag": False, "inner": [{"note": "kept"}]}]})

    assert not result.error_schema
    assert result.task_data["outer"][0]["inner"][0]["note"] == "kept"


def test__parent_reference_addresses_the_surrounding_row():
    """``parent.`` names the surrounding row: its flag is false, the condition
    matches and the field is hidden (its value is dropped)."""
    form = {
        "components": [
            {
                "type": "dynamiclist",
                "path": "outer",
                "components": [
                    {"type": "checkbox", "key": "flag"},
                    {
                        "type": "dynamiclist",
                        "path": "inner",
                        "components": [
                            {"type": "textfield", "key": "scoped_note", "conditional": {"hide": "=parent.flag = false"}},
                        ],
                    },
                ],
            },
        ],
    }

    result = _validate(form, {"outer": [{"flag": False, "inner": [{"scoped_note": "dropped"}]}]})

    assert not result.error_schema
    assert "scoped_note" not in result.task_data["outer"][0]["inner"][0]


# --- hide-if on the dynamic list itself -----------------------------------------


def test__hidden_list_does_not_enforce_min_items():
    """variant is "a", so the positions list is hidden. Its minItems of 1 does
    not apply to the empty list, and the list is dropped."""
    result = _validate(HIDDEN_LIST_FORM, {"variant": "a", "positions": []})

    assert not result.error_schema
    assert "positions" not in result.task_data


def test__rows_submitted_for_a_hidden_list_are_stripped_without_error():
    """variant is "a", so the positions list is hidden. The submitted row is
    dropped without an error."""
    result = _validate(HIDDEN_LIST_FORM, {"variant": "a", "positions": [{"name": "x"}]})

    assert not result.error_schema
    assert "positions" not in result.task_data


def test__hidden_list_does_not_enforce_required_fields_of_its_rows():
    """variant is "a", so the positions list is hidden. The row is missing its
    required name, but that is no error because the whole list is hidden."""
    result = _validate(HIDDEN_LIST_FORM, {"variant": "a", "positions": [{}]})

    assert not result.error_schema
    assert "positions" not in result.task_data


def test__visible_list_still_enforces_min_items():
    """variant is "b", so the positions list is shown. The empty list violates
    minItems of 1, so there is an error."""
    result = _validate(HIDDEN_LIST_FORM, {"variant": "b", "positions": []})

    assert "positions" in (result.error_schema or {})


def test__visible_list_still_enforces_required_fields_of_its_rows():
    """variant is "b", so the positions list is shown. The row is missing its
    required name, so there is an error."""
    result = _validate(HIDDEN_LIST_FORM, {"variant": "b", "positions": [{}]})

    assert "positions" in (result.error_schema or {})


def test__visible_list_keeps_its_rows():
    """variant is "b", so the positions list is shown. Its row passes through
    unchanged."""
    result = _validate(HIDDEN_LIST_FORM, {"variant": "b", "positions": [{"name": "x"}]})

    assert not result.error_schema
    assert result.task_data["positions"] == [{"name": "x"}]


def test__nested_hidden_list_is_evaluated_per_row():
    """An inner list hidden by a field of its surrounding row: one row keeps its
    inner rows, the other loses them - visibility differs per row."""
    form = {
        "components": [
            {
                "type": "dynamiclist",
                "path": "outer",
                "components": [
                    {"type": "select", "key": "kind", "values": AB_OPTIONS},
                    {
                        "type": "dynamiclist",
                        "path": "inner",
                        "conditional": {"hide": '=this.kind = "a"'},
                        "components": [{"type": "textfield", "key": "note"}],
                    },
                ],
            },
        ],
    }

    result = _validate(
        form,
        {
            "outer": [
                {"kind": "a", "inner": [{"note": "dropped"}]},
                {"kind": "b", "inner": [{"note": "kept"}]},
            ]
        },
    )

    assert not result.error_schema
    assert "inner" not in result.task_data["outer"][0]
    assert result.task_data["outer"][1]["inner"] == [{"note": "kept"}]


def test__hidden_attachment_field_is_stripped_without_error():
    """variant is "a", so the attachment field docs is hidden. The empty list is
    no error and docs is dropped."""
    form = {
        "components": [
            {"type": "select", "key": "variant", "values": AB_OPTIONS},
            {
                "type": "textfield",
                "key": "docs",
                "properties": {"custom_type": "attachment_multi"},
                "validate": {"required": True},
                "conditional": {"hide": '=variant = "a"'},
            },
        ],
    }

    result = _validate(form, {"variant": "a", "docs": []})

    assert not result.error_schema
    assert "docs" not in result.task_data


def test__hidden_list_leaves_no_row_skeleton_in_stored_task_data():
    """The hand-out cleanup preserves technical fields such as the row id - but
    those must not resurrect the rows the hide-if just removed as empty shells."""
    form = transform_camunda_form(HIDDEN_LIST_FORM)
    stored = {"variant": "a", "positions": [{ROW_ID_KEY: "r1", "name": "x"}]}

    result = validate_task_data(
        form=form,
        task_data=stored,
        options_folder=OPTIONS_FOLDER,
        functions_env={},
        preserve_unknown_fields=True,
    )

    assert "positions" not in result.task_data


def test__visible_list_keeps_its_row_ids_during_cleanup():
    """The hand-out cleanup of a shown list keeps rows and their row ids intact."""
    form = transform_camunda_form(HIDDEN_LIST_FORM)
    stored = {"variant": "b", "positions": [{ROW_ID_KEY: "r1", "name": "x"}]}

    result = validate_task_data(
        form=form,
        task_data=stored,
        options_folder=OPTIONS_FOLDER,
        functions_env={},
        preserve_unknown_fields=True,
    )

    assert result.task_data["positions"] == [{"name": "x", ROW_ID_KEY: "r1"}]


def test__or_across_levels_hides_when_the_root_operand_holds():
    """Condition ``this.n = 9 or rootflag = "a"``. With rootflag "a" the root
    operand is true, so the condition holds for every row regardless of n.
    ``note`` is hidden and must not appear in the result, even though the row
    submitted a value for it."""
    result = _validate(MIXED_OR_FORM, {"rootflag": "a", "rows": [{"n": 1, "note": "dropped"}]})

    assert not result.error_schema
    assert "note" not in result.task_data["rows"][0]


def test__or_across_levels_hides_per_row_when_the_row_operand_holds():
    """Condition ``this.n = 9 or rootflag = "a"``. With rootflag "b" the root
    operand is false, so only the row operand decides. In the row with n = 9
    the condition is true and ``note`` is hidden: it must not appear in that
    row's result. In the row with n = 1 the condition is false and ``note`` is
    kept as submitted."""
    result = _validate(MIXED_OR_FORM, {"rootflag": "b", "rows": [{"n": 9, "note": "dropped"}, {"n": 1, "note": "kept"}]})

    assert not result.error_schema
    assert "note" not in result.task_data["rows"][0]
    assert result.task_data["rows"][1]["note"] == "kept"


def test__or_across_levels_requires_the_field_when_neither_operand_holds():
    """Condition ``this.n = 9 or rootflag = "a"``. With rootflag "b" and n = 1
    neither operand is true, so ``note`` is visible. It is required and was not
    submitted, so validation must report an error for it."""
    result = _validate(MIXED_OR_FORM, {"rootflag": "b", "rows": [{"n": 1}]})

    assert "note" in json.dumps(result.error_schema)


@pytest.mark.parametrize(
    "condition",
    [
        '=this.n = 9 or (rootflag = "a" and this.n = 1)',
        '=(this.n = 1 and rootflag = "a") or this.n = 9',
        '=this.n = 1 and (rootflag = "a" or this.n = 9)',
    ],
)
@pytest.mark.parametrize(
    ("rootflag", "n", "hidden"),
    [
        ("a", 1, True),
        ("b", 1, False),
        ("a", 2, False),
        ("b", 2, False),
    ],
)
def test__nested_boolean_conditions_use_each_references_level(condition, rootflag, n, hidden):
    """The row and root comparisons keep their levels inside parentheses too.
    A hidden required note is dropped; a visible one is kept or reported missing."""
    form = {
        "components": [
            {"type": "textfield", "key": "rootflag"},
            {
                "type": "dynamiclist",
                "path": "rows",
                "components": [
                    {"type": "number", "key": "n"},
                    {"type": "textfield", "key": "note", "validate": {"required": True}, "conditional": {"hide": condition}},
                ],
            },
        ]
    }
    filled = _validate(form, {"rootflag": rootflag, "rows": [{"n": n, "note": "answer"}]})
    missing = _validate(form, {"rootflag": rootflag, "rows": [{"n": n}]})

    assert not filled.error_schema
    assert ("note" not in filled.task_data["rows"][0]) is hidden
    assert bool(missing.error_schema) is not hidden


@pytest.mark.parametrize(
    "condition",
    [
        '=rootflag = "a" and parent.flag = "b" and this.n = 1',
        '=this.n = 9 or (rootflag = "a" and parent.flag = "b" and this.n = 1)',
    ],
)
def test__conditions_across_three_levels_are_evaluated_per_nested_row(condition):
    """Only the matching inner row is hidden; sibling rows keep their required notes."""
    form = {
        "components": [
            {"type": "textfield", "key": "rootflag"},
            {
                "type": "dynamiclist",
                "path": "groups",
                "components": [
                    {"type": "textfield", "key": "flag"},
                    {
                        "type": "dynamiclist",
                        "path": "rows",
                        "components": [
                            {"type": "number", "key": "n"},
                            {"type": "textfield", "key": "note", "validate": {"required": True}, "conditional": {"hide": condition}},
                        ],
                    },
                ],
            },
        ]
    }
    result = _validate(
        form,
        {
            "rootflag": "a",
            "groups": [
                {"flag": "b", "rows": [{"n": 1, "note": "hidden"}, {"n": 2, "note": "kept"}]},
                {"flag": "c", "rows": [{"n": 1, "note": "other group"}]},
            ],
        },
    )

    assert not result.error_schema
    assert "note" not in result.task_data["groups"][0]["rows"][0]
    assert result.task_data["groups"][0]["rows"][1]["note"] == "kept"
    assert result.task_data["groups"][1]["rows"][0]["note"] == "other group"


def test__and_across_levels_hides_only_when_both_operands_hold():
    """Condition ``this.n = 9 and rootflag = "a"``. Only rootflag "a" together
    with n = 9 makes the condition true, so ``note`` is hidden and must not
    appear in the result. With rootflag "a" and n = 1, or rootflag "b" and
    n = 9, one operand is false, the condition is false, and ``note`` is kept
    as submitted."""
    form = {
        "components": [
            {"type": "select", "key": "rootflag", "values": AB_OPTIONS},
            {
                "type": "dynamiclist",
                "path": "rows",
                "components": [
                    {"type": "number", "key": "n"},
                    {"type": "textfield", "key": "note", "conditional": {"hide": '=this.n = 9 and rootflag = "a"'}},
                ],
            },
        ],
    }

    both = _validate(form, {"rootflag": "a", "rows": [{"n": 9, "note": "dropped"}]})
    only_root = _validate(form, {"rootflag": "a", "rows": [{"n": 1, "note": "kept"}]})
    only_row = _validate(form, {"rootflag": "b", "rows": [{"n": 9, "note": "kept"}]})

    assert "note" not in both.task_data["rows"][0]
    assert only_root.task_data["rows"][0]["note"] == "kept"
    assert only_row.task_data["rows"][0]["note"] == "kept"


def _empty_string_form() -> dict:
    """Older forms compare against "" to mean "empty". An empty field is null,
    never "", so both sides read such a comparison as one against null."""
    return {
        "components": [
            {"type": "textfield", "key": "comment", "disabled": True},
            {"type": "textfield", "key": "note", "conditional": {"hide": '=comment = ""'}},
            {"type": "textfield", "key": "reminder", "validate": {"required": True}, "conditional": {"hide": '=comment != ""'}},
        ],
    }


def test__comparison_against_the_empty_string_reads_as_null():
    """comment is unset: ``= ""`` matches like ``= null`` (note hidden) and
    ``!= ""`` does not (reminder visible and required)."""
    result = _validate(_empty_string_form(), {"note": "n"}, stored={})

    assert "note" not in result.task_data
    assert "reminder" in (result.error_schema or {})


def test__comparison_against_the_empty_string_with_a_value_set():
    """comment holds a value: ``= ""`` does not match (note visible) and
    ``!= ""`` does (reminder hidden)."""
    result = _validate(_empty_string_form(), {"note": "n"}, stored={"comment": "x"})

    assert not result.error_schema
    assert result.task_data["note"] == "n"


def test__equality_against_unset_reference_leaves_field_visible_and_required():
    """category is unset, so ``category = "a"`` is false. detail is shown,
    required and missing, so there is an error."""
    result = _validate(EQUALITY_REFERENCE_FORM, {})

    assert "detail" in (result.error_schema or {})


def test__equality_against_unset_reference_keeps_the_submitted_value():
    """category is unset, so detail is shown. The submitted detail "b" is kept.
    It used to be dropped."""
    result = _validate(EQUALITY_REFERENCE_FORM, {"detail": "b"})

    assert not result.error_schema
    assert result.task_data["detail"] == "b"


def test__equality_against_matching_reference_hides_the_field():
    """category is "a", so ``category = "a"`` is true. detail is hidden and the
    submitted value is dropped."""
    result = _validate(EQUALITY_REFERENCE_FORM, {"category": "a", "detail": "b"})

    assert not result.error_schema
    assert "detail" not in result.task_data


# ------------------------------------------------------------------------------
# Empty values
#
# An emptied field is null, and a blank does not satisfy ``required``.
#
# The browser sends null for a field the user cleared and the schema admits it, so the
# merge into the stored data overwrites the old value. A submitted blank - null, an
# empty or a whitespace-only string - is user input meaning "nothing entered": it is
# stored as null, and where the field is required (or admits no null) it is dropped so
# that the schema reports it. Trusted engine data is not touched.

BLANKS = ["", "   ", "\n\t", None]

REQUIRED_FIELDS_FORM = {
    "components": [
        {"type": "textfield", "key": "name", "validate": {"required": True}},
        {"type": "textarea", "key": "note", "validate": {"required": True}},
        {"type": "select", "key": "choice", "values": AB_OPTIONS, "validate": {"required": True}},
        {"type": "number", "key": "amount", "validate": {"required": True}},
    ],
}

FILLED = {"name": "x", "note": "y", "choice": "a", "amount": 1}

OPTIONAL_FIELDS_FORM = {
    "components": [
        {"type": "textfield", "key": "name"},
        {"type": "number", "key": "amount"},
        {"type": "select", "key": "choice", "values": AB_OPTIONS},
        {"type": "radio", "key": "kind", "values": AB_OPTIONS},
    ],
}


def test__emptied_fields_are_nullable_in_the_schema():
    """The transformation admits null for text and number fields and tells the
    browser to send null when the user clears them (``ui:emptyValue``)."""
    form = transform_camunda_form(OPTIONAL_FIELDS_FORM)

    assert form.jsonschema["properties"]["name"]["type"] == ["string", "null"]
    assert form.jsonschema["properties"]["amount"]["type"] == ["number", "null"]
    assert form.uischema["name"]["ui:emptyValue"] is None
    assert form.uischema["amount"]["ui:emptyValue"] is None


@pytest.mark.parametrize("field", ["name", "note", "choice", "amount"])
@pytest.mark.parametrize("blank", BLANKS)
def test__blank_in_required_field_is_a_required_error(field, blank):
    """Whatever kind of blank lands in a required field - empty string,
    whitespace only, or null - the answer is the same: the field is missing."""
    result = _validate(REQUIRED_FIELDS_FORM, {**FILLED, field: blank})

    assert _required_errors(result) == {field}
    assert field not in result.task_data


def test__filled_required_fields_pass():
    """The happy path: all required fields filled, everything passes unchanged."""
    result = _validate(REQUIRED_FIELDS_FORM, FILLED)

    assert not result.error_schema
    assert result.task_data == FILLED


@pytest.mark.parametrize("blank", BLANKS)
def test__blank_in_optional_field_is_stored_as_null(blank):
    """A blank in an optional field becomes null - and null is what overwrites
    the earlier value in the merge, so this is what clears a field."""
    result = _validate(OPTIONAL_FIELDS_FORM, {"name": blank, "amount": blank, "choice": blank})

    assert not result.error_schema
    assert result.task_data == {"name": None, "amount": None, "choice": None}


def test__a_blank_where_the_schema_admits_no_null_is_dropped():
    """A radio has no null in its schema, so a blank for it is dropped instead
    of stored - the result is the same: no value."""
    result = _validate(OPTIONAL_FIELDS_FORM, {"kind": ""})

    assert not result.error_schema
    assert "kind" not in result.task_data


def test__values_are_never_trimmed():
    """Only all-whitespace counts as blank; entered whitespace around a real
    value is kept as typed."""
    result = _validate(OPTIONAL_FIELDS_FORM, {"name": "  padded  "})

    assert result.task_data["name"] == "  padded  "


def test__blanks_inside_list_rows():
    """The blank rules apply inside dynamic-list rows exactly as at the root:
    a blank required field is missing, a blank optional one becomes null."""
    form = {
        "components": [
            {
                "type": "dynamiclist",
                "path": "rows",
                "components": [
                    {"type": "textfield", "key": "label", "validate": {"required": True}},
                    {"type": "textfield", "key": "remark"},
                ],
            },
        ],
    }

    result = _validate(form, {"rows": [{"label": "ok", "remark": "  "}, {"label": " ", "remark": "kept"}]})

    assert _required_errors(result) == {"label"}
    assert result.task_data["rows"][0] == {"label": "ok", "remark": None}
    assert result.task_data["rows"][1] == {"remark": "kept"}


def test__blank_reference_reads_as_unset_in_hide_if():
    """A blank in a hide-if reference counts as unset: whitespace-only mode
    keeps ``mode = null`` matching, so the dependent field stays hidden."""
    form = {
        "components": [
            {"type": "textfield", "key": "mode"},
            {"type": "textfield", "key": "detail", "validate": {"required": True}, "conditional": {"hide": "=mode = null"}},
        ],
    }

    assert not _validate(form, {"mode": "   ", "detail": "x"}).error_schema
    assert "detail" not in _validate(form, {"mode": "   ", "detail": "x"}).task_data
    assert _required_errors(_validate(form, {"mode": "on"})) == {"detail"}


@pytest.mark.parametrize("stored_status", ["", "   ", None, "<absent>"])
@pytest.mark.parametrize("condition", ["=status = null", '=status = ""'])
def test__a_blank_disabled_reference_reads_as_null(condition, stored_status):
    """The reference is disabled, so its value comes from the stored data, where
    a blank text can still sit (a server-owned value, or older data). The browser
    reads it as null and hides reason; the server must agree, or the submit fails
    with reason required although the user cannot see it."""
    form = {
        "components": [
            {"type": "textfield", "key": "status", "disabled": True},
            {"type": "textfield", "key": "reason", "validate": {"required": True}, "conditional": {"hide": condition}},
        ],
    }
    stored = {} if stored_status == "<absent>" else {"status": stored_status}

    result = _validate(form, {"status": "x"}, stored=stored)

    assert not result.error_schema


def test__a_blank_reference_does_not_match_not_null():
    """The other direction: ``status != null`` is false for a blank status, so
    the dependent field is not hidden and stays required."""
    form = {
        "components": [
            {"type": "textfield", "key": "status", "disabled": True},
            {"type": "textfield", "key": "reason", "validate": {"required": True}, "conditional": {"hide": "=status != null"}},
        ],
    }

    assert _required_errors(_validate(form, {}, stored={"status": "  "})) == {"reason"}
    assert not _validate(form, {}, stored={"status": "set"}).error_schema


def test__stored_blank_reference_hides_like_null_when_a_task_is_handed_out():
    """When a task is handed out, its stored data is cleaned as trusted data,
    without the submission rules. A stored blank still counts as null there, so
    the value of a field the browser hides is not kept."""
    form = transform_camunda_form(
        {
            "components": [
                {"type": "textfield", "key": "status"},
                {"type": "textfield", "key": "detail", "conditional": {"hide": "=status = null"}},
            ],
        }
    )
    result = validate_task_data(
        form=form,
        task_data={"status": "", "detail": "stale"},
        options_folder=OPTIONS_FOLDER,
        functions_env={},
        preserve_unknown_fields=True,
    )

    assert result.task_data == {"status": ""}


def _amount_form(condition: str) -> dict:
    return {
        "components": [
            {"type": "number", "key": "amount"},
            {"type": "textfield", "key": "detail", "validate": {"required": True}, "conditional": {"hide": condition}},
        ],
    }


@pytest.mark.parametrize(
    ("condition", "amount", "hidden"),
    [
        ("=amount > 10", 10, False),
        ("=amount > 10", 20, True),
        ("=amount >= 10", 10, True),
        ("=amount < 10", 5, True),
        ("=amount < 10", 10, False),
        ("=amount <= 10", 10, True),
        ("=10 < amount", 20, True),
        ("=10 < amount", 5, False),
        ("=amount > -1", 0, True),
        ("=amount > -1", -3, False),
    ],
)
def test__hide_if_compares_numbers_like_the_browser(condition, amount, hidden):
    """<, >, <= and >= compare numbers, as FEEL does in the browser. They used to
    be read as '=': 'amount > 10' hid the field at exactly 10 and showed it at 20."""
    result = _validate(_amount_form(condition), {"amount": amount})

    assert (_required_errors(result) == set()) is hidden


@pytest.mark.parametrize("condition", ["=amount > 10", "=amount <= 10"])
def test__a_number_comparison_on_an_unset_field_does_not_match(condition):
    """In FEEL, null compared with a number is not true - the field stays visible."""
    assert _required_errors(_validate(_amount_form(condition), {})) == {"detail"}


@pytest.mark.parametrize("condition", ['=amount > "b"', "=1 < amount < 5"])
def test__an_unsupported_comparison_is_an_error_not_a_silent_guess(condition):
    """Ordering against text, or a chain of comparisons, has no server-side meaning.
    It fails loudly instead of being evaluated as something else."""
    with pytest.raises(NotImplementedError):
        _validate(_amount_form(condition), {"amount": 2})


def _tags_form(condition: str) -> dict:
    return {
        "components": [
            {"type": "select", "key": "tags", "properties": {"custom_type": "select_multi"}, "values": AB_OPTIONS},
            {"type": "textfield", "key": "detail", "validate": {"required": True}, "conditional": {"hide": condition}},
        ],
    }


@pytest.mark.parametrize(
    ("tags", "hidden_by_null", "hidden_by_not_null"),
    [([], True, False), (["a"], False, True)],
)
def test__an_empty_multi_select_reads_as_null(tags, hidden_by_null, hidden_by_not_null):
    """A multi select with nothing chosen is empty, as in the browser: '= null'
    matches it, '!= null' does not. There was no way to test for 'nothing chosen'."""
    by_null = _validate(_tags_form("=tags = null"), {"tags": tags})
    by_not_null = _validate(_tags_form("=tags != null"), {"tags": tags})

    assert (_required_errors(by_null) == set()) is hidden_by_null
    assert (_required_errors(by_not_null) == set()) is hidden_by_not_null


@pytest.mark.parametrize("text", ["true_positive", "a=b", "null"])
def test__text_in_quotes_is_compared_as_written(text):
    """The expression is rewritten to Python before it is evaluated. Text in quotes
    used to be rewritten too ("true_positive" became "True_positive", "a=b" became
    "a==b"), so such a condition never matched."""
    form = {
        "components": [
            {"type": "textfield", "key": "kind"},
            {"type": "textfield", "key": "detail", "validate": {"required": True}, "conditional": {"hide": f'=kind = "{text}"'}},
        ],
    }

    assert not _validate(form, {"kind": text}).error_schema
    assert _required_errors(_validate(form, {"kind": "other"})) == {"detail"}


def test__submitted_data_is_not_mutated():
    """Validation works on a copy: the caller's dict looks the same afterwards."""
    submitted = {"name": "", "note": "y", "choice": "a", "amount": 1}
    snapshot = copy.deepcopy(submitted)

    _validate(REQUIRED_FIELDS_FORM, submitted)

    assert submitted == snapshot


def test__trusted_engine_data_keeps_blanks():
    """The blank rules apply to submissions only - stored engine data (e.g.
    written by a service task) passes through the cleanup untouched."""
    result = validate_task_data(
        form=transform_camunda_form(OPTIONAL_FIELDS_FORM),
        task_data={"name": "", "choice": None},
        options_folder=OPTIONS_FOLDER,
        functions_env={},
        preserve_unknown_fields=True,
    )

    assert result.task_data == {"name": "", "choice": None}


def test__attachment_objects_are_left_alone():
    """The blank walk follows the form schema and stops at attachments: an
    uploaded file's reference may legitimately carry a null mimetype, and
    nulling or dropping it would make the upload unrecognisable. Keys the
    form does not declare are not touched either."""
    schema = {
        "properties": {
            "file": {"type": "object", "properties": {"datauri": {"format": "data-url"}}},
            "name": {"type": ["string", "null"]},
        },
    }
    reference = {"id": "1", "hash": "h", "filename": "a.txt", "mimetype": None}
    data = {"file": dict(reference), "name": "", "technical": ""}

    normalize_blank_values(data, schema)

    assert data == {"file": reference, "name": None, "technical": ""}


def test__clearing_a_field_in_a_later_task_overwrites_the_stored_value():
    """The earlier task stored values; this task's user clears two of them. The
    submission carries null for both, and the merge writes null over the old
    values - the field stays empty, and a default does not come back."""
    stored = {"name": "old", "amount": 5, "choice": "a"}
    result = _validate(OPTIONAL_FIELDS_FORM, {"name": "", "amount": 5, "choice": None}, stored=stored)

    update(stored, result.task_data)

    assert stored == {"name": None, "amount": 5, "choice": None}


def test__a_key_missing_from_the_submission_deletes_nothing():
    """A missing key is not a clear: a client may send only part of the form.
    The merge keeps what it does not receive."""
    stored = {"name": "old", "result_check": {"ok": True}}
    result = _validate(OPTIONAL_FIELDS_FORM, {"amount": 5}, stored=stored)

    update(stored, result.task_data)

    assert stored == {"name": "old", "amount": 5, "result_check": {"ok": True}}


def test__disabled_values_are_kept_exactly_as_stored():
    """A disabled field belongs to the server. Whatever the client sends, the
    stored value is what the submission carries - a blank one included, it is
    not rewritten to null."""
    form = {
        "components": [
            {"type": "textfield", "key": "owner", "disabled": True},
            {"type": "textfield", "key": "remark", "disabled": True},
        ],
    }
    result = _validate(form, {"owner": "forged", "remark": "  "}, stored={"owner": "server", "remark": ""})

    assert not result.error_schema
    assert result.task_data == {"owner": "server", "remark": ""}


def _single_upload_form(required: bool) -> dict:
    field = {"type": "textfield", "key": "receipt", "properties": {"custom_type": "attachment_single"}}
    if required:
        field["validate"] = {"required": True}
    return {"components": [field]}


REFERENCE = {"id": "1", "hash": "h", "filename": "a.txt", "mimetype": "text/plain"}


def test__removing_an_optional_file_clears_the_stored_reference():
    """The browser sends null for a removed file, like for any emptied field. The
    merge then replaces the stored reference - a missing key would have kept it,
    pointing at a file the task no longer holds."""
    stored = {"receipt": dict(REFERENCE)}
    result = _validate(_single_upload_form(required=False), {"receipt": None}, stored=stored)

    update(stored, result.task_data)

    assert not result.error_schema
    assert stored == {"receipt": None}


def test__a_required_file_cannot_be_removed():
    result = _validate(_single_upload_form(required=True), {"receipt": None})

    assert "receipt" in json.dumps(result.error_schema)


def _multi_select_form() -> dict:
    """A required multi-select that a checkbox can hide."""
    return {
        "components": [
            {"type": "checkbox", "key": "flag"},
            {
                "type": "select",
                "key": "tags",
                "values": AB_OPTIONS,
                "properties": {"custom_type": "select_multi"},
                "validate": {"required": True},
                "conditional": {"hide": "=flag = true"},
            },
        ],
    }


def test__required_multi_select_needs_at_least_one_item():
    """For a multi-select, required means at least one chosen entry - an empty
    list is present in the data but carries no choice."""
    form = _multi_select_form()

    assert "tags" in json.dumps(_validate(form, {"flag": False, "tags": []}).error_schema)
    assert "tags" in json.dumps(_validate(form, {"flag": False}).error_schema)
    assert not _validate(form, {"flag": False, "tags": ["a"]}).error_schema


def test__hidden_required_multi_select_may_be_empty():
    """flag is true, so tags is hidden. The empty list is no error and tags is
    dropped."""
    result = _validate(_multi_select_form(), {"flag": True, "tags": []})

    assert not result.error_schema
    assert "tags" not in result.task_data
