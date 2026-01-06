# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH


import copy
import gettext
import json
import pathlib
import re
import xml.etree.ElementTree as ET
from functools import cache
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import pycountry
from babel import Locale as BabelLocale
from babel import localedata
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po
from babel.support import Translations

from actidoo_wfe.settings import settings
from actidoo_wfe.wf import providers as workflow_providers
from actidoo_wfe.wf.types import ReactJsonSchemaFormData


def _available_locales_for(process: str, workflow_dir: pathlib.Path) -> List[str]:
    """List the folder names under i18n/locales/ for this process."""
    locales_dir = workflow_dir / "i18n" / "locales"
    if not locales_dir.exists():
        return []
    return [
        p.name for p in locales_dir.iterdir()
        if p.is_dir() and (p / "LC_MESSAGES" / f"{process}.mo").exists()
    ]


def _load_translations(process: str, locale: str, workflow_dir: pathlib.Path) -> Union[gettext.GNUTranslations, gettext.NullTranslations]:
    """
    Loads Babel translations with context support.
    Expects: 
      wf/processes/<process>/i18n/locales/<locale>/LC_MESSAGES/<process>.mo
    """

    available = _available_locales_for(process, workflow_dir)
    
    # pick the best one
    chosen = match_translation(
        user_locale=locale or settings.default_locale,
        available=available
    )

    return Translations.load(
        dirname=workflow_dir / "i18n" / "locales",
        locales=[chosen],
        domain=process
    )


def _resolve_workflow_directory(process: str, base: Optional[pathlib.Path]) -> pathlib.Path:
    if base is None:
        return workflow_providers.get_workflow_directory(process)
    if (base / "i18n").exists():
        return base
    return base / process


def translate_form_data(
    form_data: ReactJsonSchemaFormData,
    workflow_name: str,
    locale: str,
    base_i18n_dir: Optional[pathlib.Path] = None,
) -> ReactJsonSchemaFormData:
    """
    Translates jsonschema and uischema from form_data using the .mo file
    for the given process (workflow_name) and locale.
    """
    # 1) Load translations
    workflow_dir = _resolve_workflow_directory(workflow_name, base_i18n_dir)
    t = _load_translations(workflow_name, locale, workflow_dir)

    # 2) Lookup function with context and fallback logic
    def _translate(msgid: str) -> str:
        translated = msgid
        if msgid.strip():
            translated = t.gettext(msgid)
        return translated

    # 3) Deepcopy to leave the original unchanged
    translated = copy.deepcopy(form_data)

    # 4) Translate jsonschema
    def _translate_schema(node: Any):
        if isinstance(node, dict):
            if "title" in node and isinstance(node["title"], str):
                node["title"] = _translate(node["title"])
            if "oneOf" in node and isinstance(node["oneOf"], list):
                for choice in node["oneOf"]:
                    if "title" in choice and isinstance(choice["title"], str):
                        choice["title"] = _translate(choice["title"])
            for v in node.values():
                _translate_schema(v)
        elif isinstance(node, list):
            for item in node:
                _translate_schema(item)

    _translate_schema(translated.jsonschema)

    # 5) Translate uischema
    def _translate_uischema(node: Any):
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if k in ("ui:description", "ui:label",
                         "ui:arrayAddButtonText", "ui:arrayOverviewButtonText") \
                   and isinstance(v, str):
                    node[k] = _translate(v)
                else:
                    _translate_uischema(v)
        elif isinstance(node, list):
            for item in node:
                _translate_uischema(item)

    _translate_uischema(translated.uischema)

    return translated


def translate_string(
    msgid: str,
    workflow_name: str,
    locale: str,
    base_i18n_dir: Optional[pathlib.Path] = None,
) -> str:
    # 1) Load translations
    workflow_dir = _resolve_workflow_directory(workflow_name, base_i18n_dir)
    t = _load_translations(workflow_name, locale, workflow_dir)

    # 2) Lookup function with context and fallback logic
    def _translate(msgid: str) -> str:
        translated = msgid
        if msgid.strip():
            translated = t.gettext(msgid)
        return translated

    return _translate(msgid)

def get_first(component, attrlist):
    for attr in attrlist:
        if attr in component:
            return component[attr]

def extract_strings_from_form(form_json: dict) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []

    def extract(component: dict, prefix:str = ""):
        strid = get_first(component, ["path", "key", "id"])

        for key in ("label", "description", "text"):
            if key in component and isinstance(component[key], str):
                msgid = component[key].strip()
                msgctxt = f"{prefix}{strid}.{key}"
                if key=="label" and "text" in component:
                    # Text-Views Fields have a label of "Text view" which we never show. These should not be translated.
                    continue
                entries.append((msgid, msgctxt))
        if "values" in component:
            for entry in component["values"]:
                if "label" in entry:
                    msgid = entry["label"].strip()
                    value = entry.get("value", "")
                    msgctxt = f"{prefix}{strid}.value.{value}"
                    entries.append((msgid, msgctxt))
        if "components" in component:
            for child in component["components"]:
                extract(child, prefix=f"{prefix}{strid}.")

    for json_file in form_json:
        extract(json_file)
    return entries

def extract_strings_from_bpmn(xml_path: Path) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []
    ns = {'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL'}

    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    for tag in ('process', 'lane', 'userTask'):
        for elem in root.findall(f'.//bpmn:{tag}', ns):
            name = elem.get('name')
            if name and name.strip():
                elem_id = elem.get('id', 'unknown')
                msgctxt = f"{elem_id}.{tag}"
                entries.append((name.strip(), msgctxt))
    return entries

def extract_messages_for_process(process: str):
    workflow_dir = _resolve_workflow_directory(process, None)
    pot_path = workflow_dir / "i18n" / f"{process}.pot"
    pot_path.parent.mkdir(parents=True, exist_ok=True)

    catalog = Catalog(locale=None, project=process)

    for json_path in workflow_dir.glob("*.form"):
        with open(json_path, 'r', encoding='utf-8') as f:
            form = json.load(f)
        for msgid, msgctxt in extract_strings_from_form(form.get("components", [])):
            catalog.add(id=msgid, context=msgctxt)

    for bpmn_path in workflow_dir.glob("*.bpmn"):
        for msgid, msgctxt in extract_strings_from_bpmn(bpmn_path):
            catalog.add(id=msgid, context=msgctxt)

    with open(pot_path, 'wb') as f:
        write_po(f, catalog, ignore_obsolete=True)
    return pot_path

def update_catalogue(template_pot: Path, input_po: Path, output_po: Path, locale: str):
    with open(template_pot, 'rb') as f:
        tpl = read_po(f)

    if input_po.exists():
        with open(input_po, 'rb') as f:
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
                        m.flags.add('fuzzy')
                        added = True
                        break
        if not added:
            updated.add(id=msg.id, context=msg.context)

    if existing:
        tpl_ctxs = {m.context for m in tpl}
        for old in existing:
            if old.context not in tpl_ctxs:
                obs = updated.add(id=old.id, string=old.string, context=old.context)
                setattr(obs, 'obsolete', True)

    output_po.parent.mkdir(parents=True, exist_ok=True)
    with open(output_po, 'wb') as f:
        write_po(f, updated)

def update_process(process: str, locale: str):
    workflow_dir = _resolve_workflow_directory(process, None)
    pot = workflow_dir / "i18n" / f"{process}.pot"
    po = workflow_dir / "i18n" / "locales" / locale / "LC_MESSAGES" / f"{process}.po"
    update_catalogue(template_pot=pot, input_po=po, output_po=po, locale=locale)
    return po

def compile_all():
    for workflow_dir in workflow_providers.iter_workflow_directories():
        locales_root = workflow_dir / "i18n" / "locales"
        if not locales_root.exists():
            continue
        for po_file in locales_root.glob("**/LC_MESSAGES/*.po"):
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


MAX_LOCALE_KEY_LENGTH = 10  # workflow_users.locale column length


@cache
def get_supported_locales() -> List[dict[str, str]]:
    """
    Return all Babel-known locales, with labels like
      "German (Austria)", "German (Austria, Latn)", "English", etc.
    Include script in label when needed to distinguish variants.
    Skip any codes that don’t parse or map to a known language/country.
    """
    entries: List[dict[str, str]] = []
    seen_keys: set[str] = set()
    for code in localedata.locale_identifiers():
        hyphenated = code.replace('_', '-')
        if len(hyphenated) > MAX_LOCALE_KEY_LENGTH:
            continue
        try:
            loc = BabelLocale.parse(code)
        except (ValueError, LookupError):
            continue

        # lookup language name
        lang = pycountry.languages.get(alpha_2=loc.language)
        if not lang:
            continue
        lang_name = lang.name

        # prepare label components
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

        # build label string
        if len(label_parts) > 1:
            label = f"{label_parts[0]} ({', '.join(label_parts[1:])})"
        else:
            label = label_parts[0]

        if hyphenated in seen_keys:
            continue

        entries.append({'key': hyphenated, 'label': label})
        seen_keys.add(hyphenated)

    # Sort alphabetically by label
    entries.sort(key=lambda x: x['label'])
    return entries


ACCEPT_LANG_RE = re.compile(r"""
    \s*
    (?P<lang>[A-Za-z0-9\-_]+)      # language[-REGION]
    (?:\s*;\s*q=(?P<q>0(\.\d+)?|1(\.0+)?))?  # optional ;q=0.xxx or 1.0
    \s*
""", re.VERBOSE)


def extract_primary_locale(
    accept_language_header: str
) -> Optional[str]:
    """
    Parse Accept-Language, sort by quality, but *only* return a code that’s
    in your supported_locales list (exact or language-only fallback);
    otherwise return None.
    """
    # 1) collect (code, q)
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

    # 2) sort by q desc
    entries.sort(key=lambda x: x[1], reverse=True)

    # 3) build a lowercase→canonical map of supported keys
    supported = {loc["key"].lower(): loc["key"] for loc in get_supported_locales()}

    # 4) pick the first entry that matches supported (exact or base)
    for code, _ in entries:
        lc = code.lower()
        if lc in supported:
            return supported[lc]
        base = lc.split("-", 1)[0]
        if base in supported:
            return supported[base]

    return None


def match_translation(
    user_locale: str,
    available: list[str]
) -> str:
    """
    1) Try exact match (case-insensitive) against available.
    2) Fallback to the base language (case-insensitive).
    3) Return default_locale from settings.
    """
    # build a map lowercased → original
    lowered_map = {locale.lower(): locale for locale in available}
    ul = user_locale.lower()

    # 1) exact (language+region) match
    if ul in lowered_map:
        return lowered_map[ul]

    # 2) try just the language part
    base = ul.split("-", 1)[0]
    if base in lowered_map:
        return lowered_map[base]

    # 3) fallback
    return settings.default_locale
