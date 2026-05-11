# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Per-workflow gettext catalog handling.

Each workflow ships its own ``i18n/locales/<locale>/LC_MESSAGES/<wf>.po`` and is
loaded via ``translate_string`` / ``translate_form_data``.

Generic catalog utilities (locale matching, PO/MO compile, supported-locale
listing, global ``messages`` catalog) live in :mod:`actidoo_wfe.i18n`.
"""

import copy
import gettext
import json
import pathlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from babel.messages.catalog import Catalog
from babel.messages.pofile import write_po
from babel.support import Translations

from actidoo_wfe.i18n import (
    compile_global_catalog,
    compile_po_to_mo,
    match_translation,
    update_catalogue,
)
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import providers as workflow_providers
from actidoo_wfe.wf.types import ReactJsonSchemaFormData


def _available_locales_for(process: str, workflow_dir: pathlib.Path) -> List[str]:
    """List the folder names under i18n/locales/ for this process."""
    locales_dir = workflow_dir / "i18n" / "locales"
    if not locales_dir.exists():
        return []
    return [p.name for p in locales_dir.iterdir() if p.is_dir() and (p / "LC_MESSAGES" / f"{process}.mo").exists()]


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
        available=available,
    )

    return Translations.load(
        dirname=workflow_dir / "i18n" / "locales",
        locales=[chosen],
        domain=process,
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
                if k in ("ui:description", "ui:label", "ui:arrayAddButtonText", "ui:arrayOverviewButtonText") and isinstance(v, str):
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

    def extract(component: dict, prefix: str = ""):
        strid = get_first(component, ["path", "key", "id"])

        for key in ("label", "description", "text"):
            if key in component and isinstance(component[key], str):
                msgid = component[key].strip()
                msgctxt = f"{prefix}{strid}.{key}"
                if key == "label" and "text" in component:
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
    ns = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}

    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    for tag in ("process", "lane", "userTask"):
        for elem in root.findall(f".//bpmn:{tag}", ns):
            name = elem.get("name")
            if name and name.strip():
                elem_id = elem.get("id", "unknown")
                msgctxt = f"{elem_id}.{tag}"
                entries.append((name.strip(), msgctxt))
    return entries


def extract_messages_for_process(process: str):
    workflow_dir = _resolve_workflow_directory(process, None)
    pot_path = workflow_dir / "i18n" / f"{process}.pot"
    pot_path.parent.mkdir(parents=True, exist_ok=True)

    catalog = Catalog(locale=None, project=process)

    for json_path in workflow_dir.glob("*.form"):
        with open(json_path, "r", encoding="utf-8") as f:
            form = json.load(f)
        for msgid, msgctxt in extract_strings_from_form(form.get("components", [])):
            catalog.add(id=msgid, context=msgctxt)

    for bpmn_path in workflow_dir.glob("*.bpmn"):
        for msgid, msgctxt in extract_strings_from_bpmn(bpmn_path):
            catalog.add(id=msgid, context=msgctxt)

    with open(pot_path, "wb") as f:
        write_po(f, catalog, ignore_obsolete=True)
    return pot_path


def update_process(process: str, locale: str):
    workflow_dir = _resolve_workflow_directory(process, None)
    pot = workflow_dir / "i18n" / f"{process}.pot"
    po = workflow_dir / "i18n" / "locales" / locale / "LC_MESSAGES" / f"{process}.po"
    update_catalogue(template_pot=pot, input_po=po, output_po=po, locale=locale)
    return po


def compile_all():
    """Compile every workflow's .po into .mo, then the global ``messages`` catalog."""
    for workflow_dir in workflow_providers.iter_workflow_directories():
        locales_root = workflow_dir / "i18n" / "locales"
        if not locales_root.exists():
            continue
        for po_file in locales_root.glob("**/LC_MESSAGES/*.po"):
            compile_po_to_mo(po_file)

    compile_global_catalog()
