# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Dev/test-only workflow fixtures and data models.

This package bundles the engine's own ``TestFlow*`` / ``Feel*`` workflows
(``processes/``) and their demo data models (``datamodels/``). They exist for
local development and the test suite; they are activated only when
``settings.show_test_workflows`` is on and are **excluded from the production
wheel** (see ``[tool.setuptools.packages.find].exclude`` in ``pyproject.toml``).

NAMING CONSTRAINT: the venusian scan ignores any module whose dotted name
contains the substring ``test_`` (``ignore=[re.compile("test_").search]`` in
``fastapi.py`` / ``conftest.py``). This package must therefore never be renamed
to anything containing ``test_`` (e.g. ``test_data``) — it would be silently
skipped and nothing here would register.
"""
