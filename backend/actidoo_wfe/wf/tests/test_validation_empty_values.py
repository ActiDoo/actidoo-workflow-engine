# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH
"""An emptied field is null, and a blank does not satisfy ``required``.

The browser sends null for a field the user cleared and the schema admits it, so the
merge into the stored data overwrites the old value. A submitted blank - null, an
empty or a whitespace-only string - is user input meaning "nothing entered": it is
stored as null, and where the field is required (or admits no null) it is dropped so
that the schema reports it. Trusted engine data is not touched.
"""

import copy
import json
import re
from pathlib import Path

import pytest

from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import normalize_blank_values, validate_task_data

OPTIONS_FOLDER = Path(__file__).parent / "options"

AB_OPTIONS = [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}]

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
