# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import datetime
import uuid
from typing import Any, List, Literal

import sqlalchemy.dialects.mysql as myty
import sqlalchemy.types as ty
from sqlalchemy import CheckConstraint, Computed, ForeignKey, Index, UniqueConstraint, and_, event, func, null, or_, select, true
from sqlalchemy.orm import Mapped, Session, column_property, declared_attr, deferred, mapped_column, relationship, validates
from sqlalchemy_file import File, FileField

from actidoo_wfe.database import Base, FlexibleUuid, JSONBlob, UTCDateTime, ZlibJSONBlob
from actidoo_wfe.helpers.time import dt_now_naive
from actidoo_wfe.i18n import get_supported_locales
from actidoo_wfe.settings import settings


class WorkflowUser(Base):
    __tablename__ = "workflow_users"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    idp_id: Mapped[str] = mapped_column(ty.String(255), index=True, nullable=True)

    idp_id_unique = Index(
        "uix_idp_id",
        idp_id,
        unique=True,
    )

    username: Mapped[str] = mapped_column(ty.String(100), index=True, nullable=False, unique=True)

    is_service_user: Mapped[bool] = mapped_column(ty.Boolean, nullable=False, index=True, default=False, server_default="0")

    email: Mapped[str | None] = mapped_column(ty.String(100), nullable=True, unique=True)
    email_notnull = CheckConstraint(
        or_(email != null(), is_service_user == true()),
        name="chk_email",
    )

    first_name: Mapped[str | None] = mapped_column(ty.String(255), nullable=True, index=True)
    last_name: Mapped[str | None] = mapped_column(ty.String(255), nullable=True, index=True)
    full_name: Mapped[str | None] = mapped_column(ty.String(255), Computed("CONCAT_WS(' ', NULLIF(TRIM(first_name), ''), NULLIF(TRIM(last_name), ''))"), nullable=True, index=True)

    # The column must be a nullable value, because a user is also created when a task is assigned to a user, which had never logged in before.
    # At this moment we can not know the user's preferred locale nor do we want to set the default locale as his desired locale.
    # The desired locale is first stored when the user logs in for the first time.
    # For existing users (before localization was implemented) the value will also be null (unitl the log in again).
    _locale: Mapped[str | None] = mapped_column(
        "locale",
        ty.String(10),
        nullable=True,
        comment="IETF BCP 47 locale string, e.g. 'de-DE', 'en', 'fr-CH'",
    )
    # "_locale" is the actual column and "locale" is a property with fallback to the default value.

    @property
    def locale(self) -> str:
        return self._locale or settings.default_locale

    @locale.setter
    def locale(self, value: str | None) -> None:
        self._locale = value

    @validates("_locale")
    def validate_locale(self, key, value):
        if value is None:
            return None

        keys = {loc["key"] for loc in get_supported_locales()}

        if value not in keys:
            raise ValueError(f"Unsupported locale: {value}")

        return value

    assigned_tasks: Mapped[List["WorkflowInstanceTask"]] = relationship(
        back_populates="assigned_user",
        foreign_keys="WorkflowInstanceTask.assigned_user_id",
    )
    delegated_tasks: Mapped[List["WorkflowInstanceTask"]] = relationship(
        back_populates="assigned_delegate_user",
        foreign_keys="WorkflowInstanceTask.assigned_delegate_user_id",
    )
    roles: Mapped[List["WorkflowUserRole"]] = relationship(back_populates="user")
    delegations_as_principal: Mapped[List["WorkflowUserDelegate"]] = relationship(
        back_populates="principal",
        foreign_keys="WorkflowUserDelegate.principal_user_id",
    )
    delegations_as_delegate: Mapped[List["WorkflowUserDelegate"]] = relationship(
        back_populates="delegate",
        foreign_keys="WorkflowUserDelegate.delegate_user_id",
    )
    claims: Mapped[List["WorkflowUserClaim"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    pinned_workflows: Mapped[List["WorkflowUserPinnedWorkflow"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
        index=True,
    )

    created_workflows: Mapped["WorkflowInstance"] = relationship(
        back_populates="created_by",
    )


class WorkflowUserClaim(Base):
    __tablename__ = "workflow_user_claims"
    __table_args__ = (UniqueConstraint("user_id", "claim_key"),)

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_users.id", ondelete="CASCADE"), index=True, nullable=False)
    claim_key: Mapped[str] = mapped_column(ty.String(255), nullable=False, index=True)
    claim_value: Mapped[Any | None] = mapped_column(JSONBlob(), nullable=True)
    source_name: Mapped[str | None] = mapped_column(ty.String(255), nullable=True)
    fetched_at: Mapped[datetime.datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[WorkflowUser] = relationship(back_populates="claims")


class WorkflowUserPinnedWorkflow(Base):
    __tablename__ = "workflow_user_pinned_workflows"
    __table_args__ = (UniqueConstraint("user_id", "workflow_name"),)

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_users.id", ondelete="CASCADE"), index=True, nullable=False)
    workflow_name: Mapped[str] = mapped_column(ty.String(255), nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime(), default=dt_now_naive, nullable=False)

    user: Mapped[WorkflowUser] = relationship(back_populates="pinned_workflows")


class WorkflowRole(Base):
    __tablename__ = "workflow_roles"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(ty.String(255), index=True, unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
        index=True,
    )
    users: Mapped[List["WorkflowUserRole"]] = relationship(back_populates="role")


class WorkflowUserRole(Base):
    __tablename__ = "workflow_users_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(WorkflowUser.id), index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(WorkflowRole.id), index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
        index=True,
    )

    user: Mapped[WorkflowUser] = relationship(back_populates="roles")
    role: Mapped[WorkflowRole] = relationship(back_populates="users")


class WorkflowUserDelegate(Base):
    __tablename__ = "workflow_user_delegates"
    __table_args__ = (UniqueConstraint("principal_user_id", "delegate_user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    principal_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(WorkflowUser.id, ondelete="CASCADE"),
        index=True,
    )
    delegate_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(WorkflowUser.id, ondelete="CASCADE"),
        index=True,
    )
    valid_until: Mapped[datetime.datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
    )

    principal: Mapped[WorkflowUser] = relationship(
        back_populates="delegations_as_principal",
        foreign_keys=[principal_user_id],
    )
    delegate: Mapped[WorkflowUser] = relationship(
        back_populates="delegations_as_delegate",
        foreign_keys=[delegate_user_id],
    )


class WorkflowInstanceTask(Base):
    __tablename__ = "workflow_instance_tasks"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True)
    # We want to store the order of SpiffWorkflow to show the tasks in a natural order
    sort: Mapped[int] = mapped_column(ty.Integer, nullable=False, server_default="0", index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=None,
        nullable=True,
    )

    workflow_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_instances.id", ondelete="CASCADE"),
        index=True,
    )
    workflow_instance: Mapped["WorkflowInstance"] = relationship(back_populates="tasks")

    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_users.id"),
        nullable=True,
    )
    assigned_user: Mapped[WorkflowUser | None] = relationship(
        back_populates="assigned_tasks",
        foreign_keys="WorkflowInstanceTask.assigned_user_id",
    )
    assigned_delegate_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_users.id"),
        nullable=True,
        index=True,
    )
    assigned_delegate_user: Mapped[WorkflowUser | None] = relationship(
        back_populates="delegated_tasks",
        foreign_keys="WorkflowInstanceTask.assigned_delegate_user_id",
    )
    can_be_unassigned: Mapped[bool] = mapped_column(
        ty.Boolean,
        nullable=False,
        index=True,
        default=False,
        server_default="0",
    )

    state: Mapped[int] = mapped_column(ty.Integer, nullable=False, index=True)
    state_ready: Mapped[bool] = mapped_column(
        ty.Boolean,
        nullable=False,
        index=True,
        default=False,
    )
    state_completed: Mapped[bool] = mapped_column(
        ty.Boolean,
        nullable=False,
        index=True,
        default=False,
    )
    state_error: Mapped[bool] = mapped_column(
        ty.Boolean,
        nullable=False,
        index=True,
        default=False,
    )
    state_cancelled: Mapped[bool] = mapped_column(
        ty.Boolean,
        nullable=False,
        index=True,
        default=False,
    )
    name: Mapped[str] = mapped_column(ty.String(255), nullable=False)
    title: Mapped[str] = mapped_column(ty.String(255), nullable=False, server_default="")
    manual: Mapped[bool] = mapped_column(
        ty.Boolean,
        nullable=False,
        default=False,
        index=True,
        quote=True,
        name="manual",
    )
    bpmn_id: Mapped[str | None] = mapped_column(ty.String(255), nullable=True)
    lane: Mapped[str | None] = mapped_column(
        ty.String(255),
        nullable=True,
        index=True,
        default=None,
    )
    lane_initiator: Mapped[bool] = mapped_column(
        ty.Boolean,
        nullable=False,
        index=True,
        default=False,
    )
    lane_roles: Mapped[List["WorkflowInstanceTaskRole"]] = relationship(
        back_populates="workflow_instance_task",
    )
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_users.id"),
        nullable=True,
    )
    triggered_by: Mapped[WorkflowUser | None] = relationship(
        foreign_keys="WorkflowInstanceTask.triggered_by_id",
    )
    data: Mapped[dict] = mapped_column(ZlibJSONBlob(), nullable=True)
    jsonschema: Mapped[dict] = mapped_column(ZlibJSONBlob(), nullable=True)
    uischema: Mapped[dict] = mapped_column(ZlibJSONBlob(), nullable=True)
    error_stacktrace: Mapped[str | None] = mapped_column(myty.LONGTEXT, nullable=True)
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_users.id"),
        nullable=True,
        index=True,
    )
    completed_by_user: Mapped[WorkflowUser | None] = relationship(
        foreign_keys="WorkflowInstanceTask.completed_by_user_id",
    )
    completed_by_delegate_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_users.id"),
        nullable=True,
        index=True,
    )
    completed_by_delegate_user: Mapped[WorkflowUser | None] = relationship(
        foreign_keys="WorkflowInstanceTask.completed_by_delegate_user_id",
    )
    delegate_submit_comment: Mapped[str | None] = mapped_column(ty.Text(), nullable=True)


class WorkflowSpec(Base):
    __tablename__ = "workflow_specs"
    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(ty.String(255), index=True)
    version: Mapped[int] = mapped_column(ty.Integer, index=True)
    files: Mapped[List["WorkflowSpecFile"]] = relationship(
        back_populates="workflow_spec",
    )

    __table_args__ = (UniqueConstraint("name"),)


class WorkflowSpecFile(Base):
    __tablename__ = "workflow_spec_files"
    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    workflow_spec_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_specs.id"),
    )
    workflow_spec: Mapped[WorkflowSpec] = relationship(
        back_populates="files",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(ty.String(255), index=True)
    file_type: Mapped[str] = mapped_column(ty.String(255), index=True)  # bpmn, dmm, ...
    file_hash: Mapped[str] = mapped_column(ty.String(255), index=True)
    file_content: Mapped[str | None] = mapped_column(myty.LONGTEXT, nullable=True)
    file_bpmn_process_id: Mapped[str] = mapped_column(ty.String(255), nullable=True, index=True)

    __table_args__ = (UniqueConstraint("workflow_spec_id", "file_name", "file_hash"),)


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=None,
        nullable=True,
    )

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_users.id"),
    )
    created_by: Mapped[WorkflowUser] = relationship(back_populates="created_workflows")

    tasks: Mapped[List["WorkflowInstanceTask"]] = relationship(
        back_populates="workflow_instance",
    )
    lane_mapping: Mapped[dict] = mapped_column(type_=JSONBlob())

    name: Mapped[str] = mapped_column(ty.String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(
        ty.String(255),
        nullable=False,
        index=True,
        server_default="",
    )
    subtitle: Mapped[str | None] = mapped_column(ty.String(255), nullable=True, index=True)
    data: Mapped[str] = mapped_column(ZlibJSONBlob())

    is_completed: Mapped[bool] = mapped_column(
        ty.Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    active_tasks: Mapped[List["WorkflowInstanceTask"]] = relationship(
        "WorkflowInstanceTask",
        primaryjoin="and_(WorkflowInstanceTask.workflow_instance_id == WorkflowInstance.id,WorkflowInstanceTask.state_ready == True)",
        viewonly=True,
    )

    completed_tasks: Mapped[List["WorkflowInstanceTask"]] = relationship(
        "WorkflowInstanceTask",
        primaryjoin="and_(WorkflowInstanceTask.workflow_instance_id == WorkflowInstance.id,WorkflowInstanceTask.state_completed == True)",
        viewonly=True,
    )

    has_task_in_error_state: Mapped[bool] = column_property(
        select(WorkflowInstanceTask.id)
        .where(
            and_(
                WorkflowInstanceTask.state_error == true(),
                WorkflowInstanceTask.workflow_instance_id == id,
            ),
        )
        .exists(),
    )


class WorkflowInstanceTaskRole(Base):
    __tablename__ = "workflow_instance_task_roles"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)

    workflow_instance_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_instance_tasks.id", ondelete="CASCADE"),
        index=True,
    )
    workflow_instance_task: Mapped[WorkflowInstanceTask] = relationship(
        back_populates="lane_roles",
    )

    name: Mapped[str] = mapped_column(ty.String(255), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("workflow_instance_task_id", "name"),)


class WorkflowAttachment(Base):
    __tablename__ = "workflow_attachments"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    file: Mapped[File | None] = mapped_column(FileField, nullable=True)
    hash: Mapped[str] = mapped_column(
        ty.String(255),
        nullable=False,
        index=True,
        unique=True,
    )
    mimetype: Mapped[str] = mapped_column(ty.String(255), nullable=True)
    first_filename: Mapped[str] = mapped_column(
        ty.String(255),
        nullable=False,
    )  # this is set when the file is first uploaded
    workflow_instance_attachments: Mapped[List["WorkflowInstanceAttachment"]] = relationship(back_populates="attachment")
    workflow_instance_task_attachments: Mapped[List["WorkflowInstanceTaskAttachment"]] = relationship(back_populates="attachment")


class WorkflowInstanceAttachment(Base):
    __tablename__ = "workflow_instance_attachments"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(ty.String(255), nullable=False)
    workflow_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_instances.id", ondelete="CASCADE"),
        index=True,
    )
    workflow_attachment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_attachments.id"), index=True)
    attachment: Mapped[WorkflowAttachment] = relationship(
        back_populates="workflow_instance_attachments",
    )


class WorkflowInstanceTaskAttachment(Base):
    __tablename__ = "workflow_instance_task_attachments"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(ty.String(255), nullable=False)
    workflow_instance_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_instance_tasks.id", ondelete="CASCADE"),
        index=True,
    )
    workflow_attachment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_attachments.id", ondelete="CASCADE"),
        index=True,
    )
    attachment: Mapped[WorkflowAttachment] = relationship(
        back_populates="workflow_instance_task_attachments",
    )


class DataModelFile(Base):
    """A file referenced by a data-model row version through a ``file`` field.

    The sole storage of data-model file references (there is no JSON column) and
    the single source ``repository.delete_dangling_attachment`` counts as the
    third reference table. Mirrors ``WorkflowInstanceTaskAttachment``: a link row
    to a hash-deduped ``WorkflowAttachment`` carrying the per-reference display
    filename, so a download names the file in *this* row's context. The row side
    is a logical key ``(model_name, row_id, row_version)`` — data-model rows live
    in dynamic ``ext_`` tables with no shared parent to FK against.
    """

    __tablename__ = "data_model_files"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(ty.String(255), nullable=False)
    row_id: Mapped[uuid.UUID] = mapped_column(FlexibleUuid, nullable=False)
    # 0 for non-versioned models (single row per id); the row's version otherwise.
    row_version: Mapped[int] = mapped_column(ty.Integer, nullable=False, default=0)
    field_name: Mapped[str] = mapped_column(ty.String(255), nullable=False)
    workflow_attachment_id: Mapped[uuid.UUID] = mapped_column(
        # Explicit FK name so create_all (fresh/test DBs) and the migration
        # (prod upgrades) agree; the convention-derived name would also differ
        # per path.
        ForeignKey("workflow_attachments.id", ondelete="CASCADE", name="fk_dmf_attachment"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(ty.String(255), nullable=False)
    mimetype: Mapped[str | None] = mapped_column(ty.String(255), nullable=True)
    # Ordering for multi-file fields, stable within (row version, field).
    position: Mapped[int] = mapped_column(ty.Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
    )
    attachment: Mapped[WorkflowAttachment] = relationship()

    __table_args__ = (
        # Read path: fetch all files for a page of (model, row, version) in one query.
        Index("ix_dmf_lookup", "model_name", "row_id", "row_version"),
        # Idempotent-upsert key (mirrors store_attachment_for_task's select-by-key).
        # Short explicit name: the convention-expanded name exceeds MySQL's 64-char limit.
        UniqueConstraint(
            "model_name",
            "row_id",
            "row_version",
            "field_name",
            "workflow_attachment_id",
            name="uq_dmf_ref",
        ),
    )


class WorkflowMessage(Base):
    __tablename__ = "workflow_messages"
    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
        index=True,
    )
    processed_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=None,
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(ty.String(255), nullable=False, index=True)
    correlation_key: Mapped[str] = mapped_column(ty.String(255), nullable=False, index=True)
    data: Mapped[dict] = deferred(mapped_column(ZlibJSONBlob()))

    # Was the message sent by an existing workflow?
    sent_by_workflow_instance_id: Mapped[None | uuid.UUID] = mapped_column(ForeignKey("workflow_instances.id", ondelete="SET NULL"), index=True)

    # We currently assume that a message is always sent by a user
    sent_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_users.id"), index=True)

    # https://docs.camunda.io/docs/next/components/concepts/messages/#message-correlation-overview
    # Do we need a TTL?


class WorkflowMessageWorkflowInstance(Base):
    __tablename__ = "workflow_message_instances"
    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, ForeignKey("workflow_messages.id", ondelete="CASCADE"), index=True, nullable=False)
    workflow_instance_id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)


class WorkflowMessageSubscription(Base):
    __tablename__ = "workflow_message_subscriptions"
    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(),
        default=dt_now_naive,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(ty.String(255), nullable=False, index=True)
    correlation_key: Mapped[str] = mapped_column(ty.String(255), nullable=False, index=True)
    workflow_instance_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_instance_tasks.id", ondelete="CASCADE"), nullable=False, index=True)


class WorkflowTimeEvent(Base):
    """
    Represents a pending or processed BPMN timer.
    Locking is handled by the cron/job system at process-level, not here.
    """

    __tablename__ = "workflow_time_events"

    id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, primary_key=True, default=uuid.uuid4)
    workflow_instance_id: Mapped[uuid.UUID] = mapped_column(
        ty.Uuid,
        ForeignKey("workflow_instances.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    timer_task_id: Mapped[uuid.UUID] = mapped_column(ty.Uuid, nullable=False)

    # "time_date" | "time_duration" | "time_cycle"
    timer_kind: Mapped[Literal["time_date", "time_duration", "time_cycle"]] = mapped_column(ty.String(32), nullable=False)

    # For timeDate/timeDuration: evaluated ISO timestamp (string)
    expression: Mapped[str | None] = mapped_column(ty.Text, nullable=True)

    # whether it interrupts the attached activity.
    interrupting: Mapped[bool] = mapped_column(ty.Boolean, nullable=False, default=True)

    # Next due time in UTC
    due_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)

    # For cycles: remaining count; -1 = infinite; None = not a cycle timer.
    remaining_cycles: Mapped[int | None] = mapped_column(ty.Integer, nullable=True)

    # Allowed values: "scheduled", "completed", "cancelled", "error"
    status: Mapped[str] = mapped_column(ty.String(24), nullable=False, default="scheduled")

    # Number of times this timer has fired (useful for metrics/debug)
    fire_count: Mapped[int] = mapped_column(ty.Integer, nullable=False, default=0)

    # Last error message if processing failed (optional, truncated in repository layer)
    last_error: Mapped[str | None] = mapped_column(ty.Text, nullable=True)

    # Auditing
    created_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime(), default=dt_now_naive, nullable=False, index=True)

    __table_args__ = (
        # One timer record per timer task within a workflow instance.
        UniqueConstraint(
            "workflow_instance_id",
            "timer_task_id",
            name="uq_wte_per_task",
        ),
        # Efficient scanning for due timers by status and due time.
        Index("ix_wte_due_status", "due_at", "status"),
        # Guard against invalid status values at the DB level (optional but nice).
        CheckConstraint(
            "status IN ('scheduled','completed','cancelled','error')",
            name="ck_wte_status_values",
        ),
    )


#### Extension model base + data-model mixins (DataModelMixin / VersionedMixin) ####


def extension_model_base(namespace: str) -> type:
    """Create an abstract base class whose subclasses get auto-prefixed table names.

    Usage in an extension project::

        AcmeModel = extension_model_base("acme")

        class OrderApproval(AcmeModel):
            _ext_table = "order_approval"
            # -> __tablename__ = "ext_acme_order_approval"
    """

    class _ExtBase(Base):
        __abstract__ = True
        _ext_namespace: str = namespace
        _ext_table: str  # must be defined by subclass

        @declared_attr.directive
        def __tablename__(cls) -> str:
            table = getattr(cls, "_ext_table", None)
            if not table:
                raise ValueError(
                    f"{cls.__name__} must define '_ext_table' as a stable DB identifier",
                )
            return f"ext_{namespace}_{table}"

    return _ExtBase


# System columns hidden from the default (inferred) field projection — pure
# plumbing, not display fields. The stable ``id`` and the record ``title`` stay
# out of this set so they are projectable and searchable; ``serialize_row``
# always carries them (and ``version``) for the client.
_MIXIN_SYSTEM_COLUMNS = frozenset(
    {
        "version",
        "is_current",
        "workflow_instance_id",
        "action",
        "created_at",
    }
)


class DataModelMixin:
    """Base mixin: a stable surrogate ``id`` for any registry-tracked model.

    The model's own identity, independent of any workflow — the sole primary key
    for a plain (non-versioned, non-displayed) model such as a config / lookup
    table. Carries no ``title``: a human-readable record name is part of the
    workflow-managed contract (``WorkflowManagedMixin``), not every model.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        FlexibleUuid,
        primary_key=True,
        default=uuid.uuid4,
        sort_order=-100,  # keep id first; composite-PK order across mixins needs explicit sort_order
    )


class VersionedMixin(DataModelMixin):
    """Opt-in versioning on top of ``DataModelMixin``.

    Each modification appends a new row that shares the record's stable ``id`` and
    bumps ``version`` (counted per ``id``); the current row carries ``is_current``.
    The primary key is the composite ``(id, version)``. Pure versioning mechanism —
    workflow provenance and the display title live in ``WorkflowManagedMixin``.
    """

    version: Mapped[int] = mapped_column(
        ty.Integer,
        primary_key=True,
        default=1,
        sort_order=-99,
    )
    is_current: Mapped[bool] = mapped_column(
        ty.Boolean,
        nullable=False,
        default=True,
        index=True,
        sort_order=-98,
    )
    created_at: Mapped[datetime.datetime | None] = mapped_column(
        ty.DateTime,
        nullable=True,
        default=dt_now_naive,
        sort_order=-95,
    )

    @classmethod
    def get_current_by_id(cls, db: Session, record_id: uuid.UUID | str):
        """Return the current (head) version for ``record_id``, or ``None`` if absent.

        Selects the row carrying ``is_current`` — the head of the version chain for the
        stable id. ``record_id`` may be a ``uuid.UUID`` or its string form (e.g. a
        ``source_id`` seed carried through the engine as task data).
        """
        if isinstance(record_id, str):
            record_id = uuid.UUID(record_id)
        return db.scalars(select(cls).where(cls.id == record_id, cls.is_current.is_(True))).one_or_none()


class WorkflowManagedMixin(VersionedMixin):
    """Versioned data produced by a workflow and exposed via the BFF data API.

    The precondition for ``register_data_model(api=...)``: such a record carries
    its workflow provenance (``workflow_instance_id``, mandatory — which workflow
    instance produced this version), an optional ``action`` label, and a reserved,
    human-readable ``title`` the API projects and the global search uses. A model
    declaring its own ``title`` column would silently shadow the reserved one, so
    registration rejects that (the registry gate keys on the ``info`` marker).
    """

    # Provenance: which workflow instance produced THIS version (not the identity).
    workflow_instance_id: Mapped[uuid.UUID] = mapped_column(
        FlexibleUuid,
        nullable=False,
        sort_order=-97,
    )
    action: Mapped[str | None] = mapped_column(
        ty.String(100),
        nullable=True,
        sort_order=-96,
    )
    title: Mapped[str | None] = mapped_column(
        ty.String(200),
        nullable=True,
        sort_order=-94,  # behind the versioning columns; PK order (id, version) stays untouched
        info={"wfe_reserved_title": True},
    )


@event.listens_for(Session, "before_flush")
def _assign_versions(session: Session, flush_context, instances) -> None:
    """Maintain ``version``/``is_current`` for newly added versioned rows.

    A service task writes plain ORM — ``db.add(Model(**fields))`` for a new record
    (a fresh ``id`` is defaulted) or ``db.add(Model(id=record_id, **fields))`` to
    append a version. This hook then assigns ``version`` (1, or ``max+1`` for an
    existing id) and ``is_current=True``, demoting the previous head. It only acts
    when ``version`` is left unset, so tests that seed explicit version rows are
    untouched. ``created_at`` comes from a column default; provenance
    (``workflow_instance_id``) and ``action`` stay caller-set. ``id`` is
    front-loaded here when unset (instead of relying on the column default firing
    at INSERT) so a later before_flush listener — the data-model file
    materializer — sees the final ``(id, version)`` for this row.
    """
    for obj in list(session.new):
        if not isinstance(obj, VersionedMixin) or obj.version is not None:
            continue
        # Front-load the id so it is final for downstream before_flush listeners.
        # A fresh uuid matches no existing row, so version assignment is unchanged.
        if obj.id is None:
            obj.id = uuid.uuid4()
        model_class = type(obj)
        with session.no_autoflush:
            existing_max = session.scalar(select(func.max(model_class.version)).where(model_class.id == obj.id))
            if existing_max is not None:
                current_head = session.scalar(
                    select(model_class).where(model_class.id == obj.id, model_class.is_current.is_(True))
                )
                if current_head is not None and current_head is not obj:
                    current_head.is_current = False
        obj.version = existing_max + 1 if existing_max is not None else 1
        obj.is_current = True
