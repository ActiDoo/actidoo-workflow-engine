# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import copy
from pathlib import Path

from actidoo_wfe.wf import service_form
from actidoo_wfe.wf.tests.helpers.dicts import (
    are_dicts_equal,
    load_dict_from_file,
    read_and_transform,
    save_dict_to_file,
)

TESTS_DIR = Path(__file__).parent
SNAPSHOT_JSONSCHEMA = TESTS_DIR / "snapshots" / "hide-if-jsonschema.json"
SNAPSHOT_JSONSCHEMA_CONVERTED = TESTS_DIR / "snapshots" / "hide-if-jsonschema-converted.json"
SNAPSHOT_UISCHEMA = TESTS_DIR / "snapshots" / "hide-if-uischema.json"
FILE_FORM = TESTS_DIR / "forms" / "test_hide_if.form"


def _read_snapshot_jsonschema():  # -> dict[Any, Any]:
    return load_dict_from_file(SNAPSHOT_JSONSCHEMA)


def _read_snapshot_jsonschema_converted():
    return load_dict_from_file(SNAPSHOT_JSONSCHEMA_CONVERTED)


def _read_snapshot_uischema():  # -> dict[Any, Any]:
    return load_dict_from_file(SNAPSHOT_UISCHEMA)


def _create_snapshots():
    form = read_and_transform(FILE_FORM)

    save_dict_to_file(form[0], SNAPSHOT_JSONSCHEMA)
    save_dict_to_file(form[1], SNAPSHOT_UISCHEMA)

    service_form.convert_hide_if_props_to_declarative_jsonschema(form[0])
    save_dict_to_file(form[0], SNAPSHOT_JSONSCHEMA_CONVERTED)


# _create_snapshots() # USE THIS IF YOU WANT TO CREATE NEW SNAPSHOTS!


def test__convert_hide_if_props_to_declarative_jsonschema__returns__expected_snapshots():
    jsonschema, uischema = read_and_transform(FILE_FORM)

    are_dicts_equal(jsonschema, _read_snapshot_jsonschema(), True)
    are_dicts_equal(uischema, _read_snapshot_uischema(), True)

    # validate_task_data() testen!
    # oder eigentlich reicht auch convert_hide_if_props_to_declarative_jsonschema

    converted = copy.deepcopy(jsonschema)
    service_form.convert_hide_if_props_to_declarative_jsonschema(converted)

    are_dicts_equal(converted, _read_snapshot_jsonschema_converted(), True)
