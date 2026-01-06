# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import socket
import string

from actidoo_wfe.helpers.string import create_random_string


def guess_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 1))  # connect() for UDP doesn't send packets
            return s.getsockname()[0]
    except OSError:
        return "0.0.0.0"

def generate_instance_name():
    _instance_name = (
        f"{socket.getfqdn()} - {guess_local_ip()} - "
        f"{create_random_string(length=8, characters=string.ascii_letters)}"
    )
    return _instance_name
