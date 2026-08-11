# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Dynamic-list row identity (ADR 010) at the validation level.

Persisted form schemas never contain the technical ROW_ID_KEY: submission
validation admits the submitted IDs through a throwaway validation schema,
disabled fields resolve to their effective value (stored, else the declared
default) matched per row, duplicated IDs reject, and the monitored
``row-id-merge-fallback`` marker fires only for genuine ID-less dynamic-list
submissions. The merge itself is covered in ``test_task_update.py``.
"""

import copy
import logging
from pathlib import Path

from actidoo_wfe.wf.constants import ROW_ID_KEY
from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import (
    inject_row_ids_into_validation_schema,
    validate_task_data,
)
from actidoo_wfe.wf.service_workflow import warn_id_less_dynamic_list_submissions

OPTIONS_FOLDER = Path(__file__).parent / "options"

NESTED_LIST_FORM = {
    "components": [
        {
            "type": "dynamiclist",
            "path": "outer",
            "components": [
                {"type": "textfield", "key": "name"},
                {
                    "type": "dynamiclist",
                    "path": "inner",
                    "components": [{"type": "textfield", "key": "note"}],
                },
            ],
        },
    ],
}

FORCED_ASSIGNMENT_FORM = {
    "components": [
        {"type": "textfield", "key": "note"},
        {"type": "textfield", "key": "forced_type", "disabled": True, "defaultValue": "K"},
        {"type": "textfield", "key": "backend_stamped", "disabled": True},
    ],
}

DYNAMIC_LIST_FORM = {
    "components": [
        {
            "type": "dynamiclist",
            "path": "positions",
            "components": [
                {"type": "textfield", "key": "name"},
                {"type": "textfield", "key": "pos_type", "disabled": True, "defaultValue": "K"},
                {"type": "textfield", "key": "asset_number", "disabled": True},
            ],
        },
    ],
}


def _validate(form: dict, task_data: dict, stored: dict | None = None):
    return validate_task_data(
        form=transform_camunda_form(form),
        task_data=task_data,
        options_folder=OPTIONS_FOLDER,
        functions_env={},
        authoritative_disabled_values=stored if stored is not None else {},
    )


# --- transient schema admission -------------------------------------------------


def test__transformed_schemas_do_not_contain_the_technical_field():
    form = transform_camunda_form(NESTED_LIST_FORM)

    outer_items = form.jsonschema["properties"]["outer"]["items"]
    assert ROW_ID_KEY not in outer_items["properties"]
    assert ROW_ID_KEY not in outer_items["properties"]["inner"]["items"]["properties"]
    assert ROW_ID_KEY not in form.uischema["outer"]["items"]


def test__injection_covers_nested_lists_and_leaves_the_uischema_alone():
    form = transform_camunda_form(NESTED_LIST_FORM)
    uischema_reference = copy.deepcopy(form.uischema)

    inject_row_ids_into_validation_schema(form.jsonschema, form.uischema)

    outer_items = form.jsonschema["properties"]["outer"]["items"]
    assert outer_items["properties"][ROW_ID_KEY] == {"type": "string"}
    assert outer_items["properties"]["inner"]["items"]["properties"][ROW_ID_KEY] == {"type": "string"}
    # The uischema is the read-only detector - it must never be mutated.
    assert form.uischema == uischema_reference


def test__injection_is_idempotent():
    form = transform_camunda_form(NESTED_LIST_FORM)

    inject_row_ids_into_validation_schema(form.jsonschema, form.uischema)
    reference = copy.deepcopy(form.jsonschema)
    inject_row_ids_into_validation_schema(form.jsonschema, form.uischema)

    assert form.jsonschema == reference


def test__non_dynamiclist_arrays_stay_untouched():
    # Array of objects without the dynamic-list uischema signature (like
    # attachment uploads) must not be mistaken for a dynamic list.
    jsonschema = {
        "type": "object",
        "properties": {
            "uploads": {
                "type": "array",
                "items": {"type": "object", "properties": {"filename": {"type": "string"}}},
            },
        },
    }
    uischema = {"uploads": {"ui:field": "AttachmentMulti"}}
    reference = copy.deepcopy(jsonschema)

    inject_row_ids_into_validation_schema(jsonschema, uischema)

    assert jsonschema == reference


# --- effective values of disabled fields ----------------------------------------


def test__stored_value_beats_the_default():
    result = _validate(FORCED_ASSIGNMENT_FORM, {"note": "x", "forced_type": "garbage"}, stored={"forced_type": "C"})

    assert not result.error_schema
    assert result.task_data["forced_type"] == "C"


def test__default_fills_in_when_nothing_is_stored():
    result = _validate(FORCED_ASSIGNMENT_FORM, {"note": "x"}, stored={})

    assert not result.error_schema
    assert result.task_data["forced_type"] == "K"


def test__submitted_value_never_wins_over_the_default():
    result = _validate(FORCED_ASSIGNMENT_FORM, {"forced_type": "forged"}, stored={})

    assert result.task_data["forced_type"] == "K"


def test__no_default_and_nothing_stored_stays_absent():
    result = _validate(FORCED_ASSIGNMENT_FORM, {"note": "x"}, stored={})

    assert not result.error_schema
    assert "backend_stamped" not in result.task_data


def test__hidden_disabled_field_default_is_not_persisted():
    """A forced assignment applies to what the user's action produces - a field
    that is currently hidden is not part of it. Its default must be stripped
    like any other hidden value instead of flip-flopping into task data."""
    hidden_forced_form = {
        "components": [
            {
                "type": "select",
                "key": "mode",
                "values": [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
            },
            {
                "type": "textfield",
                "key": "fee",
                "disabled": True,
                "defaultValue": "100",
                "conditional": {"hide": '=mode != "b"'},
            },
        ],
    }

    hidden = _validate(hidden_forced_form, {"mode": "a"}, stored={})
    assert not hidden.error_schema
    assert "fee" not in hidden.task_data

    visible = _validate(hidden_forced_form, {"mode": "b"}, stored={})
    assert visible.task_data["fee"] == "100"


# --- per-row matching -----------------------------------------------------------


def test__added_row_gets_the_forced_assignment():
    stored = {"positions": [{"_row_id": "r1", "name": "a", "pos_type": "C", "asset_number": "A-1"}]}
    submitted = {
        "positions": [
            {"_row_id": "r1", "name": "a"},
            {"_row_id": "r2", "name": "b"},
        ],
    }

    result = _validate(DYNAMIC_LIST_FORM, submitted, stored=stored)

    assert not result.error_schema
    rows = result.task_data["positions"]
    # Existing row: stored value wins, matched by ID.
    assert rows[0]["pos_type"] == "C"
    # Added row: no stored counterpart, the declared default is the forced value.
    assert rows[1]["pos_type"] == "K"
    # No default and nothing stored: stays absent until the backend fills it.
    assert "asset_number" not in rows[1]


def test__deleting_a_row_does_not_shift_backend_values_onto_neighbors():
    stored = {
        "positions": [
            {"_row_id": "r1", "name": "a", "asset_number": "A-1"},
            {"_row_id": "r2", "name": "b", "asset_number": "A-2"},
            {"_row_id": "r3", "name": "c", "asset_number": "A-3"},
        ],
    }
    submitted = {"positions": [{"_row_id": "r1", "name": "a"}, {"_row_id": "r3", "name": "c"}]}

    result = _validate(DYNAMIC_LIST_FORM, submitted, stored=stored)

    rows = result.task_data["positions"]
    assert rows[0]["asset_number"] == "A-1"
    assert rows[1]["asset_number"] == "A-3"  # index alignment would say A-2


def test__id_less_row_in_an_id_carrying_list_does_not_inherit_neighbor_values():
    """A row without an ID inside a list whose stored rows carry IDs is a NEW
    row (e.g. appended by an API client). It must not be index-matched onto a
    stored neighbor - that would graft foreign backend-owned values onto it."""
    stored = {
        "positions": [
            {"_row_id": "r1", "name": "a", "asset_number": "A-1"},
            {"_row_id": "r2", "name": "b", "asset_number": "A-2"},
        ],
    }
    submitted = {
        "positions": [
            {"_row_id": "r1", "name": "a"},
            {"name": "new row without id"},
        ],
    }

    result = _validate(DYNAMIC_LIST_FORM, submitted, stored=stored)

    rows = result.task_data["positions"]
    assert rows[0]["asset_number"] == "A-1"
    assert "asset_number" not in rows[1]


def test__fully_id_less_submission_still_index_matches_stamped_stored_rows():
    """Legacy client on an already-stamped instance: the whole submission has
    no IDs, so index matching (the status quo) must keep restoring values."""
    stored = {"positions": [{"_row_id": "r1", "name": "a", "asset_number": "A-1"}]}
    submitted = {"positions": [{"name": "a"}]}

    result = _validate(DYNAMIC_LIST_FORM, submitted, stored=stored)

    assert result.task_data["positions"][0]["asset_number"] == "A-1"


# --- duplicate IDs --------------------------------------------------------------


def test__duplicate_row_ids_are_a_validation_error():
    submitted = {
        "positions": [
            {"_row_id": "dup", "name": "a"},
            {"_row_id": "dup", "name": "b"},
        ],
    }

    result = _validate(DYNAMIC_LIST_FORM, submitted, stored={})

    assert result.error_schema is not None


def test__hidden_lists_keep_their_data_so_their_duplicates_still_reject():
    """Hidden dynamic lists are NOT stripped by the engine (only scalar hidden
    fields are) - their rows reach the merge and get persisted. The duplicate
    check therefore must guard hidden lists too. The check runs after hidden-
    value removal on purpose: whatever IS stripped can no longer reject."""
    hidden_list_form = {
        "components": [
            {
                "type": "select",
                "key": "mode",
                "values": [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
            },
            {
                "type": "dynamiclist",
                "path": "positions",
                "conditional": {"hide": '=mode != "b"'},
                "components": [{"type": "textfield", "key": "name"}],
            },
        ],
    }
    submitted = {
        "mode": "a",
        "positions": [
            {"_row_id": "dup", "name": "x"},
            {"_row_id": "dup", "name": "y"},
        ],
    }

    result = _validate(hidden_list_form, submitted, stored={})

    # The hidden list's rows survive cleaning (pre-existing engine behavior) ...
    assert result.task_data["positions"][0]["name"] == "x"
    # ... so an ambiguous identity inside it must still block the submission.
    assert result.error_schema is not None


# --- fallback-warning marker ----------------------------------------------------

DYNAMIC_LIST_UISCHEMA = {
    "ui:field": "layout",
    "ui:layout": {},
    "positions": {
        "items": {"ui:field": "layout", "ui:layout": {}},
        "ui:label": "Positions",
    },
    "uploads": {"ui:field": "AttachmentMulti"},
}


def test__update_itself_never_logs_the_fallback_marker(caplog):
    from actidoo_wfe.wf.service_workflow import update

    # Attachment arrays and service-task lists flow through update() on every
    # submission and can never carry IDs - the marker must not fire here.
    with caplog.at_level(logging.WARNING):
        update({"uploads": [{"filename": "old.pdf"}]}, {"uploads": [{"filename": "new.pdf"}]})

    assert "row-id-merge-fallback" not in caplog.text


def test__marker_fires_for_id_less_dynamic_list_submission(caplog):
    data = {
        "positions": [{"name": "x"}],
        "uploads": [{"filename": "new.pdf"}],
    }

    with caplog.at_level(logging.WARNING):
        warn_id_less_dynamic_list_submissions(DYNAMIC_LIST_UISCHEMA, data)

    assert "row-id-merge-fallback" in caplog.text
    assert "positions" in caplog.text
    assert "uploads" not in caplog.text


def test__marker_stays_quiet_for_stamped_submissions(caplog):
    data = {
        "positions": [{"_row_id": "r1", "name": "x"}],
        "uploads": [{"filename": "new.pdf"}],
    }

    with caplog.at_level(logging.WARNING):
        warn_id_less_dynamic_list_submissions(DYNAMIC_LIST_UISCHEMA, data)

    assert "row-id-merge-fallback" not in caplog.text
