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
        }
    ],
    "list_to_be_updated": [
        {
            "old_value": "will_be_kept",
            "update_me": "kick me",
        }
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
        # TODO in this case we assume that the last element of task_data.list_to_be_truncated was removed.
        # But how can we be sure? It might as well be that the second got removed and the third was just updated.
        # To fix this for Dynamic List a 'list' is not sufficient, but we will need a data structure which stores the
        # original position and the information if a position got deleted completely.
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
