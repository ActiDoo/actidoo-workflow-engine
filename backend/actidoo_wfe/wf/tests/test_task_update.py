# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import pytest

from actidoo_wfe.wf.service_workflow import update
from actidoo_wfe.wf.tests.helpers.dicts import are_dicts_equal

task_data = {
    "instance_id": "9ffcbf6b-8844-4e4c-aa1b-245bb9f01bea",
    "translation_languages": None,  # real world example for an initial multi-select
    "some_other_translaction_languaes": ["ae", "az", "as", "de"],
    "updated_translation_languages": ["ae", "az", "as", "de"],
    "some_other_list_type_dict": "Overwrite my with a list of objects",
    "some_other_list_type_string": "Overwrite my with a list of string",
    "positions": [
        {
            "position_description": "Meine Ware Nr. 1",
            "position_material": "Mat123",
            "position_tariff_number": "__ALT__",
            "position_origin": "__SAME__",
        },
    ],
    "list_to_be_updated": [
        {
            "old_value": "will_be_kept",
            "update_me": "kick me",
        },
    ],
    "list_to_be_truncated": [
        {
            "aaa": "bbb",
        },
        {
            "ddd": "eee",
        },
        {
            "fff": "ggg",
        },
    ],
    "new_list_to_replace_none": None,
    "client_reference_code": "ref123",
    "some_old_dict": {
        "a": "b",
        "c": "d",
    },
}

cleaned_task_data = {
    "translation_languages": ["ae", "az", "as", "de"],
    "new_translation_languages": ["ae", "az", "as", "de"],
    "updated_translation_languages": ["de"],
    "some_other_list_type_dict": [{"x": "y"}],
    "some_other_list_type_string": ["a", "b"],
    "positions": [{"position_tariff_number": "__NEU__", "position_origin": "__SAME__", "position_dangerous": "__CREATED__"}],
    "new_list": [
        {
            "new_list_key": "new_list_value",
        },
        {
            "new_list_key2": "new_list_value2",
        },
    ],
    "list_to_be_updated": [{"update_me": "new_value", "this_is_a_new_key": "with_a_new_value"}, {"a": "c", "d": "e"}],
    "list_to_be_truncated": [
        # Without row IDs the merge cannot know WHICH element was removed and
        # assumes it was the last one. The row-id merge (ADR 010) solved this -
        # deletion is explicit there; this fixture deliberately exercises the
        # remaining ID-less legacy fallback, where the ambiguity is by design.
        {
            "aaa": "bbb",
        },
        {
            "ddd": "xyz",
        },
    ],
    "new_list_to_replace_none": [
        {
            "some": "thing",
        },
        {
            "peter": "pan",
        },
    ],
    "some_old_dict": {"a": "z", "fresh": "breeze"},
    "some_new_dict": {"c": "d"},
}


task_data_EXPECTED = {
    "instance_id": "9ffcbf6b-8844-4e4c-aa1b-245bb9f01bea",
    "translation_languages": ["ae", "az", "as", "de"],
    "some_other_translaction_languaes": ["ae", "az", "as", "de"],
    "new_translation_languages": ["ae", "az", "as", "de"],
    "updated_translation_languages": ["de"],
    "some_other_list_type_dict": [{"x": "y"}],
    "some_other_list_type_string": ["a", "b"],
    "positions": [{"position_description": "Meine Ware Nr. 1", "position_material": "Mat123", "position_tariff_number": "__NEU__", "position_origin": "__SAME__", "position_dangerous": "__CREATED__"}],
    "new_list": [
        {
            "new_list_key": "new_list_value",
        },
        {
            "new_list_key2": "new_list_value2",
        },
    ],
    "list_to_be_updated": [{"old_value": "will_be_kept", "update_me": "new_value", "this_is_a_new_key": "with_a_new_value"}, {"a": "c", "d": "e"}],
    "list_to_be_truncated": [
        {
            "aaa": "bbb",
        },
        {
            "ddd": "xyz",
        },
    ],
    "new_list_to_replace_none": [
        {
            "some": "thing",
        },
        {
            "peter": "pan",
        },
    ],
    "client_reference_code": "ref123",
    "some_old_dict": {"a": "z", "c": "d", "fresh": "breeze"},
    "some_new_dict": {"c": "d"},
}


def test_task_data_will_be_updated_as_expected():
    update(task_data, cleaned_task_data)

    print(task_data)

    print(are_dicts_equal(task_data_EXPECTED, task_data, True))


# ==================== ROW-ID MERGE (ADR 010) ====================
# Lists of dicts whose submitted items carry a _row_id are merged by identity:
# order and existence follow the submission, backend-owned values return to
# their own row only.


def test_row_id_merge_restores_stored_values_per_row():
    stored = {
        "positions": [
            {"_row_id": "r1", "asset_number": "A-1", "amount": 1},
            {"_row_id": "r2", "asset_number": "A-2", "amount": 2},
        ],
    }
    submitted = {
        "positions": [
            {"_row_id": "r1", "amount": 10},
            {"_row_id": "r2", "amount": 20},
        ],
    }

    update(stored, submitted)

    assert stored["positions"] == [
        {"_row_id": "r1", "asset_number": "A-1", "amount": 10},
        {"_row_id": "r2", "asset_number": "A-2", "amount": 20},
    ]


def test_row_id_merge_deleting_middle_row_does_not_mix_neighbors():
    stored = {
        "positions": [
            {"_row_id": "r1", "asset_number": "A-1"},
            {"_row_id": "r2", "asset_number": "A-2"},
            {"_row_id": "r3", "asset_number": "A-3"},
        ],
    }
    submitted = {"positions": [{"_row_id": "r1"}, {"_row_id": "r3"}]}

    update(stored, submitted)

    # The row after the deleted one keeps ITS OWN backend value - the index
    # merge would have grafted A-2 onto it.
    assert stored["positions"] == [
        {"_row_id": "r1", "asset_number": "A-1"},
        {"_row_id": "r3", "asset_number": "A-3"},
    ]


def test_row_id_merge_added_row_keeps_exactly_the_submitted_values():
    stored = {"positions": [{"_row_id": "r1", "asset_number": "A-1"}]}
    submitted = {
        "positions": [
            {"_row_id": "r1"},
            {"_row_id": "new-row", "amount": 5},
        ],
    }

    update(stored, submitted)

    assert stored["positions"][1] == {"_row_id": "new-row", "amount": 5}


def test_row_id_merge_forged_id_cannot_pull_another_rows_values():
    stored = {"positions": [{"_row_id": "r1", "asset_number": "SECRET"}]}
    submitted = {"positions": [{"_row_id": "r1"}, {"_row_id": "forged", "amount": 1}]}

    update(stored, submitted)

    assert "asset_number" not in stored["positions"][1]


def test_row_id_merge_reordering_keeps_rows_intact():
    stored = {
        "positions": [
            {"_row_id": "r1", "asset_number": "A-1"},
            {"_row_id": "r2", "asset_number": "A-2"},
        ],
    }
    submitted = {"positions": [{"_row_id": "r2"}, {"_row_id": "r1"}]}

    update(stored, submitted)

    assert stored["positions"] == [
        {"_row_id": "r2", "asset_number": "A-2"},
        {"_row_id": "r1", "asset_number": "A-1"},
    ]


def test_row_id_merge_recurses_into_nested_lists():
    stored = {
        "positions": [
            {
                "_row_id": "r1",
                "sub_items": [
                    {"_row_id": "s1", "hidden_value": "keep-me"},
                    {"_row_id": "s2", "hidden_value": "drop-me"},
                ],
            },
        ],
    }
    submitted = {
        "positions": [
            {"_row_id": "r1", "sub_items": [{"_row_id": "s1", "note": "x"}]},
        ],
    }

    update(stored, submitted)

    assert stored["positions"][0]["sub_items"] == [{"_row_id": "s1", "hidden_value": "keep-me", "note": "x"}]


def test_row_id_merge_rejects_non_object_rows():
    """Rows of a dynamic list must be objects. Hidden lists bypass item-type
    validation, so the merge is the last line of defense - persisting junk
    silently would crash downstream consumers much later."""
    stored = {"positions": [{"_row_id": "r1", "asset_number": "A-1"}]}
    submitted = {"positions": [{"_row_id": "r1"}, "junk"]}

    with pytest.raises(TypeError):
        update(stored, submitted)


def test_list_without_row_ids_falls_back_to_index_merge():
    stored = {"positions": [{"a": 1}, {"a": 2}]}
    submitted = {"positions": [{"b": 9}]}

    update(stored, submitted)

    assert stored["positions"] == [{"a": 1, "b": 9}]


def test_rollout_window_stored_rows_without_ids_are_index_matched():
    """Rollout window: stored data predates the rollout (no IDs), but the new
    frontend stamps fresh UUIDs onto the delivered rows before submitting.
    The merge must fall back to index matching - treating every row as 'new'
    would silently drop all backend-owned values of every row."""
    stored = {
        "positions": [
            {"asset_number": "A-1", "amount": 1},
            {"asset_number": "A-2", "amount": 2},
        ],
    }
    submitted = {
        "positions": [
            {"_row_id": "fresh-1", "amount": 10},
            {"_row_id": "fresh-2", "amount": 20},
        ],
    }

    update(stored, submitted)

    assert stored["positions"][0]["asset_number"] == "A-1"
    assert stored["positions"][1]["asset_number"] == "A-2"
    assert stored["positions"][0]["amount"] == 10
    assert stored["positions"][1]["amount"] == 20
    # The merged rows keep the submitted IDs, so the next submission ID-matches.
    assert stored["positions"][0]["_row_id"] == "fresh-1"
