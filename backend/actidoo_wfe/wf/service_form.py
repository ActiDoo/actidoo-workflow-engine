# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""
This module implements logic around forms:
- validating POST data from the frontend
- provide options for dropdowns
- ...
"""

import ast
import copy
import csv
import logging
import pathlib
import re
import uuid
from dataclasses import dataclass
from typing import Any

import jsonschema._utils
import jsonschema.exceptions
import jsonschema.validators
from pydantic_core import ValidationError
from SpiffWorkflow.bpmn.script_engine.feel_engine import fixes as feel_fixes

from actidoo_wfe.helpers.collections import remove_item, set_item
from actidoo_wfe.helpers.datauri import DATA_URI_RE
from actidoo_wfe.helpers.json_traverse import get_position_tracker
from actidoo_wfe.wf.error_schema import validate_and_create_error_dict
from actidoo_wfe.wf.exceptions import (
    OptionFunctionNotFound,
    OptionsFileCouldNotBeReadException,
    OptionsFileNotExistsException,
)
from actidoo_wfe.wf.form_transformation import _traverse_schema
from actidoo_wfe.wf.option_task_helper import OptionTaskHelper
from actidoo_wfe.wf.types import (
    ReactJsonSchemaFormData,
    UploadedAttachmentRepresentation,
)
from actidoo_wfe.wf.validation_task_helper import ValidationTaskHelper

log = logging.getLogger(__name__)

# Form Service

def _find_property_upwards(
    global_jsonschema: dict, starting_path: list[str], property: str
):
    found = False
    found_path = None

    queue = starting_path.copy()
    while len(queue) > 0 and not found:
        jsonschema = _traverse_schema(global_jsonschema, starting_path)
        if property in jsonschema.get("properties", {}):
            found = True
            found_path = queue
        else:
            queue.pop()

    if not found:
        if property in global_jsonschema.get("properties", {}):
            found = True
            found_path = []

    if found_path is None:
        log.exception(f"EXCEPTION: Property {property} not found with starting_path {starting_path}")
        raise Exception(f"Property {property} not found with starting_path {starting_path}")

    return found_path


def convert_hide_if_props_to_declarative_jsonschema(global_jsonschema, path=None):
    # hier haben wir das jsonschema schon aufgebaut und in den properties zusätzlich "hideif" definiert
    # das müssen wir nun in allOf/if/then konstruke umwandeln
    # Wir iterieren über all properties und gehen rekursiv in array/objects rein.
    # Der "path" zeigt auf das aktuell betrachtete unterschema

    if path is None:
        path = []

    # Wir holen uns das aktuell betrachtete Unterschema (nach dem aktuellen path), auf der Suche nach hideif properties.
    jsonschema = _traverse_schema(global_jsonschema, path)

    # Die aktuelle Node (jsonschema) sollte direkt "properties" Kinder haben
    for key in jsonschema["properties"]:
        try:
            if (
                jsonschema["properties"][key]["type"] == "array"
                and "items" in jsonschema["properties"][key]
                and "properties" in jsonschema["properties"][key]["items"]
            ):
                convert_hide_if_props_to_declarative_jsonschema(
                    global_jsonschema=global_jsonschema,
                    path=path
                    + [
                        key,
                    ],
                )
            elif jsonschema["properties"][key].get("hideif", None) is not None:
                # Hier haben wir eine hideif property gefunden
                # der path zeigt auf den container, in dem die property ist
                hideif = jsonschema["properties"][key].get("hideif")

                # Wir extrahieren das Schema für die Property, die versteckt werden soll
                then_property = copy.deepcopy(
                    jsonschema["properties"][key]
                )  # Das ist der positive Fall, also der korrekte Schema
                else_property = {
                    "type": "null"
                }  # Im negativen Fall, setzen wir den Typen auf null, dadurch wird das Feld nicht angezeigt
                is_required = "required" in jsonschema and key in jsonschema["required"]

                # Aufräumen: hideif Property löschen; im globalen Schema das Property auf "True" setzen, weil die eigentliche Definition erst im allOf Teil folgt; required rausziehen
                del then_property["hideif"]
                jsonschema["properties"][key] = True
                if is_required:
                    jsonschema["required"].remove(key)

                outer_ifthenschema, inner_ifthenschema = _build_allOf_schema_for_path(path)

                if "allOf" not in global_jsonschema:
                    global_jsonschema["allOf"] = []

                global_jsonschema["allOf"].append(outer_ifthenschema)

                # Das allOfSchema ist eine hierarchische Struktur, ganz innen ist ein {"if": {}, "then": {}, "else": {}}
                # Das innerste "then" ist immer das Feld, das wir verstecken/anzeigen wollen.

                inner_ifthenschema["then"]["properties"][key] = copy.deepcopy(then_property)
                if is_required:
                    inner_ifthenschema["then"]["required"] = [key]
                inner_ifthenschema["else"] = {
                    "properties": {key: else_property},
                    "type": "object",
                }

                # Das richtige if müssen wir nach dem parsen finden

                global_jsonschema["allOf"].append(outer_ifthenschema)

                # Das allOfSchema ist eine hierarchische Struktur, ganz innen ist ein {"if": {}, "then": {}, "else": {}}
                # Das innerste "then" ist immer das Feld, das wir verstecken/anzeigen wollen.

                inner_ifthenschema["then"]["properties"][key] = copy.deepcopy(then_property)
                if is_required:
                    inner_ifthenschema["then"]["required"] = [key]
                inner_ifthenschema["else"] = {
                    "properties": {key: else_property},
                    "type": "object",
                }

                # Das richtige if müssen wir nach dem parsen finden
                # if = subschema mit werten, die gesetzt sein müssen (inkl. arrays...)

                patched: str = hideif.lstrip("= ").strip(" ")
                patched = patched.replace("\n"," ")
                patched = _patch_expression(patched)
                ast_tree = ast.parse(patched, mode="eval")
                
                # Prüfen, dass der Ausdruck ein Vergleich ist.
                assert (isinstance(ast_tree.body, ast.Compare) or isinstance(ast_tree.body, ast.BoolOp))

                # if = subschema mit werten, die gesetzt sein müssen (inkl. arrays...)
                # For example the Camunda hide-if expression
                # status = "rejected" or action = "update"
                # becomes
                # {'anyOf': [{'type': 'object', 'properties': {'status': {'const': 'rejected', 'default': ''}}}, {'type': 'object', 'properties': {'action': {'const': 'update', 'default': ''}}}]}
                if_not_schema, if_path = _camunda_hide_if_expression_ast_to_jsonschema(
                    node=ast_tree.body, global_jsonschema=global_jsonschema, path=path
                ) # can raise an exception
                
                # nun müssen wir im "allOfSchema" schema dem if_path folgen und das if_schema einfügen
                pointer = outer_ifthenschema
                for p in if_path:
                    pointer = pointer["then"]["properties"][p]["items"]  # ["anyOf"][0]

                pointer["if"] = {"not": if_not_schema}

        except Exception as error:
            log.exception(f'{type(error).__name__}: {error.args}. Raised in convert_hide_if_props_to_declarative_jsonschema for key={key}')
            raise error


def _patch_expression(invalid_python, lhs=""):
    # This is taken from SpiffWorkflow.bpmn.FeelLikeScriptEngine::FeelLikeScriptEngine.patch_expression
    if invalid_python is None:
        raise Exception("Expression to patch is None")
    proposed_python = invalid_python
    for transformation in feel_fixes:
        if isinstance(transformation[1], str):
            proposed_python = re.sub(
                transformation[0], transformation[1], proposed_python
            )
        else:
            for x in re.findall(transformation[0], proposed_python):
                if "." in (x):
                    proposed_python = proposed_python.replace(x, transformation[1](x))
    if lhs is not None:
        proposed_python = lhs + proposed_python

    # This is added by us (replace single "=" with double "==")
    patched = re.sub(r"(?<!=|<|>|\!)=(?!=|<|>|\!)", "==", proposed_python)

    return patched


def _camunda_hide_if_expression_ast_to_jsonschema(node, global_jsonschema, path):
    if isinstance(node, ast.Compare):  # =; !=
        assert (isinstance(node.left, ast.Name) or isinstance(node.left, ast.Constant))
        assert (isinstance(node.comparators[0], ast.Name) or isinstance(node.comparators[0], ast.Constant))

        if isinstance(node.left, ast.Name):
            left, _ = _camunda_hide_if_expression_ast_to_jsonschema(
                node.left, global_jsonschema, path
            )
            right, _ = _camunda_hide_if_expression_ast_to_jsonschema(
                node.comparators[0], global_jsonschema, path
            )
        else:
            left, _ = _camunda_hide_if_expression_ast_to_jsonschema(
                node.comparators[0], global_jsonschema, path
            )
            right, _ = _camunda_hide_if_expression_ast_to_jsonschema(
                node.left, global_jsonschema, path
            )

        op = node.ops[0]

        # left auflösen und auf const wert setzen
        found_path = _find_property_upwards(global_jsonschema, path, left)
        left_node = _traverse_schema(
            global_jsonschema=global_jsonschema, path=found_path
        )["properties"][left]
        left_type = left_node["type"] if isinstance(left_node, dict) else None
        # left_type can be a single string like "boolean" or "string" or a list of strings like: ["string", "null"]
        right_type = type(right)
        is_bool_type = left_type == "boolean" or right_type == bool

        if_schema = {
            "type": "object",
            "properties": {
                left: {
                    "const": right,
                    "default": False if right_type == "boolean" else "",
                }
            },
        }

        if is_bool_type:  # checkbox has no value if not checked
            if_schema["required"] = [left]

        if isinstance(op, ast.NotEq):
            cp = copy.deepcopy(if_schema)
            if_schema.clear()
            if_schema["not"] = cp

        return if_schema, found_path

    # <=, => currently not implemented, maybe like this...
    # elif isinstance(op, ast.Gt):
    #     return {
    #         "if": {"properties": {left: {"minimum": right + 1}}},
    #         "then": {"required": [left]},
    #     }
    # elif isinstance(op, ast.Lt):
    #     return {
    #         "if": {"properties": {left: {"maximum": right - 1}}},
    #         "then": {"required": [left]},
    #     }
    # else:
    #   raise NotImplementedError("Unsupported comparison operator")

    elif isinstance(node, ast.BoolOp):  # and/or
        values_jsonschema = []
        for i in range(len(node.values)):
            assert (isinstance(node.values[i], ast.Compare) or isinstance(node.values[i], ast.BoolOp))
            value_jsonschema, _ = _camunda_hide_if_expression_ast_to_jsonschema(
                node.values[i], global_jsonschema, path
            )
            values_jsonschema.append(value_jsonschema)
        
        if isinstance(node.op, ast.And):
            return {"allOf": values_jsonschema}, []
        elif isinstance(node.op, ast.Or):
            return {"anyOf": values_jsonschema}, []
        else:
            raise NotImplementedError("Unsupported boolean operator")
    elif isinstance(node, ast.Name):  # Variable
        return node.id, []
    elif isinstance(node, ast.Constant):  # Constant
        if isinstance(node.value, (int, float, bool, str)):
            return node.value, []
        else:
            raise NotImplementedError("Unsupported constant type")
    else:
        raise NotImplementedError("Unsupported node type")


def _build_allOf_schema_for_path(path: list[str]):
    inner = {"if": {}, "then": {"type": "object", "properties": {}}, "else": {}}
    pointer = inner
    for p in path:
        new = {
            "if": {},
            "then": {
                "type": "object",
                "properties": {p: {"type": "array", "items": pointer}},
            },
            "else": {},
        }

        pointer = new

    return pointer, inner


def get_jsonschema_for_validation(
    form: ReactJsonSchemaFormData,
    preserve_disabled_fields: bool = False,
) -> dict[Any, Any]:
    """Returns the jsonschma used for validation.
    The validation schema needs to be slightly different (remove null fields; do not allow additional properties)
    This is to be used when a user is submitting data to user tasks.
    """

    schema = copy.deepcopy(form.jsonschema)
    uischema = copy.deepcopy(form.uischema)
    if not preserve_disabled_fields:
        convert_disabled_fields_to_null_fields(
            global_jsonschema=schema, global_uischema=uischema, path=[]
        )
    convert_hide_if_props_to_declarative_jsonschema(schema, [])

    remove_data_uri_fields(schema)  # type: ignore

    schema["additionalProperties"] = False

    # null fields are removed while validating in validate_task_data

    def setAdditionalProperties(d: dict | list, set_no_additional_properties=True):
        if isinstance(d, dict):
            if set_no_additional_properties and "properties" in d:
                d["additionalProperties"] = False
            d = {
                k: setAdditionalProperties(
                    x,
                    (
                        set_no_additional_properties
                        and k not in ["anyOf", "allOf", "if"]
                    ),
                )
                for k, x in d.items()
            }
        elif isinstance(d, list):
            d = [setAdditionalProperties(x, set_no_additional_properties) for x in d]

        return d

    schema = setAdditionalProperties(schema, True)  # type: ignore
    assert isinstance(schema, dict)
    return schema


def remove_unknown_fields_from_task_data(data, validation_schema, on_remove=None):
    cls = jsonschema.validators.validator_for(validation_schema)
    validator = cls(validation_schema)
    errors = [x for x in validator.iter_errors(data)]

    for err in errors:
        if err.validator == "additionalProperties":
            path_list: list = list(err.absolute_path)
            subdata = data
            for item in path_list:
                subdata = subdata[item]
            keys = list(
                jsonschema._utils.find_additional_properties(err.instance, err.schema)
            )
            for k in keys:
                value = subdata[k]
                if on_remove is not None:
                    on_remove(path_list + [k], value)
                del subdata[k]
                log.info(f"Removing Additional Field {k} from POST data")

    return data


def get_static_options(jsonschema, path):
    node = _traverse_schema(global_jsonschema=jsonschema, path=path)
    oneOf = node.get("oneOf", [])
    values = {}

    if oneOf:
        values = {x["const"]: {"value": x["const"], "label": x["title"]} for x in oneOf}

    return values


def get_file_options(options_folder, options_file) -> list[tuple[str, str]]:
    filepath: pathlib.Path = options_folder / options_file
    data: list[tuple[str, str]] = []

    if not filepath.exists():
        raise OptionsFileNotExistsException(f"{filepath}")

    try:
        with open(filepath, "r", newline="") as csvfile:
            reader = csv.reader(csvfile, delimiter=";")
            next(reader)  # Skip the first line (headers)
            for row in reader:
                if len(row) >= 2:  # Make sure there are at least two columns in the row
                    column1, column2 = row[:2]  # Get the first two columns
                    data.append(
                        (column1, column2)
                    )  # Append them as a tuple to the list
                else:
                    log.error(f"get_file_options() of {options_folder}/{options_file}: row length={len(row)} instead of expected >= 2")
    except Exception as error:
        log.exception(f'{type(error).__name__}: {error.args}.')
        raise OptionsFileCouldNotBeReadException(f"{filepath}")

    return data

def get_function_options(jsonschema, property_path, options_function, form_data, functions_env):
    try:
        func = functions_env[options_function]
    except KeyError:
        raise OptionFunctionNotFound(f"Error when looking up options_function '{options_function}'")
    
    oth = OptionTaskHelper(
        form_data=form_data,
        property_path=property_path
    )
    data = func(oth=oth)
    return data
    

def get_options(jsonschema, property_path, options_folder, form_data, functions_env):
    custom_properties = get_custom_properties(jsonschema=jsonschema, path=property_path)
    options_file = custom_properties.get("options_file", None)
    options_function = custom_properties.get("options_function", None)

    data: list[tuple[str, str]] = []

    if options_file is not None:
        data = get_file_options(
            options_folder=options_folder, options_file=options_file
        )
    elif options_function is not None:
        data = get_function_options(
            jsonschema, property_path, options_function=options_function,
            form_data=form_data, functions_env=functions_env
        )
    else:
        static_options = get_static_options(jsonschema=jsonschema, path=property_path)
        data = [(x["value"], x["label"]) for x in static_options.values()]

    return data


def get_options_detailed(jsonschema, property_path: list[str], options_folder, form_data, functions_env):
    custom_properties = get_custom_properties(jsonschema=jsonschema, path=property_path)
    options_file = custom_properties.get("options_file", None)
    options_function = custom_properties.get("options_function", None)

    if options_file is not None:
        filepath: pathlib.Path = options_folder / options_file

        if not filepath.exists():
            raise OptionsFileNotExistsException()

        data: dict[str, dict] = {}
        try:
            headers = list()
            with open(filepath, "r", newline="") as csvfile:
                reader = csv.reader(csvfile, delimiter=";")
                csv_line_1 = next(reader)  # Skip the first line (headers)
                for header in csv_line_1:
                    headers.append(header)

                for row in reader:
                    rowdata = {}
                    for colidx in range(len(row)):
                        val = row[colidx]
                        if colidx == 0:
                            rowdata["value"] = val
                        if colidx == 1:
                            rowdata["label"] = val

                        rowdata[headers[colidx]] = val

                    data[rowdata["value"]] = rowdata
        except Exception:
            log.exception(f"Could not read options_file {str(filepath)}")
            raise OptionsFileCouldNotBeReadException(f"{filepath}")
    elif options_function is not None:
        data = get_function_options(
            jsonschema, property_path, options_function=options_function, form_data=form_data, functions_env=functions_env
        )
    else:
        static_options = get_static_options(jsonschema=jsonschema, path=property_path)
        data = static_options

    return data


def get_custom_properties(jsonschema, path: list[str]):
    node = _traverse_schema(global_jsonschema=jsonschema, path=path)
    return node.get("custom_properties", {})


def get_options_limit(jsonschema, path: list[str], default_limit: int = 15) -> int | None:
    """
    Read optional options_limit from field custom_properties.
    Default is `default_limit`; explicit 0 disables limiting.
    Always returns exactly once.
    """
    limit = default_limit
    try:
        custom_props = get_custom_properties(jsonschema=jsonschema, path=path)
        raw_limit = custom_props.get("options_limit", default_limit)
        if isinstance(raw_limit, str):
            raw_limit = int(raw_limit)
        if raw_limit == 0:
            limit = None
        elif isinstance(raw_limit, int) and raw_limit > 0:
            limit = raw_limit
    except Exception:
        limit = default_limit

    return limit


def make_uischema_read_only(
    uischema: dict,
    *,
    jsonschema: dict,
    workflow,
    task_id: uuid.UUID,
    form_data: dict | None,
) -> tuple[dict, dict]:
    """Return read-only copies of the ui schema and jsonschema for workflow previews."""
    read_only_uischema = copy.deepcopy(uischema)
    read_only_jsonschema = copy.deepcopy(jsonschema)

    from actidoo_wfe.wf import service_workflow as _service_workflow

    def _resolve_schema_node(schema: dict, path: list[str]) -> dict:
        node = schema
        remaining = list(path)

        while remaining:
            segment = remaining[0]
            properties = node.get("properties")
            if isinstance(properties, dict) and segment in properties:
                node = properties[segment]
                remaining.pop(0)
                continue

            items = node.get("items")
            if isinstance(items, dict):
                node = items
                continue

            raise KeyError(f"Schema path {path} could not be resolved.")

        return node

    def _get_selected_values(data: dict | None, path: list[str]) -> list[Any]:
        if data is None:
            return []

        current: Any = data
        for segment in path:
            if not isinstance(current, dict):
                return []
            current = current.get(segment)

        if current is None:
            return [None]
        if isinstance(current, list):
            return current
        return [current]

    def _inject_static_options(path: list[str]) -> None:
        schema_node = _resolve_schema_node(read_only_jsonschema, path)

        options = _service_workflow.get_options_for_property(
            workflow=workflow,
            task_id=task_id,
            property_path=path,
            form_data=form_data,
        )
        if not options:
            return

        option_map = {value: label for value, label in options}
        selected_values = _get_selected_values(form_data, path)
        if not selected_values:
            return

        schema_node["oneOf"] = [
            {
                "const": value,
                "title": option_map.get(
                    value,
                    "-" if value is None else str(value),
                ),
            }
            for value in selected_values
        ]

    def _mark_disabled(node: Any) -> None:
        if isinstance(node, dict):
            if "ui:path" in node:
                node["ui:disabled"] = True

            widget = node.get("ui:widget")
            if widget == "SelectDynamic":
                node["ui:widget"] = "SelectStatic"
                path = node.get("ui:path")
                if isinstance(path, list):
                    _inject_static_options(path)

            for value in node.values():
                _mark_disabled(value)
        elif isinstance(node, list):
            for item in node:
                _mark_disabled(item)

    _mark_disabled(read_only_uischema)
    return read_only_uischema, read_only_jsonschema


def remove_data_uri_fields(schema):
    """
    Recursively removes fields with the key "datauri" from the given JSON schema.
    If you have upload fields, your jsonschema will contain this...
    ```
    "properties": {
        "datauri": { # --> delete this!
            "format": "data-url",
            "type": "string"
        },
        "filename": {
            "type": "string"
        },
        "hash": {
            "type": "string"
        },
        "id": {
            "type": "string"
        },
        "mimetype": {
            "type": "string"
        }
    }
    ```

    ...and this function will remove the 'datauri' property.

    Args:
        schema (dict | list): The JSON schema from which to remove datauri fields.
        This will be a dictionary when called from the outside (because your jsonschema is an object)
        and can be a list if called recursively.

    Returns:
        None: The function modifies the schema in place and does not return a value.
    """
    if isinstance(schema, dict):
        if "datauri" in schema and schema["datauri"].get("format", None) == "data-url":
            # do not ask for 'datauri' alone, but also for the 'format', otherwise a field with a key
            # called 'datauri' (who knows what's configured in a form...) will be deleted, too.
            del schema["datauri"]
        else:
            for key in schema.keys():
                remove_data_uri_fields(schema[key])
    elif isinstance(schema, list):
        for s in schema:
            remove_data_uri_fields(s)


def make_custom_properties_validator(form: ReactJsonSchemaFormData, task_data, property_path, options_folder, functions_env):
    def custom_properties_validator(validator, value, instance, schema):
        log.info("custom_properties_validator: instance=%s, property_path=%s, value=%s)",instance, property_path, value)

        options_file = schema.get("custom_properties", {}).get("options_file", None)

        if instance is not None and options_file:
            data = get_file_options(
                options_folder=options_folder, options_file=options_file
            )
            if isinstance(instance, list):
                for instance_item in instance:
                    if not any(x for x in data if x[0] == instance_item):
                        yield jsonschema.exceptions.ValidationError(
                            f"Provided value {instance_item} not found in options_file {options_file}!"
                        )
            else:
                if not any(x for x in data if x[0] == instance):
                    yield jsonschema.exceptions.ValidationError(
                        f"Provided value {instance} not found in options_file {options_file}!"
                    )

        options_function = schema.get("custom_properties", {}).get("options_function", None)

        # log.info("Calling _traverse_schema, my path = %s", property_path)  # e.g. ["articleList", 0, "componentList", 0, "priceList", 0] or ["request_positions", 1]
        # property_path is the current position inside the tracked task data.
        # It can contain indices if we have e.g. nested lists in our task data, but these indices must be
        # deleted from the path, when getting the subschema for validation:
        p = [x for x in property_path if not isinstance(x, int)]

        required_list = _traverse_schema(global_jsonschema=form.jsonschema, path=p).get("required",[])

        is_required = p in required_list # TODO property_path is a list, can this work?
        # log.info("custom_properties_validator: required_list=%s,property_path=%s,is_required=%s",required_list, p, is_required)
        required_and_not_none = instance is not None and is_required
        not_required_but_exists = instance is not None and instance != "" and not is_required

        if options_function and (required_and_not_none or not_required_but_exists):
            # TODO not_required_but_exists:
            # aktuell ist es so, dass hier z.B. select_sub_type = '' reinkommt, obwohl der User
            # das nicht ausgewählt hat. Dafür darf dann keine Validierung gemacht werden, denn die schlägt fehl.
            # Eigentlich dürfte das Frontend gar keinen LeerString dafür erzeugen, sondern null oder undefined.
            try:
                valid_options = get_function_options(
                    jsonschema=form.jsonschema, 
                    property_path=list(property_path),
                    options_function=options_function,
                    functions_env=functions_env,
                    form_data=task_data
                )
            except OptionFunctionNotFound:
                yield jsonschema.exceptions.ValidationError(
                    f"The expected options_function '{options_function}' was not found in code!"
                )
                return

            if isinstance(instance, list):
                for instance_item in instance:
                    if not any(x for x in valid_options if x[0] == instance_item):
                        yield jsonschema.exceptions.ValidationError(
                            f"Provided value {instance_item} not found in options_function {options_function}!"
                        )
            else:
                if not any(x for x in valid_options if x[0] == instance):
                    yield jsonschema.exceptions.ValidationError(
                        f"Provided value {instance} not found in options_function {options_function}!"
                    )

        validation_function = schema.get("custom_properties", {}).get("validation_function", None)
        if validation_function:
            func = functions_env[validation_function]
            vth = ValidationTaskHelper(
                form_data=task_data,
                property_path=p
            )
            try:
                data = func(vth=vth)
            except jsonschema.exceptions.ValidationError as ex:
                yield ex

    return custom_properties_validator

@dataclass
class ValidationResult:
    task_data: dict
    error_schema: dict|None


def validate_task_data(
    form: ReactJsonSchemaFormData,
    task_data: dict,
    options_folder: pathlib.Path,
    functions_env: dict,
    preserve_unknown_fields: bool = False,
    preserve_disabled_fields: bool = False,
    log_validation_errors: bool = True
) -> ValidationResult:
    """Validate incoming task data against a form definition and clean it up.

    This is used right before task data is persisted or reused (e.g. when copying
    a workflow instance). It removes fields that are not part of the form
    definition, optionally remembers technical fields that should survive the
    check, and applies the hide-if handling so that hidden values cannot
    leak into user tasks. With ``preserve_disabled_fields`` callers can opt to
    keep values of read-only/disabled form fields. The function returns the 
    cleaned task data together with an error payload."""

    log.info("> validate_task_data")

    removed_unknown_fields: list[tuple[list, Any]] = []

    def _collect_unknown_field(path: list, value: Any):
        if preserve_unknown_fields:
            removed_unknown_fields.append((path, value))

    validation_schema = get_jsonschema_for_validation(
        form,
        preserve_disabled_fields=preserve_disabled_fields,
    )

    cleaned_task_data = remove_unknown_fields_from_task_data(
        task_data,
        validation_schema,
        on_remove=_collect_unknown_field if preserve_unknown_fields else None,
    )

    position, tracked_task_data = get_position_tracker(cleaned_task_data)

    # if there's "custom_properties"  within jsonschema["properties"] (the contents are the custom properties from the Camunda Modeler),
    # then this validator is called:
    CustomValidator = jsonschema.validators.extend(
        jsonschema.Draft202012Validator,
        validators={
            "custom_properties": make_custom_properties_validator(
                options_folder=options_folder,
                functions_env=functions_env,
                task_data = cleaned_task_data,
                property_path=position,
                form=form
            )
        },
    )

    validator_instance: jsonschema.Validator = CustomValidator(validation_schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)

    run_again = True
    removed = []
    while run_again:
        run_again = False
        try:
            # log.info(f"validate {tracked_task_data}")
            validator_instance.validate(instance=tracked_task_data)
        except jsonschema.ValidationError as ex:
            if ex.validator == "type" and ex.validator_value == "null":  # null fields are not allowed, we will remove them here

                tracked_task_data = remove_item(tracked_task_data, ex.absolute_path)
                removed.append(list(ex.absolute_path))
                run_again = True
            elif log_validation_errors:
                log.exception(f"Validation error: {ex.message}; path={ex.json_path}; instance={ex.instance}")
            
    error_schema = validate_and_create_error_dict(validator=validator_instance,instance=tracked_task_data)
    # log.debug("removed = %s", removed)

    untracked_task_data = copy.deepcopy(tracked_task_data)

    if preserve_unknown_fields and removed_unknown_fields:
        for path, value in removed_unknown_fields:
            set_item(untracked_task_data, path, value)

    if log_validation_errors:
        log.info("< validate_task_data, errors = %s", error_schema)
    else:
        log.info("< validate_task_data")

    return ValidationResult(task_data = untracked_task_data, error_schema = error_schema)


def iterate_and_replace_datauri(json_data, replace_function):
    """
    Iterate recursively over a json structure and recognise fields that contain a DataURI.
    For these fields, call an external function that replaces the content.

    Args:
      json_data: The json structure to be iterated over.
      replace_function: An external function that replaces the content of a DataURI.

    Returns:
      The modified json structure.
    """
    if isinstance(json_data, dict):
        if "datauri" in json_data and DATA_URI_RE.match(json_data["datauri"]):
            new_data = replace_function(json_data["datauri"])
            json_data.clear()
            json_data.update(new_data)
            return json_data
        else:
            new_dict = {}
            for key, value in json_data.items():
                new_item = iterate_and_replace_datauri(value, replace_function)
                new_dict[key] = new_item
            return new_dict
    elif isinstance(json_data, list):
        new_list = []
        for item in json_data:
            new_list.append(iterate_and_replace_datauri(item, replace_function))
        return new_list
    else:
        return json_data


def get_attachments(task_data) -> list[UploadedAttachmentRepresentation]:
    """Recursively extracts and validates attachments from the provided JSON data structure.

    This function traverses the input data, which can be a dictionary or a list, searching for instances
    of UploadedAttachmentRepresentation. If a dictionary is given, it tries to validate the data
    as an UploadedAttachmentRepresentation. In case of validation failure, the function will recursively
    explore each value in the dictionary for potential attachment structures. For lists, it iterates
    through each item and checks for attachments.
    Args:
        task_data (dict | list): The input JSON data structure to search for attachments.

    Returns:
        list[UploadedAttachmentRepresentation]: A list of successfully validated attachments.
    """
    attachments: list[UploadedAttachmentRepresentation] = []
    if isinstance(task_data, dict):
        try:
            attachment = UploadedAttachmentRepresentation.model_validate(task_data)
            attachments.append(attachment)
        except ValidationError:
            # If validation fails then it's not an attachment structure, so we go deeper into the nested task data
            for k, v in task_data.items():
                attachments += get_attachments(v)
    elif isinstance(task_data, list):
        for v in task_data:
            attachments += get_attachments(v)
    else:
        pass
    return attachments


def convert_disabled_fields_to_null_fields(global_jsonschema, global_uischema, path=[]):
    """We convert disabled fields to null fields for validating posted formdata"""
    uischema = _traverse_uischema(global_uischema=global_uischema, path=path)
    jsonschema = _traverse_schema(global_jsonschema=global_jsonschema, path=path)

    for k in uischema.keys():
        if isinstance(uischema[k], dict) and uischema[k].get("ui:disabled", False):
            jsonschema["properties"][k]["type"] = "null"

    for k in jsonschema.get("properties",{}).keys(): # properties might be missing. e.g. in a multi select, we will have an array of strings
        if "type" in jsonschema["properties"][k] and jsonschema["properties"][k][
            "type"
        ] in ["object", "array"]:
            convert_disabled_fields_to_null_fields(
                global_jsonschema=global_jsonschema,
                global_uischema=global_uischema,
                path=path+[k,]
            )


def _traverse_uischema(global_uischema: dict, path: list[str]):
    schema = global_uischema
    for p in path:
        if "items" in schema:
            schema = schema["items"]

        schema = schema[p]

        if "items" in schema:
            schema = schema["items"]

    return schema
