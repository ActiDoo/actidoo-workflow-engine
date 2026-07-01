# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Materialization of data-model ``file`` field references into the side table.

Workflow code writes a data-model row with plain ORM (``db.add(Model(...))``) and
declares its uploads via ``ServiceTaskHelper.attach_files``. The row's id/version
are only assigned during flush (by ``models._assign_versions``), so the file rows
cannot be written at ``attach_files`` time. Instead the intent is recorded in the
session's scratch space and materialized by the ``before_flush`` listener below —
registered after ``_assign_versions`` (this module is imported at the bottom of
``registry_data_model``, which imports ``models`` first), so it sees the final
``(id, version)``.

Repository functions do the DB work (flush-free, see repository.py); this module
is only the trigger plus the author-facing intent recording.
"""

import logging
import uuid

from sqlalchemy import event
from sqlalchemy.orm import Session

from actidoo_wfe.wf.models import DataModelMixin, VersionedMixin

log = logging.getLogger(__name__)

# Per-Session scratch (SQLAlchemy's official place for caller state) holding the
# pending file intents, keyed by the row's Python identity because its primary
# key is not assigned until flush.
_INTENT_KEY = "_dm_file_intents"


def record_file_intent(db: Session, row, field_name: str, files) -> None:
    """Record that *row*'s ``file`` field *field_name* should reference *files*.

    *files* is one upload ref or a list of them, as they appear in ``task_data``
    ({id, hash, filename, mimetype}). An empty list is a "clear this field"
    sentinel that suppresses version copy-forward. Materialized at flush.
    """
    refs = files if isinstance(files, list) else [files]
    intents = db.info.setdefault(_INTENT_KEY, {})
    # Keyed by Python identity (the PK is not yet assigned); the row object is kept
    # so the materializer can act on a persistent row even if no column changed.
    intents.setdefault(id(row), []).append((row, field_name, [_as_ref(r) for r in refs]))


def _as_ref(ref) -> dict:
    """Normalize an upload ref (dict or UploadedAttachmentRepresentation) to a dict."""
    if isinstance(ref, dict):
        return ref
    return {
        "id": getattr(ref, "id", None),
        "hash": getattr(ref, "hash", None),
        "filename": getattr(ref, "filename", None),
        "mimetype": getattr(ref, "mimetype", None),
    }


def _attachment_id(ref: dict) -> uuid.UUID | None:
    raw = ref.get("id")
    if raw is None:
        return None
    if isinstance(raw, uuid.UUID):
        return raw
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def _row_version(obj) -> int | None:
    if isinstance(obj, VersionedMixin):
        return obj.version  # assigned by _assign_versions; None only if ordering broke
    return 0


@event.listens_for(Session, "before_flush")
def _materialize_data_model_files(session: Session, flush_context, instances) -> None:
    """Turn recorded file intents (and version copy-forward) into ``data_model_files`` rows."""

    def in_scope(obj) -> bool:
        # On a partial flush (session.flush(objects=...)) only act on those objects,
        # so a file row never flushes ahead of the row it belongs to.
        return isinstance(obj, DataModelMixin) and (instances is None or obj in instances)

    new_rows = [o for o in session.new if in_scope(o)]
    deleted_rows = [o for o in session.deleted if in_scope(o)]
    intents: dict = session.info.get(_INTENT_KEY) or {}
    if not (new_rows or deleted_rows or intents):
        return

    # Late imports break the import cycle (this module is imported by the registry).
    from actidoo_wfe.wf import repository
    from actidoo_wfe.wf.registry_data_model import data_model_registry

    def file_fields(descriptor):
        fields = descriptor.api.fields if descriptor.api else None
        return [f for f in (fields or []) if f.type == "file"]

    # Per-row fields the author set explicitly (so auto copy-forward skips them).
    specified_by_row: dict[int, set[str]] = {}

    with session.no_autoflush:
        # Explicit attach_files/clear_files. Driven by the intents (not session.new/
        # dirty), so a file-only change on a persistent row materializes too.
        for entries in intents.values():
            row = entries[0][0]
            if not in_scope(row):
                continue
            descriptors = data_model_registry.descriptors_for_class(type(row))
            if not descriptors:
                continue
            # Non-versioned new rows reach here with id unset (their column default
            # has not fired yet); front-load it so the file rows get the real PK.
            if row.id is None:
                row.id = uuid.uuid4()
            version = _row_version(row)
            if version is None:
                log.warning(
                    "data-model row %s flushed without an assigned version; file refs deferred",
                    type(row).__name__,
                )
                continue
            specified_by_row[id(row)] = {field_name for (_r, field_name, _refs) in entries}
            for descriptor in descriptors:
                for _r, field_name, refs in entries:
                    # Replace this field's files for this version.
                    repository.delete_data_model_files_for_row(
                        session,
                        model_name=descriptor.name,
                        row_id=row.id,
                        row_version=version,
                        field_name=field_name,
                    )
                    for position, ref in enumerate(refs):
                        attachment_id = _attachment_id(ref)
                        if attachment_id is None:
                            continue
                        repository.store_data_model_file(
                            session,
                            model_name=descriptor.name,
                            row_id=row.id,
                            row_version=version,
                            field_name=field_name,
                            attachment_id=attachment_id,
                            filename=ref.get("filename") or "",
                            mimetype=ref.get("mimetype"),
                            position=position,
                        )

        # Auto copy-forward: for a new version, carry over file fields the author
        # did not touch (mirrors the old receipt=current.receipt).
        for row in new_rows:
            if not isinstance(row, VersionedMixin):
                continue
            version = _row_version(row)
            if version is None or version <= 1:
                continue
            specified = specified_by_row.get(id(row), set())
            for descriptor in data_model_registry.descriptors_for_class(type(row)):
                for field in file_fields(descriptor):
                    if field.name in specified:
                        continue
                    repository.copy_data_model_files_forward(
                        session,
                        model_name=descriptor.name,
                        row_id=row.id,
                        from_version=version - 1,
                        to_version=version,
                        field_name=field.name,
                    )

        # Hard-deleted rows: drop their file rows so they do not pin attachments forever.
        for row in deleted_rows:
            version = _row_version(row) or 0
            for descriptor in data_model_registry.descriptors_for_class(type(row)):
                repository.delete_data_model_files_for_row(
                    session,
                    model_name=descriptor.name,
                    row_id=row.id,
                    row_version=version,
                )

    session.info.pop(_INTENT_KEY, None)


@event.listens_for(Session, "after_rollback")
def _clear_file_intents(session: Session) -> None:
    """Drop any unmaterialized intents when the transaction rolls back."""
    session.info.pop(_INTENT_KEY, None)
