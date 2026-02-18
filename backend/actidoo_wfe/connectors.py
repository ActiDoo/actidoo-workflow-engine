# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""
Connector Registry — generic extension point for external connectors.

Extensions register connector *types* (name + config schema + factory).
Deployments configure named *instances* via ``settings.connectors``.
Workflow code obtains a context-manager handle via
``sth.get_connector(type_name, instance_name)``.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, ContextManager, Dict, List, Type

import venusian
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConnectorTypeNotFoundError(KeyError):
    """Raised when a connector type has not been registered."""


class ConnectorInstanceNotFoundError(KeyError):
    """Raised when a named connector instance is not present in settings."""


# ---------------------------------------------------------------------------
# ConnectorType — immutable descriptor for a registered connector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConnectorType:
    name: str
    config_schema: Type[BaseModel]
    factory: Callable[[BaseModel], ContextManager]
    source_name: str = ""


# ---------------------------------------------------------------------------
# ConnectorRegistry
# ---------------------------------------------------------------------------


class ConnectorRegistry:
    """Singleton-style registry for connector types."""

    def __init__(self) -> None:
        self._types: Dict[str, ConnectorType] = {}

    def register(self, ct: ConnectorType) -> None:
        existing = self._types.get(ct.name)
        if existing is not None:
            if existing.factory is ct.factory:
                return  # dedup — same factory, no conflict
            raise ValueError(
                f"Connector type '{ct.name}' already registered with a different factory "
                f"(existing source: {existing.source_name!r}, new source: {ct.source_name!r})"
            )
        self._types[ct.name] = ct
        log.debug("Registered connector type %r (source=%s)", ct.name, ct.source_name or "?")

    def get_type(self, name: str) -> ConnectorType:
        try:
            return self._types[name]
        except KeyError:
            raise ConnectorTypeNotFoundError(
                f"Connector type '{name}' is not registered. "
                f"Available types: {sorted(self._types)}"
            ) from None

    def list_types(self) -> List[str]:
        return sorted(self._types)

    def clear(self) -> None:
        self._types.clear()


connector_registry = ConnectorRegistry()


# ---------------------------------------------------------------------------
# get_connector — resolution helper
# ---------------------------------------------------------------------------


def get_connector(type_name: str, instance_name: str) -> ContextManager:
    """Resolve a configured connector instance and return its context manager.

    1. Look up the registered *type*.
    2. Load the raw config dict from ``settings.connectors[type_name][instance_name]``.
    3. Validate via the type's Pydantic config schema.
    4. Call the factory to obtain a context manager.
    """
    from actidoo_wfe.settings import settings

    ct = connector_registry.get_type(type_name)

    type_instances = settings.connectors.get(type_name)
    if not type_instances:
        raise ConnectorInstanceNotFoundError(
            f"No connector instances configured for type '{type_name}'. "
            f"Expected settings.connectors['{type_name}'] to contain instance configs."
        )

    raw_config = type_instances.get(instance_name)
    if raw_config is None:
        raise ConnectorInstanceNotFoundError(
            f"Connector instance '{instance_name}' not found for type '{type_name}'. "
            f"Available instances: {sorted(type_instances)}"
        )

    validated = ct.config_schema(**raw_config)
    return ct.factory(validated)


# ---------------------------------------------------------------------------
# Startup validation (optional, non-blocking)
# ---------------------------------------------------------------------------


def validate_configured_connectors() -> List[str]:
    """Validate all configured connector instances against their schemas.

    Returns a list of warning strings.  Does **not** raise.
    """
    from actidoo_wfe.settings import settings

    warnings: List[str] = []
    for type_name, instances in settings.connectors.items():
        try:
            ct = connector_registry.get_type(type_name)
        except ConnectorTypeNotFoundError:
            warnings.append(f"Configured connector type '{type_name}' is not registered")
            continue

        if not isinstance(instances, dict):
            warnings.append(f"Connector '{type_name}': expected dict of instances, got {type(instances).__name__}")
            continue

        for instance_name, raw_config in instances.items():
            try:
                ct.config_schema(**raw_config)
            except ValidationError as exc:
                warnings.append(f"Connector {type_name}/{instance_name}: {exc}")
            except Exception as exc:
                warnings.append(f"Connector {type_name}/{instance_name}: unexpected error: {exc}")

    return warnings


# ---------------------------------------------------------------------------
# @register_connector_type — venusian decorator (dual registration)
# ---------------------------------------------------------------------------


def register_connector_type(
    *,
    name: str,
    config_schema: Type[BaseModel],
    source_name: str = "",
):
    """Decorator to register a connector factory via venusian scan.

    Follows the same dual-registration pattern as ``@register_workflow_provider``:
    the factory is registered immediately (so tests/scripts work without scanning)
    **and** via a venusian callback (for normal app startup).

    Usage::

        @register_connector_type(name="jira", config_schema=JiraConfig)
        @contextlib.contextmanager
        def jira_connector(config: JiraConfig):
            jira = Jira(url=config.url, ...)
            try:
                yield jira
            finally:
                jira.close()
    """

    def decorator(factory: Callable[[BaseModel], ContextManager]):
        ct = ConnectorType(
            name=name,
            config_schema=config_schema,
            factory=factory,
            source_name=source_name or getattr(factory, "__qualname__", str(factory)),
        )

        def callback(scanner, _name, _ob):
            connector_registry.register(ct)

        venusian.attach(factory, callback)
        connector_registry.register(ct)
        return factory

    return decorator
