# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Server-side hide-if semantics of ``validate_task_data`` for submitted task data.

The validation must reach the same visibility verdict as the frontend's FEEL
evaluation:

- A missing reference value counts as null: ``null = x`` is false, ``null != x``
  is true, and comparisons against the ``null`` literal match exactly the unset
  case.
- Disabled references cannot be trusted from the client: their effective values
  come from ``authoritative_disabled_values`` (the task's stored data), falling
  back to the schema default, and stay in the result (ADR 010).
- Values submitted for hidden fields are dropped without raising errors, while
  visible required fields stay required.
"""

import json
from pathlib import Path

import pytest

from actidoo_wfe.wf.constants import ROW_ID_KEY
from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import MAX_MIXED_LEVEL_HIDE_IF_COMPARISONS, validate_task_data

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

MIXED_AND_FORM = {
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


def test__garbage_in_disabled_field_is_replaced_by_the_stored_value():
    result = _validate(
        DISABLED_REFERENCE_FORM,
        {"testclass": "NOT_A_VALID_OPTION", "approval": "approved"},
        stored={"testclass": "b"},
    )

    assert not result.error_schema
    assert result.task_data["testclass"] == "b"


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


LIST_OR_CONDITION_FORM = {
    # Regression: multi-condition hide-if in a dynamic list must be evaluated per item.
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

MISSING_REFERENCE_FORM = {
    # A hide-if that references a field which no longer exists in the form at all (e.g. a
    # checkbox was removed but its paired select still guards on it). FEEL treats the missing
    # reference as null: 'null = false' is false, so the field stays visible — and, crucially,
    # building the schema must not raise.
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


def test__list_or_condition_is_evaluated_per_item():
    result = _validate(
        LIST_OR_CONDITION_FORM,
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
    # Regression: an absent reference used to raise and 500 the request. It must now behave
    # like FEEL null — 'null = false' is false, so the field is visible and its required rule
    # applies, instead of crashing the whole submit/advance.
    result = _validate(MISSING_REFERENCE_FORM, {})

    assert "subarea" in (result.error_schema or {})


SCOPED_REFERENCE_FORM = {
    # 'this.' binds to the row the field itself lives in, and 'parent.' to the surrounding one -
    # exactly like the frontend binds them. 'flag' sits two levels up, so 'this.flag' names nothing
    # and counts as unset (FEEL null): 'null = false' is false and the field stays visible.
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
                        {"type": "textfield", "key": "scoped_note", "conditional": {"hide": "=parent.flag = false"}},
                    ],
                },
            ],
        },
    ],
}


def test__this_reference_does_not_reach_into_an_outer_row():
    result = _validate(SCOPED_REFERENCE_FORM, {"outer": [{"flag": False, "inner": [{"note": "kept"}]}]})

    assert not result.error_schema
    assert result.task_data["outer"][0]["inner"][0]["note"] == "kept"


def test__parent_reference_addresses_the_surrounding_row():
    result = _validate(SCOPED_REFERENCE_FORM, {"outer": [{"flag": False, "inner": [{"scoped_note": "dropped"}]}]})

    assert not result.error_schema
    assert "scoped_note" not in result.task_data["outer"][0]["inner"][0]


# --- hide-if on the dynamic list itself -----------------------------------------

HIDDEN_LIST_FORM = {
    # The hide-if sits on the list, not on a field inside it. A dynamic list is an array of
    # objects and used to take the recursion branch only, so its own condition was never
    # converted: the list stayed validated (and persisted) as if it were visible.
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

NESTED_HIDDEN_LIST_FORM = {
    # The inner list is hidden by a field of the surrounding row, so visibility differs per row.
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

HIDDEN_ATTACHMENT_FORM = {
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


def test__hidden_list_does_not_enforce_min_items():
    result = _validate(HIDDEN_LIST_FORM, {"variant": "a", "positions": []})

    assert not result.error_schema
    assert "positions" not in result.task_data


def test__rows_submitted_for_a_hidden_list_are_stripped_without_error():
    result = _validate(HIDDEN_LIST_FORM, {"variant": "a", "positions": [{"name": "x"}]})

    assert not result.error_schema
    assert "positions" not in result.task_data


def test__hidden_list_does_not_enforce_required_fields_of_its_rows():
    result = _validate(HIDDEN_LIST_FORM, {"variant": "a", "positions": [{}]})

    assert not result.error_schema
    assert "positions" not in result.task_data


def test__visible_list_still_enforces_min_items():
    result = _validate(HIDDEN_LIST_FORM, {"variant": "b", "positions": []})

    assert "positions" in (result.error_schema or {})


def test__visible_list_still_enforces_required_fields_of_its_rows():
    result = _validate(HIDDEN_LIST_FORM, {"variant": "b", "positions": [{}]})

    assert "positions" in (result.error_schema or {})


def test__visible_list_keeps_its_rows():
    result = _validate(HIDDEN_LIST_FORM, {"variant": "b", "positions": [{"name": "x"}]})

    assert not result.error_schema
    assert result.task_data["positions"] == [{"name": "x"}]


def test__nested_hidden_list_is_evaluated_per_row():
    result = _validate(
        NESTED_HIDDEN_LIST_FORM,
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
    result = _validate(HIDDEN_ATTACHMENT_FORM, {"variant": "a", "docs": []})

    assert not result.error_schema
    assert "docs" not in result.task_data


def test__hidden_list_leaves_no_row_skeleton_in_stored_task_data():
    # The engine-side cleanup (strip_hidden_field_values) preserves unknown/technical fields
    # such as the row id. Those must not resurrect the very rows the hide-if just removed.
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
    result = _validate(MIXED_OR_FORM, {"rootflag": "a", "rows": [{"n": 1, "note": "dropped"}]})

    assert not result.error_schema
    assert "note" not in result.task_data["rows"][0]


def test__or_across_levels_hides_per_row_when_the_row_operand_holds():
    result = _validate(MIXED_OR_FORM, {"rootflag": "b", "rows": [{"n": 9, "note": "dropped"}, {"n": 1, "note": "kept"}]})

    assert not result.error_schema
    assert "note" not in result.task_data["rows"][0]
    assert result.task_data["rows"][1]["note"] == "kept"


def test__or_across_levels_requires_the_field_when_neither_operand_holds():
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


def _mixed_level_form(comparisons: int) -> dict:
    """A row field hidden by alternating root and row comparisons."""
    parts = [f'root{i} = "x"' if i % 2 else f"this.n{i} = 1" for i in range(comparisons)]
    return {
        "components": [
            *[{"type": "textfield", "key": f"root{i}"} for i in range(1, comparisons, 2)],
            {
                "type": "dynamiclist",
                "path": "rows",
                "components": [
                    *[{"type": "number", "key": f"n{i}"} for i in range(0, comparisons, 2)],
                    {"type": "textfield", "key": "note", "conditional": {"hide": "=" + " or ".join(parts)}},
                ],
            },
        ],
    }


def test__a_mixed_level_condition_has_a_limit_of_comparisons():
    """A condition across levels becomes a decision tree that grows with every
    comparison. Up to the limit it works; above it, the form fails with a clear
    message instead of building a huge schema."""
    within = _validate(_mixed_level_form(MAX_MIXED_LEVEL_HIDE_IF_COMPARISONS), {"rows": [{"n0": 1, "note": "x"}]})
    assert "note" not in within.task_data["rows"][0]

    with pytest.raises(NotImplementedError, match="at most"):
        _validate(_mixed_level_form(MAX_MIXED_LEVEL_HIDE_IF_COMPARISONS + 1), {"rows": [{"n0": 1}]})


def test__and_across_levels_hides_only_when_both_operands_hold():
    both = _validate(MIXED_AND_FORM, {"rootflag": "a", "rows": [{"n": 9, "note": "dropped"}]})
    only_root = _validate(MIXED_AND_FORM, {"rootflag": "a", "rows": [{"n": 1, "note": "kept"}]})
    only_row = _validate(MIXED_AND_FORM, {"rootflag": "b", "rows": [{"n": 9, "note": "kept"}]})

    assert "note" not in both.task_data["rows"][0]
    assert only_root.task_data["rows"][0]["note"] == "kept"
    assert only_row.task_data["rows"][0]["note"] == "kept"
