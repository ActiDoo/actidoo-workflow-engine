# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging
import os
import re

from actidoo_wfe.storage import _unsetup_storage
import pytest
import venusian

pytest_plugins = ["actidoo_wfe.testing.pytest_plugin"]

# Do not test third-party code.
collect_ignore_glob = [
    "**/node_modules/*",
    "**/web_modules/*",
]

# Configure Logging
if os.path.exists("log-unittest.log"):
    os.remove("log-unittest.log")
# logging.basicConfig(filename="log-unittest.log", level=logging.DEBUG, format="%(asctime)s\t[%(levelname)s]\t%(message)s")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("faker.factory").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("spiff.metrics").setLevel(logging.INFO)
# logging.getLogger("fontTools.subset").setLevel(logging.WARNING)
# logging.getLogger("fpdf").setLevel(logging.WARNING)
# from http.client import HTTPConnection  # py3
# HTTPConnection.debuglevel = 1


def pytest_configure(config):
    """This hook is called after command line options have been parsed"""
    config.option.log_cli = True
    config.option.log_cli_level = "DEBUG"
    import sys

    # We are setting a global flag, so we can trace whether we are currently inside a test.
    # This is read in actidoo_wfe.helpers.test
    sys._called_from_test = True  # type: ignore

    if os.getenv("AUTH_TEST_SKIP_APP_INIT") == "1":
        return

    import actidoo_wfe as pyapp

    scanner = venusian.Scanner()
    scanner.scan(pyapp, ignore=[re.compile("test_").search])


def pytest_unconfigure(config):
    """This hook is called before the test process is exited"""
    import sys

    del sys._called_from_test  # type: ignore

    _unsetup_storage()
