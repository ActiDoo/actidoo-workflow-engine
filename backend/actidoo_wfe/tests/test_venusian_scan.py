# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import types

import pytest

from actidoo_wfe.venusian_scan import ENTRY_POINT_GROUP, discover_venusian_scan_targets


def test_discover_targets_loads_modules(monkeypatch):
    loaded = {"count": 0}

    class FakeEntryPoint:
        name = "ext"

        def load(self):
            loaded["count"] += 1
            return "math"

    def fake_entry_points():
        class EPCollection:
            def select(self, group):
                return [FakeEntryPoint()] if group == ENTRY_POINT_GROUP else []

        return EPCollection()

    monkeypatch.setattr("actidoo_wfe.venusian_scan.metadata.entry_points", fake_entry_points)

    targets = discover_venusian_scan_targets(default_modules=[])

    assert loaded["count"] == 1
    assert any(mod.__name__ == "math" for mod in targets)


def test_discover_targets_ignores_duplicates(monkeypatch):
    mod = types.ModuleType("dummy")

    class FakeEntryPoint:
        name = "ext"

        def load(self):
            return mod

    def fake_entry_points():
        class EPCollection:
            def select(self, group):
                return [FakeEntryPoint()] if group == ENTRY_POINT_GROUP else []

        return EPCollection()

    monkeypatch.setattr("actidoo_wfe.venusian_scan.metadata.entry_points", fake_entry_points)

    targets = discover_venusian_scan_targets(default_modules=[mod])

    assert targets.count(mod) == 1
