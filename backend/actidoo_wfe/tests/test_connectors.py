# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Tests for the Connector Registry (T1 from migration test plan)."""

import contextlib
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from actidoo_wfe.connectors import (
    ConnectorInstanceNotFoundError,
    ConnectorType,
    ConnectorTypeNotFoundError,
    connector_registry,
    get_connector,
    register_connector_type,
    validate_configured_connectors,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DummyConfig(BaseModel):
    url: str
    token: str = "default"


class IncompleteConfig(BaseModel):
    url: str  # required, no default


@contextlib.contextmanager
def dummy_factory(config: DummyConfig):
    yield {"url": config.url, "token": config.token}


@contextlib.contextmanager
def other_factory(config: DummyConfig):
    yield {"url": config.url}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure a clean registry for each test."""
    connector_registry.clear()
    yield
    connector_registry.clear()


# ---------------------------------------------------------------------------
# Unit tests — ConnectorRegistry
# ---------------------------------------------------------------------------


class TestConnectorRegistry:
    def test_register_connector_type(self):
        ct = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        connector_registry.register(ct)
        assert "dummy" in connector_registry.list_types()

    def test_register_duplicate_same_factory(self):
        ct = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        connector_registry.register(ct)
        connector_registry.register(ct)  # should not raise
        assert connector_registry.list_types().count("dummy") == 1

    def test_register_duplicate_different_factory(self):
        ct1 = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        ct2 = ConnectorType(name="dummy", config_schema=DummyConfig, factory=other_factory)
        connector_registry.register(ct1)
        with pytest.raises(ValueError, match="already registered"):
            connector_registry.register(ct2)

    def test_get_type_not_found(self):
        with pytest.raises(ConnectorTypeNotFoundError):
            connector_registry.get_type("nonexistent")

    def test_get_type_success(self):
        ct = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        connector_registry.register(ct)
        result = connector_registry.get_type("dummy")
        assert result is ct

    def test_clear_registry(self):
        ct = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        connector_registry.register(ct)
        connector_registry.clear()
        assert connector_registry.list_types() == []

    def test_list_types_sorted(self):
        connector_registry.register(ConnectorType(name="zebra", config_schema=DummyConfig, factory=dummy_factory))
        connector_registry.register(ConnectorType(name="alpha", config_schema=DummyConfig, factory=other_factory))
        assert connector_registry.list_types() == ["alpha", "zebra"]


# ---------------------------------------------------------------------------
# Unit tests — get_connector
# ---------------------------------------------------------------------------


class TestGetConnector:
    def test_get_connector_success(self, monkeypatch):
        ct = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        connector_registry.register(ct)

        fake_settings = MagicMock()
        fake_settings.connectors = {"dummy": {"inst1": {"url": "https://example.com", "token": "abc"}}}
        monkeypatch.setattr("actidoo_wfe.settings.settings", fake_settings)

        ctx = get_connector("dummy", "inst1")
        with ctx as obj:
            assert obj["url"] == "https://example.com"
            assert obj["token"] == "abc"

    def test_get_connector_invalid_config(self, monkeypatch):
        ct = ConnectorType(name="dummy", config_schema=IncompleteConfig, factory=dummy_factory)
        connector_registry.register(ct)

        fake_settings = MagicMock()
        fake_settings.connectors = {"dummy": {"inst1": {"missing_field": "value"}}}
        monkeypatch.setattr("actidoo_wfe.settings.settings", fake_settings)

        with pytest.raises(Exception):  # ValidationError from pydantic
            get_connector("dummy", "inst1")

    def test_get_connector_type_not_found(self, monkeypatch):
        fake_settings = MagicMock()
        fake_settings.connectors = {}
        monkeypatch.setattr("actidoo_wfe.settings.settings", fake_settings)

        with pytest.raises(ConnectorTypeNotFoundError):
            get_connector("unknown", "inst1")

    def test_get_connector_instance_not_found(self, monkeypatch):
        ct = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        connector_registry.register(ct)

        fake_settings = MagicMock()
        fake_settings.connectors = {"dummy": {"other_inst": {"url": "x"}}}
        monkeypatch.setattr("actidoo_wfe.settings.settings", fake_settings)

        with pytest.raises(ConnectorInstanceNotFoundError, match="inst1"):
            get_connector("dummy", "inst1")

    def test_get_connector_no_instances_for_type(self, monkeypatch):
        ct = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        connector_registry.register(ct)

        fake_settings = MagicMock()
        fake_settings.connectors = {}
        monkeypatch.setattr("actidoo_wfe.settings.settings", fake_settings)

        with pytest.raises(ConnectorInstanceNotFoundError):
            get_connector("dummy", "inst1")


# ---------------------------------------------------------------------------
# Unit tests — validate_configured_connectors
# ---------------------------------------------------------------------------


class TestValidateConfiguredConnectors:
    def test_validate_warns_on_misconfigured(self, monkeypatch):
        ct = ConnectorType(name="dummy", config_schema=IncompleteConfig, factory=dummy_factory)
        connector_registry.register(ct)

        fake_settings = MagicMock()
        fake_settings.connectors = {"dummy": {"bad": {"wrong_field": "x"}}}
        monkeypatch.setattr("actidoo_wfe.settings.settings", fake_settings)

        warnings = validate_configured_connectors()
        assert len(warnings) == 1
        assert "dummy/bad" in warnings[0]

    def test_validate_warns_on_unknown_type(self, monkeypatch):
        fake_settings = MagicMock()
        fake_settings.connectors = {"nonexistent": {"inst": {"url": "x"}}}
        monkeypatch.setattr("actidoo_wfe.settings.settings", fake_settings)

        warnings = validate_configured_connectors()
        assert len(warnings) == 1
        assert "not registered" in warnings[0]

    def test_validate_clean_config(self, monkeypatch):
        ct = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        connector_registry.register(ct)

        fake_settings = MagicMock()
        fake_settings.connectors = {"dummy": {"inst1": {"url": "https://ok.com", "token": "t"}}}
        monkeypatch.setattr("actidoo_wfe.settings.settings", fake_settings)

        warnings = validate_configured_connectors()
        assert warnings == []


# ---------------------------------------------------------------------------
# Unit tests — @register_connector_type decorator
# ---------------------------------------------------------------------------


class TestRegisterConnectorTypeDecorator:
    def test_decorator_registers_immediately(self):
        @register_connector_type(name="decorated", config_schema=DummyConfig)
        @contextlib.contextmanager
        def my_connector(config: DummyConfig):
            yield config

        assert "decorated" in connector_registry.list_types()

    def test_decorator_preserves_function(self):
        @register_connector_type(name="preserved", config_schema=DummyConfig)
        @contextlib.contextmanager
        def my_connector(config: DummyConfig):
            yield "hello"

        # The decorator should return the original function
        with my_connector(DummyConfig(url="x")) as result:
            assert result == "hello"


# ---------------------------------------------------------------------------
# Integration tests — Helper classes delegate to get_connector
# ---------------------------------------------------------------------------


class TestHelperIntegration:
    def test_sth_get_connector(self, monkeypatch):
        ct = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        connector_registry.register(ct)

        fake_settings = MagicMock()
        fake_settings.connectors = {"dummy": {"inst1": {"url": "https://sth.test"}}}
        monkeypatch.setattr("actidoo_wfe.settings.settings", fake_settings)

        from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

        sth = object.__new__(ServiceTaskHelper)  # skip __init__
        with sth.get_connector("dummy", "inst1") as obj:
            assert obj["url"] == "https://sth.test"

    def test_oth_get_connector(self, monkeypatch):
        ct = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        connector_registry.register(ct)

        fake_settings = MagicMock()
        fake_settings.connectors = {"dummy": {"inst1": {"url": "https://oth.test"}}}
        monkeypatch.setattr("actidoo_wfe.settings.settings", fake_settings)

        from actidoo_wfe.wf.option_task_helper import OptionTaskHelper

        oth = object.__new__(OptionTaskHelper)
        with oth.get_connector("dummy", "inst1") as obj:
            assert obj["url"] == "https://oth.test"

    def test_vth_get_connector(self, monkeypatch):
        ct = ConnectorType(name="dummy", config_schema=DummyConfig, factory=dummy_factory)
        connector_registry.register(ct)

        fake_settings = MagicMock()
        fake_settings.connectors = {"dummy": {"inst1": {"url": "https://vth.test"}}}
        monkeypatch.setattr("actidoo_wfe.settings.settings", fake_settings)

        from actidoo_wfe.wf.validation_task_helper import ValidationTaskHelper

        vth = object.__new__(ValidationTaskHelper)
        with vth.get_connector("dummy", "inst1") as obj:
            assert obj["url"] == "https://vth.test"
