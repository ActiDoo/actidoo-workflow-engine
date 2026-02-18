# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Tests for the Workflow Data REST API."""

import pytest
from unittest.mock import MagicMock

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from actidoo_wfe.data_models import (
    DataModelDescriptor,
    VirtualField,
    WorkflowDataApiConfig,
    WorkflowManagedMixin,
    _MIXIN_SYSTEM_COLUMNS,
    data_model_registry,
    extension_model_base,
    register_data_model,
    _columns_from_model,
    _fields_metadata,
    _serialize_row,
    _user_has_read_access,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    data_model_registry.clear()
    yield
    data_model_registry.clear()


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------


_ApiTestBase = extension_model_base("apitest")


class ApiTestModel(_ApiTestBase, WorkflowManagedMixin):
    _ext_table = "ate"
    __abstract__ = False
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    value: Mapped[int | None] = mapped_column(nullable=True)


# A plain model without mixin (for testing non-API models)
class PlainTestModel(_ApiTestBase):
    _ext_table = "pte"
    __abstract__ = False
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)


# ---------------------------------------------------------------------------
# Column metadata tests
# ---------------------------------------------------------------------------


class TestColumnMetadata:
    def test_columns_from_model_excludes_mixin_system_columns(self):
        cols = _columns_from_model(ApiTestModel)
        col_names = [c["name"] for c in cols]
        # Business + visible mixin columns
        assert "workflow_instance_id" in col_names
        assert "created_at" in col_names
        assert "name" in col_names
        assert "value" in col_names
        # System columns excluded
        assert "parent_workflow_instance_id" not in col_names
        assert "child_workflow_instance_id" not in col_names
        assert "action" not in col_names

    def test_columns_from_model_primary_key(self):
        cols = _columns_from_model(ApiTestModel)
        wf_col = next(c for c in cols if c["name"] == "workflow_instance_id")
        assert wf_col["primary_key"] is True

    def test_columns_from_plain_model(self):
        """Plain model (no mixin) returns all columns."""
        cols = _columns_from_model(PlainTestModel)
        col_names = [c["name"] for c in cols]
        assert "id" in col_names
        assert "title" in col_names


# ---------------------------------------------------------------------------
# Fields metadata tests
# ---------------------------------------------------------------------------


class TestFieldsMetadata:
    def test_fields_metadata_without_fields_config(self):
        """No fields config — returns all columns minus system columns."""
        api_cfg = WorkflowDataApiConfig()
        desc = DataModelDescriptor(
            name="Test", model_class=ApiTestModel, namespace="apitest", api=api_cfg
        )
        meta = _fields_metadata(desc)
        names = [m["name"] for m in meta]
        assert "workflow_instance_id" in names
        assert "name" in names
        assert "parent_workflow_instance_id" not in names

    def test_fields_metadata_with_explicit_fields(self):
        """Explicit fields list controls which fields appear and in what order."""
        api_cfg = WorkflowDataApiConfig(
            fields=["name", "value"],
        )
        desc = DataModelDescriptor(
            name="Test", model_class=ApiTestModel, namespace="apitest", api=api_cfg
        )
        meta = _fields_metadata(desc)
        assert len(meta) == 2
        assert meta[0]["name"] == "name"
        assert meta[1]["name"] == "value"

    def test_fields_metadata_with_virtual_field(self):
        vf = VirtualField("is_high", type="boolean", value=lambda row: row.value > 10)
        api_cfg = WorkflowDataApiConfig(
            fields=["name", vf],
        )
        desc = DataModelDescriptor(
            name="Test", model_class=ApiTestModel, namespace="apitest", api=api_cfg
        )
        meta = _fields_metadata(desc)
        assert len(meta) == 2
        assert meta[0]["name"] == "name"
        assert meta[1]["name"] == "is_high"
        assert meta[1]["type"] == "boolean"
        assert meta[1]["virtual"] is True


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_serialize_row_excludes_mixin_system_columns(self):
        row = ApiTestModel(
            workflow_instance_id="wf1", name="Test", value=42,
            parent_workflow_instance_id="wf0",
            child_workflow_instance_id=None,
            action="create",
        )
        result = _serialize_row(row)
        assert result["workflow_instance_id"] == "wf1"
        assert result["name"] == "Test"
        assert result["value"] == 42
        # System columns excluded
        assert "parent_workflow_instance_id" not in result
        assert "child_workflow_instance_id" not in result
        assert "action" not in result

    def test_serialize_row_with_fields(self):
        row = ApiTestModel(
            workflow_instance_id="wf1", name="Test", value=42,
        )
        result = _serialize_row(row, fields=["workflow_instance_id", "name"])
        assert result == {"workflow_instance_id": "wf1", "name": "Test"}

    def test_serialize_row_with_virtual_field(self):
        vf = VirtualField("doubled", type="integer", value=lambda r: r.value * 2)
        row = ApiTestModel(
            workflow_instance_id="wf1", name="Test", value=21,
        )
        result = _serialize_row(row, fields=["name", vf])
        assert result == {"name": "Test", "doubled": 42}


# ---------------------------------------------------------------------------
# Access control helper tests
# ---------------------------------------------------------------------------


class TestAccessControl:
    def test_user_has_read_access_no_roles(self):
        """No read_roles restriction = all authenticated users have access."""
        api_cfg = WorkflowDataApiConfig(read_roles=[])
        descriptor = DataModelDescriptor(
            name="Test", model_class=ApiTestModel, namespace="apitest", api=api_cfg
        )
        user = MagicMock()
        user.roles = []
        assert _user_has_read_access(user, descriptor, MagicMock()) is True

    def test_user_has_read_access_with_role(self):
        api_cfg = WorkflowDataApiConfig(read_roles=["viewer"])
        descriptor = DataModelDescriptor(
            name="Test", model_class=ApiTestModel, namespace="apitest", api=api_cfg
        )
        role_mock = MagicMock()
        role_mock.role.name = "viewer"
        user = MagicMock()
        user.roles = [role_mock]
        assert _user_has_read_access(user, descriptor, MagicMock()) is True

    def test_user_lacks_read_access(self):
        api_cfg = WorkflowDataApiConfig(read_roles=["admin"])
        descriptor = DataModelDescriptor(
            name="Test", model_class=ApiTestModel, namespace="apitest", api=api_cfg
        )
        role_mock = MagicMock()
        role_mock.role.name = "viewer"
        user = MagicMock()
        user.roles = [role_mock]
        assert _user_has_read_access(user, descriptor, MagicMock()) is False

    def test_no_api_config(self):
        descriptor = DataModelDescriptor(
            name="Test", model_class=ApiTestModel, namespace="apitest", api=None
        )
        user = MagicMock()
        user.roles = []
        assert _user_has_read_access(user, descriptor, MagicMock()) is False


# ---------------------------------------------------------------------------
# list_models endpoint logic tests
# ---------------------------------------------------------------------------


class TestListModels:
    def test_only_api_configured_models_listed(self):
        api_model = DataModelDescriptor(
            name="WithApi", model_class=ApiTestModel, namespace="apitest",
            api=WorkflowDataApiConfig(),
        )
        no_api = DataModelDescriptor(
            name="NoApi", model_class=ApiTestModel, namespace="apitest",
            api=None,
        )
        data_model_registry.register(api_model)
        data_model_registry.register(no_api)

        # Simulate the list_models filter logic (presence of api = exposed)
        result = [
            {"name": d.name, "columns": _columns_from_model(d.model_class)}
            for d in data_model_registry.list_models()
            if d.api
        ]
        assert len(result) == 1
        assert result[0]["name"] == "WithApi"


# ---------------------------------------------------------------------------
# VirtualField tests
# ---------------------------------------------------------------------------


class TestVirtualField:
    def test_virtual_field_types(self):
        """All specified types are accepted."""
        for t in ("string", "integer", "number", "boolean", "datetime", "array"):
            vf = VirtualField("test", type=t, value=lambda r: None)
            assert vf.type == t

    def test_virtual_field_is_frozen(self):
        vf = VirtualField("test", type="string", value=lambda r: "x")
        with pytest.raises(AttributeError):
            vf.name = "other"
