# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import json

from actidoo_wfe.wf import service_form
from actidoo_wfe.wf.form_transformation import transform_camunda_form


def are_dicts_equal(dict1, dict2, shall_assert_if_unequal=False):
    """
    Recursively checks if two dictionaries are equal (have the same keys and values).
    Prints the differences if they are not equal.

    Args:
        dict1 (dict): The first dictionary.
        dict2 (dict): The second dictionary.

    Returns:
        bool: True if the dictionaries are equal, False otherwise.
    """
    if dict1 == dict2:
        return True
    else:
        # Recursively compare dictionaries
        def compare(d1, d2, path=""):
            for key in set(d1.keys()) | set(d2.keys()):
                if key not in d1 or key not in d2:
                    print(f"Different key found at path: {path + str(key)}")
                    if shall_assert_if_unequal:
                        print("*****")
                        assert False, f"Different key found at path: {path + str(key)}"
                    return False
                elif isinstance(d1[key], dict) and isinstance(d2[key], dict):
                    if not compare(d1[key], d2[key], path + str(key) + "."):
                        return False
                elif d1[key] != d2[key]:
                    print(f"Different value found at path: {path + str(key)}")
                    print(f"Value 1: {d1[key]}")
                    print(f"Value 2: {d2[key]}")
                    if shall_assert_if_unequal:
                        assert False, f"Different value found at path: {path + str(key)}" + "\n" + f"Value 1: {d1[key]}" + "\n" + f"Value 2: {d2[key]}"
                    return False
            return True

        return compare(dict1, dict2)


def load_dict_from_file(filename) -> dict:
    """
    Loads a dictionary from a JSON file.

    Args:
        filename (str): The name of the file containing the dictionary.

    Returns:
        dict: The loaded dictionary.
    """
    with open(filename, "r") as file:
        return json.load(file)


def save_dict_to_file(dictionary, filename):
    """
    Saves a dictionary to a JSON file.

    Args:
        dictionary (dict): The dictionary to be saved.
        filename (str): The name of the file to save the dictionary to.
    """
    with open(filename, "w") as file:
        json.dump(dictionary, file, indent=4, ensure_ascii=False)


def read_and_transform(file) -> service_form.ReactJsonSchemaFormData:
    with open(file, "r") as fp:
        form_camunda_json = json.load(fp)
        form = transform_camunda_form(form_camunda_json)
    return form
