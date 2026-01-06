# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import copy
import logging
import uuid

from sqlalchemy.orm import Session

from actidoo_wfe.wf import service_application, service_user

log: logging.Logger = logging.getLogger(__name__)

class UserDummy:
    def __init__(self, db: Session, user):
        self.db: Session = db
        self.user: service_user.WorkflowUser = user

    def get_usertasks(self, workflow_instance_id, expected_task_count: int|None = None):
        """returns the ready user tasks of the user, also if the user is not yet assigned to it, but only has the right role. throws if len(tasks) != expected_task_count"""
        # It was unclear why
        # views.bff_get_workflows_with_usertasks
        # and
        # service_application.get_usertasks_for_user_id()
        # where both used in this test, because checking against 'get_usertasks_for_user_id()' already is sufficient.
        # If the functionality of 'views.bff_get_workflows_with_usertasks()' should be checked,
        # then this should be a separate test and not be mixed in here:

        user_tasks = service_application.get_usertasks_for_user_id(
            db=self.db,
            user_id=self.user.id,
            workflow_instance_id=workflow_instance_id, # type: ignore
            state="ready",
        )
        
        if expected_task_count is not None:
            assert len(user_tasks) == expected_task_count, \
            f"Assertion failed: Expected {expected_task_count} user tasks, but got {len(user_tasks)}, users_tasks: {user_tasks}"
    

        return user_tasks

    def submit(self, task_data, workflow_instance_id, task_name = None, task_id = None):
        """ is analogue to /submit_task_data, which is called after sending a form """
        
        if task_id is None:
            # if no task_id is given, we expect that there's only one ready task (or one ready task with the given name)
            usertasks = []
            if not task_name:
                # if there is no task_name given, we expect only ONE ready task, because if there's more than one task
                # we can not know to which task we shall submit the data
                usertasks = self.get_usertasks(workflow_instance_id, 1)
                
            else:
                ready_tasks = self.get_usertasks(workflow_instance_id)
                for t in ready_tasks:
                    if t.name == task_name:
                        usertasks.append(t)
                assert len(usertasks) == 1 # we expect only one ready instance of a task with the same name

            task_id = usertasks[0].id

        
        (success, workflow_instance_id) = service_application.submit_task_data(
            db=self.db,
            task_id=task_id,
            user_id=self.user.id,
            task_data=copy.deepcopy(task_data),
        )
        
        self.db.commit()

    def assign_task(self, task_id):
        service_application.assign_task_to_me(db=self.db, task_id=task_id, user_id=self.user.id)
        self.db.commit()

    def assign_submit(self, workflow_instance_id, task_data):
        usertasks = self.get_usertasks(workflow_instance_id, 1)
        task_id = usertasks[0].id

        self.assign_task(task_id=task_id)
        self.submit(
            task_data=task_data,
            workflow_instance_id = workflow_instance_id
        )

    def search_options(self, property_path: list[str], search: str, task_id):
        return service_application.search_property_options(
            db=self.db,
            task_id=task_id,
            user_id=self.user.id,
            property_path=property_path,
            search=search,
            include_value=None,
            form_data=form_data
        )    

    def send_message(self, message_name, correlation_key, data):
        service_application.receive_message(db=self.db, message_name=message_name, correlation_key=correlation_key, data=data, user_id=self.user.id)
        service_application.handle_messages(db=self.db)
        self.db.commit()




class ServiceUserDummy:
    def __init__(self, db, user):
        self.db = db
        self.user = user
        self.email = self.user.email
        self.workflow_instance_id: uuid.UUID = uuid.uuid4()  # dummy

    def get_usertasks(self, assert_number: int | None):
        user_tasks = service_application.get_usertasks_for_user_id(
            db=self.db,
            user_id=self.user.id,
            workflow_instance_id=self.workflow_instance_id, # type: ignore
            state="ready",
        )
        
        assert len(user_tasks) == assert_number

        return user_tasks
    
    def send_message(self, message_name, correlation_key, data):
        service_application.receive_message(db=self.db, message_name=message_name, correlation_key=correlation_key, data=data, user_id=self.user.id)
        service_application.handle_messages(db=self.db) # normally this would be done in the background cron job
        self.db.commit()

        