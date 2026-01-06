# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import copy

from sqlalchemy.orm import Session

from actidoo_wfe.database import SessionLocal


class OptionTaskHelper:
    """
        This class is instantiated and passed to functions for providing options for dynamic select form fields.
        The options functions are defined in the processes.
    """

    def __init__(
        self,
        form_data,
        property_path
    ):
        self.db: Session = SessionLocal()
        self.form_data = form_data
        self.property_path = property_path

    def get_form_field_environment(self):
        result = copy.deepcopy(self.form_data) if self.form_data else {}
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
