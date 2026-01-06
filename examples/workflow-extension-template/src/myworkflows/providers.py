# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from __future__ import annotations

"""Workflow provider that exposes packaged BPMN assets to the host engine."""

from pathlib import Path

from actidoo_wfe.wf.providers import FileSystemWorkflowProvider, register_workflow_provider


@register_workflow_provider(name="myworkflows")
def get_provider() -> FileSystemWorkflowProvider:
    """Registered via venusian scan; exposes packaged workflows."""
    base_path = Path(__file__).parent / "workflows"
    return FileSystemWorkflowProvider(
        base_path=base_path,
        name="myworkflows",
        priority=100,
        module_base="myworkflows.workflows",
    )
