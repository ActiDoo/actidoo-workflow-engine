# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Tests for the BFF client-version gate (ADR 011).

Every BFF request must carry exactly the backend's BFF contract version. A stale
tab that survived a deploy would otherwise keep submitting against a contract it
does not speak - for dynamic lists that means silently index-merged rows (ADR 010).

The gate is checked before authentication on purpose, so these tests do not need a
session: an unauthenticated request with a good version must fail on auth (401/403),
never on the version, and a bad version must fail on the version even without a session.
"""

from __future__ import annotations

import pytest

from actidoo_wfe.fastapi import app as root_app
from actidoo_wfe.wf.constants import BFF_CLIENT_VERSION_HEADER, BFF_CLIENT_VERSION_IGNORE, BFF_CONTRACT_VERSION
from actidoo_wfe.wf.tests.helpers.client import Client

# A representative route from each of the three gated BFF routers, with the method
# it accepts - a wrong method is answered with 405 during routing, before any
# dependency runs, so it would never reach the gate.
BFF_ROUTES = [
    ("bff_user", "get_my_wfe_user", "POST"),
    ("bff_admin", "bff_admin_system_information", "GET"),
    ("bff_user_data_model", "list_models", "GET"),
]


def _call(client: Client, route_name: str, method: str = "GET"):
    return client.root_client.request(method=method, url=root_app.url_path_for(route_name), json={})


@pytest.mark.parametrize("router,route_name,method", BFF_ROUTES)
def test_missing_version_header_is_refused(router, route_name, method):
    response = _call(Client(client_version=None), route_name, method)

    assert response.status_code == 426
    body = response.json()
    assert body["code"] == "client_version_mismatch"
    assert body["client_version"] is None
    assert body["server_contract_version"] == BFF_CONTRACT_VERSION


@pytest.mark.parametrize("router,route_name,method", BFF_ROUTES)
def test_older_client_is_refused(router, route_name, method):
    """The stale-tab case the gate exists for."""
    response = _call(Client(client_version=BFF_CONTRACT_VERSION - 1), route_name, method)

    assert response.status_code == 426
    assert response.json()["client_version"] == BFF_CONTRACT_VERSION - 1


@pytest.mark.parametrize("router,route_name,method", BFF_ROUTES)
def test_newer_client_is_refused(router, route_name, method):
    """The rollback case - and the whole reason the check is '!=' and not '>='.

    A backend rolled back below the bundle that browsers still hold must refuse
    it: the bundle speaks a contract this backend does not know.
    """
    response = _call(Client(client_version=BFF_CONTRACT_VERSION + 1), route_name, method)

    assert response.status_code == 426
    assert response.json()["client_version"] == BFF_CONTRACT_VERSION + 1


def test_non_numeric_version_is_refused():
    client = Client(client_version=None)
    client.root_client.headers[BFF_CLIENT_VERSION_HEADER] = "not-a-number"

    response = _call(client, "get_my_wfe_user", "POST")

    assert response.status_code == 426
    assert response.json()["client_version"] is None


@pytest.mark.parametrize("router,route_name,method", BFF_ROUTES)
def test_matching_version_passes_the_gate(router, route_name, method):
    """A matching version must not be answered by the gate. Without a session the
    request still fails on authentication - that is the proof it got past 426."""
    response = _call(Client(), route_name, method)

    assert response.status_code != 426
    assert response.status_code in (401, 403)


def test_version_check_runs_before_the_role_check():
    """A stale tab whose session also expired must see the version error, not a 401
    that would send the SPA into a login redirect."""
    response = _call(Client(client_version=BFF_CONTRACT_VERSION - 1), "get_my_wfe_user", "POST")

    assert response.status_code == 426


@pytest.mark.parametrize("router,route_name,method", BFF_ROUTES)
def test_the_ignore_sentinel_opts_out_of_the_check(router, route_name, method):
    """Reaching the auth check is the proof the request got past the gate."""
    client = Client(client_version=None)
    client.root_client.headers[BFF_CLIENT_VERSION_HEADER] = BFF_CLIENT_VERSION_IGNORE

    response = _call(client, route_name, method)

    assert response.status_code != 426
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("sent", ["IGNORE", "Ignore", "  ignore  "])
def test_the_ignore_sentinel_is_case_insensitive_and_trimmed(sent):
    """A hand-configured header should not fail over capitalisation or a stray space."""
    client = Client(client_version=None)
    client.root_client.headers[BFF_CLIENT_VERSION_HEADER] = sent

    response = _call(client, "get_my_wfe_user", "POST")

    assert response.status_code != 426


@pytest.mark.parametrize("sent", ["ignored", "ignore-me", "please ignore", ""])
def test_values_that_only_look_like_the_sentinel_are_still_refused(sent):
    """The opt-out is one exact word - anything else is a malformed version."""
    client = Client(client_version=None)
    client.root_client.headers[BFF_CLIENT_VERSION_HEADER] = sent

    response = _call(client, "get_my_wfe_user", "POST")

    assert response.status_code == 426


def test_version_endpoint_is_ungated_and_reports_the_contract_version():
    """What the SPA polls to notice its bundle no longer matches - it must answer
    even a client the BFF refuses, otherwise a blocked tab can never find out why."""
    response = _call(Client(client_version=None), "app_version")

    assert response.status_code == 200
    assert response.json()["bff_contract_version"] == BFF_CONTRACT_VERSION
