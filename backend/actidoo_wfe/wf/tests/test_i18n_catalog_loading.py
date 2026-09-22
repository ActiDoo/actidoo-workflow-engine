# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""The engine reads translation catalogs straight from ``.po`` files.

There is no compiled ``.mo`` and no build step: ``load_catalog`` parses the
``.po`` on first use, drops the msgctxt so lookups work by msgid alone, and
re-reads the file when it changes.
"""

import gettext
import os

from babel.messages.catalog import Catalog
from babel.messages.pofile import write_po

from actidoo_wfe.i18n import load_catalog


def _write_po(path, translations, context=None):
    catalog = Catalog(locale="de")
    for msgid, msgstr in translations.items():
        catalog.add(id=msgid, string=msgstr, context=context)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        write_po(f, catalog)


def test_loadCatalog_translatesByMsgidIgnoringContext(tmp_path):
    """A .po entry written with a msgctxt is found by its msgid alone, as the
    form and BPMN translators look strings up."""
    po = tmp_path / "de" / "LC_MESSAGES" / "Demo.po"
    _write_po(po, {"Amount": "Betrag"}, context="field.amount.label")

    catalog = load_catalog(po)

    assert catalog.gettext("Amount") == "Betrag"
    assert catalog.gettext("Unknown") == "Unknown"


def test_loadCatalog_missingFileFallsBackToMsgid(tmp_path):
    catalog = load_catalog(tmp_path / "de" / "LC_MESSAGES" / "Missing.po")

    assert isinstance(catalog, gettext.NullTranslations)
    assert catalog.gettext("Amount") == "Amount"


def test_loadCatalog_reloadsWhenFileChanges(tmp_path):
    """An edited .po takes effect without a restart: the cache is keyed by mtime."""
    po = tmp_path / "de" / "LC_MESSAGES" / "Demo.po"
    _write_po(po, {"Amount": "Betrag"})
    assert load_catalog(po).gettext("Amount") == "Betrag"

    _write_po(po, {"Amount": "Summe"})
    stat = po.stat()
    os.utime(po, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

    assert load_catalog(po).gettext("Amount") == "Summe"


def test_loadCatalog_unreadableFileFallsBackToMsgid(tmp_path, caplog):
    """A .po that cannot be parsed (wrong encoding, truncated write) must not take
    forms or mails down: the texts stay untranslated and the cause is logged."""
    po = tmp_path / "de" / "LC_MESSAGES" / "Broken.po"
    po.parent.mkdir(parents=True)
    po.write_bytes(b'msgid "Amount"\nmsgstr "Betr\xe4g"\n')  # Latin-1, not UTF-8

    catalog = load_catalog(po)

    assert catalog.gettext("Amount") == "Amount"
    assert "Cannot read translation catalog" in caplog.text
