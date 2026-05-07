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
