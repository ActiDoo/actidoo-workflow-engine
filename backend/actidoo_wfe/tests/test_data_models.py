# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Tests for Data Model Persistence."""

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy import String, inspect as sa_inspect
from sqlalchemy.orm import Mapped, mapped_column

from actidoo_wfe.data_models import (
    DataModelAccessDeniedError,
    DataModelDescriptor,
    DataModelNotFoundError,
    WorkflowDataApiConfig,
    WorkflowManagedMixin,
    data_model_registry,
    extension_model_base,
    register_data_model,
)
from actidoo_wfe.database import Base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    data_model_registry.clear()
    yield
    data_model_registry.clear()


# ---------------------------------------------------------------------------
# extension_model_base tests
# ---------------------------------------------------------------------------


class TestExtensionModelBase:
    def test_tablename_generation(self):
        TestModel = extension_model_base("testns")

        class Fwa(TestModel):
            _ext_table = "fwa"
            __abstract__ = False
            id: Mapped[str] = mapped_column(String(50), primary_key=True)

        assert Fwa.__tablename__ == "ext_testns_fwa"

    def test_missing_ext_table_raises(self):
        TestModel = extension_model_base("phoenix")

        with pytest.raises(ValueError, match="must define '_ext_table'"):
            class Bad(TestModel):
                __abstract__ = False
                id: Mapped[str] = mapped_column(String(50), primary_key=True)

            # Access __tablename__ to trigger the error
            _ = Bad.__tablename__

    def test_namespace_attribute(self):
        TestModel = extension_model_base("myns")
        assert TestModel._ext_namespace == "myns"


# ---------------------------------------------------------------------------
# WorkflowManagedMixin tests
# ---------------------------------------------------------------------------


class TestWorkflowManagedMixin:
    def test_mixin_columns_present(self):
        TestModel = extension_model_base("mixin_test")

        class MixinModel(TestModel, WorkflowManagedMixin):
            _ext_table = "mt"
            __abstract__ = False

        mapper = sa_inspect(MixinModel)
        col_names = {col.key for col in mapper.columns}
        assert "workflow_instance_id" in col_names
        assert "parent_workflow_instance_id" in col_names
        assert "child_workflow_instance_id" in col_names
        assert "action" in col_names
        assert "created_at" in col_names

    def test_workflow_instance_id_is_primary_key(self):
        TestModel = extension_model_base("mixin_pk")

        class PkModel(TestModel, WorkflowManagedMixin):
            _ext_table = "mpk"
            __abstract__ = False

        mapper = sa_inspect(PkModel)
        pk_names = [col.key for col in mapper.primary_key]
        assert pk_names == ["workflow_instance_id"]

    def test_mixin_with_business_columns(self):
        TestModel = extension_model_base("mixin_biz")

        class BizModel(TestModel, WorkflowManagedMixin):
            _ext_table = "mbiz"
            __abstract__ = False
            status: Mapped[str | None] = mapped_column(String(50), nullable=True)

        mapper = sa_inspect(BizModel)
        col_names = {col.key for col in mapper.columns}
        assert "status" in col_names
        assert "workflow_instance_id" in col_names


# ---------------------------------------------------------------------------
# DataModelRegistry tests
# ---------------------------------------------------------------------------


class TestDataModelRegistry:
    def test_register_model(self):
        TestModel = extension_model_base("test")

        class Item(TestModel):
            _ext_table = "item"
            __abstract__ = False
            id: Mapped[str] = mapped_column(String(50), primary_key=True)

        descriptor = DataModelDescriptor(name="Item", model_class=Item, namespace="test")
        data_model_registry.register(descriptor)
        assert "Item" in data_model_registry.list_names()

    def test_register_duplicate_same_class(self):
        TestModel = extension_model_base("test2")

        class Item2(TestModel):
            _ext_table = "item2"
            __abstract__ = False
            id: Mapped[str] = mapped_column(String(50), primary_key=True)

        d = DataModelDescriptor(name="Item2", model_class=Item2, namespace="test2")
        data_model_registry.register(d)
        data_model_registry.register(d)  # dedup, no error
        assert data_model_registry.list_names().count("Item2") == 1

    def test_register_duplicate_different_class(self):
        TestModel = extension_model_base("test3")

        class ItemA(TestModel):
            _ext_table = "itema"
            __abstract__ = False
            id: Mapped[str] = mapped_column(String(50), primary_key=True)

        class ItemB(TestModel):
            _ext_table = "itemb"
            __abstract__ = False
            id: Mapped[str] = mapped_column(String(50), primary_key=True)

        d1 = DataModelDescriptor(name="ConflictItem", model_class=ItemA, namespace="test3")
        d2 = DataModelDescriptor(name="ConflictItem", model_class=ItemB, namespace="test3")
        data_model_registry.register(d1)
        with pytest.raises(ValueError, match="already registered"):
            data_model_registry.register(d2)

    def test_get_not_found(self):
        with pytest.raises(DataModelNotFoundError):
            data_model_registry.get("nonexistent")

    def test_clear_registry(self):
        d = DataModelDescriptor(name="X", model_class=Base, namespace="x")
        data_model_registry.register(d)
        data_model_registry.clear()
        assert data_model_registry.list_names() == []


# ---------------------------------------------------------------------------
# @register_data_model decorator tests
# ---------------------------------------------------------------------------


class TestRegisterDataModelDecorator:
    def test_decorator_registers_immediately(self):
        TestModel = extension_model_base("dec_test")

        @register_data_model(name="DecTestModel")
        class DecTestModel(TestModel):
            _ext_table = "dte"
            __abstract__ = False
            id: Mapped[str] = mapped_column(String(50), primary_key=True)

        assert "DecTestModel" in data_model_registry.list_names()

    def test_decorator_with_api_config_requires_mixin(self):
        """api config without WorkflowManagedMixin raises TypeError."""
        TestModel = extension_model_base("dec_api_test")
        api_cfg = WorkflowDataApiConfig(read_roles=["viewer"])

        with pytest.raises(TypeError, match="WorkflowManagedMixin"):
            @register_data_model(name="BadApiModel", api=api_cfg)
            class BadApiModel(TestModel):
                _ext_table = "bam"
                __abstract__ = False
                id: Mapped[str] = mapped_column(String(50), primary_key=True)

    def test_decorator_with_api_config_and_mixin(self):
        """api config with WorkflowManagedMixin succeeds."""
        TestModel = extension_model_base("dec_mixin_test")
        api_cfg = WorkflowDataApiConfig(read_roles=["viewer"])

        @register_data_model(name="GoodApiModel", api=api_cfg)
        class GoodApiModel(TestModel, WorkflowManagedMixin):
            _ext_table = "gam"
            __abstract__ = False

        desc = data_model_registry.get("GoodApiModel")
        assert desc.api is not None
        assert desc.api.read_roles == ["viewer"]

    def test_decorator_without_api_no_mixin_required(self):
        """No api config — no mixin required."""
        TestModel = extension_model_base("dec_no_api")

        @register_data_model(name="PlainModel")
        class PlainModel(TestModel):
            _ext_table = "pm"
            __abstract__ = False
            id: Mapped[str] = mapped_column(String(50), primary_key=True)

        desc = data_model_registry.get("PlainModel")
        assert desc.api is None


# ---------------------------------------------------------------------------
# Dependency Enforcement tests
# ---------------------------------------------------------------------------


class TestDependencyEnforcement:
    def test_get_model_allowed(self):
        TestModel = extension_model_base("enf_test")

        @register_data_model(name="AllowedModel")
        class AllowedModel(TestModel):
            _ext_table = "ae2"
            __abstract__ = False
            id: Mapped[str] = mapped_column(String(50), primary_key=True)

        from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper
        sth = object.__new__(ServiceTaskHelper)
        sth._allowed_data_models = {"AllowedModel"}
        sth.db = MagicMock()

        model_class = sth.get_model("AllowedModel")
        assert model_class is AllowedModel

    def test_get_model_denied(self):
        from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper
        sth = object.__new__(ServiceTaskHelper)
        sth._allowed_data_models = set()
        sth.db = MagicMock()

        with pytest.raises(DataModelAccessDeniedError, match="Access denied"):
            sth.get_model("ForbiddenModel")

    def test_enforcement_oth(self):
        from actidoo_wfe.wf.option_task_helper import OptionTaskHelper
        oth = object.__new__(OptionTaskHelper)
        oth._allowed_data_models = set()
        oth.db = MagicMock()

        with pytest.raises(DataModelAccessDeniedError):
            oth.get_model("SomeModel")

    def test_enforcement_vth(self):
        from actidoo_wfe.wf.validation_task_helper import ValidationTaskHelper
        vth = object.__new__(ValidationTaskHelper)
        vth._allowed_data_models = set()
        vth.db = MagicMock()

        with pytest.raises(DataModelAccessDeniedError):
            vth.get_model("SomeModel")
