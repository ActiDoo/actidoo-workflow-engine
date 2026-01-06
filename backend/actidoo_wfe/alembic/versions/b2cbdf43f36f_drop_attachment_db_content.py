# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""drop attachment db content

Revision ID: b2cbdf43f36f
Revises: 0f3c5b7fa4d9
Create Date: 2025-12-15

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql
from sqlalchemy_file import File
from sqlalchemy_file.storage import StorageManager

from actidoo_wfe.helpers.datauri import sanitize_metadata_value
from actidoo_wfe.settings import settings
from actidoo_wfe.storage import setup_storage

# revision identifiers, used by Alembic.
revision = "b2cbdf43f36f"
down_revision = "0f3c5b7fa4d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    setup_storage(settings)

    conn = op.get_bind()
    cols = {c["name"] for c in sa.inspect(conn).get_columns("workflow_attachments")}
    if "data" not in cols:
        return

    batch_size = 100

    while True:
        rows = conn.execute(
            sa.text(
                f"""
                SELECT id, data, first_filename, mimetype
                FROM workflow_attachments
                WHERE data IS NOT NULL AND file IS NULL
                LIMIT {batch_size}
                """
            )
        ).fetchall()

        if not rows:
            break

        for attachment_id, data, first_filename, mimetype in rows:
            if data is None:
                continue
            upload = StorageManager.get_default()
            stored = File(
                content=data,
                filename=sanitize_metadata_value(first_filename or "unnamed"),
                content_type=mimetype or "application/octet-stream",
            )
            stored.save_to_storage(upload)
            conn.execute(
                sa.text("UPDATE workflow_attachments SET file = :file WHERE id = :id"),
                {"file": stored.encode(), "id": attachment_id},
            )

    remaining = conn.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM workflow_attachments
            WHERE data IS NOT NULL AND file IS NULL
            """
        )
    ).scalar()
    if remaining:
        raise RuntimeError(
            f"Unable to migrate {remaining} attachment(s) from workflow_attachments.data to workflow_attachments.file"
        )

    op.drop_column("workflow_attachments", "data")


def downgrade() -> None:
    op.add_column(
        "workflow_attachments",
        sa.Column("data", mysql.LONGBLOB(), nullable=True),
    )
