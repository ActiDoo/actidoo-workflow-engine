# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Regex validation of text fields (the Modeler's ``validate.pattern``) and the custom
property ``pattern_message`` that replaces the raw regex in the error shown to the user."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from babel.messages.catalog import Catalog
from babel.messages.pofile import write_po

from actidoo_wfe.wf import service_application, service_i18n
from actidoo_wfe.wf.exceptions import ValidationResultContainsErrors
from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import validate_task_data

OPTIONS_FOLDER = Path(__file__).parent / "options"

PLATE_PATTERN = r"^[A-Z]{1,3}-[A-Z]{1,2} \d{1,4}$"
PLATE_MESSAGE = "Enter a plate like B-AB 1234"

FORM = {
    "components": [
        {
            "type": "textfield",
            "key": "plate",
            "validate": {"required": True, "pattern": PLATE_PATTERN},
            "properties": {"pattern_message": PLATE_MESSAGE},
        },
        {"type": "textfield", "key": "code", "validate": {"pattern": r"^\d{3}$"}},
        {
            "type": "dynamiclist",
            "path": "rows",
            "components": [
                {
                    "type": "textfield",
                    "key": "zip",
                    "validate": {"pattern": r"^\d{5}$"},
                    "properties": {"pattern_message": "Five digits"},
                },
            ],
        },
    ],
}


def _validate(form, data):
    return validate_task_data(form=form, task_data=data, options_folder=OPTIONS_FOLDER, functions_env={}, locale="en").error_schema


def test_transformation_carries_pattern_and_message():
    form = transform_camunda_form(FORM)

    assert form.jsonschema["properties"]["plate"]["pattern"] == PLATE_PATTERN
    assert form.uischema["plate"]["ui:patternMessage"] == PLATE_MESSAGE
    assert "ui:patternMessage" not in form.uischema["code"]
    assert form.jsonschema["properties"]["rows"]["items"]["properties"]["zip"]["pattern"] == r"^\d{5}$"
    assert form.uischema["rows"]["items"]["zip"]["ui:patternMessage"] == "Five digits"


def test_matching_values_pass():
    form = transform_camunda_form(FORM)

    assert _validate(form, {"plate": "B-AB 1234", "code": "123", "rows": [{"zip": "12345"}]}) is None


def test_mismatch_reports_custom_message_else_default():
    form = transform_camunda_form(FORM)

    errors = _validate(form, {"plate": "foo", "code": "12", "rows": [{"zip": "12345"}, {"zip": "1"}]})

    assert errors["plate"]["__errors"] == [PLATE_MESSAGE]
    assert errors["code"]["__errors"] == ["The input does not have the expected format"]
    assert errors["rows"] == [{}, {"zip": {"__errors": ["Five digits"]}}]


def test_pattern_message_is_extracted_for_translation():
    entries = service_i18n.extract_strings_from_form(FORM["components"])

    assert (PLATE_MESSAGE, "plate.pattern_message") in entries
    assert ("Five digits", "rows.zip.pattern_message") in entries


@pytest.mark.parametrize("pattern", [r"^(?<code>[A-Z]{2})-[0-9]{4}$", "["])
def test_invalid_pattern_is_rejected_when_loading_the_form(pattern):
    with pytest.raises(ValueError, match="field 'code': invalid pattern"):
        transform_camunda_form({"components": [{"type": "textfield", "key": "code", "validate": {"pattern": pattern}}]})


@pytest.mark.parametrize("pattern, value, valid", [
    (r"^(?P<code>[A-Z]{2})-[0-9]{4}$", "CC-1234", True),
    (r"^(?P<code>[A-Z]{2})-[0-9]{4}$", "wrong", False),
    (r"^\w+$", "Ärger", True),
])
def test_patterns_use_backend_semantics(pattern, value, valid):
    form = transform_camunda_form({"components": [{"type": "textfield", "key": "value", "validate": {"pattern": pattern}}]})
    assert (_validate(form, {"value": value}) is None) == valid


@pytest.mark.parametrize("locale, fallback", [
    ("de-DE", "Die Eingabe hat nicht das erwartete Format"),
    ("en", "The input does not have the expected format"),
])
def test_submission_returns_localized_pattern_errors(tmp_path, monkeypatch, locale, fallback):
    catalog = Catalog(locale="de")
    catalog.add(PLATE_MESSAGE, "Kennzeichen wie B-AB 1234 eingeben")
    catalog.add("Five digits", "Fünf Ziffern")
    po_path = tmp_path / "i18n" / "locales" / "de" / "LC_MESSAGES" / "Demo.po"
    po_path.parent.mkdir(parents=True)
    with po_path.open("wb") as po:
        write_po(po, catalog)
    english = Catalog(locale="en")
    english.add(PLATE_MESSAGE, PLATE_MESSAGE)
    english.add("Five digits", "Five digits")
    en_path = tmp_path / "i18n" / "locales" / "en" / "LC_MESSAGES" / "Demo.po"
    en_path.parent.mkdir(parents=True)
    with en_path.open("wb") as po:
        write_po(po, english)

    monkeypatch.setattr(service_application.workflow_providers, "get_workflow_directory", lambda _: tmp_path)
    monkeypatch.setattr(service_application.workflow_providers, "get_workflow_module_path", lambda _: None)
    form = transform_camunda_form(FORM)
    task = SimpleNamespace(jsonschema=form.jsonschema, uischema=form.uischema, data={})
    workflow = SimpleNamespace(spec=SimpleNamespace(name="Demo"))
    with pytest.raises(ValidationResultContainsErrors) as error:
        service_application._clean_submitted_task_data(
            workflow=workflow, task=task,
            submitted_data={"plate": "wrong", "code": "12", "rows": [{"zip": "1"}]}, locale=locale,
        )

    errors = error.value.error_schema
    assert errors["plate"]["__errors"] == ["Kennzeichen wie B-AB 1234 eingeben" if locale.startswith("de") else PLATE_MESSAGE]
    assert errors["code"]["__errors"] == [fallback]
    assert errors["rows"][0]["zip"]["__errors"] == ["Fünf Ziffern" if locale.startswith("de") else "Five digits"]
    assert form.uischema["plate"]["ui:patternMessage"] == PLATE_MESSAGE
