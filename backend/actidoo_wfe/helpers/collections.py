# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging

log = logging.getLogger(__name__)

def remove_item(obj, path):
    # log.info(f"remove_item {path} from {obj}")
    if not path:
        return obj

    path = list(path)

    key = path[0]
    if isinstance(obj, list) and isinstance(key, int):
        if key < len(obj):
            if len(path) == 1:
                obj.pop(key)
            else:
                obj[key] = remove_item(obj[key], path[1:])
    elif isinstance(obj, dict) and isinstance(key, str) and key in obj:
        if len(path) == 1:
            del obj[key]
        else:
            obj[key] = remove_item(obj[key], path[1:])

    return obj


def set_item(obj, path, value):
    if not path:
        return value

    cursor = obj
    for idx, key in enumerate(path):
        is_last = idx == len(path) - 1
        if is_last:
            if isinstance(key, int):
                if not isinstance(cursor, list):
                    raise TypeError("Expected list while setting item")
                while len(cursor) <= key:
                    cursor.append(None)
                cursor[key] = value
            else:
                if not isinstance(cursor, dict):
                    raise TypeError("Expected dict while setting item")
                cursor[key] = value
            return obj

        next_key = path[idx + 1]
        if isinstance(key, int):
            if not isinstance(cursor, list):
                raise TypeError("Expected list while traversing path")
            while len(cursor) <= key:
                cursor.append({} if not isinstance(next_key, int) else [])
            if cursor[key] is None:
                cursor[key] = {} if not isinstance(next_key, int) else []
            cursor = cursor[key]
        else:
            if not isinstance(cursor, dict):
                raise TypeError("Expected dict while traversing path")
            if key not in cursor or cursor[key] is None:
                cursor[key] = [] if isinstance(next_key, int) else {}
            cursor = cursor[key]

    return obj
