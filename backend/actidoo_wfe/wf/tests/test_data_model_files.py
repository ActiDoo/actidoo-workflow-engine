# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Tests for the normalized data-model file storage (data_model_files side table).

Covers the before_flush materializer (create, version copy-forward, clear,
non-versioned replace, delete, rollback), the attachment GC's third reference
source, and the registry helpers.
"""

import uuid

import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column

from actidoo_wfe.database import SessionMaker, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import repository
from actidoo_wfe.wf.config_data_model import READ_ALL_WORKFLOW_USERS, FieldDef, WorkflowDataApiConfig
from actidoo_wfe.wf.data_model_files import record_file_intent
from actidoo_wfe.wf.models import (
    DataModelFile,
    DataModelMixin,
    VersionedMixin,
    WorkflowInstance,
    WorkflowInstanceAttachment,
    WorkflowManagedMixin,
    extension_model_base,
)
from actidoo_wfe.wf.registry_data_model import DataModelDescriptor, data_model_registry

setup_db(settings=settings)

_Base = extension_model_base("dmf")


class VersionedDoc(_Base, VersionedMixin):
    _ext_table = "vdoc"
    __abstract__ = False
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)


class PlainDoc(_Base, DataModelMixin):
    _ext_table = "pdoc"
    __abstract__ = False
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)


class ManagedDoc(_Base, WorkflowManagedMixin):
    """WorkflowManagedMixin model — the only kind the api= gate accepts."""

    _ext_table = "mdoc"
    __abstract__ = False
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)


@pytest.fixture(autouse=True)
def _clean_registry():
    data_model_registry.clear()
    yield
    data_model_registry.clear()


def _create_tables():
    engine = SessionMaker.kw["bind"]
    VersionedDoc.__table__.create(bind=engine, checkfirst=True)
    PlainDoc.__table__.create(bind=engine, checkfirst=True)


def _register(model_class, name, *, versioned):
    data_model_registry.register(
        DataModelDescriptor(
            name=name,
            model_class=model_class,
            namespace="dmf",
            is_versioned=versioned,
            api=WorkflowDataApiConfig(
                read_roles=[READ_ALL_WORKFLOW_USERS],
                fields=[FieldDef("name"), FieldDef("doc", type="file")],
            ),
        ),
    )


def _store_attachment(file_hash, *, filename="f.pdf", mimetype="application/pdf", content=b"X"):
    with SessionMaker() as db, db.begin():
        return repository.store_attachment(db=db, filename=filename, mimetype=mimetype, data=content, hash=file_hash).id


def _ref(att_id, *, hash, filename="f.pdf", mimetype="application/pdf"):
    return {"id": str(att_id), "hash": hash, "filename": filename, "mimetype": mimetype}


def _files(db, model_name, row_id, row_version):
    return list(
        db.execute(
            select(DataModelFile)
            .where(
                DataModelFile.model_name == model_name,
                DataModelFile.row_id == row_id,
                DataModelFile.row_version == row_version,
            )
            .order_by(DataModelFile.position)
        ).scalars()
    )


class TestMaterializer:
    def test_create_writes_side_row_with_version_and_filename(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            _register(VersionedDoc, "Docs", versioned=True)
            att = _store_attachment("h1", filename="ctx.pdf")
            with SessionMaker() as db, db.begin():
                row = VersionedDoc(name="A")
                db.add(row)
                record_file_intent(db, row, "doc", _ref(att, hash="h1", filename="ctx.pdf"))
                db.flush()
                assert row.version == 1
                assert row.id is not None
                record_id = row.id
            with SessionMaker() as db:
                files = _files(db, "Docs", record_id, 1)
                assert len(files) == 1
                assert files[0].workflow_attachment_id == att
                assert files[0].filename == "ctx.pdf"

    def test_update_auto_copies_files_forward(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            _register(VersionedDoc, "Docs", versioned=True)
            att = _store_attachment("h1", filename="ctx.pdf")
            with SessionMaker() as db, db.begin():
                row = VersionedDoc(name="A")
                db.add(row)
                record_file_intent(db, row, "doc", _ref(att, hash="h1"))
                db.flush()
                record_id = row.id
            # New version, no attach_files -> framework auto-copies the file forward.
            with SessionMaker() as db, db.begin():
                row2 = VersionedDoc(id=record_id, name="B")
                db.add(row2)
                db.flush()
                assert row2.version == 2
            with SessionMaker() as db:
                v2 = _files(db, "Docs", record_id, 2)
                assert len(v2) == 1 and v2[0].workflow_attachment_id == att

    def test_clear_files_suppresses_copy_forward(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            _register(VersionedDoc, "Docs", versioned=True)
            att = _store_attachment("h1")
            with SessionMaker() as db, db.begin():
                row = VersionedDoc(name="A")
                db.add(row)
                record_file_intent(db, row, "doc", _ref(att, hash="h1"))
                db.flush()
                record_id = row.id
            with SessionMaker() as db, db.begin():
                row2 = VersionedDoc(id=record_id, name="B")
                db.add(row2)
                record_file_intent(db, row2, "doc", [])  # clear
                db.flush()
            with SessionMaker() as db:
                assert _files(db, "Docs", record_id, 2) == []

    def test_non_versioned_in_place_replace(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            _register(PlainDoc, "Plain", versioned=False)
            a1 = _store_attachment("h1")
            a2 = _store_attachment("h2")
            with SessionMaker() as db, db.begin():
                row = PlainDoc(name="A")
                db.add(row)
                record_file_intent(db, row, "doc", _ref(a1, hash="h1"))
                db.flush()
                record_id = row.id
            with SessionMaker() as db:
                f = _files(db, "Plain", record_id, 0)
                assert len(f) == 1 and f[0].workflow_attachment_id == a1
            # In-place update: replace the file (and touch a column so the row flushes).
            with SessionMaker() as db, db.begin():
                row = db.get(PlainDoc, record_id)
                row.name = "A2"
                record_file_intent(db, row, "doc", _ref(a2, hash="h2"))
                db.flush()
            with SessionMaker() as db:
                f = _files(db, "Plain", record_id, 0)
                assert len(f) == 1 and f[0].workflow_attachment_id == a2

    def test_delete_row_removes_side_rows(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            _register(PlainDoc, "Plain", versioned=False)
            att = _store_attachment("h1")
            with SessionMaker() as db, db.begin():
                row = PlainDoc(name="A")
                db.add(row)
                record_file_intent(db, row, "doc", _ref(att, hash="h1"))
                db.flush()
                record_id = row.id
            with SessionMaker() as db, db.begin():
                db.delete(db.get(PlainDoc, record_id))
            with SessionMaker() as db:
                assert _files(db, "Plain", record_id, 0) == []

    def test_rollback_discards_intents(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            _register(VersionedDoc, "Docs", versioned=True)
            att = _store_attachment("h1")
            record_id = uuid.uuid4()
            try:
                with SessionMaker() as db, db.begin():
                    row = VersionedDoc(id=record_id, name="A")
                    db.add(row)
                    record_file_intent(db, row, "doc", _ref(att, hash="h1"))
                    db.flush()
                    raise RuntimeError("boom")  # roll the transaction back
            except RuntimeError:
                pass
            with SessionMaker() as db:
                assert _files(db, "Docs", record_id, 1) == []

    def test_repeated_flush_does_not_duplicate(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            _register(VersionedDoc, "Docs", versioned=True)
            att = _store_attachment("h1")
            with SessionMaker() as db, db.begin():
                row = VersionedDoc(name="A")
                db.add(row)
                record_file_intent(db, row, "doc", _ref(att, hash="h1"))
                db.flush()
                row.name = "A2"
                db.flush()  # a second flush must not duplicate the side row
                record_id = row.id
            with SessionMaker() as db:
                assert len(_files(db, "Docs", record_id, 1)) == 1

    def test_unregistered_class_gets_no_side_rows(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()  # model exists but is NOT registered
            att = _store_attachment("h1")
            with SessionMaker() as db, db.begin():
                row = VersionedDoc(name="A")
                db.add(row)
                record_file_intent(db, row, "doc", _ref(att, hash="h1"))
                db.flush()
                record_id = row.id
            with SessionMaker() as db:
                assert _files(db, "Docs", record_id, 1) == []


class TestAttachmentGc:
    def test_data_model_file_keeps_attachment_alive(self, db_engine_ctx):
        with db_engine_ctx():
            _create_tables()
            _register(VersionedDoc, "Docs", versioned=True)
            att = _store_attachment("h1")
            with SessionMaker() as db, db.begin():
                row = VersionedDoc(name="A")
                db.add(row)
                record_file_intent(db, row, "doc", _ref(att, hash="h1"))
                db.flush()
                record_id, version = row.id, row.version
            # No task/instance links exist; only the data-model file references it.
            with SessionMaker() as db, db.begin():
                repository.delete_dangling_attachment(db=db, attachment_id=att)
            with SessionMaker() as db:
                assert repository.find_attachment_by_id(db=db, attachment_id=att) is not None
            # Drop the file row -> attachment becomes collectable.
            with SessionMaker() as db, db.begin():
                repository.delete_data_model_files_for_row(db, "Docs", record_id, version)
            with SessionMaker() as db, db.begin():
                repository.delete_dangling_attachment(db=db, attachment_id=att)
            with SessionMaker() as db:
                assert repository.find_attachment_by_id(db=db, attachment_id=att) is None

    def test_dangling_delete_tolerates_missing_attachment(self, db_engine_ctx):
        with db_engine_ctx():
            with SessionMaker() as db, db.begin():
                repository.delete_dangling_attachment(db=db, attachment_id=uuid.uuid4())  # no error

    def _instance_with_attachment(self, file_hash):
        """Seed a WorkflowInstance with one instance-level attachment link; return ids."""
        instance_id = uuid.uuid4()
        with SessionMaker() as db, db.begin():
            db.add(WorkflowInstance(id=instance_id, name="del-test", lane_mapping={}, data={}))
            att = repository.store_attachment(db=db, filename="f.pdf", mimetype="application/pdf", data=b"X", hash=file_hash)
            db.add(WorkflowInstanceAttachment(workflow_instance_id=instance_id, workflow_attachment_id=att.id, filename="f.pdf"))
            att_id = att.id
        return instance_id, att_id

    def test_delete_workflow_instance_collects_orphan_attachment(self, db_engine_ctx):
        """delete_workflow_instance now GCs attachments left orphaned by the cascade."""
        from types import SimpleNamespace

        with db_engine_ctx():
            instance_id, att_id = self._instance_with_attachment("h-orphan")
            workflow = SimpleNamespace(task_tree=SimpleNamespace(id=instance_id))
            with SessionMaker() as db, db.begin():
                repository.delete_workflow_instance(db=db, workflow=workflow)
            with SessionMaker() as db:
                assert repository.find_attachment_by_id(db=db, attachment_id=att_id) is None

    def test_delete_workflow_instance_keeps_data_model_referenced_attachment(self, db_engine_ctx):
        from types import SimpleNamespace

        with db_engine_ctx():
            _create_tables()
            _register(VersionedDoc, "Docs", versioned=True)
            instance_id, att_id = self._instance_with_attachment("h-shared")
            # A data-model row also references the same attachment (by hash dedup).
            with SessionMaker() as db, db.begin():
                row = VersionedDoc(name="A")
                db.add(row)
                record_file_intent(db, row, "doc", _ref(att_id, hash="h-shared"))
                db.flush()
            workflow = SimpleNamespace(task_tree=SimpleNamespace(id=instance_id))
            with SessionMaker() as db, db.begin():
                repository.delete_workflow_instance(db=db, workflow=workflow)
            with SessionMaker() as db:
                assert repository.find_attachment_by_id(db=db, attachment_id=att_id) is not None


class TestRegistryHelpers:
    def test_descriptors_and_name_for_class(self, db_engine_ctx):
        with db_engine_ctx():
            _register(VersionedDoc, "Docs", versioned=True)
            assert [d.name for d in data_model_registry.descriptors_for_class(VersionedDoc)] == ["Docs"]
            assert data_model_registry.name_for_class(VersionedDoc) == "Docs"
            assert data_model_registry.descriptors_for_class(PlainDoc) == []
            assert data_model_registry.name_for_class(PlainDoc) is None

    def test_computed_file_field_is_rejected(self):
        from actidoo_wfe.wf.registry_data_model import register_data_model

        # WorkflowManagedMixin so the api gate passes and the computed-file check is reached.
        with pytest.raises(ValueError, match="computed file field"):
            register_data_model(
                name="BadComputedFile",
                api=WorkflowDataApiConfig(
                    read_roles=[READ_ALL_WORKFLOW_USERS],
                    fields=[FieldDef("doc", type="file", compute=lambda row: [])],
                ),
            )(ManagedDoc)
