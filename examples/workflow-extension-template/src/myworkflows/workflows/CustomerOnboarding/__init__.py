# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Python helpers that can be referenced from BPMN service or script tasks."""

from __future__ import annotations

from datetime import datetime, timezone


def set_initial_payload(task, **_kwargs):
    """Populate default data for the onboarding workflow."""

    task.data.setdefault("applicant_name", "Sample Applicant")
    task.data["submitted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")


def approve_application(task, **_kwargs):
    """Mark the workflow as approved."""

    task.data["status"] = "approved"
