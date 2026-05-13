# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH


class WorkflowSpecNotFoundException(Exception):
    pass


class InvalidWorkflowSpecException(Exception):
    pass


class UserMayNotStartWorkflowException(Exception):
    pass


class UserMayNotCopyWorkflowException(Exception):
    pass


class FormNotFoundException(Exception):
    pass


class TaskNotFoundException(Exception):
    pass


class TaskAlreadyAssignedToDifferentUserException(Exception):
    pass


class TaskIsNotInReadyUsertasksException(Exception):
    pass


class OptionsFileNotSpecifiedException(Exception):
    pass


class OptionsFileNotExistsException(Exception):
    pass


class OptionsFileCouldNotBeReadException(Exception):
    pass


class OptionFunctionNotFound(Exception):
    pass


class AttachmentNotFoundException(Exception):
    pass


class TaskCannotBeUnassignedException(Exception):
    pass


class TaskContainsUnexpectedData(Exception):
    def __init__(self, message):
        super().__init__(message)


class ValidationResultContainsErrors(Exception):
    def __init__(self, message, error_schema):
        super().__init__(message)
        self.error_schema = error_schema


class UserMayNotAdministrateThisWorkflowException(Exception):
    pass


class UserMayNotAdministrateUsersException(Exception):
    pass


class TaskIsNotErroneousException(Exception):
    pass


class WorkflowDefinitionMissingError(Exception):
    """Raised when a workflow instance's definition is no longer served by any provider.

    Used by write paths (submit, assign, admin actions) to surface a clear HTTP 410 to
    clients that try to act on an orphan instance. Read paths do not raise — they mark
    the response as read-only and let the frontend disable UI controls.
    """

    def __init__(self, workflow_name: str):
        self.workflow_name = workflow_name
        super().__init__(f"Workflow definition '{workflow_name}' is not available from any provider")


class DataModelNotFoundError(KeyError):
    """Raised when a data model name is not in the registry."""


class DataModelAccessDeniedError(Exception):
    """Raised when a workflow accesses a data model it did not declare."""

    def __init__(self, model_name: str, allowed: set[str]):
        self.model_name = model_name
        self.allowed = allowed
        super().__init__(
            f"Access denied to data model '{model_name}'. Allowed models for this workflow: {sorted(allowed)}",
        )
