# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import copy
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, TypeVar

from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from SpiffWorkflow.bpmn.specs.event_definitions.timer import TimerEventDefinition
from SpiffWorkflow.task import TaskState

from actidoo_wfe.wf import repository, service_application, service_user, views
from actidoo_wfe.wf.models import WorkflowInstance, WorkflowTimeEvent
from actidoo_wfe.wf.tests.helpers.user_dummy import ServiceUserDummy, UserDummy
from actidoo_wfe.wf.tests.helpers.user_profiles import TEST_PROFILES, TestUserProfile

log: logging.Logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class WorkflowDummy:
    def __init__(
        self,
        db_session: Session,
        users_with_roles: Dict[str, List["str"]] | None = None,
        service_users_with_roles: Dict[str, List["str"]] | None = None,
        workflow_name: str | None = None,
        start_user: str | None = None,
    ):
        """Inititializes and (if `workflow_name` and `start_user` is given) starts a workflow

        Args:
            db_session: a database session
            users_with_roles: the needed users and their roles
            workflow_name: name of the workflow
            start_user: user that is assigned firts
        """
        self.db: Session = db_session

        self.users = {}
        self.service_users = {}

        self._create_users(users_with_roles, service_users_with_roles)

        if workflow_name is not None and start_user is not None:
            if start_user in self.users:
                start_user_id = self.users[start_user].user.id
            elif start_user in self.service_users:
                start_user_id = self.service_users[start_user].user.id
            else:
                raise KeyError(f"start user {start_user} not found")
            
            self.workflow_instance_id = service_application.start_workflow(
                db=self.db, name=workflow_name, user_id=start_user_id
            )
        else:
            self.workflow_instance_id = None

        self.db.commit()

    def _create_users(self, users_with_roles, service_users_with_roles):
        if users_with_roles and service_users_with_roles:
            schnittmenge = set(users_with_roles.keys()) & set(service_users_with_roles.keys())
            if len(schnittmenge) > 0:
                raise Exception(f"Do not use the same identifiers for users and service_users. {str(schnittmenge)}")
            
        profiles = copy.deepcopy(TEST_PROFILES)
        if users_with_roles is not None:
            # self.users will have same keys as users_with_roles
            self.users = {
                k: self._create_user(profiles.pop(), role_names=roles, email=k)
                for k, roles in users_with_roles.items()
            }

        if service_users_with_roles is not None:
            self.service_users = {
                k: self._create_service_user(profiles.pop(), role_names=roles)
                for k, roles in service_users_with_roles.items()
            }
        

    def _create_user(self, profile: TestUserProfile, role_names=[], email: str = ""
    ) -> "UserDummy":
        if "@" not in email:
            email = email + "@example.com"
        user: service_user.WorkflowUser = service_user.upsert_user(
            db=self.db,
            idp_user_id=profile.idp_user_id,
            username=email,
            email=email,
            first_name=profile.first_name,
            last_name=profile.last_name,
            is_service_user=False
        )
        service_user.assign_roles(db=self.db, user_id=user.id, role_names=role_names)

        user = service_user.get_user(db=self.db, user_id=user.id) # type: ignore
        assert user is not None
        return UserDummy(db=self.db, user=user)
    
    def _create_service_user(
        self, profile: TestUserProfile, role_names=[]
    ) -> "ServiceUserDummy":
        user = service_user.upsert_user(
            db=self.db,
            idp_user_id=profile.idp_user_id,
            username=profile.username,
            email=None,
            first_name=None,
            last_name=None,
            is_service_user=True
        )
        service_user.assign_roles(db=self.db, user_id=user.id, role_names=role_names)

        user = service_user.get_user(db=self.db, user_id=user.id)
        assert user is not None
        return ServiceUserDummy(
            db=self.db, user=user
        )

    def user(self, key) -> UserDummy:
        return self.users[key]

    def service_user(self, key) -> "ServiceUserDummy":
        user_helper = self.service_users[key]
        user_helper.workflow_instance_id = self.workflow_instance_id
        return user_helper
    
    def auto_set_workflow_instance_id(self):
        q = select(WorkflowInstance)
        workflow_instance = self.db.execute(q).scalar_one()
        self.workflow_instance_id = workflow_instance.id

    def get_attachments(self, workflow_instance_id):
        return service_application.find_all_workflow_attachments(
            db=self.db, workflow_instance_id=workflow_instance_id
        )
    
    def assert_completed(self):
        workflow_instance = views.get_workflow_by_instance_id(db=self.db, workflow_instance_id=self.workflow_instance_id)
        assert workflow_instance.completed_at is not None
        assert workflow_instance.is_completed

    def get_message_subscriptions(self):
        subscriptions = views.get_message_subscriptions_by_instance_id(db=self.db, workflow_instance_id=self.workflow_instance_id)
        return subscriptions

    def trigger_timer_events(self, timer_bpmn_id: str):
        workflow = repository.load_workflow_instance(db=self.db, workflow_id=self.workflow_instance_id)

        now = datetime.now(timezone.utc)
        past_iso = (now - timedelta(seconds=1)).isoformat()
        triggered_task_ids: set = set()

        for task in workflow.get_tasks():
            if not task.has_state(TaskState.WAITING):
                continue
            task_spec = task.task_spec
            timer_def = getattr(task_spec, "event_definition", None)
            if not isinstance(timer_def, TimerEventDefinition):
                continue
            if timer_bpmn_id is not None and task_spec.bpmn_id != timer_bpmn_id:
                continue
            task._set_internal_data(event_value=past_iso)
            triggered_task_ids.add(task.id)

        if not triggered_task_ids:
            return

        repository.store_workflow_instance(db=self.db, workflow=workflow)
        service_application.handle_timeevents(db=self.db)
        self.db.commit()
