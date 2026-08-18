# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Exports form fixtures for the frontend's workflow-form tests.

The frontend tests render forms from JSON files that hold what the BFF returns for a
form: jsonschema + uischema (as in the task view) or the options of a select field (as in
POST user/search_property_options). A manifest lists the fixtures and their sources:

    {
      "test-flow-bff/form1.fixture.json": {"form": "TestFlowBff/Form1.form"},
      "test-flow-bff/form1.category-options.fixture.json": {
        "form": "TestFlowBff/Form1.form", "options": "category"
      }
    }

Fixture paths are relative to the manifest, form paths relative to wf/testdata/processes.
CLI: python -m actidoo_wfe.cli export-form-fixtures [--check]  (or `yarn fixtures` in frontend/)
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from actidoo_wfe.wf.form_transformation import transform_camunda_form_from_file
from actidoo_wfe.wf.service_form import get_options

PROCESSES_DIR = Path(__file__).resolve().parent / "testdata" / "processes"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = REPO_ROOT / "frontend" / "src" / "test" / "workflows" / "fixtures.json"


@dataclass
class ExportResult:
    updated: list[Path] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)
    stale: list[Path] = field(default_factory=list)  # check mode only: would change


def build_fixture(source: dict) -> dict:
    form_path = PROCESSES_DIR / source["form"]
    if not form_path.exists():
        raise FileNotFoundError(f"form file not found: {form_path}")
    form = transform_camunda_form_from_file(form_path)

    if "options" not in source:
        return {"jsonschema": form.jsonschema, "uischema": form.uischema}

    options = get_options(
        jsonschema=form.jsonschema,
        property_path=[source["options"]],
        options_folder=form_path.parent / "options",
        form_data={},
        functions_env={},
    )
    return {"options": [{"value": value, "label": label} for value, label in options]}


def export_form_fixtures(manifest_path: Path = DEFAULT_MANIFEST, check: bool = False) -> ExportResult:
    """Writes every fixture of the manifest; with check=True only reports what would change."""
    manifest = json.loads(manifest_path.read_text())
    result = ExportResult()
    for fixture, source in manifest.items():
        fixture_path = manifest_path.parent / fixture
        content = json.dumps(build_fixture(source), indent=2, ensure_ascii=False) + "\n"
        current = fixture_path.read_text() if fixture_path.exists() else None

        if current == content:
            result.unchanged.append(fixture_path)
        elif check:
            result.stale.append(fixture_path)
        else:
            fixture_path.parent.mkdir(parents=True, exist_ok=True)
            fixture_path.write_text(content)
            result.updated.append(fixture_path)
    return result
