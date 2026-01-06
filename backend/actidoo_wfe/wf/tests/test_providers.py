# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from actidoo_wfe.wf import providers as workflow_providers


@pytest.fixture(autouse=True)
def reload_registry():
    workflow_providers.registry.reload()
    yield
    workflow_providers.registry.reload()


def test_builtin_provider_exposes_default_workflows():
    names = list(workflow_providers.iter_workflow_names())
    assert "TestFlowBasicStart" in names

    workflow_dir = workflow_providers.get_workflow_directory("TestFlowBasicStart")
    assert workflow_dir.name == "TestFlowBasicStart"
    assert workflow_dir.exists()


def test_get_workflow_module_path_for_builtin_workflow():
    module_path = workflow_providers.get_workflow_module_path("TestFlowBasicStart")
    assert module_path == "actidoo_wfe.wf.processes.TestFlowBasicStart"


@dataclass
class DummyWorkflowProvider:
    workflow_dir: Path
    name: str = "dummy-provider"
    priority: int = 100

    def iter_workflow_names(self):
        yield "DummyFlow"

    def get_workflow_directory(self, workflow_name: str):  # pragma: no cover - structural typing
        if workflow_name == "DummyFlow":
            return self.workflow_dir
        return None

    def iter_directories(self):
        yield self.workflow_dir

    def get_module_path(self, workflow_name: str):
        return None


def test_custom_provider_registration(tmp_path: Path):
    dummy_dir = tmp_path / "DummyFlow"
    dummy_dir.mkdir()

    provider = DummyWorkflowProvider(workflow_dir=dummy_dir)
    workflow_providers.registry.register(provider, prepend=True)

    assert workflow_providers.get_workflow_directory("DummyFlow") == dummy_dir
    assert workflow_providers.get_provider("DummyFlow") is provider
