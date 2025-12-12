import logging
import random
import socket
import sys
import time

log = logging.getLogger(__name__)


def wait_for_server(host, port):
    """Wait until we can successfully open a socket to the given host, port. This can be used, e.g. to wait for the database server to be available before running app init code."""

    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((host, port))
                #log.info(f"Successfully connected to {host}:{port}")
                break
        except socket.error:
            log.info(f"Waiting for {host}:{port}")
            time.sleep(0.5 + (random.randint(0, 100) / 1000))

    if getattr(sys, "_called_from_test", False) is False:
        time.sleep(3)
