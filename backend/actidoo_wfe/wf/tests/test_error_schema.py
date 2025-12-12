
from jsonschema import Draft202012Validator

from actidoo_wfe.wf.error_schema import validate_and_create_error_dict


def get_validator(schema):
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def test_simple_error():
    schema = {
        "type": "object",
        "properties": {
            "firstName": {"type": "string"}
        },
        "required": ["firstName"]
    }
    instance = {}
    expected = {
        "firstName": {
            "__errors": [
                "'firstName' is a required property"
            ]
        }
    }
    assert validate_and_create_error_dict(get_validator(schema), instance) == expected

def test_nested_error():
    schema = {
        "type": "object",
        "properties": {
            "addresses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string"},
                    },
                    "required": ["street"]
                }
            }
        }
    }
    instance = {"addresses": [{}]}
    expected = {
        "addresses": [
            {
                "street": {
                    "__errors": [
                        "'street' is a required property"
                    ]
                }
            }
        ]
    }
    assert validate_and_create_error_dict(get_validator(schema), instance) == expected

def test_multiple_errors():
    schema = {
        "type": "object",
        "properties": {
            "firstName": {"type": "string"},
            "age": {"type": "integer", "minimum": 18},
        },
        "required": ["firstName", "age"]
    }
    instance = {
        "firstName": "John",
        "age": 16
    }
    expected = {
        "age": {
            "__errors": [
                "16 is less than the minimum of 18"
            ]
        }
    }
    assert validate_and_create_error_dict(get_validator(schema), instance) == expected

def test_array_index_error():
    schema = {
        "type": "object",
        "properties": {
            "addresses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                    },
                    "required": ["street"]
                }
            }
        }
    }
    instance = {
        "addresses": [{
            "city": "New York"
        }]
    }
    expected = {
        "addresses": [
            {
                "street": {
                    "__errors": [
                        "'street' is a required property"
                    ]
                }
            }
        ]
    }
    assert validate_and_create_error_dict(get_validator(schema), instance) == expected

def test_allOf_error():
    schema = {
        "type": "object",
        "properties": {
            "user": {
                "type": "object",
                "allOf": [
                    {"properties": {"firstName": {"type": "string"}}, "required": ["firstName"]},
                    {"properties": {"lastName": {"type": "string"}}, "required": ["lastName"]}
                ]
            }
        }
    }
    instance = {"user": {"firstName": "John"}}
    expected = {
        "user": {
            "lastName": {
                "__errors": [
                    "'lastName' is a required property"
                ]
            }
        }
    }
    assert validate_and_create_error_dict(get_validator(schema), instance) == expected

def test_anyOf_error():
    schema = {
        "type": "object",
        "properties": {
            "contact": {
                "type": "object",
                "anyOf": [
                    {"properties": {"email": {"type": "string", "format": "email"}}, "additionalProperties": False, "required": ["email"],},
                    {"properties": {"phone": {"type": "string", "pattern": "^[0-9]+$"}}, "additionalProperties": False, "required": ["phone"],}
                ]
            }
        }
    }
    instance = {"contact": {"email": "invalid-email"}}
    expected = {
        "contact": {
            "__errors": [
                "{'email': 'invalid-email'} is not valid under any of the given schemas"
            ]
        }
    }
    result = validate_and_create_error_dict(get_validator(schema), instance)
    assert result == expected

def test_if_then_else():
    schema = {
        "type": "object",
        "properties": {
            "age": {"type": "integer"},
            "drivingLicense": {"type": "string"}
        },
        "if": {
            "properties": {"age": {"minimum": 18}}
        },
        "then": {
            "required": ["drivingLicense"]
        },
        "else": {
            "properties": {"drivingLicense": {"const": None}}
        }
    }
    instance = {"age": 17, "drivingLicense": "A12345"}
    expected = {
        "drivingLicense": {
            "__errors": [
                "None was expected"
            ]
        }
    }
    assert validate_and_create_error_dict(get_validator(schema), instance) == expected

