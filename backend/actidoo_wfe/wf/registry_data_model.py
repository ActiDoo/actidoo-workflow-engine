# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

import venusian

from actidoo_wfe.wf.config_data_model import WorkflowDataApiConfig
from actidoo_wfe.wf.exceptions import DataModelNotFoundError
from actidoo_wfe.wf.models import WorkflowManagedMixin

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataModelDescriptor:
    name: str
    model_class: type
    namespace: str
    api: WorkflowDataApiConfig | None = None


class DataModelRegistry:
    def __init__(self) -> None:
        self._models: Dict[str, DataModelDescriptor] = {}

    def register(self, descriptor: DataModelDescriptor) -> None:
        existing = self._models.get(descriptor.name)
        if existing is not None:
            if existing.model_class is descriptor.model_class:
                return  # dedup
            raise ValueError(
                f"Data model '{descriptor.name}' already registered with a different model class (existing: {existing.model_class.__name__}, new: {descriptor.model_class.__name__})",
            )
        self._models[descriptor.name] = descriptor
        log.debug("Registered data model %r (namespace=%s, table=%s)", descriptor.name, descriptor.namespace, getattr(descriptor.model_class, "__tablename__", "?"))

    def get(self, name: str) -> DataModelDescriptor:
        try:
            return self._models[name]
        except KeyError:
            raise DataModelNotFoundError(
                f"Data model '{name}' is not registered. Available: {sorted(self._models)}",
            ) from None

    def list_names(self) -> List[str]:
        return sorted(self._models)

    def list_models(self) -> List[DataModelDescriptor]:
        return list(self._models.values())

    def clear(self) -> None:
        self._models.clear()


data_model_registry = DataModelRegistry()


def register_data_model(
    *,
    name: str,
    api: WorkflowDataApiConfig | None = None,
):
    """Decorator to register a data model class.

    Usage::

        @register_data_model(name="OrderApproval")
        class OrderApproval(AcmeModel):
            _ext_table = "order_approval"
            ...

    If *api* is provided, the model must use ``WorkflowManagedMixin``.
    """

    def decorator(model_class: type) -> type:
        if api is not None and not issubclass(model_class, WorkflowManagedMixin):
            raise TypeError(
                f"Data model '{name}' provides an api config but does not use WorkflowManagedMixin. Only workflow-managed models can be exposed via the API.",
            )

        namespace = getattr(model_class, "_ext_namespace", "")
        descriptor = DataModelDescriptor(
            name=name,
            model_class=model_class,
            namespace=namespace,
            api=api,
        )

        def callback(scanner, _name, _ob):
            data_model_registry.register(descriptor)

        venusian.attach(model_class, callback)
        data_model_registry.register(descriptor)
        return model_class

    return decorator
