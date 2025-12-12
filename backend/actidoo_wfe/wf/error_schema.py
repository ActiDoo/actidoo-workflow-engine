


# Function to set nested errors
def set_nested_error(errors_dict, path, message):
    #print(str(path))

    path = [x for x in path if isinstance(x, str) or isinstance(x, int)]

    for i in range(len(path)-1):
        p = path[i]
        p_next = path[i+1]

        if isinstance(errors_dict, list):
            assert isinstance(p, int)
            while len(errors_dict) < p + 1:
                errors_dict.append({})

        if isinstance(p_next, str) and ((p not in errors_dict) or not isinstance(errors_dict[p], dict)):
            # parent is dict
            errors_dict[p] = {}
        elif isinstance(p_next, int) and ((p not in errors_dict) or not isinstance(errors_dict[p], list)):
            # parent is list
            errors_dict[p] = []
        
        errors_dict = errors_dict[p]

    if path:
        if isinstance(path[-1], int):
            while len(errors_dict) < path[-1] + 1:
                errors_dict.append({})

        if isinstance(path[-1], str):
            if path[-1] not in errors_dict:
                errors_dict[path[-1]] = {}
        
        if "__errors" not in errors_dict[path[-1]]:
            errors_dict[path[-1]]["__errors"] = []

        errors_dict[path[-1]]["__errors"].append(message)
    

# Function to validate instance and generate errors dict
def validate_and_create_error_dict(validator, instance):
    errors_dict = {}
    for error in validator.iter_errors(instance):
        path = list(error.absolute_path) + (list(error.validator_value) if isinstance(error.validator_value, list) else [])
        set_nested_error(errors_dict, path, error.message)
    return dict(errors_dict) if errors_dict != {} else None

