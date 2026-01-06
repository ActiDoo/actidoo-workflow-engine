# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH


import logging
import sys
from actidoo_wfe.storage import _unsetup_storage

pytest_plugins = ["actidoo_wfe.testing.pytest_plugin"]

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("faker.factory").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("spiff.metrics").setLevel(logging.INFO)

log = logging.getLogger(__name__)

def pytest_configure(config):
    """Align test init with the main engine tests."""
    config.option.log_cli = True
    config.option.log_cli_level = "DEBUG"


    sys._called_from_test = True  # type: ignore


def pytest_unconfigure(config):
    """Clean up global test markers and storage state."""
    import sys

    if hasattr(sys, "_called_from_test"):
        del sys._called_from_test  # type: ignore

    _unsetup_storage()
