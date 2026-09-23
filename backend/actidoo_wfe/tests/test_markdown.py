# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import pytest
from markupsafe import Markup

from actidoo_wfe.helpers.markdown import escape_markdown, markdown_to_html_document, render_markdown


@pytest.mark.parametrize(
    "value",
    [
        "# Title",
        "- item",
        "+ item",
        "1. one",
        "1) one",
        "---",
        "a *b* _c_ [d](x) <b>e</b> | f ~g~ `h` \\i",
    ],
)
def test_escaped_value_renders_literally(value):
    html = render_markdown(escape_markdown(value))
    text = html.replace("<p>", "").replace("</p>", "").strip()
    assert text == value.replace("<", "&lt;").replace(">", "&gt;")
    assert "<a " not in html and "<em>" not in html and "<h1>" not in html and "<li>" not in html


def test_escape_leaves_harmless_text_alone():
    assert escape_markdown("2026-09-17 - Angebot #4711 (Entwurf)") == "2026-09-17 - Angebot #4711 (Entwurf)"


def test_escape_handles_none_and_markup():
    assert escape_markdown(None) == ""
    assert escape_markdown(Markup("https://example.com/a_b")) == "https://example.com/a_b"


def test_render_escapes_raw_html_and_keeps_links_and_breaks():
    html = render_markdown("Line one <script>x</script>\nLine two [doc](https://example.com/d) https://example.com/bare")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<br />" in html
    assert '<a href="https://example.com/d">doc</a>' in html
    assert '<a href="https://example.com/bare">https://example.com/bare</a>' in html


def test_render_rejects_unsafe_schemes():
    html = render_markdown("[x](javascript:alert(1)) [y](data:text/html,hi) [z](vbscript:foo)")
    assert "<a " not in html


def test_document_wrapper():
    doc = markdown_to_html_document("**hi**")
    assert doc.startswith("<!DOCTYPE html>")
    assert '<meta charset="utf-8">' in doc
    assert "<strong>hi</strong>" in doc
