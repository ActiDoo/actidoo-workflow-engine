# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""How submitted form data behaves: hide-if visibility, empty values and required.

One module on purpose: every detail rule about what a submission means lives here,
next to its neighbours. Sections:

1. Hide-if semantics - the validation must reach the same visibility verdict as the
   frontend's FEEL evaluation.
2. Empty values - an emptied field is null and a blank does not satisfy ``required``.

Hide-if ground rules:

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

import copy
import json
import re
from pathlib import Path

import pytest

from actidoo_wfe.wf.constants import ROW_ID_KEY
from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import normalize_blank_values, validate_task_data

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


EMPTY_STRING_FORM = {
    # Older forms compare against "" to mean "empty". An empty field is null, never "",
    # so both sides read such a comparison as one against null.
    "components": [
        {"type": "textfield", "key": "comment", "disabled": True},
        {"type": "textfield", "key": "note", "conditional": {"hide": '=comment = ""'}},
        {"type": "textfield", "key": "reminder", "validate": {"required": True}, "conditional": {"hide": '=comment != ""'}},
    ],
}

EQUALITY_REFERENCE_FORM = {
    # An equality against a plain optional reference: an unset reference is FEEL null,
    # and null = "a" is false - so the dependent field stays visible and required.
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


def test__comparison_against_the_empty_string_reads_as_null():
    # comment is unset: '= ""' matches (note hidden), '!= ""' does not (reminder visible).
    result = _validate(EMPTY_STRING_FORM, {"note": "n"}, stored={})

    assert "note" not in result.task_data
    assert "reminder" in (result.error_schema or {})


def test__comparison_against_the_empty_string_with_a_value_set():
    # comment holds a value: '= ""' does not match (note visible), '!= ""' does (reminder hidden).
    result = _validate(EMPTY_STRING_FORM, {"note": "n"}, stored={"comment": "x"})

    assert not result.error_schema
    assert result.task_data["note"] == "n"


def test__equality_against_unset_reference_leaves_field_visible_and_required():
    result = _validate(EQUALITY_REFERENCE_FORM, {})

    assert "detail" in (result.error_schema or {})


def test__equality_against_unset_reference_keeps_the_submitted_value():
    result = _validate(EQUALITY_REFERENCE_FORM, {"detail": "b"})

    assert not result.error_schema
    assert result.task_data["detail"] == "b"


def test__equality_against_matching_reference_hides_the_field():
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

LIST_FORM = {
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


MULTI_SELECT_FORM = {
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


def _required_errors(result) -> set[str]:
    """Names of the fields reported as missing (the error dict nests required errors)."""
    return set(re.findall(r"'([^']+)' is a required property", json.dumps(result.error_schema or {})))


def _submit(form: dict, task_data: dict):
    return validate_task_data(
        form=transform_camunda_form(form),
        task_data=task_data,
        options_folder=OPTIONS_FOLDER,
        functions_env={},
        authoritative_disabled_values={},
    )


def test__emptied_fields_are_nullable_in_the_schema():
    form = transform_camunda_form(OPTIONAL_FIELDS_FORM)

    assert form.jsonschema["properties"]["name"]["type"] == ["string", "null"]
    assert form.jsonschema["properties"]["amount"]["type"] == ["number", "null"]
    assert form.uischema["name"]["ui:emptyValue"] is None
    assert form.uischema["amount"]["ui:emptyValue"] is None


@pytest.mark.parametrize("field", ["name", "note", "choice", "amount"])
@pytest.mark.parametrize("blank", BLANKS)
def test__blank_in_required_field_is_a_required_error(field, blank):
    result = _submit(REQUIRED_FIELDS_FORM, {**FILLED, field: blank})

    assert _required_errors(result) == {field}
    assert field not in result.task_data


def test__filled_required_fields_pass():
    result = _submit(REQUIRED_FIELDS_FORM, FILLED)

    assert not result.error_schema
    assert result.task_data == FILLED


@pytest.mark.parametrize("blank", BLANKS)
def test__blank_in_optional_field_is_stored_as_null(blank):
    # null overwrites the earlier value in the merge - that is what clears a field.
    result = _submit(OPTIONAL_FIELDS_FORM, {"name": blank, "amount": blank, "choice": blank})

    assert not result.error_schema
    assert result.task_data == {"name": None, "amount": None, "choice": None}


def test__a_blank_where_the_schema_admits_no_null_is_dropped():
    result = _submit(OPTIONAL_FIELDS_FORM, {"kind": ""})

    assert not result.error_schema
    assert "kind" not in result.task_data


def test__values_are_never_trimmed():
    result = _submit(OPTIONAL_FIELDS_FORM, {"name": "  padded  "})

    assert result.task_data["name"] == "  padded  "


def test__blanks_inside_list_rows():
    result = _submit(LIST_FORM, {"rows": [{"label": "ok", "remark": "  "}, {"label": " ", "remark": "kept"}]})

    assert _required_errors(result) == {"label"}
    assert result.task_data["rows"][0] == {"label": "ok", "remark": None}
    assert result.task_data["rows"][1] == {"remark": "kept"}


def test__blank_reference_reads_as_unset_in_hide_if():
    form = {
        "components": [
            {"type": "textfield", "key": "mode"},
            {"type": "textfield", "key": "detail", "validate": {"required": True}, "conditional": {"hide": "=mode = null"}},
        ],
    }

    # detail is hidden while mode is unset; a blank mode is no mode, so detail stays hidden.
    assert not _submit(form, {"mode": "   ", "detail": "x"}).error_schema
    assert "detail" not in _submit(form, {"mode": "   ", "detail": "x"}).task_data
    assert _required_errors(_submit(form, {"mode": "on"})) == {"detail"}


def test__submitted_data_is_not_mutated():
    submitted = {"name": "", "note": "y", "choice": "a", "amount": 1}
    snapshot = copy.deepcopy(submitted)

    _submit(REQUIRED_FIELDS_FORM, submitted)

    assert submitted == snapshot


def test__trusted_engine_data_keeps_blanks():
    result = validate_task_data(
        form=transform_camunda_form(OPTIONAL_FIELDS_FORM),
        task_data={"name": "", "choice": None},
        options_folder=OPTIONS_FOLDER,
        functions_env={},
        preserve_unknown_fields=True,
    )

    assert result.task_data == {"name": "", "choice": None}


def test__attachment_objects_are_left_alone():
    # An uploaded file arrives as a reference whose mimetype may legitimately be None;
    # nulling or dropping it would make the upload unrecognisable.
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


def test__required_multi_select_needs_at_least_one_item():
    # [] is a value (the list exists), so 'required' alone would let it pass.
    assert "tags" in json.dumps(_submit(MULTI_SELECT_FORM, {"flag": False, "tags": []}).error_schema)
    assert "tags" in json.dumps(_submit(MULTI_SELECT_FORM, {"flag": False}).error_schema)
    assert not _submit(MULTI_SELECT_FORM, {"flag": False, "tags": ["a"]}).error_schema


def test__hidden_required_multi_select_may_be_empty():
    result = _submit(MULTI_SELECT_FORM, {"flag": True, "tags": []})

    assert not result.error_schema
    assert "tags" not in result.task_data
