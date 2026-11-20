# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import pytest

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.exceptions import ValidationResultContainsErrors
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy


def test_prefilled_validation_cases_and_last_submit(db_engine_ctx):
    with db_engine_ctx():
        workflow = WorkflowDummy(
            db_session=SessionLocal(),
            users_with_roles={"initiator": ["wf-user"]},
            workflow_name="TestFlow_FormSemantics",
            start_user="initiator",
        )
        user = workflow.user("initiator")
        instance = workflow.workflow_instance_id
        task = user.get_usertasks(instance, 1)[0]
        assert len(task.data["required_positions"]) == 1
        assert task.data["required_tags"] == ["a"]
        assert task.data["required_choice"] == "a"
        assert task.data["hide_required_lists"] is False
        assert task.data["confirm_review"] is True

        # Submit the values shown in a fresh task, including form defaults.
        payload = {
            key: task.data.get(key, schema.get("default"))
            for key, schema in task.jsonschema["properties"].items()
            if key in task.data or "default" in schema
        }
        with pytest.raises(ValidationResultContainsErrors) as cleared:
            user.submit({**payload, "required_choice": None, "confirm_review": False}, instance, task_id=task.id)
        assert set(cleared.value.error_schema) == {"required_choice", "confirm_review"}
        with pytest.raises(ValidationResultContainsErrors) as unchecked:
            user.submit({**payload, "confirm_review": False}, instance, task_id=task.id)
        assert set(unchecked.value.error_schema) == {"confirm_review"}

        empty_lists = {**payload, "required_positions": [], "required_tags": []}
        with pytest.raises(ValidationResultContainsErrors) as visible:
            user.submit(empty_lists, instance, task_id=task.id)
        assert set(visible.value.error_schema) == {"required_positions", "required_tags"}

        user.submit(payload, instance, task_id=task.id)
        next_task = user.get_usertasks(instance, 1)[0]
        assert "1c. Confirm review = true" in next_task.data["service_saw"]
        user.submit({**empty_lists, "hide_required_lists": True}, instance, task_id=next_task.id)
        assert user.get_usertasks(instance, 1)[0].data["hide_required_lists"] is True
