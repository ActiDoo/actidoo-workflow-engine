# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import importlib
import logging
from importlib import metadata
from types import ModuleType
from typing import Any, Iterable, List

log = logging.getLogger(__name__)

# Extensions advertise themselves for venusian scanning via this entry point group.
# The engine scans actidoo_wfe + all advertised modules to pick up decorator registrations
# (cron tasks, login hooks, workflow/user attribute providers, etc.).
ENTRY_POINT_GROUP = "actidoo_wfe.venusian_scan"


def _as_module(candidate: Any, entry_point_name: str) -> list[ModuleType]:
    """Normalize a single entry point result to modules (string, module, callable or iterable)."""
    modules: list[ModuleType] = []

    if isinstance(candidate, str):
        try:
            modules.append(importlib.import_module(candidate))
        except Exception as error:
            log.error("Unable to import module '%s' from venusian scan entry point '%s': %s", candidate, entry_point_name, error)
        return modules

    if isinstance(candidate, ModuleType):
        modules.append(candidate)
        return modules

    if callable(candidate):
        try:
            returned = candidate()
        except Exception as error:
            log.error("Calling venusian scan entry point '%s' failed: %s", entry_point_name, error)
            return modules
        return _as_module(returned, entry_point_name)

    if isinstance(candidate, Iterable):
        for item in candidate:
            modules.extend(_as_module(item, entry_point_name))
        return modules

    log.error("Entry point '%s' did not yield a module, string, callable or iterable of those.", entry_point_name)
    return modules


def discover_venusian_scan_targets(default_modules: Iterable[ModuleType]) -> List[ModuleType]:
    """Return modules to be scanned by Venusian, combining defaults and entry points."""
    targets: list[ModuleType] = list(default_modules)
    seen: set[str] = {mod.__name__ for mod in targets if hasattr(mod, "__name__")}

    try:
        entries = metadata.entry_points().select(group=ENTRY_POINT_GROUP)
    except Exception as error:
        log.warning("Failed to load venusian scan entry points: %s", error)
        entries = []

    for entry_point in entries:
        for module in _as_module(entry_point.load(), entry_point.name):
            if not hasattr(module, "__name__"):
                continue
            if module.__name__ in seen:
                continue
            seen.add(module.__name__)
            targets.append(module)

    return targets
