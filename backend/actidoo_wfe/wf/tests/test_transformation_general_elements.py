from actidoo_wfe.wf.tests.helpers.dicts import are_dicts_equal, load_dict_from_file, read_and_transform, save_dict_to_file

PATH_FORM = "./actidoo_wfe/wf/tests/forms/test_general_elements.form"
PATH_SNAPSHOT_JSONSCHEMA = "./actidoo_wfe/wf/tests/snapshots/general_jsonschema.json"
PATH_SNAPSHOT_UISCHEMA = "./actidoo_wfe/wf/tests/snapshots/general_uischema.json"


def _read_snapshot_jsonschema():
    return load_dict_from_file(PATH_SNAPSHOT_JSONSCHEMA)


def _read_snapshot_uischema():
    return load_dict_from_file(PATH_SNAPSHOT_UISCHEMA)


def _create_snapshots():
    form = read_and_transform(PATH_FORM)

    save_dict_to_file(form[0], PATH_SNAPSHOT_JSONSCHEMA)
    save_dict_to_file(form[1], PATH_SNAPSHOT_UISCHEMA)


# _create_snapshots() # USE THIS IF YOU WANT TO CREATE NEW SNAPSHOTS!


def test_transformation_camunda_form__returns__expected_snapshots():
    jsonschema, uischema = read_and_transform(PATH_FORM)

    # assertions are within 'are_dicts_equal'
    are_dicts_equal(jsonschema, _read_snapshot_jsonschema(), True)
    are_dicts_equal(uischema, _read_snapshot_uischema(), True)
