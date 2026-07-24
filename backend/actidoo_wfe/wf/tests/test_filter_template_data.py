# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from actidoo_wfe.wf.service_form import filter_template_data


def _schema(properties):
    return {"type": "object", "properties": properties}


def test_blacklist_keeps_unflagged_and_excludes_disabled():
    schema = _schema(
        {
            "a": {"type": "string", "title": "A"},
            "b": {"type": "string", "title": "B", "custom_properties": {"template_field": "false"}},
        }
    )
    kept, skipped = filter_template_data(jsonschema=schema, data={"a": "x", "b": "y"}, mode="blacklist", apply_value_rule=True)
    assert kept == {"a": "x"}
    assert ["b"] in skipped


def test_whitelist_keeps_only_flagged():
    schema = _schema(
        {
            "a": {"type": "string", "custom_properties": {"template_field": "true"}},
            "b": {"type": "string"},
        }
    )
    kept, _ = filter_template_data(jsonschema=schema, data={"a": "x", "b": "y"}, mode="whitelist", apply_value_rule=True)
    assert kept == {"a": "x"}


def test_off_returns_empty():
    schema = _schema({"a": {"type": "string"}})
    assert filter_template_data(jsonschema=schema, data={"a": "x"}, mode="off", apply_value_rule=True) == ({}, [])


def test_value_rule_drops_none_and_empty_string_keeps_falsy():
    schema = _schema({k: {"type": "string"} for k in ["s", "empty", "none", "zero", "flag", "arr", "obj"]})
    data = {"s": "x", "empty": "", "none": None, "zero": 0, "flag": False, "arr": [], "obj": {}}
    kept, _ = filter_template_data(jsonschema=schema, data=data, mode="blacklist", apply_value_rule=True)
    assert kept == {"s": "x", "zero": 0, "flag": False, "arr": [], "obj": {}}


def test_apply_mode_does_not_drop_empty_values():
    schema = _schema({"empty": {"type": "string"}})
    kept, _ = filter_template_data(jsonschema=schema, data={"empty": ""}, mode="blacklist", apply_value_rule=False)
    assert kept == {"empty": ""}


def test_attachment_field_never_templatable():
    schema = _schema(
        {
            "doc": {
                "type": "object",
                "properties": {
                    "datauri": {"type": "string", "format": "data-url"},
                    "filename": {"type": "string"},
                    "hash": {"type": "string"},
                },
            },
        }
    )
    kept, skipped = filter_template_data(
        jsonschema=schema, data={"doc": {"filename": "a.pdf"}}, mode="blacklist", apply_value_rule=True
    )
    assert kept == {}
    assert ["doc"] in skipped


def test_nested_object_descends_and_filters():
    schema = _schema(
        {
            "group": {
                "type": "object",
                "properties": {
                    "keep": {"type": "string"},
                    "drop": {"type": "string", "custom_properties": {"template_field": "false"}},
                },
            },
        }
    )
    kept, skipped = filter_template_data(
        jsonschema=schema, data={"group": {"keep": "x", "drop": "y"}}, mode="blacklist", apply_value_rule=True
    )
    assert kept == {"group": {"keep": "x"}}
    assert ["group", "drop"] in skipped


def test_unknown_field_is_skipped_on_apply():
    schema = _schema({"known": {"type": "string"}})
    kept, skipped = filter_template_data(
        jsonschema=schema, data={"known": "x", "ghost": "y"}, mode="blacklist", apply_value_rule=False
    )
    assert kept == {"known": "x"}
    assert ["ghost"] in skipped
