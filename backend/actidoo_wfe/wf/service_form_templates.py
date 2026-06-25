# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""User-private form templates: named presets of a task form's input.

Scope and eligibility are derived server-side from the live task, so the client only passes the
runtime task id. The trust boundary lives here and in service_form.filter_template_data.
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from actidoo_wfe.helpers.time import dt_now_naive
from actidoo_wfe.wf import repository, service_form, service_user, service_workflow
from actidoo_wfe.wf.exceptions import (
    FormTemplatesDisabledException,
    FormTemplatesNotAvailableException,
    TaskNotAccessibleException,
    TemplateNotFoundException,
)
from actidoo_wfe.wf.constants import TEMPLATE_MODE_UISCHEMA_KEY, TemplateMode
from actidoo_wfe.wf.models import WorkflowUserFormTemplate
from actidoo_wfe.wf.types import ReactJsonSchemaFormData

log = logging.getLogger(__name__)


@dataclass
class ResolvedTask:
    workflow_name: str
    stable_task_key: str
    jsonschema: dict
    uischema: dict
    template_mode: str


@dataclass
class ResolveResult:
    applicable_data: dict
    skipped_fields: list[dict]


def _resolve_task_for_user(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> ResolvedTask:
    """Loads the live task the user may access and derives template scope + schema from it."""
    try:
        workflow = repository.load_workflow_instance_by_task_id(db=db, task_id=task_id)
    except NoResultFound:
        raise TaskNotAccessibleException()

    user = repository.load_user(db=db, user_id=user_id)
    delegation_targets = service_user.get_active_principals_for_delegate(db=db, delegate_user_id=user_id)
    # Templates are only used while filling a ready task (mirrors submit_task_data). No workflow
    # state is mutated here, so the _require_definition_for_write check of the write paths is not needed.
    usertasks = service_workflow.get_usertasks_for_user(
        workflow=workflow,
        user=user,
        state=["ready"],
        delegation_targets=delegation_targets,
    )
    task = next((t for t in usertasks if t.id == task_id), None)
    if task is None:
        raise TaskNotAccessibleException()
    if not task.jsonschema:
        raise FormTemplatesNotAvailableException()

    # The form-level template_mode lives in the uischema root; absent only for form-less tasks.
    template_mode = (task.uischema or {}).get(TEMPLATE_MODE_UISCHEMA_KEY, TemplateMode.OFF)
    return ResolvedTask(
        workflow_name=workflow.spec.name,
        stable_task_key=task.name,
        jsonschema=task.jsonschema,
        uischema=task.uischema or {},
        template_mode=template_mode,
    )


def _drop_hidden_fields(resolved: ResolvedTask, data: dict) -> dict:
    """Drop values of currently hidden fields so they never enter a template."""
    form_spec = ReactJsonSchemaFormData(jsonschema=resolved.jsonschema, uischema=resolved.uischema)
    return service_workflow.strip_hidden_field_values(resolved.workflow_name, form_spec, data)


def list_templates(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> tuple[list[WorkflowUserFormTemplate], str]:
    resolved = _resolve_task_for_user(db=db, user_id=user_id, task_id=task_id)
    if resolved.template_mode == TemplateMode.OFF:
        return [], resolved.template_mode

    rows = (
        db.execute(
            select(WorkflowUserFormTemplate)
            .where(
                WorkflowUserFormTemplate.user_id == user_id,
                WorkflowUserFormTemplate.workflow_name == resolved.workflow_name,
                WorkflowUserFormTemplate.task_name == resolved.stable_task_key,
            )
            .order_by(WorkflowUserFormTemplate.template_name, WorkflowUserFormTemplate.updated_at),
        )
        .scalars()
        .all()
    )
    for row in rows:
        db.expunge(row)
    return rows, resolved.template_mode


def save_template(
    db: Session,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    template_name: str,
    template_data: dict,
) -> WorkflowUserFormTemplate:
    resolved = _resolve_task_for_user(db=db, user_id=user_id, task_id=task_id)
    if resolved.template_mode == TemplateMode.OFF:
        raise FormTemplatesDisabledException()

    name = (template_name or "").strip()
    if not name:
        raise ValueError("template_name must not be empty")

    visible_data = _drop_hidden_fields(resolved, template_data)
    kept, _skipped = service_form.filter_template_data(
        jsonschema=resolved.jsonschema,
        data=visible_data,
        mode=resolved.template_mode,
        apply_value_rule=True,
    )

    existing = db.execute(
        select(WorkflowUserFormTemplate).where(
            WorkflowUserFormTemplate.user_id == user_id,
            WorkflowUserFormTemplate.workflow_name == resolved.workflow_name,
            WorkflowUserFormTemplate.task_name == resolved.stable_task_key,
            WorkflowUserFormTemplate.template_name == name,
        ),
    ).scalar()

    if existing is not None:
        # Overwrite supports the "apply, correct, save again" workflow from the ADR.
        existing.template_data = kept
        existing.updated_at = dt_now_naive()
        row = existing
    else:
        row = WorkflowUserFormTemplate(
            user_id=user_id,
            workflow_name=resolved.workflow_name,
            task_name=resolved.stable_task_key,
            template_name=name,
            template_data=kept,
        )
        db.add(row)

    db.flush()
    return row


def preview_template(
    db: Session,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    template_data: dict,
) -> ResolveResult:
    """Previews what a save would store: the eligible, non-empty subset plus the excluded fields."""
    resolved = _resolve_task_for_user(db=db, user_id=user_id, task_id=task_id)
    if resolved.template_mode == TemplateMode.OFF:
        raise FormTemplatesDisabledException()

    visible_data = _drop_hidden_fields(resolved, template_data)
    applicable, skipped_paths = service_form.filter_template_data(
        jsonschema=resolved.jsonschema,
        data=visible_data,
        mode=resolved.template_mode,
        apply_value_rule=True,
    )
    # Only surface excluded fields the user actually filled in (hidden ones are already dropped).
    filled_paths = [path for path in skipped_paths if _is_filled_value(_value_at_path(visible_data, path))]
    skipped = [
        _describe_skipped(resolved.jsonschema, path, _value_at_path(visible_data, path)) for path in filled_paths
    ]
    return ResolveResult(applicable_data=applicable, skipped_fields=skipped)


def _value_at_path(data, path: list):
    node = data
    for segment in path:
        if isinstance(node, dict):
            node = node.get(segment)
        elif isinstance(node, list) and isinstance(segment, int) and 0 <= segment < len(node):
            node = node[segment]
        else:
            return None
    return node


def _is_filled_value(value) -> bool:
    if isinstance(value, bool):
        return True
    return value not in (None, "", [], {})


def resolve_template_for_apply(
    db: Session,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    template_id: uuid.UUID,
) -> ResolveResult:
    resolved = _resolve_task_for_user(db=db, user_id=user_id, task_id=task_id)
    if resolved.template_mode == TemplateMode.OFF:
        raise FormTemplatesDisabledException()

    row = db.execute(
        select(WorkflowUserFormTemplate).where(WorkflowUserFormTemplate.id == template_id),
    ).scalar()
    if row is None or row.user_id != user_id:
        raise TemplateNotFoundException()
    if row.workflow_name != resolved.workflow_name or row.task_name != resolved.stable_task_key:
        raise TemplateNotFoundException()

    applicable, skipped_paths = service_form.filter_template_data(
        jsonschema=resolved.jsonschema,
        data=row.template_data,
        mode=resolved.template_mode,
        apply_value_rule=False,
    )
    skipped = [
        _describe_skipped(resolved.jsonschema, path, _value_at_path(row.template_data, path)) for path in skipped_paths
    ]
    return ResolveResult(applicable_data=applicable, skipped_fields=skipped)


def delete_template(db: Session, user_id: uuid.UUID, template_id: uuid.UUID) -> None:
    row = db.execute(
        select(WorkflowUserFormTemplate).where(WorkflowUserFormTemplate.id == template_id),
    ).scalar()
    if row is None or row.user_id != user_id:
        # 404 (not 403) so the existence of another user's template is not leaked.
        raise TemplateNotFoundException()
    db.delete(row)
    db.flush()


def _describe_skipped(jsonschema: dict, path: list, value=None) -> dict:
    """Best-effort label/value for a skipped field; falls back to the dotted key for removed fields."""
    key = ".".join(str(segment) for segment in path)
    node = jsonschema
    for segment in path:
        if isinstance(segment, int):
            node = node.get("items", {}) if isinstance(node, dict) else {}
            continue
        properties = node.get("properties", {}) if isinstance(node, dict) else {}
        node = properties.get(segment, {})
    label = node.get("title") if isinstance(node, dict) else None
    return {"key": key, "label": label or key, "value": value}
