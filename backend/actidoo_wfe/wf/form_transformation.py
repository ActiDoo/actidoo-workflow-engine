import logging
import string
from functools import cache
from pathlib import Path

import orjson

from actidoo_wfe.helpers.string import create_random_string
from actidoo_wfe.wf.types import ReactJsonSchemaFormData

log = logging.getLogger(__name__)


def empty_form():
    jsonschema = {"definitions": dict(), "type": "object", "properties": dict()}
    uischema = {"ui:field": "layout", "ui:layout": dict()}
    return ReactJsonSchemaFormData(jsonschema=jsonschema, uischema=uischema)

@cache
def transform_camunda_form_from_file(form_file_path: Path):
    log.info("> transform_camunda_form_from_file: path=%s", form_file_path)
    if not form_file_path.exists():
            return empty_form()
    
    with open(form_file_path, "r") as fp:
        form_camunda_json = orjson.loads(fp.read())
        form = transform_camunda_form(form_camunda_json)
    log.info("< transform_camunda_form_from_file")
    return form

def transform_camunda_form(form_camunda_json) -> ReactJsonSchemaFormData:
    """Transforms a camunda form to jsonschema + uischema. This should be sent to the browser to render the form."""
    jsonschema = {"definitions": dict(), "type": "object", "properties": dict()}
    uischema = {"ui:field": "layout", "ui:layout": dict()}

    for component in form_camunda_json["components"]:
        _insert_component(component=component, global_jsonschema=jsonschema, jsonschemapath=[], uischema=uischema)
    # convert_hide_if_props_to_declarative_jsonschema(jsonschema, []) 

    return ReactJsonSchemaFormData(jsonschema=jsonschema, uischema=uischema)

def _insert_component(component: dict, global_jsonschema: dict, jsonschemapath: list[str], uischema: dict):
    is_dynamiclist = component.get("type", "") == "dynamiclist"
    itemgroup = component.get("path", "")

    if is_dynamiclist:
        all_itemgroup_components = [
            comp
            for comp in component["components"]
        ]
        add_button_text = component.get("properties", {}).get("itemgroup_addbutton", "Add")
        arrayAllowAddRemove = component.get("allowAddRemove", True)
        overview_button_text = component.get("properties", {}).get("itemgroup_overviewbutton", "Overview")
        try:
            min_items = int(component.get("properties", {}).get("minItems", 0))
        except ValueError:
            min_items = 0 # just in case someone configured a string

        default_repetitions = component.get("defaultRepetitions", 0)
        label = component.get("label", "")
        _insert_array_component(
            component, itemgroup, all_itemgroup_components, global_jsonschema, jsonschemapath, uischema, add_button_text, arrayAllowAddRemove, overview_button_text, min_items, default_repetitions, label
        )
    else:
        _insert_single_component(component, global_jsonschema, jsonschemapath, uischema)

def _insert_array_component(
    component, itemgroup, all_itemgroup_components, global_jsonschema, jsonschemapath, uischema, add_button_text, arrayAllowAddRemove, overview_button_text, min_items, default_repetitions, label
):
    """
    Will create a array-property of the name {itemgroup} in the given jsonschema/uischema.
    The children are given in {all_itemgroup_components} and will be inserted using the _insert_component function
    """

    jsonschema = _traverse_schema(global_jsonschema, jsonschemapath)

    jsonschema["properties"][itemgroup] = {
        "type": "array",
        "items": {"type": "object", "properties": {}},
    }
    if min_items > 0:
        jsonschema["properties"][itemgroup]["minItems"] = min_items

    uischema[itemgroup] = {
        "items": {"ui:field": "layout", "ui:layout": dict()},
        "ui:arrayAddButtonText": add_button_text,
        "ui:arrayAllowAddRemove": str(arrayAllowAddRemove),
        "ui:arrayOverviewButtonText": overview_button_text,
        "ui:defaultRepetitions": default_repetitions,
        "ui:label": label,
    }
    if itemgroup not in uischema["ui:layout"]:
        uischema["ui:layout"][itemgroup] = [itemgroup]

    _handle_conditional_hide(component, uischema, jsonschema, itemgroup)

    for component in all_itemgroup_components:
        path = jsonschemapath + [itemgroup]
        _insert_component(
            component,
            global_jsonschema,
            path,
            uischema[itemgroup]["items"],
        )


def _traverse_schema(global_jsonschema: dict, path: list[str]):
    jsonschema = global_jsonschema
    # log.info("> _traverse_schema: path=%s", path)
    # log.info("> _traverse_schema: global_jsonschema=%s", global_jsonschema)
    for p in path:
        # log.info("_traverse_schema: p=%s", p)

        if "properties" in jsonschema:
            jsonschema = jsonschema["properties"]
        if "items" in jsonschema and "properties" in jsonschema["items"]:
            jsonschema = jsonschema["items"]

        jsonschema = jsonschema[p]

        if "properties" in jsonschema:
            jsonschema = jsonschema["properties"]
        if "items" in jsonschema and "properties" in jsonschema["items"]:
            jsonschema = jsonschema["items"]
    # log.info("< _traverse_schema %s", jsonschema)
    return jsonschema


def _insert_single_component(
    component: dict, global_jsonschema: dict, jsonschemapath: list[str], uischema: dict
):
    jsonschema = _traverse_schema(global_jsonschema, jsonschemapath)
    key = component.get("key", component.get("id"))

    if _is_attachment_multi(component):
        _handle_label(component, jsonschema, key)
        _handle_default_value(component, jsonschema, key)
        _handle_layout(component, uischema, key)
        _create_ui_schema_key(component, jsonschemapath, uischema, key, markdown=False)
        _handle_conditional_hide(component, uischema, jsonschema, key)
        _handle_disable(component, uischema, jsonschema, key)

        uischema[key].update(
            {
                "ui:field": "AttachmentMulti",
            }
        )
        jsonschema["properties"][key].update({
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "datauri": {"type": "string", "format": "data-url"},
                    "filename": {"type": "string"},
                    "hash": {"type": "string"},
                    "id": {"type": "string"},
                    "mimetype": {"type": "string"},
                },
            },
        })
        # If the attachment_multi field is 'required' we must set the minItems attribute,
        # because in the jsonschema the type is an array, which means we must have at least one file attached.
        # That is also the reaons we do not need call _handle_validate() for this component.
        if _is_required(component):
            jsonschema["properties"][key]["minItems"] = 1
        return
    elif _is_attachment_single(component):
        _handle_label(component, jsonschema, key)
        _handle_default_value(component, jsonschema, key)
        _handle_validate(component, jsonschema, key)
        _handle_layout(component, uischema, key)
        _create_ui_schema_key(component, jsonschemapath, uischema, key, markdown=False)
        _handle_conditional_hide(component, uischema, jsonschema, key)
        _handle_disable(component, uischema, jsonschema, key)
        uischema[key].update(
            {
                "ui:field": "AttachmentSingle",
            }
        )
        jsonschema["properties"][key].update({
            "type": "object",
            "properties": {
                "datauri": {"type": "string", "format": "data-url"},
                "filename": {"type": "string"},
                "hash": {"type": "string"},
                "id": {"type": "string"},
                "mimetype": {"type": "string"},
            }
        })
        return


    _handle_label(component, jsonschema, key)

    _handle_default_value(component, jsonschema, key)

    _handle_validate(component, jsonschema, key)

    _handle_layout(component, uischema, key)

    _create_ui_schema_key(component, jsonschemapath, uischema, key)

    _handle_conditional_hide(component, uischema, jsonschema, key)

    _handle_disable(component, uischema, jsonschema, key)

    custom_properties = _handle_custom_properties(component, jsonschema, key)

    
    if component["type"] == "text":
        jsonschema["properties"][component["id"]].update({"type": "null", "title": ""})
        uischema[key].update(
            {
                "ui:description": component.get("text", ""),
            }
        )
    elif component["type"] == "textfield":
        pass
    elif component["type"] == "textarea":
        uischema[key].update(
            {
                "ui:widget": "textarea", # TODO no custom behaviour for 'textarea' in Frontend code??
            }
        )
    elif component["type"] == "select" and custom_properties.get("custom_type", "") == "select_multi":
        
        jsonschema["properties"][key].update({
            "type": "array",
            "items": {
                "type": "string",
            },
        })

        if not custom_properties.get("options_file") and not custom_properties.get("options_function"):
            # static values configured
            uischema[key].update({"ui:widget": "MultiSelectStatic"})
            oneOf = [
                        {"const": x["value"], "title": x["label"]}
                        for x in component["values"]
                    ]
            jsonschema["properties"][key]["items"].update(
                {
                    "oneOf": oneOf
                }
            )
        else:
            uischema[key].update({"ui:widget": "MultiSelectDynamic"})
            # "depends_on" property only makes sense in conjunction with "options_function"
            if custom_properties.get("depends_on"):
                uischema[key].update({"ui:dependsOn": [x.strip() for x in custom_properties.get("depends_on").split(",")]})
        
        

    elif component["type"] == "select":
        # We don't have the necessacity to add None/null as default-value, which would be done like this:
        # uischema[key].update({"ui:emptyValue": None})
        
        jsonschema["properties"][key].update({
            "type": ["string", "null"], # For single values we allow 'null' in case a user deselects a drop-down
        })        
        
        if not custom_properties.get("options_file") and not custom_properties.get("options_function"):
            # static values configured
            uischema[key].update({"ui:widget": "SelectStatic"})            
            oneOf = [
                        {"const": x["value"], "title": x["label"]}
                        for x in component["values"]
                    ]
            oneOf.append({"const": None, "title": "(null)"})
            jsonschema["properties"][key].update(
                {
                    "oneOf": oneOf
                }
            )
        else:
            uischema[key].update({"ui:widget": "SelectDynamic"})
            if custom_properties.get("depends_on"):
                uischema[key].update({"ui:dependsOn": [x.strip() for x in custom_properties.get("depends_on").split(",")]})

    elif component["type"] == "number":
        jsonschema["properties"][key].update(
            {
                "type": "number",
            }
        )
        if component.get("appearance", None) and component["appearance"].get("suffixAdorner", None):
            uischema[key].update({"ui:suffixAdorner":component["appearance"]["suffixAdorner"]})
            title = jsonschema["properties"][key]["title"]
            # title += " /" + component["appearance"]["suffixAdorner"]
            title += " (" + component["appearance"]["suffixAdorner"] + ") "
            jsonschema["properties"][key].update({"title": title})
            pass
    elif component["type"] == "date":
        jsonschema["properties"][key].update(
            {"title": component["dateLabel"], "type": "string", "format": "date"}
        )
    elif component["type"] == "checkbox":
        jsonschema["properties"][key].update(
            {
                "type": "boolean",
            }
        )
    elif component["type"] == "radio":
        jsonschema["properties"][key].update(
            {
                "oneOf": [
                    {"const": x["value"], "title": x["label"]}
                    for x in component["values"]
                ]
            }
        )
        uischema[key].update({"ui:widget": "radio"}) # TODO no custom behaviour for 'radio' in Frontend code??
    elif component["type"] == "datetime" and component.get("subtype", None) == "date":
        jsonschema["properties"][key].update(
            {"title": component["dateLabel"], "type": "string", "format": "date"}
        )
    # The code for the time field works and a time field gets correctly rendered.
    # However, the validation of the time field fails, therefore I leave this code still as comment
    # elif component["type"] == "datetime" and component.get("subtype", None) == "time":
    #     jsonschema["properties"][key].update(
    #         {"title": component["timeLabel"], "type": "string", "format": "time"}
    #     )
    elif component["type"] == "datetime" and component.get("subtype", None) == "datetime":
        # I Camunda Modeler a "datetime" component gets rendered as two fields with distinct labels.
        # In our WfE frontend it's a connected field with only one label, so we only use the 'dataLabel' parameter
        # and omit the 'timeLabel' parameter.
        jsonschema["properties"][key].update(
            {"title": component["dateLabel"], "type": "string", "format": "datetime"}
        )

def _handle_custom_properties(component, jsonschema, key):
    custom_properties = component.get("properties", {})
    if len(custom_properties) > 0:
        jsonschema["properties"][key].update(
            {"custom_properties": custom_properties}
        )
        
    return custom_properties

def _handle_label(component, jsonschema, key):
    jsonschema["properties"][key] = {
        "type": "string",
        "title": component.get("label", component.get("text", "")),
    }

def _is_attachment_single(component):
    custom_properties = component.get("properties", {})
    return custom_properties.get("custom_type", "") == "attachment_single"

def _is_attachment_multi(component):
    custom_properties = component.get("properties", {})
    return custom_properties.get("custom_type", "") == "attachment_multi"

def _handle_disable(component, uischema, jsonschema, key):
    if _is_disabled(component):
        uischema[key]["ui:disabled"] = True

def _is_disabled(component):
    return component.get("disabled", False)

def _handle_conditional_hide(component, uischema, jsonschema, key):
    conditional = component.get("conditional", {})
    hide: str = conditional.get("hide", "")
    if hide != "":
        jsonschema["properties"][key]["hideif"] = hide  # We will handle this later
        uischema[key]["ui:hideif"] = hide  # We will handle this later

def _create_ui_schema_key(component, jsonschemapath, uischema, key, markdown=True):
    # TODO I guess there are many components, whose Frontend code will not support markdown, but this is the default
    # and then the uischema will contain unnecessary and misleading data.
    if markdown:
        uischema[key] = {
            "ui:description": component.get("description", ""),
            "ui:enableMarkdownInDescription": True,
            "ui:path": jsonschemapath + [key],
        }
    else:
        uischema[key] = {
        "ui:description": component.get("description", ""),
        "ui:path": jsonschemapath + [key],
    }


def _handle_layout(component, uischema, key):
    if "layout" in component and "row" in component["layout"]:
        row = component["layout"]["row"]
    else:
        row = create_random_string(length=8, characters=string.ascii_letters)

    if row not in uischema["ui:layout"]:
        uischema["ui:layout"][row] = []
    uischema["ui:layout"][row].append(key)

def _handle_validate(component, jsonschema, key):
    validate = component.get("validate", {})
    if _is_required(component) and not _is_attachment_multi(component):
        jsonschema["required"] = jsonschema.get("required", []) + [
            key,
        ]
    if validate.get("minLength", None) is not None:
        jsonschema["properties"][key]["minLength"] = validate.get("minLength")
    if validate.get("maxLength", None) is not None:
        jsonschema["properties"][key]["maxLength"] = validate.get("maxLength")

def _is_required(component):
    validate = component.get("validate", {})
    return validate.get("required", False) and not _is_disabled(component)

def _handle_default_value(component, jsonschema, key):
    if component.get("defaultValue", None) is not None:
        jsonschema["properties"][key]["default"] = component.get("defaultValue")

