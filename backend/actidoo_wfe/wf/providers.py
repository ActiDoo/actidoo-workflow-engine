# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Protocol, Sequence, Tuple

import venusian
from actidoo_wfe.wf.constants import BPMN_DIRECTORY

log = logging.getLogger(__name__)


class WorkflowProvider(Protocol):
    """Lightweight protocol describing workflow providers."""

    name: str
    priority: int

    def iter_workflow_names(self) -> Iterable[str]:
        ...

    def get_workflow_directory(self, workflow_name: str) -> Optional[Path]:
        ...

    def iter_directories(self) -> Iterable[Path]:
        ...

    def get_module_path(self, workflow_name: str) -> Optional[str]:
        ...


@dataclass(eq=False)
class FileSystemWorkflowProvider:
    """Provider exposing workflows from a directory on disk."""

    base_path: Path
    name: str = "builtin"
    priority: int = 0
    module_base: Optional[str] = "actidoo_wfe.wf.processes"

    def iter_workflow_names(self) -> Iterable[str]:
        for directory in self.iter_directories():
            yield directory.name

    def iter_directories(self) -> Iterable[Path]:
        if not self.base_path.exists():
            return []
        return [path for path in self.base_path.iterdir() if path.is_dir()]

    def get_workflow_directory(self, workflow_name: str) -> Optional[Path]:
        candidate = self.base_path / workflow_name
        return candidate if candidate.exists() else None

    def get_module_path(self, workflow_name: str) -> Optional[str]:
        if not self.module_base:
            return None
        return f"{self.module_base}.{workflow_name}"


@dataclass
class WorkflowProviderRegistry:
    """Collects installed workflow providers (built-in + venusian-registered) and resolves workflows."""

    providers: List[WorkflowProvider] = field(default_factory=list)

    def __post_init__(self) -> None:
        builtin = FileSystemWorkflowProvider(base_path=BPMN_DIRECTORY)
        self.providers = self._sort_providers([builtin])

    def reload(self) -> None:
        """Reset to builtin provider set."""
        builtin = FileSystemWorkflowProvider(base_path=BPMN_DIRECTORY)
        self.providers = self._sort_providers([builtin])

    def register(self, provider: WorkflowProvider, *, prepend: bool = False) -> None:
        if provider in self.providers:
            return
        if prepend:
            self.providers.insert(0, provider)
        else:
            self.providers.append(provider)
        self.providers = self._sort_providers(self.providers)

    def clear(self) -> None:
        self.providers = []

    def iter_providers(self) -> Iterator[WorkflowProvider]:
        yield from self.providers

    def iter_workflow_entries(self) -> Iterator[Tuple[str, Path]]:
        seen: set[str] = set()
        for provider in self.providers:
            for name in provider.iter_workflow_names():
                if name in seen:
                    continue
                directory = provider.get_workflow_directory(name)
                if directory is None:
                    continue
                seen.add(name)
                yield name, directory

    def iter_workflow_names(self) -> Iterator[str]:
        for name, _ in self.iter_workflow_entries():
            yield name

    def iter_workflow_directories(self) -> Iterator[Path]:
        for _, directory in self.iter_workflow_entries():
            yield directory

    def get_workflow_directory(self, workflow_name: str) -> Path:
        for provider in self.providers:
            directory = provider.get_workflow_directory(workflow_name)
            if directory is not None:
                return directory
        raise FileNotFoundError(f"No workflow named '{workflow_name}' found in registered providers.")

    def get_provider_for(self, workflow_name: str) -> WorkflowProvider:
        for provider in self.providers:
            directory = provider.get_workflow_directory(workflow_name)
            if directory is not None:
                return provider
        raise FileNotFoundError(f"No workflow named '{workflow_name}' found in registered providers.")

    def _sort_providers(self, providers: Sequence[WorkflowProvider]) -> List[WorkflowProvider]:
        return sorted(providers, key=lambda provider: getattr(provider, "priority", 0), reverse=True)


registry = WorkflowProviderRegistry()


def _normalize_provider(candidate, label: str) -> Optional[WorkflowProvider]:
    obj = candidate
    if callable(candidate) and not hasattr(candidate, "iter_workflow_names"):
        try:
            obj = candidate()
        except Exception as error:
            log.error("Calling workflow provider factory '%s' failed: %s", label, error)
            return None

    if all(
        hasattr(obj, attr)
        for attr in ("iter_workflow_names", "get_workflow_directory", "get_module_path")
    ):
        return obj

    log.error("Workflow provider '%s' did not yield a valid provider.", label)
    return None


def register_workflow_provider(*, name: str | None = None):
    """
    Decorator to register a workflow provider (instance or factory) via venusian scan.
    Used by engine-internal providers and extensions that mark themselves for scanning.
    """

    def decorator(candidate):
        label = name or getattr(candidate, "__name__", str(candidate))
        provider_instance: WorkflowProvider | None = None

        def resolve():
            nonlocal provider_instance
            if provider_instance is None:
                provider_instance = _normalize_provider(candidate, label)
            return provider_instance

        def callback(scanner, _name, _ob):
            provider = resolve()
            if provider is not None:
                registry.register(provider)

        venusian.attach(candidate, callback)
        provider = resolve()
        if provider is not None:
            registry.register(provider)
        return candidate

    return decorator


def get_workflow_directory(workflow_name: str) -> Path:
    return registry.get_workflow_directory(workflow_name)


def get_workflow_module_path(workflow_name: str) -> Optional[str]:
    provider = registry.get_provider_for(workflow_name)
    return provider.get_module_path(workflow_name)


def iter_workflow_entries() -> Iterator[Tuple[str, Path]]:
    return registry.iter_workflow_entries()


def iter_workflow_directories() -> Iterator[Path]:
    return registry.iter_workflow_directories()


def iter_workflow_names() -> Iterator[str]:
    return registry.iter_workflow_names()


def get_provider(workflow_name: str) -> WorkflowProvider:
    return registry.get_provider_for(workflow_name)


__all__ = [
    "ENTRY_POINT_GROUP",
    "FileSystemWorkflowProvider",
    "WorkflowProvider",
    "WorkflowProviderRegistry",
    "get_provider",
    "get_workflow_directory",
    "get_workflow_module_path",
    "iter_workflow_directories",
    "iter_workflow_entries",
    "iter_workflow_names",
    "registry",
]
