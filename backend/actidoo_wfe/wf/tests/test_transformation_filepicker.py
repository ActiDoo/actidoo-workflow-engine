# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import pytest

from actidoo_wfe.wf.form_transformation import transform_camunda_form
from actidoo_wfe.wf.service_form import file_matches_accept


def _transform(*components):
    form = transform_camunda_form({"components": list(components)})
    return form.jsonschema, form.uischema


def _filepicker(**attrs):
    return {"type": "filepicker", "id": "Field_1", "key": "upload", "label": "Upload", "layout": {"row": "Row_1"}, **attrs}


def _textfield_upload(custom_type, **properties):
    return {"type": "textfield", "id": "Field_1", "key": "upload", "label": "Upload", "layout": {"row": "Row_1"}, "properties": {"custom_type": custom_type, **properties}}


def test__filepicker_equals_the_textfield_upload():
    required = {"validate": {"required": True}}
    assert _transform(_filepicker(**required)) == _transform(_textfield_upload("attachment_single") | required)
    assert _transform(_filepicker(multiple=True, **required)) == _transform(_textfield_upload("attachment_multi") | required)


def test__accept_is_normalized():
    expected = [".pdf", ".xml", "image/*"]
    assert _transform(_filepicker(accept="pdf, .XML ,image/*,"))[0]["properties"]["upload"]["accept"] == expected
    assert _transform(_textfield_upload("attachment_multi", accept="pdf, .XML ,image/*,"))[0]["properties"]["upload"]["accept"] == expected


@pytest.mark.parametrize("accept", ["*/*", "pdf, *"])
def test__accept_with_a_wildcard_allows_any_file(accept):
    assert "accept" not in _transform(_filepicker(accept=accept))[0]["properties"]["upload"]


@pytest.mark.parametrize("attrs", [{"multiple": "=allowMany"}, {"accept": "=allowedTypes"}])
def test__feel_expressions_are_rejected(attrs):
    with pytest.raises(ValueError, match="FEEL expressions are not supported"):
        _transform(_filepicker(**attrs))


@pytest.mark.parametrize(
    "filename, mimetype, accept, expected",
    [
        ("REPORT.PDF", "application/pdf", [".pdf"], True),
        ("report.pdf.txt", "text/plain", [".pdf"], False),
        ("image.png", "image/png", [".pdf", "image/*"], True),
        ("data.json", "application/json", ["application/json"], True),
    ],
)
def test__file_matches_accept(filename, mimetype, accept, expected):
    assert file_matches_accept(filename, mimetype, accept) is expected
