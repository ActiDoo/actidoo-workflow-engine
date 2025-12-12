"""
See ../init.py for description
"""
from pathlib import Path

from actidoo_wfe.wf.tests.helpers.dicts import are_dicts_equal, load_dict_from_file, read_and_transform, save_dict_to_file

PATH_FORM = Path(__file__).parent / "../SimpleForm.form"
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
