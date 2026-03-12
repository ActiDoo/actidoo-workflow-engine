# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import copy

import jsonschema.exceptions
from sqlalchemy.orm import Session

from actidoo_wfe.database import SessionLocal


class ValidationTaskHelper:
    """
        This class is instantiated and passed to functions for custom form field validation
    """

    def __init__(
        self,
        form_data,
        property_path,
        allowed_data_models: set[str] | None = None,
    ):
        self.db: Session = SessionLocal()
        self.form_data = form_data
        self.property_path = property_path
        self._allowed_data_models: set[str] = allowed_data_models or set()

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
        if not self.form_data:
            return {}
        result = copy.deepcopy(self.form_data)
        current = self.form_data

        for key in self.property_path:
            if isinstance(current, list) and isinstance(key, int):
                current = current[key]
            elif isinstance(current, dict) and key in current:
                current = current[key]
            else:
                current = {}
                #raise ValueError("Invalid property path or data structure")

            if isinstance(current, dict):
                result.update(current)

        return result

    def raise_error(self, message):
        raise jsonschema.exceptions.ValidationError(message)
    