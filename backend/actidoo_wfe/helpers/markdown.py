# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import re
from functools import cache

from markdown_it import MarkdownIt

_INLINE_SPECIALS = re.compile(r"([\\`*_\[\]<>~|])")
_LINE_START_MARKERS = re.compile(r"^(\s*)(#{1,6}(?=\s|$)|[+\-](?=\s|$)|[-=]+(?=\s*$))", re.MULTILINE)
_LINE_START_ORDERED = re.compile(r"^(\s*\d{1,9})([.)])(?=\s|$)", re.MULTILINE)
_URL_AUTOLINK = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]{1,31}:[^<>\x00-\x20]*")

HTML_DOCUMENT_STYLE = "font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #1f2937;"


@cache
def _parser() -> MarkdownIt:
    return MarkdownIt("gfm-like", {"html": False, "breaks": True})


def render_markdown(content: str) -> str:
    """Render Markdown to an HTML fragment. Raw HTML in the source is escaped, unsafe link schemes are dropped."""
    return _parser().render(content)


def wrap_html_document(body: str) -> str:
    return f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="{HTML_DOCUMENT_STYLE}">{body}</body></html>'


def markdown_to_html_document(content: str) -> str:
    return wrap_html_document(render_markdown(content))


def escape_markdown(value) -> str:
    """Escape a value so it renders literally when embedded in Markdown. URLs in it stay links."""
    if value is None:
        return ""
    text = str(value)
    # A URL becomes an autolink: escaping inside it would break the link, and an autolink always shows its own target.
    parts, end = [], 0
    for match in _parser().linkify.match(text) or []:
        if match.schema != "mailto:" and _URL_AUTOLINK.fullmatch(match.url):
            parts += [_INLINE_SPECIALS.sub(r"\\\1", text[end : match.index]), f"<{match.url}>"]
            end = match.last_index
    parts.append(_INLINE_SPECIALS.sub(r"\\\1", text[end:]))
    text = _LINE_START_MARKERS.sub(r"\1\\\2", "".join(parts))
    return _LINE_START_ORDERED.sub(r"\1\\\2", text)
