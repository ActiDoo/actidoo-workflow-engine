# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import copy

from sqlalchemy.orm import Session

from actidoo_wfe.database import SessionLocal


class ChangeTaskHelper:
    """
    This class is instantiated and passed to change functions, which derive form values from other form values.
    The change functions are defined in the processes and modify ``form_data`` in place.
    """

    def __init__(
        self,
        form_data,
        path,
        allowed_data_models: set[str] | None = None,
        jsonschema: dict | None = None,
    ):
        self.db: Session = SessionLocal()
        self.form_data = form_data
        self.jsonschema = jsonschema or {}
        self._allowed_data_models: set[str] = allowed_data_models or set()
        self.path = list(path)
        self.key = self.path[-1]
        self.row = form_data
        for part in self.path[:-1]:
            self.row = self.row[part]
        self.value = self.row.get(self.key)

    def get_connector(self, type_name: str, instance_name: str):
        """Obtain a configured connector as a context manager."""
        from actidoo_wfe.connectors import get_connector

        return get_connector(type_name=type_name, instance_name=instance_name)

    def get_model(self, model_name: str) -> type:
        """Return the SQLAlchemy model class for a declared data model.

        Raises DataModelAccessDeniedError if the workflow did not declare
        the model in its DATA_MODELS list.
        """
        from actidoo_wfe.wf.exceptions import DataModelAccessDeniedError
        from actidoo_wfe.wf.registry_data_model import data_model_registry

        if model_name not in self._allowed_data_models:
            raise DataModelAccessDeniedError(model_name, self._allowed_data_models)
        descriptor = data_model_registry.get(model_name)
        return descriptor.model_class

    def get_form_field_environment(self):
        result = copy.deepcopy(self.form_data) if self.form_data else {}
        current = self.form_data
        schema = self.jsonschema

        for key in self.path:
            schema = schema.get("items", {}) if isinstance(key, int) else schema.get("properties", {}).get(key, {})
            if isinstance(current, list) and isinstance(key, int) or isinstance(current, dict) and key in current:
                current = current[key]
            else:
                current = {}

            if isinstance(current, dict):
                result.update(dict.fromkeys(schema.get("properties", {})))
                result.update(current)

        return result
