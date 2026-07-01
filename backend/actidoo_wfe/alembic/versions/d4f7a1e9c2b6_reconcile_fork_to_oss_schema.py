# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""reconcile existing databases

Revision ID: d4f7a1e9c2b6
Revises: c4e1a7b9d6f2
Create Date: 2026-06-30 13:00:00.000000

"""

import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy_file import File
from sqlalchemy_file.storage import StorageManager
from sqlalchemy_file.types import FileField

import actidoo_wfe.database
from actidoo_wfe.helpers.datauri import sanitize_metadata_value
from actidoo_wfe.settings import settings
from actidoo_wfe.storage import setup_storage

log = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = "d4f7a1e9c2b6"
down_revision = "c4e1a7b9d6f2"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    # Fresh inspector per call: a cached Inspector goes stale after DDL ops below.
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    # --- workflow_user_claims
    if not insp.has_table("workflow_user_claims"):
        op.create_table(
            "workflow_user_claims",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("claim_key", sa.String(length=255), nullable=False),
            sa.Column("claim_value", actidoo_wfe.database.JSONBlob(), nullable=True),
            sa.Column("source_name", sa.String(length=255), nullable=True),
            sa.Column("fetched_at", actidoo_wfe.database.UTCDateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["user_id"], ["workflow_users.id"],
                name=op.f("fk_workflow_user_claims_user_id_workflow_users"), ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_user_claims")),
            sa.UniqueConstraint("user_id", "claim_key", name=op.f("uq_workflow_user_claims_user_id_claim_key")),
        )
    else:
        claim_cols = _columns("workflow_user_claims")
        if "source_name" not in claim_cols:
            op.add_column("workflow_user_claims", sa.Column("source_name", sa.String(length=255), nullable=True))
        if "fetched_at" not in claim_cols:
            op.add_column("workflow_user_claims", sa.Column("fetched_at", actidoo_wfe.database.UTCDateTime(), nullable=True))

    claim_indexes = _indexes("workflow_user_claims")
    if "ix_workflow_user_claims_user_id" not in claim_indexes:
        op.create_index(op.f("ix_workflow_user_claims_user_id"), "workflow_user_claims", ["user_id"], unique=False)
    if "ix_workflow_user_claims_claim_key" not in claim_indexes:
        op.create_index(op.f("ix_workflow_user_claims_claim_key"), "workflow_user_claims", ["claim_key"], unique=False)

    # --- ts_queue / ts_results
    for table in ("ts_queue", "ts_results"):
        cols = _columns(table)
        if "key_concurrent" not in cols:
            op.add_column(table, sa.Column("key_concurrent", sa.String(length=255), nullable=True))
        if "key_dedup" not in cols:
            op.add_column(table, sa.Column("key_dedup", sa.String(length=255), nullable=True))
        indexes = _indexes(table)
        if f"ix_{table}_key_concurrent" not in indexes:
            op.create_index(f"ix_{table}_key_concurrent", table, ["key_concurrent"])
        if f"ix_{table}_key_dedup" not in indexes:
            op.create_index(f"ix_{table}_key_dedup", table, ["key_dedup"])

    # --- workflow_attachments
    if "data" in _columns("workflow_attachments"):
        setup_storage(settings)
        conn = op.get_bind()
        attachments = sa.table(
            "workflow_attachments",
            sa.column("id"),
            sa.column("data"),
            sa.column("file", FileField()),
            sa.column("first_filename"),
            sa.column("mimetype"),
        )
        pending = sa.select(
            attachments.c.id, attachments.c.data,
            attachments.c.first_filename, attachments.c.mimetype,
        ).where(attachments.c.data.isnot(None), attachments.c.file.is_(None))

        while True:
            rows = conn.execute(pending.limit(100)).fetchall()
            if not rows:
                break
            for attachment_id, data, first_filename, mimetype in rows:
                log.warning(
                    "workflow_attachments backfill: migrating id=%s filename=%r mimetype=%r size=%s",
                    attachment_id, first_filename, mimetype, len(data),
                )
                stored = File(
                    content=data,
                    filename=sanitize_metadata_value(first_filename or "unnamed"),
                    content_type=mimetype or "application/octet-stream",
                )
                stored.save_to_storage(StorageManager.get_default())
                conn.execute(
                    attachments.update().where(attachments.c.id == attachment_id).values(file=stored)
                )

        remaining = conn.execute(
            sa.select(sa.func.count()).select_from(pending.subquery())
        ).scalar()
        if remaining:
            raise RuntimeError(
                f"Unable to migrate {remaining} attachment(s) from workflow_attachments.data to workflow_attachments.file"
            )

        op.drop_column("workflow_attachments", "data")


def downgrade() -> None:
    pass
