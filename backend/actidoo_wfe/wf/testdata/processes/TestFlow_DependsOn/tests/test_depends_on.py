# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy


def test_list_options_follow_the_rows_car_type(db_engine_ctx):
    with db_engine_ctx():
        workflow = WorkflowDummy(
            db_session=SessionLocal(),
            users_with_roles={"initiator": ["wf-user"]},
            workflow_name="TestFlow_DependsOn",
            start_user="initiator",
        )
        user = workflow.user("initiator")
        task = user.get_usertasks(workflow.workflow_instance_id, 1)[0]

        options = user.search_options(
            property_path=["vehicles", 0, "car_sub_type"],
            search="",
            task_id=task.id,
            form_data={"car_type": "car", "vehicles": [{"car_type": "truck"}]},
        )

        assert {value for value, _label in options} == {"pickup", "semi", "dump"}
