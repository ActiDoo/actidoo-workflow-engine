# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Backend-wide i18n helpers — top-level layer.

This module owns:

* The **global** gettext catalog at ``backend/actidoo_wfe/locales/`` (domain
  ``messages``), used for everything that is not workflow-specific — mail
  templates, mail subjects, future cross-cutting strings.
* Generic gettext utilities reused by the per-workflow catalog
  implementation in ``actidoo_wfe.wf.service_i18n`` — locale matching,
  PO/MO compilation, supported-locale listing, Accept-Language parsing.

Workflow-specific catalog handling (form labels, BPMN names, per-process
``.po`` files in ``wf/processes/<wf>/i18n/``) stays in ``wf.service_i18n``
because it depends on the workflow plugin layout.
"""

import gettext
import pathlib
import re
from functools import cache
from pathlib import Path
from typing import Callable, List, Optional, Union

import pycountry
from babel import Locale as BabelLocale
from babel import localedata
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po
from babel.support import Translations

from actidoo_wfe.settings import settings

# --- Global catalog layout ---------------------------------------------------

GLOBAL_CATALOG_DOMAIN = "messages"
GLOBAL_I18N_DIR = pathlib.Path(__file__).parent / "locales"
# extract_global_messages() scans every .py / .mako under here for `_(...)` calls.
GLOBAL_I18N_SCAN_ROOT = pathlib.Path(__file__).parent
GLOBAL_I18N_SCAN_SKIP_DIR_NAMES = {"processes", "tests", "__pycache__", "locales", ".venv"}

_GLOBAL_GETTEXT_CALL_RE = re.compile(r'_\(\s*(?:r?"((?:[^"\\]|\\.)*)"|r?\'((?:[^\'\\]|\\.)*)\')\s*\)')

# workflow_users.locale column length
MAX_LOCALE_KEY_LENGTH = 10


# --- Locale matching --------------------------------------------------------


def match_translation(user_locale: str, available: list[str]) -> str:
    """Pick the best available locale for a user locale.

    1) Exact (case-insensitive) match against ``available``.
    2) Fallback to the base language (case-insensitive).
    3) Return ``settings.default_locale``.
    """
    lowered_map = {locale.lower(): locale for locale in available}
    ul = user_locale.lower()
    if ul in lowered_map:
        return lowered_map[ul]
    base = ul.split("-", 1)[0]
    if base in lowered_map:
        return lowered_map[base]
    return settings.default_locale


# --- Global catalog ---------------------------------------------------------


def _available_global_locales() -> List[str]:
    if not GLOBAL_I18N_DIR.exists():
        return []
    return [
        p.name
        for p in GLOBAL_I18N_DIR.iterdir()
        if p.is_dir() and (p / "LC_MESSAGES" / f"{GLOBAL_CATALOG_DOMAIN}.mo").exists()
    ]


def _load_global_translations(locale: str) -> Union[gettext.GNUTranslations, gettext.NullTranslations]:
    """Load the global backend gettext catalog for the given locale."""
    available = _available_global_locales()
    chosen = match_translation(user_locale=locale or settings.default_locale, available=available)
    return Translations.load(dirname=GLOBAL_I18N_DIR, locales=[chosen], domain=GLOBAL_CATALOG_DOMAIN)


def translate(msgid: str, locale: Optional[str] = None) -> str:
    """Translate a global backend string for the given locale.

    Returns ``msgid`` unchanged if no translation is available. Workflow-specific
    strings (form labels, task/instance titles) must use
    ``actidoo_wfe.wf.service_i18n.translate_string`` with the workflow's own
    catalog.
    """
    if not msgid or not msgid.strip():
        return msgid
    effective_locale = locale or settings.default_locale
    t = _load_global_translations(effective_locale)
    return t.gettext(msgid)


def make_translator(locale: Optional[str]) -> Callable[[str], str]:
    """Return a single-argument callable bound to ``locale``.

    Intended as the ``_`` helper injected into Mako templates and as a local
    shortcut in Python functions that render many strings for the same locale.
    """
    return lambda s: translate(s, locale)


# --- Catalog build / merge / compile (generic helpers, used by global + workflow catalogs) ---


def update_catalogue(template_pot: Path, input_po: Path, output_po: Path, locale: str):
    """Merge a fresh .pot into an existing .po, preserving existing translations.

    Re-used by both the global catalog and per-workflow catalogs in service_i18n.
    """
    with open(template_pot, "rb") as f:
        tpl = read_po(f)

    if input_po.exists():
        with open(input_po, "rb") as f:
            existing = read_po(f)
        locale_used = existing.locale or locale
        project = existing.project
    else:
        existing = None
        locale_used = locale
        project = tpl.project

    updated = Catalog(locale=locale_used, project=project)

    for msg in tpl:
        added = False
        if existing:
            old_exact = existing.get(msg.id, msg.context)
            if old_exact and old_exact.string:
                updated.add(id=msg.id, string=old_exact.string, context=msg.context)
                added = True
            else:
                for e in existing:
                    if e.context == msg.context and e.string:
                        m = updated.add(id=msg.id, string=e.string, context=msg.context)
                        m.flags.add("fuzzy")
                        added = True
                        break
        if not added:
            updated.add(id=msg.id, context=msg.context)

    if existing:
        tpl_ctxs = {m.context for m in tpl}
        for old in existing:
            if old.context not in tpl_ctxs:
                obs = updated.add(id=old.id, string=old.string, context=old.context)
                setattr(obs, "obsolete", True)

    output_po.parent.mkdir(parents=True, exist_ok=True)
    with open(output_po, "wb") as f:
        write_po(f, updated)


def compile_po_to_mo(po_file: Path):
    """Compile a .po file into its sibling .mo (flat catalog, no msgctxt)."""
    mo_file = po_file.with_suffix(".mo")
    mo_file.parent.mkdir(parents=True, exist_ok=True)
    with open(po_file, "r", encoding="utf-8") as f:
        original_catalog = read_po(f)

    flat_catalog = Catalog(locale=original_catalog.locale, project=original_catalog.project)
    for message in original_catalog:
        if message.id and message.string:
            flat_catalog.add(id=message.id, string=message.string)

    with open(mo_file, "wb") as f:
        write_mo(f, flat_catalog)


def extract_global_messages() -> Path:
    """Extract translatable strings from all backend .py + .mako files into messages.pot.

    Scans every ``.py`` / ``.mako`` file under ``backend/actidoo_wfe/`` for
    underscore-gettext calls, skipping workflow-specific ``processes/`` (those
    have their own catalogs), ``tests/``, ``__pycache__/``, ``locales/`` and ``.venv/``.
    """
    pot_path = GLOBAL_I18N_DIR / f"{GLOBAL_CATALOG_DOMAIN}.pot"
    pot_path.parent.mkdir(parents=True, exist_ok=True)

    catalog = Catalog(locale=None, project=GLOBAL_CATALOG_DOMAIN)
    seen: set[str] = set()

    def _add(msgid: str):
        s = msgid.strip()
        if not s or s in seen:
            return
        seen.add(s)
        catalog.add(id=s)

    for path in GLOBAL_I18N_SCAN_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in (".py", ".mako"):
            continue
        if any(p in GLOBAL_I18N_SCAN_SKIP_DIR_NAMES for p in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for m in _GLOBAL_GETTEXT_CALL_RE.finditer(text):
            _add(m.group(1) or m.group(2))

    with open(pot_path, "wb") as f:
        write_po(f, catalog, ignore_obsolete=True)
    return pot_path


def update_global_catalogue(locale: str) -> Path:
    pot = GLOBAL_I18N_DIR / f"{GLOBAL_CATALOG_DOMAIN}.pot"
    po = GLOBAL_I18N_DIR / locale / "LC_MESSAGES" / f"{GLOBAL_CATALOG_DOMAIN}.po"
    update_catalogue(template_pot=pot, input_po=po, output_po=po, locale=locale)
    return po


def compile_global_catalog():
    """Compile every locale's messages.po → messages.mo in the global catalog."""
    if not GLOBAL_I18N_DIR.exists():
        return
    for po_file in GLOBAL_I18N_DIR.glob(f"**/LC_MESSAGES/{GLOBAL_CATALOG_DOMAIN}.po"):
        compile_po_to_mo(po_file)


# --- Supported locales (Babel-driven) + Accept-Language parsing -------------


@cache
def get_supported_locales() -> List[dict[str, str]]:
    """Return all Babel-known locales with human labels like "German (Germany)".

    Skips codes that don't parse or don't map to a known language/country.
    """
    entries: List[dict[str, str]] = []
    seen_keys: set[str] = set()
    for code in localedata.locale_identifiers():
        hyphenated = code.replace("_", "-")
        if len(hyphenated) > MAX_LOCALE_KEY_LENGTH:
            continue
        try:
            loc = BabelLocale.parse(code)
        except (ValueError, LookupError):
            continue

        lang = pycountry.languages.get(alpha_2=loc.language)
        if not lang:
            continue
        lang_name = lang.name

        label_parts = [lang_name]
        territory = loc.territory
        script = loc.script
        if territory:
            country = pycountry.countries.get(alpha_2=territory)
            if not country:
                continue
            label_parts.append(country.name)
        else:
            continue
        if script:
            label_parts.append(script)

        if len(label_parts) > 1:
            label = f"{label_parts[0]} ({', '.join(label_parts[1:])})"
        else:
            label = label_parts[0]

        if hyphenated in seen_keys:
            continue
        entries.append({"key": hyphenated, "label": label})
        seen_keys.add(hyphenated)

    entries.sort(key=lambda x: x["label"])
    return entries


ACCEPT_LANG_RE = re.compile(
    r"""
    \s*
    (?P<lang>[A-Za-z0-9\-_]+)      # language[-REGION]
    (?:\s*;\s*q=(?P<q>0(\.\d+)?|1(\.0+)?))?  # optional ;q=0.xxx or 1.0
    \s*
""",
    re.VERBOSE,
)


def extract_primary_locale(accept_language_header: str) -> Optional[str]:
    """Parse Accept-Language, sort by quality, return a code that's in ``get_supported_locales()``.

    Exact match wins, then language-only fallback. Returns None when nothing matches.
    """
    entries = []
    for part in accept_language_header.split(","):
        m = ACCEPT_LANG_RE.fullmatch(part)
        if not m:
            continue
        code = m.group("lang")
        q = float(m.group("q")) if m.group("q") is not None else 1.0
        entries.append((code, q))

    if not entries:
        return None

    entries.sort(key=lambda x: x[1], reverse=True)

    supported = {loc["key"].lower(): loc["key"] for loc in get_supported_locales()}

    for code, _ in entries:
        lc = code.lower()
        if lc in supported:
            return supported[lc]
        base = lc.split("-", 1)[0]
        if base in supported:
            return supported[base]

    return None
