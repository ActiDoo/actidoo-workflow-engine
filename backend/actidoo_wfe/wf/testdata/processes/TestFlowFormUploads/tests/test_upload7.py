# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import base64
import pytest
import uuid
import copy
import logging
from pathlib import Path

from actidoo_wfe.database import SessionLocal
from actidoo_wfe.wf.exceptions import ValidationResultContainsErrors
from actidoo_wfe.wf.service_form import remove_data_uri_fields
from actidoo_wfe.wf.tests.helpers.dicts import are_dicts_equal, load_dict_from_file, read_and_transform, save_dict_to_file
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy

WF_NAME = "TestFlowFormUploads"

log = logging.getLogger(__name__)


##create attachment from our test PDF:
def file_to_base64(file_path):
    with open(file_path, "rb") as pdf_file:
        encoded_string = base64.b64encode(pdf_file.read())
    return encoded_string.decode("utf-8")


# content_as_b64 = file_to_base64(Path(__file__).parent / "240512_Sample.pdf")
content_as_b64 = file_to_base64(Path(__file__).parent / "test.png")

ATTACHMENTS = [
    {"datauri": f"data:image/png;name=test.png;base64,{content_as_b64}"},
]

FORM_DATA = {
    "uploadFieldMulti": [ATTACHMENTS[0]],
    "uploadFieldSingle": ATTACHMENTS[0],
    "uploadFieldMultiRequired": [ATTACHMENTS[0]],
    "uploadFieldSingleRequired": ATTACHMENTS[0],
    "multi_default": [ATTACHMENTS[0]],
    "single_default": ATTACHMENTS[0],
    "multiDefaultRequired": [ATTACHMENTS[0]],
    "singleDefaultRequired": ATTACHMENTS[0],
}


def _start_workflow():
    db_session = SessionLocal()

    workflow = WorkflowDummy(
        db_session=db_session,
        users_with_roles={  # dev-realm dummy
            "initiator": ["wf-user"],
        },
        workflow_name=WF_NAME,
        start_user="initiator",
    )

    return workflow


def test_happy(db_engine_ctx, mock_send_text_mail):
    """for 'db_engine_ctx' see conftest.py"""
    with db_engine_ctx():
        workflow = _start_workflow()

        workflow.user("initiator").submit(
            task_data=FORM_DATA,
            workflow_instance_id=workflow.workflow_instance_id,
        )

        pass


def test__echoing_a_datauri_into_a_disabled_field_leaves_no_duplicate(db_engine_ctx, mock_send_text_mail):
    """A hand-built client may echo the original datauri into a field that is
    disabled in the current step (a browser would send the stored reference
    instead). Cleaning replaces the fresh upload with the authoritative stored
    reference - the fresh blob must then be removed again, otherwise every such
    submission grows the instance's attachment list by a duplicate."""
    with db_engine_ctx():
        workflow = _start_workflow()
        workflow.user("initiator").submit(
            task_data=FORM_DATA,
            workflow_instance_id=workflow.workflow_instance_id,
        )
        before = len(workflow.get_attachments(workflow_instance_id=workflow.workflow_instance_id))

        # step 2: every field is disabled - echo the original datauri anyway
        workflow.user("initiator").submit(
            task_data={"uploadFieldSingle": ATTACHMENTS[0]},
            workflow_instance_id=workflow.workflow_instance_id,
        )

        attachments = workflow.get_attachments(workflow_instance_id=workflow.workflow_instance_id)
        assert len(attachments) == before


def test__a_file_for_a_disabled_field_is_never_stored(db_engine_ctx, mock_send_text_mail):
    """A file the client sends into a field that is disabled in this step does
    not reach the database at all - not even as an unreferenced blob. The
    cleaning replaces the reference by the stored value, so there is nothing
    left to store."""
    with db_engine_ctx():
        workflow = _start_workflow()
        workflow.user("initiator").submit(
            task_data=FORM_DATA,
            workflow_instance_id=workflow.workflow_instance_id,
        )
        before = {a.hash for a in workflow.get_attachments(workflow_instance_id=workflow.workflow_instance_id)}

        # step 2: all fields are disabled - send a file the instance has never seen
        other_file = {"datauri": "data:text/plain;name=other.txt;base64,dGhlIG90aGVyIGZpbGU="}
        workflow.user("initiator").submit(
            task_data={"uploadFieldSingle": other_file},
            workflow_instance_id=workflow.workflow_instance_id,
        )

        after = workflow.get_attachments(workflow_instance_id=workflow.workflow_instance_id)
        assert {a.hash for a in after} == before
        assert all(a.filename != "other.txt" for a in after)


def test__the_same_file_in_several_fields_is_stored_once(db_engine_ctx, mock_send_text_mail):
    """FORM_DATA puts the same file into all eight upload fields. They share one
    attachment, and every reference carries the same stored id - the id the
    extraction minted is replaced by the one storage assigned."""
    with db_engine_ctx():
        workflow = _start_workflow()
        workflow.user("initiator").submit(
            task_data=FORM_DATA,
            workflow_instance_id=workflow.workflow_instance_id,
        )

        data = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0].data
        ids = {data["uploadFieldSingle"]["id"], data["uploadFieldSingleRequired"]["id"], data["uploadFieldMulti"][0]["id"]}
        assert len(ids) == 1
        attachments = workflow.get_attachments(workflow_instance_id=workflow.workflow_instance_id)
        assert len(attachments) == 1
        assert str(attachments[0].hash) and data["uploadFieldSingle"]["hash"] == attachments[0].hash


def test__several_files_in_one_multi_field_are_all_stored(db_engine_ctx, mock_send_text_mail):
    """A multi upload arrives as a list. Every entry is stored and keeps its own
    reference; a reference the client sends back unchanged is not a datauri and
    passes through the extraction untouched."""
    with db_engine_ctx():
        workflow = _start_workflow()
        second_file = {"datauri": "data:text/plain;name=second.txt;base64,dGhlIHNlY29uZCBmaWxl"}
        workflow.user("initiator").submit(
            task_data={**FORM_DATA, "uploadFieldMulti": [ATTACHMENTS[0], second_file]},
            workflow_instance_id=workflow.workflow_instance_id,
        )

        refs = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)[0].data["uploadFieldMulti"]
        assert [r["filename"] for r in refs] == ["test.png", "second.txt"]
        assert refs[0]["id"] != refs[1]["id"]
        assert {a.filename for a in workflow.get_attachments(workflow_instance_id=workflow.workflow_instance_id)} == {
            "test.png",
            "second.txt",
        }


UNREADABLE_ATTACHMENTS = [
    # a data URI is only recognised with "name" before "charset"
    {"datauri": f"data:text/plain;charset=utf-8;name=note.txt;base64,{content_as_b64}"},
    # an unencoded space in the file name
    {"datauri": f"data:image/png;name=my file.png;base64,{content_as_b64}"},
    {"datauri": None},
    {"datauri": 42},
]


@pytest.mark.parametrize("broken", UNREADABLE_ATTACHMENTS)
def test__an_unreadable_datauri_is_rejected(db_engine_ctx, mock_send_text_mail, broken):
    """A file the server cannot read must be reported, not silently dropped.

    Dropping it leaves the stored reference of the previous file in place while
    the submitted file name is merged over it - the client gets 200 OK and finds
    the old file under the new name."""
    with db_engine_ctx():
        workflow = _start_workflow()

        with pytest.raises(ValidationResultContainsErrors):
            workflow.user("initiator").submit(
                task_data={**FORM_DATA, "uploadFieldSingle": broken},
                workflow_instance_id=workflow.workflow_instance_id,
            )


def test__a_field_called_id_does_not_disturb_the_upload_step():
    """Nothing says a form field cannot be called "id". Looking for the upload
    placeholders must cope with whatever such a field holds instead of tripping
    over an unhashable value."""
    from actidoo_wfe.wf.service_application import _materialise_uploads, _PendingUpload

    task_data = {"id": ["one", "two"], "group": {"id": {"nested": True}}}
    pending = {"a-placeholder": _PendingUpload(data=b"x", filename="x.txt", mimetype="text/plain", hash="h")}

    _materialise_uploads(
        db=None,
        workflow_instance_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        cleaned_task_data=task_data,
        pending=pending,
    )

    assert task_data == {"id": ["one", "two"], "group": {"id": {"nested": True}}}


PATH_FORM = Path(__file__).parent / "../test_upload.form"
PATH_SNAPSHOT_JSONSCHEMA = Path(__file__).parent / "snapshot_jsonschema.json"
PATH_SNAPSHOT_UISCHEMA = Path(__file__).parent / "snapshot_uischema.json"


def _read_snapshot_jsonschema():
    return load_dict_from_file(PATH_SNAPSHOT_JSONSCHEMA)


def _read_snapshot_uischema():
    return load_dict_from_file(PATH_SNAPSHOT_UISCHEMA)


def _create_snapshots():
    form = read_and_transform(PATH_FORM)

    save_dict_to_file(form[0], PATH_SNAPSHOT_JSONSCHEMA)
    save_dict_to_file(form[1], PATH_SNAPSHOT_UISCHEMA)


# _create_snapshots()  # USE THIS IF YOU WANT TO CREATE NEW SNAPSHOTS!


def test_transformation_camunda_form__returns__expected_snapshots():
    """
    Test case for the transformation of a Camunda form.

    This test verifies that the JSON schema and UI schema generated
    from the provided Camunda form match the expected snapshots.
    It loads the expected snapshots from JSON files and compares them
    with the actual outputs of the transformation using the
    read_and_transform function. The assertions are performed
    through the are_dicts_equal helper function.

    The comparison is done to ensure that any changes to the read_and_transform function
    do not unintentionally alter the expected structure of
    the generated schemas.
    """
    jsonschema, uischema = read_and_transform(PATH_FORM)

    # assertions are within 'are_dicts_equal'
    are_dicts_equal(jsonschema, _read_snapshot_jsonschema(), True)
    are_dicts_equal(uischema, _read_snapshot_uischema(), True)


EXPECTED = {
    "definitions": {},
    "properties": {
        "Field_096r6we": {
            "title": "",
            "type": "null",
        },
        "Field_097qdo7": {
            "title": "",
            "type": "null",
        },
        "multi_default": {
            "items": {
                "properties": {
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "title": "",
            "type": "array",
        },
        "multiDefaultRequired": {
            "items": {
                "properties": {
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "minItems": 1,
            "title": "",
            "type": "array",
        },
        "single_default": {
            "properties": {
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "",
            "type": "object",
        },
        "singleDefaultRequired": {
            "properties": {
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "",
            "type": "object",
        },
        "uploadFieldMulti": {
            "items": {
                "properties": {
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "title": "Multi upload",
            "type": "array",
        },
        "uploadFieldMultiDisabled": {
            "items": {
                "properties": {
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "title": "Multi upload disabled",
            "type": "array",
        },
        "uploadFieldMultiRequired": {
            "items": {
                "properties": {
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "minItems": 1,
            "title": "Multi upload required",
            "type": "array",
        },
        "uploadFieldMultiRequiredDisabledEmpty": {
            "items": {
                "properties": {
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "title": "Multi Upload required+disabled, empty",
            "type": "array",
        },
        "uploadFieldSingle": {
            "properties": {
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "Single upload",
            "type": "object",
        },
        "uploadFieldSingleDisabled": {
            "properties": {
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "Single upload disabled",
            "type": "object",
        },
        "uploadFieldSingleRequired": {
            "properties": {
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "Single upload required",
            "type": "object",
        },
        "uploadFieldSingleRequiredDisabledEmpty": {
            "properties": {
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "Single Upload required+disabled, empty",
            "type": "object",
        },
    },
    "required": [
        "uploadFieldSingleRequired",
        "singleDefaultRequired",
    ],
    "type": "object",
}

JSONSCHEMA_ORG = {
    "definitions": {},
    "properties": {
        "Field_096r6we": {
            "title": "",
            "type": "null",
        },
        "Field_097qdo7": {
            "title": "",
            "type": "null",
        },
        "multi_default": {
            "items": {
                "properties": {
                    "datauri": {
                        "format": "data-url",
                        "type": "string",
                    },
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "title": "",
            "type": "array",
        },
        "multiDefaultRequired": {
            "items": {
                "properties": {
                    "datauri": {
                        "format": "data-url",
                        "type": "string",
                    },
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "minItems": 1,
            "title": "",
            "type": "array",
        },
        "single_default": {
            "properties": {
                "datauri": {
                    "format": "data-url",
                    "type": "string",
                },
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "",
            "type": "object",
        },
        "singleDefaultRequired": {
            "properties": {
                "datauri": {
                    "format": "data-url",
                    "type": "string",
                },
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "",
            "type": "object",
        },
        "uploadFieldMulti": {
            "items": {
                "properties": {
                    "datauri": {
                        "format": "data-url",
                        "type": "string",
                    },
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "title": "Multi upload",
            "type": "array",
        },
        "uploadFieldMultiDisabled": {
            "items": {
                "properties": {
                    "datauri": {
                        "format": "data-url",
                        "type": "string",
                    },
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "title": "Multi upload disabled",
            "type": "array",
        },
        "uploadFieldMultiRequired": {
            "items": {
                "properties": {
                    "datauri": {
                        "format": "data-url",
                        "type": "string",
                    },
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "minItems": 1,
            "title": "Multi upload required",
            "type": "array",
        },
        "uploadFieldMultiRequiredDisabledEmpty": {
            "items": {
                "properties": {
                    "datauri": {
                        "format": "data-url",
                        "type": "string",
                    },
                    "filename": {
                        "type": "string",
                    },
                    "hash": {
                        "type": "string",
                    },
                    "id": {
                        "type": "string",
                    },
                    "mimetype": {
                        "type": "string",
                    },
                },
                "type": "object",
            },
            "title": "Multi Upload required+disabled, empty",
            "type": "array",
        },
        "uploadFieldSingle": {
            "properties": {
                "datauri": {
                    "format": "data-url",
                    "type": "string",
                },
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "Single upload",
            "type": "object",
        },
        "uploadFieldSingleDisabled": {
            "properties": {
                "datauri": {
                    "format": "data-url",
                    "type": "string",
                },
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "Single upload disabled",
            "type": "object",
        },
        "uploadFieldSingleRequired": {
            "properties": {
                "datauri": {
                    "format": "data-url",
                    "type": "string",
                },
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "Single upload required",
            "type": "object",
        },
        "uploadFieldSingleRequiredDisabledEmpty": {
            "properties": {
                "datauri": {
                    "format": "data-url",
                    "type": "string",
                },
                "filename": {
                    "type": "string",
                },
                "hash": {
                    "type": "string",
                },
                "id": {
                    "type": "string",
                },
                "mimetype": {
                    "type": "string",
                },
            },
            "title": "Single Upload required+disabled, empty",
            "type": "object",
        },
    },
    "required": [
        "uploadFieldSingleRequired",
        "singleDefaultRequired",
    ],
    "type": "object",
}


def test__remove_data_uri_fields__works__as_expected(db_engine_ctx):
    """
    Test the function 'remove_data_uri_fields' by starting a workflow and retrieving the task's jsonschema,
    which will be used as input for 'remove_data_uri_fields'.
    """
    with db_engine_ctx():
        workflow = _start_workflow()
        tasks = workflow.user("initiator").get_usertasks(workflow.workflow_instance_id, 1)  # expect one task

        # JSONSCHEMA_ORG and EXPECTED fit together, so make sure JSONSCHEMA_ORG has not changed due to an updated form or other changes:
        assert tasks[0].jsonschema == JSONSCHEMA_ORG

        # now the test itself:
        my_dict = copy.deepcopy(tasks[0].jsonschema)
        remove_data_uri_fields(my_dict)
        assert my_dict == EXPECTED


def test__remove_data_uri_fields__works__as_expected__hard_coded():
    my_dict = copy.deepcopy(JSONSCHEMA_ORG)
    remove_data_uri_fields(my_dict)
    assert my_dict == EXPECTED
