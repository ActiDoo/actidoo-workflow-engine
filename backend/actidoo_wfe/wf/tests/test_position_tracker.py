# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import copy

import pytest

from actidoo_wfe.helpers.collections import remove_item
from actidoo_wfe.helpers.json_traverse import get_position_tracker

TEST_DATA = {
    "mission_sector": "deep_space_lab",
    "task_queue": [
        {
            "quantity_requested": 8,
            "unit": "modules",
        }
    ],
    "summary_title": "Prototype Calibration Run",
    "lead_scientist": "Dr. Ada Vector",
    "support_files": [
        {"id": "logbook-entry-1", "hash": "0c9c721ee2c648ef919c6ccb0b5d78d3", "filename": "log_entry.txt", "mimetype": "text/plain"},
        {"id": "blueprint-draft-A", "hash": "63a11f7ad5a74764a28dcb457a0fc8d9", "filename": "assembly_blueprint.pdf", "mimetype": "application/pdf"},
    ],
    "primary_reviewer": "reviewer.delta@example.com",
    "backup_reviewer": "reviewer.epsilon@example.com",
    "external_observer": "observer.zeta@example.com",
    "config_bundle": {
        "phase": "initialization",
        "stage": "simulation",
        "checkpoint": {"status": "draft"},
    },
    "payloads": [
        {
            "systems": [
                {
                    "quotes": [
                        {
                            "cycle_time": 1,
                            "cost_estimate": 1,
                        },
                        {
                            "cycle_time": 2,
                            "cost_estimate": 2,
                        },
                        {
                            "cycle_time": 3,
                            "cost_estimate": 3,
                        },
                        
                    ],
                    "module_name": "Telemetry Array",
                    "Field_0f13pgm": None,
                }
            ],
            "reference_code": "REF-001",
            "reference_label": "Mock Reference",
        }
    ],
}


def test_position_tracker_does_not_affect_original_data():
    position, tracked_task_data = get_position_tracker(TEST_DATA)
    assert position == []

    TEST_DATA["task_queue"][0]  # type: ignore
    assert position == []  # --> position still unchanged.


def test_independence_of_tracked_data():
    position, tracked_task_data = get_position_tracker(TEST_DATA)
    position_2, tracked_task_data_2 = get_position_tracker(TEST_DATA)

    tracked_task_data["task_queue"][0]
    assert position != []
    tracked_task_data_2.get("summary_title")
    assert position_2 == []

    assert position != position_2


def test_position_tracker_behaves_correctly_for_simple_level_1_entries():
    position, tracked_task_data = get_position_tracker(TEST_DATA)

    val = tracked_task_data["primary_reviewer"]
    assert val == "reviewer.delta@example.com"
    assert position == []

    val = tracked_task_data["backup_reviewer"]
    assert val == "reviewer.epsilon@example.com"
    assert position == []

    with pytest.raises(KeyError):
        tracked_task_data["I do not know"]
    assert position == []


def test_position_tracker_behaves_correctly_for_level_1_lists():
    position, tracked_task_data = get_position_tracker(TEST_DATA)

    val = tracked_task_data["task_queue"]
    assert val == [
        {
            "quantity_requested": 8,
            "unit": "modules",
        }
    ]
    assert position == []


def test_position_tracker_behaves_correctly_for_level_1_lists_2():
    position, tracked_task_data = get_position_tracker(TEST_DATA)

    tracked_task_data["support_files"]
    assert position == []


def test_position_tracker_behaves_correctly_for_level_1_lists_3():
    position, tracked_task_data = get_position_tracker(TEST_DATA)

    tracked_task_data["task_queue"]
    tracked_task_data["support_files"]
    assert position == []


def test_position_tracker_behaves_correctly_for_level_1_list_entries():
    position, tracked_task_data = get_position_tracker(TEST_DATA)

    val = tracked_task_data["task_queue"][0]
    assert val == {
        "quantity_requested": 8,
        "unit": "modules",
    }
    assert position == ["task_queue"]


def test_position_tracker_behaves_correctly_for_level_1_list_entry_member():
    position, tracked_task_data = get_position_tracker(TEST_DATA)

    val = tracked_task_data["task_queue"][0]["quantity_requested"]
    assert position == ["task_queue", 0]
    assert val == 8


def test_position_tracker_behaves_correctly_when_mixing_access_order():
    # first check level 1 data, then level 2, then again level 1

    position, tracked_task_data = get_position_tracker(TEST_DATA)

    val = tracked_task_data["primary_reviewer"]
    assert val == "reviewer.delta@example.com"
    assert position == []

    tracked_task_data["task_queue"][0]  # now I check something deeper nested

    tracked_task_data["primary_reviewer"]  # now again the first one, which must have the original position
    assert val == "reviewer.delta@example.com"
    assert position == []


def test_position_tracker_behaves_correctly_when_mixing_access_order_2():
    # first check level 2 data, then other level 2, then again level 1

    position, tracked_task_data = get_position_tracker(TEST_DATA)

    val = tracked_task_data["task_queue"][0]
    assert val == {
        "quantity_requested": 8,
        "unit": "modules",
    }

    val = tracked_task_data["support_files"][1]
    assert val == {"id": "blueprint-draft-A", "hash": "63a11f7ad5a74764a28dcb457a0fc8d9", "filename": "assembly_blueprint.pdf", "mimetype": "application/pdf"}

    assert position == ["support_files"]

    val = tracked_task_data["task_queue"][0]["quantity_requested"]
    assert val == 8
    assert position == ["task_queue", 0]


def test_group():
    position, tracked_task_data = get_position_tracker(TEST_DATA)

    val = tracked_task_data["config_bundle"]
    assert val == {
        "phase": "initialization",
        "stage": "simulation",
        "checkpoint": {"status": "draft"},
    }
    assert position == []


def test_group_members():
    position, tracked_task_data = get_position_tracker(TEST_DATA)

    val = tracked_task_data["config_bundle"]["stage"]
    assert val == "simulation"
    assert position == ["config_bundle"]


def test_inner_group():
    position, tracked_task_data = get_position_tracker(TEST_DATA)

    val = tracked_task_data["config_bundle"]["checkpoint"]
    assert val == {"status": "draft"}

    assert position == ["config_bundle"]


def test_inner_group_member():
    position, tracked_task_data = get_position_tracker(TEST_DATA)

    val = tracked_task_data["config_bundle"]["checkpoint"]["status"]
    assert val == "draft"

    assert position == ["config_bundle", "checkpoint"]


def test_three_levels():
    position, tracked_task_data = get_position_tracker(TEST_DATA)
    val = tracked_task_data["payloads"][0]["systems"][0]["quotes"][0]
    assert val == {
        "cycle_time": 1,
        "cost_estimate": 1,
    }
    assert position == ["payloads", 0, "systems", 0, "quotes"]

    val = tracked_task_data["payloads"][0]["systems"][0]["quotes"][0]["cycle_time"]
    assert val == 1
    assert position == ["payloads", 0, "systems", 0, "quotes", 0]

FORM_DATA_BIG = {
    "articleList": [
        {
            "componentList": [
                {
                    "priceList": [
                        {
                            "time_processing_setup": 15,
                            "time_printing_setup": 15,
                            "Field_00yfiu2": None,
                            "Field_1n68x25": None,
                            "moq": 4,
                            "price_processing_cost": 10,
                            "price_processing_factor": 4,
                            "price_processing": 40,
                            "time_processing_te": 13,
                            "price_printing_cost": 12.45,
                            "price_printing_factor": 3,
                            "price_printing": 37.35,
                            "time_printing_te": 14,
                            "price": 77.35,
                        }
                    ],
                    "modification_processing": "mechanical",
                    "modification_printing": "pad",
                    "Field_0qwww3i": None,
                    "Field_0rthk37": None,
                    "standardComponent_number": "Komponentennummer 1",
                    "standardComponent_name": "Komponentenbezeichnung1",
                    "Field_0f13pgm": None,
                },
                {
                    "priceList": [
                        {
                            "time_processing_setup": 15,
                            "time_printing_setup": 15,
                            "Field_00yfiu2": None,
                            "Field_1n68x25": None,
                            "moq": 5,
                            "price_processing_cost": 1,
                            "price_processing_factor": 1,
                            "price_processing": 1,
                            "time_processing_te": 14,
                            "price_printing_cost": 5,
                            "price_printing_factor": 2,
                            "time_printing_te": 54,
                            "price_printing": 10,
                            "price": 11,
                        }
                    ],
                    "modification_processing": "mechanical",
                    "modification_printing": "none",
                    "Field_0qwww3i": None,
                    "Field_0rthk37": None,
                    "standardComponent_number": "Kompi 2",
                    "standardComponent_name": "Hallo2",
                    "Field_0f13pgm": None,
                },
            ],
            "productionType": "inhouse",
            "customer_requirement": [],
            "Field_03fhoov": None,
            "customer_requirement_overall": True,
            "Field_0i45ftj": None,
            "Field_06sxpkv": None,
            "Field_0fjzld9": None,
            "Field_0e0qvc6": None,
            "standardArticle_number": "Artikel 1",
            "standardArticle_name": "Bezeichnung1",
            "comparisonArticle_number": "Vergleicher1",
            "comparisonArticle_name": "Bezeichner1",
            "standardArticle_price": 402,
        }
    ],
    "next_step020": "forward",
    "instance_id": "40af9caf-8acf-42f5-bb11-d792631c131b",
    "requester_name": "WF-User Smith",
    "requester_email": "requester@example.com",
    "requester_full_info": "WF-User Smith (requester@example.com))",
    "result_Activity_assign_product_manager": None,
    "act": [{"sales_employee": "userY@example.com", "sales_country": "515883"}],
    "customer_exclusive": "true",
    "customerList": [{"customer_number": "Kunde1", "customer_name": "Endkunde 1"}],
    "Field_1k9s8z5": None,
    "Field_1m6h0ij": None,
    "Field_1q0joig": None,
    "Field_0toy4nz": None,
    "Field_0qolngj": None,
    "Field_09du9vc": None,
    "Field_07dpkck": None,
    "Field_0ytj7o2": None,
    "Field_1jz8n0n": None,
    "hsNumber": "25-001",
    "date_inquiry": "2025-06-11",
    "Field_0y143is": None,
    "Field_1ezy1kw": None,
    "Field_0y57654": None,
}

def test_deepcopy_after_removal_inside_big_structure():
    position, tracked_task_data = get_position_tracker(FORM_DATA_BIG)
    
    removal_list = [
        ["hsNumber"],
        ["articleList", 0, "standardArticle_number"],
        ["articleList", 0, "standardArticle_name"],
        ["articleList", 0, "componentList", 0, "standardComponent_number"],
        ["articleList", 0, "componentList", 0, "standardComponent_name"],
        ["articleList", 0, "componentList", 0, "modification_processing"],
        ["articleList", 0, "componentList", 0, "modification_printing"],
        ["articleList", 0, "componentList", 1, "standardComponent_number"],
        ["articleList", 0, "componentList", 1, "standardComponent_name"],
        ["articleList", 0, "componentList", 1, "modification_processing"], # after deleting this, the old implementation was throwing an Recursion Error when doing copy.deepcopy
        ["articleList", 0, "componentList", 1, "modification_printing"],
    ]
    for r in removal_list:
        tracked_task_data = remove_item(tracked_task_data, r)
        untracked = copy.deepcopy(tracked_task_data)



def test_deepcopy_after_removal_inside_big_structure_2():
    position, tracked_task_data = get_position_tracker(FORM_DATA_BIG)
    
    removal_list = [
        ["articleList", 0, "componentList", 0, "standardComponent_number"],
        ["articleList", 0, "componentList", 0, "standardComponent_name"],
        ["articleList", 0, "componentList", 0, "modification_processing"],
        ["articleList", 0, "componentList", 0, "modification_printing"],
        ["articleList", 0, "componentList", 1, "standardComponent_number"],
        ["articleList", 0, "componentList", 1, "standardComponent_name"],
        ["articleList", 0, "componentList", 1, "modification_processing"],
        ["articleList", 0, "componentList", 1, "modification_printing"],
    ]
    # this still worked with the old solution
    for r in removal_list:
        tracked_task_data = remove_item(tracked_task_data, r)
        untracked = copy.deepcopy(tracked_task_data)


def test_deepcopy():
    position, tracked_task_data = get_position_tracker(FORM_DATA_BIG)
    
    # this still worked with the old solution. it is not the number of deepcopy-calls, but the depth of the deepcopy
    for i in range(10000):
        untracked = copy.deepcopy(tracked_task_data)

def test_removal_create_deepcopy():
    position, tracked_task_data = get_position_tracker(FORM_DATA_BIG)
    
    #failed with the old solution at 10-th removal
    for i in range(100):
        try:
            tracked_task_data = remove_item(tracked_task_data, ["articleList", 0, "componentList", 0, "standardComponent_number"])
            print(i)
        except Exception:
            print(f"Failed at {i}-th removal")
            raise
        
