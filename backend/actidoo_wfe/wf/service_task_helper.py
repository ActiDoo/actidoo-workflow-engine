# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""
This module defined a "helper" class which is passed to all script tasks.
Script tasks are defined next to the .bpmn files.
"""

import hashlib
import io
import json
import logging
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID
from zoneinfo import ZoneInfo

from SpiffWorkflow.bpmn.specs.bpmn_task_spec import BpmnTaskSpec
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow, Task
from SpiffWorkflow.task import TaskState
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

import actidoo_wfe.helpers.mail as mail_helpers
from actidoo_wfe.database import SessionLocal
from actidoo_wfe.helpers.datauri import DataURI
from actidoo_wfe.helpers.string import get_boxed_text
from actidoo_wfe.storage import get_file_content
from actidoo_wfe.wf import repository
from actidoo_wfe.wf.constants import (
    DATA_KEY_WORKFLOW_INSTANCE_SUBTITLE,
)
from actidoo_wfe.wf.exceptions import AttachmentNotFoundException, TaskNotFoundException
from actidoo_wfe.wf.models import WorkflowInstanceTask, WorkflowInstanceTaskAttachment
from actidoo_wfe.wf.service_user import get_users_of_role
from actidoo_wfe.wf.types import Attachment, TaskToUserMapping, UploadedAttachmentRepresentation, UserRepresentation
from actidoo_wfe.wf.views import get_single_task

log = logging.getLogger(__name__)

class ServiceTaskHelper:
    # NOTE: We must not use application services here, which load and save the workflow. The workflow is already in a modification state during task execution.
    # Only use service_workflow when modifying the workflow/task state!!!!

    def __init__(
        self,
        workflow: BpmnWorkflow,
        task_data: dict,
        task_to_user_mapping: TaskToUserMapping,
        task_uuid: UUID
    ):
        # Aktuell laufen die Service Task im Context des Requests.
        # Da hier schon eine Transaktion gestartet wurde, machen wir das hier erstmal nicht.
        # Falls die Service-Tasks irgendwann im Hintergrund passieren sollen, müsste man das Handling der Transaktion nochmal betrachten
        self.db: Session = SessionLocal()

        self.workflow = workflow
        self.workflow_instance_id = workflow.task_tree.id
        self.task_data = task_data
        self.task_to_user_mapping = task_to_user_mapping
        self.task_uuid = task_uuid

    def pretty_log(self, json_data: dict, boxed = True):
        """
        Logs the provided JSON data in a formatted/boxed manner.

        Parameters:
            json_data (dict): The dictionary containing the JSON data to be logged.
            boxed (bool): Optional; if True, the output will be boxed with a decorative format. Defaults to True.
        """
        json_formatted_str = json.dumps(json_data, indent=4)
        if boxed:
            log.debug("\n" + get_boxed_text(json_formatted_str))
        else:
            log.debug(json_formatted_str)
        
    def get_task(self, bpmn_task_id) -> Task | None:
        for task in self.workflow.get_tasks():
            task_spec: BpmnTaskSpec = task.task_spec
            if task_spec.bpmn_id == bpmn_task_id:
                return task
        return None
    
    def _get_db_task(self, bpmn_task_id) -> WorkflowInstanceTask:
        spiff_task = self.get_task(bpmn_task_id=bpmn_task_id)
        if not spiff_task:
            raise TaskNotFoundException(f"{bpmn_task_id} not found")
        
        task_uuid = spiff_task.id

        db_task = get_single_task(self.db, task_uuid)

        return db_task
    
    def get_task_completion_day(self, bpmn_task_id) -> str:
        try:
            datetime_obj = self._get_db_task(bpmn_task_id).completed_at
            # timing problem: "completed_at" may not be written into the database, yet.
            # Use now() in such a case.:
            if not datetime_obj:                
                datetime_obj = datetime.now()
            
            datetime_obj = datetime_obj.replace(tzinfo=timezone.utc) # timedate.replace will make the object timezone-aware
                
                
            datetime_obj = datetime_obj.astimezone(ZoneInfo('Europe/Berlin'))
            
            # Format the date
            formatted_date = datetime_obj.strftime('%d.%m.%Y')
            return formatted_date
        except Exception as error:
            log.exception(f"{type(error).__name__}: {error.args}")
            return "??.??.????"
        
    def get_task_completion_datetime(self, bpmn_task_id) -> str:
        try:
            datetime_obj = self._get_db_task(bpmn_task_id).completed_at.replace(tzinfo=timezone.utc) # timedate.replace will make the object timezone-aware
            datetime_obj = datetime_obj.astimezone(ZoneInfo('Europe/Berlin'))
            
            # Format the date
            formatted_date = datetime_obj.strftime('%d.%m.%Y %H:%M:%S')
            return formatted_date
        except Exception as error:
            log.exception(f"{type(error).__name__}: {error.args}")
            return "??:??"

    def send_text_mail(
        self,
        subject: str,
        content: str,
        recipient_or_recipients_list: list[str] | str,
        attachments: dict[str, io.BytesIO],
    ):
        return mail_helpers.send_text_mail(
            subject=subject,
            content=content,
            recipient_or_recipients_list=recipient_or_recipients_list,
            attachments=attachments,
        )

    def get_user_by_id(self, user_id):
        if user_id is None:
            return None

        if isinstance(user_id, str):
            user_id = UUID(user_id)
        return repository.load_user(db=self.db, user_id=user_id)
    
    def update_task_data(self, update_dict):
        """
        deprecated, use "set_task_data" instead
        """
        log.warning("DECPRECATED use of update_task_data()")
        self.task_data.update(**update_dict)

    def set_task_data(self, update_dict):
        """
        Updates the task data with the provided dictionary.

        Parameters:
            update_dict (dict): A dictionary containing key-value pairs to update
                                the task data. Existing keys will be updated with
                                new values, while new keys will be added.

        This method mutates the internal task_data attribute, reflecting the
        changes immediately in the context of the workflow.
        """
        self.task_data.update(**update_dict)

    def set_task_data_key(self, key, value):
        """
        Updates the task data by setting a specific key to a given value.

        Parameters:
            key (str): The key in the task data to be updated or added.
            value: The value to be set for the specified key.
        """
        self.set_task_data({key: value})

    def get_user_by_task_name(self, task_name):
        """
        Retrieves the user assigned to the most recently completed task instance with the specified name.

        Parameters:
            task_name (str): The name of the task to find, e.g. 'Form_10_fill_data'

        Returns:
            UserRepresentation: The user assigned to the specified task.
        
        Raises:
            AssertionError: If the user representation is not of the expected type.
            IndexError: If no completed tasks with the given name exist.
        """
        task = self.get_completed_tasks_by_name_sorted_by_last_state_change(name=task_name)[0]
        user_id = self.get_assigned_user(task)
        user = self.get_user_by_id(user_id=user_id)
        assert isinstance(user, UserRepresentation)
        return user

    def get_created_by(self):
        """
        Returns the user who created the workflow.

        Returns:
            UserRepresentation | None: The user representation of the creator if found,
            otherwise returns None.
        """
        from actidoo_wfe.wf import (
            service_workflow,
        )

        created_by_id = service_workflow.get_created_by_id(workflow=self.workflow)
        user_rep = None
        if created_by_id is not None:
            user_rep = self.get_user_by_id(user_id=created_by_id)

        return user_rep
    
    def get_attachment_by_hash(self, hash):

        attachments = repository.find_task_attachments_by_worfklow_instance_id(
            db=self.db, workflow_instance_id=self.workflow_instance_id
        )
        att: WorkflowInstanceTaskAttachment | None = next(
            (a for a in attachments if a.attachment.hash == hash), None
        )
        if att is None:
            raise AttachmentNotFoundException()
        if not att.attachment.file:
            raise RuntimeError(f"Attachment content missing for hash={hash}")
        return Attachment(
            id=att.id,
            hash=att.attachment.hash,
            filename=att.attachment.first_filename,
            mimetype=att.attachment.mimetype,
            data=get_file_content(att.attachment.file.file_id),
        )

    def set_workflow_instance_subtitle(self, subtitle):
        if subtitle and len(subtitle)>50:
            subtitle = subtitle[:47] + "..."
        self.workflow.set_data(**{DATA_KEY_WORKFLOW_INSTANCE_SUBTITLE: subtitle})

    def set_data(self, key_value_dict: dict) -> None:
        """
        deprecated, use "set_workflow_data" instead
        """
        log.warning("DECPRECATED use of set_data()")
        self.workflow.set_data(**key_value_dict)

    def set_workflow_data(self, key_value_dict: dict) -> None:
        """
        Updates the workflow data with the provided dictionary.

        Parameters:
            key_value_dict (dict): A dictionary containing key-value pairs to update
                                   the workflow data. Existing keys will be updated with
                                   new values, while new keys will be added.

        This method applies the changes directly to the workflow, ensuring that the
        updates are reflected immediately in the current context.
        """
        self.workflow.set_data(**key_value_dict)

    def assign_task_roles(self, bpmn_task_id, roles):
        from actidoo_wfe.wf import (
            service_workflow,
        )

        upcoming_tasks = self._get_upcoming_tasks_by_name(bpmn_task_id)

        service_workflow.set_manually_assigned_roles(workflow=self.workflow, task_id=upcoming_tasks[0].id, roles=roles)

    def assign_user_without_role(self, bpmn_task_id, email, create_user=False):
        """
        Assigns a user to a specified task, which is not intended to be assigned to a users of a specific role.

        This method attempts to find a user by their email address. If the user
        does not exist and the create_user flag is set to True, a new user
        will be created. The method will then associate the user with the
        provided BPMN task ID in the workflow. If multiple task instances
        exist for the same BPMN task ID, the method assigns the user to
        all those instances.

        Parameters:
            bpmn_task_id (str): The ID of the BPMN task to which the user will be assigned,e.g. "Form_010".
            email (str): The email address of the user to be assigned.
            create_user (bool): Flag indicating whether to create a new user if one does not exist.

        Returns:
            UserRepresentation: The user that was assigned to the task.

        Raises:
            AssertionError: If the user is not found or created.
        """
        from actidoo_wfe.wf import service_workflow

        try:
            user = repository.load_user_by_email(db=self.db, email=email)
        except NoResultFound:
            if create_user:
                user = repository.upsert_user(db=self.db, idp_user_id=None, username=email, email=email, first_name=None, last_name=None, is_service_user=False)
            else:
                user = None

        assert user is not None
        assert user.email == email

        upcoming_tasks = self._get_upcoming_tasks_by_name(bpmn_task_id)

        service_workflow.assign_task_without_checks(workflow=self.workflow, task_id=upcoming_tasks[0].id, user_id=user.id)
        service_workflow.set_manually_assigned_roles(workflow=self.workflow, task_id=upcoming_tasks[0].id, roles=set())

        return user

    def _get_upcoming_tasks_by_name(self, bpmn_task_id):
        # Get tasks which are WAITING, FUTURE, LIKELY, MAYBE; they are already sorted by Spiffworkflow by having the completed first, followed by the future ones.
        filtered_tasks = [task for task in self.workflow.get_tasks() if task.task_spec.name == bpmn_task_id and task.state <= TaskState.WAITING]

        # that a task is not found, should already be noticed during (unit) testing. We want to make it obvious here,
        # because sometimes the file name with extension ".form" was given as bpmn_task_id and this error was hard to track down:
        assert len(filtered_tasks) > 0
        return filtered_tasks

    def get_options_with_details(self, bpmn_task_id, property_path: list[str]):
        """
        return a dict for the given property_path (aka a key in the .form file) which maps from the possible
        values to a dict with the details
        """
        from actidoo_wfe.wf import (
            service_workflow,
        )

        found_task = None
        for task in self.workflow.get_tasks():
            task_spec: BpmnTaskSpec = task.task_spec
            if task_spec.bpmn_id == bpmn_task_id:
                found_task = task
                break
        assert found_task is not None
        return service_workflow.get_options_detailed_for_property(workflow=self.workflow, task_id=found_task.id, property_path=property_path, form_data=None)

    def get_completed_tasks_by_name_sorted_by_last_state_change(self, name):
        """
        Returns all completed tasks that match the given name ("Form010...")
        If you have round-trips in you bpmn you can have more than one task instance,
        the most recently completed task is on index 0
        """
        filtered_keys = [task for task in self.task_to_user_mapping.keys() if task.task_spec.name == name and task.has_state(TaskState.COMPLETED)]
        sorted_keys = sorted(filtered_keys, key=lambda task: task.last_state_change, reverse=True)
        return sorted_keys

    def get_last_completed_task(self) -> Task:
        """
        Gets the last completed task. It's not fetched from the database but from the engine,
        because in the database it can still be in READY at this point in time, due to the ongoing seesion.
        """
        filtered_keys = [task for task in self.task_to_user_mapping.keys() if task.has_state(TaskState.COMPLETED)]
        assert len(filtered_keys) >= 1
        sorted_keys = sorted(filtered_keys, key=lambda task: task.last_state_change, reverse=True)  # Newest one (the last in the workflow with highest last_state_change) is on 0
        return sorted_keys[0]

    def get_next_task(self) -> Task:
        """
        Retrieves the next task in the workflow that is in the 'FUTURE' state.

        Returns:
            Task: The next task that is scheduled.

        Raises:
            TaskNotFoundException: If no future task is found in the workflow.
        """
        for task in self.workflow.get_tasks(): # returns an ordered list, so the first FUTURE task will be the next one.
            if task.has_state(TaskState.FUTURE):
                return task
        raise TaskNotFoundException("No future task found")

    def get_last_completed_task_name(self) -> str:
        '''
        Returns the last completed task name (e.g. "Form040_CostApproval")
        '''
        return self.get_last_completed_task().task_spec.name

    def get_single_completed_task_by_name_and_condition_sorted_by_last_state_change(self, name, condition_func: Callable):
        filtered_keys = [task for task in self.task_to_user_mapping.keys() if task.task_spec.name == name and task.has_state(TaskState.COMPLETED) and condition_func(task)]
        assert len(filtered_keys) >= 1
        sorted_keys = sorted(filtered_keys, key=lambda task: task.last_state_change, reverse=True)
        return sorted_keys[0]

    def get_assigned_user(self, task: Task):
        return self.task_to_user_mapping.get(task, None)

    def get_users_of_role(self, role_name):
        return get_users_of_role(self.db, role_name)
    
    def get_label_from_form(self, form_id, form_key, default_value=""):
        """
        Retrieves the label associated with a value from a specified form based on the provided form ID and key.

        Args:
            form_id (str): The unique identifier of the form from which to retrieve the label, e.g. "Form010_FillForm"
            form_key (str): The key in the form data whose corresponding label is to be fetched.
            default_value (str, optional): The value to return if no valid label is found. Defaults to "---".

        Returns:
            str: The label corresponding to the user's chosen value, or the default value if no valid label exists.

        If the chosen value by the user is not found in the form data, the method logs an exception and returns the default value.
        """
        chosen_by_user = self.task_data.get(form_key, None)

        if chosen_by_user is None:
            return default_value

        # e.g. details = {'australia_new_zealand': {'value': 'australia_new_zealand', 'label': 'Australia/New Zealand'}, 'new': {'value': 'new', 'label': '- New -'}, ..........
        details = self.get_options_with_details(
            bpmn_task_id=form_id,
            property_path=[form_key],
        )

        try:
            return details[chosen_by_user]["label"]
        except Exception as error:
            # An error should never occur, as this means that a user would have selected a value
            # that is not contained in the form data.
            log.exception(f"{type(error).__name__}: {error.args}")
            return default_value
        
    def _upload_attachment(self, datauri: str) -> UploadedAttachmentRepresentation:
        # TODO see service_application for the same implementation. Move to repository.py?
        
        db = self.db

        workflow = self.workflow

        datauri = DataURI(datauri)

        data = datauri.data
        mimetype = datauri.mimetype
        filename = datauri.name

        assert filename is not None

        hasher = hashlib.sha256()
        hasher.update(data)
        hash = hasher.hexdigest()

        attachment = repository.store_attachment(
            db=db, filename=filename, mimetype=mimetype, data=data, hash=hash
        )
        repository.store_attachment_for_workflow_instance(
            db=db,
            workflow_instance_id=workflow.task_tree.id,
            attachment_id=attachment.id,
            filename=filename,
        )
        repository.store_attachment_for_task(
            db=db, task_id=self.task_uuid, attachment_id=attachment.id, filename=filename
        )

        return UploadedAttachmentRepresentation(
            hash=hash, filename=filename, id=attachment.id, mimetype=mimetype
        )

    


