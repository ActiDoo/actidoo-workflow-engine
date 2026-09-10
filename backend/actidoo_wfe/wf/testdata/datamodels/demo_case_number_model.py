# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Demo number range for the reference example (ADR 012).

``DemoCaseNumber`` is a number range: its rows *are* the issued numbers, so the
same table is both the sequence and the record of which workflow instance and
which step received which number. Driven by ``TestFlowNumberRange``.

Registered without an API config - a range is numbering machinery, not a business
record for the Data page. Registered only with test workflows enabled, so it never
appears in production.
"""

from __future__ import annotations

from actidoo_wfe.settings import settings
from actidoo_wfe.wf.models import extension_model_base
from actidoo_wfe.wf.models import NumberRangeMixin
from actidoo_wfe.wf.registry_data_model import register_data_model

DemoBase = extension_model_base("demo")


class DemoCaseNumber(DemoBase, NumberRangeMixin):
    _ext_table = "case_number"  # -> ext_demo_case_number

    # id comes from the data-model base; value / formatted / scope_key /
    # workflow_instance_task_id / alloc_key / workflow_instance_id / created_at
    # come from NumberRangeMixin. A plain range needs no columns of its own -
    # only the scheme below.

    @classmethod
    def next_value(cls, previous: int | None) -> int:
        """One dense sequence starting at 1000."""
        return 1000 if previous is None else previous + 1

    @classmethod
    def format_number(cls, value: int, scope_key: str) -> str:
        return f"CASE-{value:05d}"


def register_demo_case_number() -> None:
    """Register the demo range. Idempotent (the registry dedups by model class)."""
    register_data_model(name="DemoCaseNumber")(DemoCaseNumber)


if settings.show_test_workflows:
    register_demo_case_number()
