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
