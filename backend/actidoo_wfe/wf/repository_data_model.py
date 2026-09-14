# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 ActiDoo GmbH

"""DB access for data-model rows and their file references.

The data-model counterpart of ``repository`` (which is the workflow-instance
repository). Kept apart from it because the file materializer
(``data_model_files``, a before_flush listener) needs these functions, and that
module is imported by the data-model registry — pulling the workflow repository
in there would drag the engine layer into the form layer.
"""

import uuid

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session, joinedload

from actidoo_wfe.wf.models import DataModelFile, WorkflowAttachment

# None of these functions call session.flush(). They are used from a
# before_flush listener (data_model_files), and a flush inside a flush is not
# allowed. They only add or delete ORM objects; the flush that is already
# running writes them. Callers outside a flush have to flush themselves.
#
# Call them under session.no_autoflush. Otherwise the SELECTs inside would
# start a second flush.


def store_data_model_file(
    db: Session,
    *,
    model_name: str,
    row_id: uuid.UUID,
    row_version: int,
    field_name: str,
    attachment_id: uuid.UUID,
    filename: str,
    mimetype: str | None,
    position: int,
) -> DataModelFile:
    """Link one attachment to a field of one row version.

    Calling it twice for the same link is fine: the existing row is returned.
    """
    obj = db.execute(
        select(DataModelFile).where(
            DataModelFile.model_name == model_name,
            DataModelFile.row_id == row_id,
            DataModelFile.row_version == row_version,
            DataModelFile.field_name == field_name,
            DataModelFile.workflow_attachment_id == attachment_id,
        ),
    ).scalar()

    if not obj:
        obj = DataModelFile(
            model_name=model_name,
            row_id=row_id,
            row_version=row_version,
            field_name=field_name,
            workflow_attachment_id=attachment_id,
            filename=filename,
            mimetype=mimetype,
            position=position,
        )
        db.add(obj)

    return obj


def find_data_model_files_for_rows(
    db: Session,
    model_name: str,
    keys: list[tuple[uuid.UUID, int]],
) -> list[DataModelFile]:
    """All file links of the given ``(row_id, row_version)`` pairs, in one query.

    Loads the attachment with each link; the read path needs its hash.
    """
    if not keys:
        return []
    return list(
        db.execute(
            select(DataModelFile)
            .options(joinedload(DataModelFile.attachment))
            .where(
                DataModelFile.model_name == model_name,
                tuple_(DataModelFile.row_id, DataModelFile.row_version).in_(keys),
            )
            .order_by(DataModelFile.position),
        ).scalars(),
    )


def find_data_model_file_by_hash(
    db: Session,
    model_name: str,
    row_id: uuid.UUID,
    row_version: int,
    file_hash: str,
) -> DataModelFile | None:
    """The file link of one row version whose attachment has this hash, or None.

    This is the download check: a file may be downloaded for a row version only
    if that version links to it. Loads the attachment, the download needs its bytes.
    """
    return db.execute(
        select(DataModelFile)
        .options(joinedload(DataModelFile.attachment))
        .join(WorkflowAttachment, WorkflowAttachment.id == DataModelFile.workflow_attachment_id)
        .where(
            DataModelFile.model_name == model_name,
            DataModelFile.row_id == row_id,
            DataModelFile.row_version == row_version,
            WorkflowAttachment.hash == file_hash,
        ),
    ).scalars().first()


def delete_data_model_files_for_row(
    db: Session,
    model_name: str,
    row_id: uuid.UUID,
    row_version: int,
    field_name: str | None = None,
):
    """Remove the file links of one row version, or only those of one field.

    Deletes through the ORM (select, then ``session.delete``) instead of a bulk
    DELETE, so the running flush picks the deletions up.
    """
    stmt = select(DataModelFile).where(
        DataModelFile.model_name == model_name,
        DataModelFile.row_id == row_id,
        DataModelFile.row_version == row_version,
    )
    if field_name is not None:
        stmt = stmt.where(DataModelFile.field_name == field_name)
    for obj in db.execute(stmt).scalars():
        db.delete(obj)


def copy_data_model_files_forward(
    db: Session,
    model_name: str,
    row_id: uuid.UUID,
    from_version: int,
    to_version: int,
    field_name: str,
):
    """Give a new row version the same file links one field had in an older version."""
    sources = db.execute(
        select(DataModelFile).where(
            DataModelFile.model_name == model_name,
            DataModelFile.row_id == row_id,
            DataModelFile.row_version == from_version,
            DataModelFile.field_name == field_name,
        ),
    ).scalars()
    for src in sources:
        store_data_model_file(
            db,
            model_name=model_name,
            row_id=row_id,
            row_version=to_version,
            field_name=field_name,
            attachment_id=src.workflow_attachment_id,
            filename=src.filename,
            mimetype=src.mimetype,
            position=src.position,
        )
