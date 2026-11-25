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
