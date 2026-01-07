# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""
Read-Only queries which work directly on the database instead of domain objects
"""

import datetime
import uuid
from typing import Literal

from sqlalchemy import and_, false, null, or_, select, true, func
from sqlalchemy.orm import Session, aliased, contains_eager, selectinload
from sqlalchemy.orm.attributes import set_committed_value

from actidoo_wfe.helpers.bff_table import BFFTable, BffTableQuerySchemaBase
from actidoo_wfe.helpers.schema import PaginatedDataSchema
from actidoo_wfe.helpers.time import dt_ago_naive, dt_now_naive
from actidoo_wfe.wf.exceptions import TaskNotFoundException
from actidoo_wfe.wf.models import (
    WorkflowInstance,
    WorkflowInstanceTask,
    WorkflowInstanceTaskRole,
    WorkflowMessageSubscription,
    WorkflowSpec,
    WorkflowUser,
    WorkflowUserRole,
)
from actidoo_wfe.wf.types import (
    InlineUserRepresentation,
    ReducedWorkflowState,
    MessageSubscriptionRepresentation,
    ReducedWorkflowInstanceResponse,
    UserRepresentation,
    WorkflowInstanceRepresentation,
    WorkflowInstanceTaskAdminRepresentation,
    WorkflowInstanceWithoutTasksRepresentation,
    WorkflowStateResponse, 
    TaskState
)


def bff_get_workflows_with_usertasks(
    db: Session,
    bff_table_request_params: BffTableQuerySchemaBase,
    user_id: uuid.UUID,
    state: Literal["ready", "completed"],
):
    user: WorkflowUser = db.execute(
        select(WorkflowUser).where(WorkflowUser.id == user_id)
    ).scalar_one()

    role_names = set([r.role.name for r in user.roles])

    sq_where = [
        WorkflowInstanceTask.manual == true(),
    ]

    if state == "ready":
        sq_where.append(WorkflowInstanceTask.state_ready == true())
        sq_where.append(
            or_(
                WorkflowInstanceTask.assigned_user == user,
                and_(
                    select(WorkflowInstanceTaskRole)
                    .where(
                        WorkflowInstanceTaskRole.workflow_instance_task_id
                        == WorkflowInstanceTask.id,
                        WorkflowInstanceTaskRole.name.in_(role_names),
                    )
                    .exists(),
                    WorkflowInstanceTask.assigned_user == null(), 
                ),
            )
        )

    elif state == "completed":
        sq_where.append(WorkflowInstanceTask.state_completed == true())
        sq_where.append(
            WorkflowInstanceTask.assigned_user == user,
        )

    q1 = (
        select(WorkflowInstanceTask.id.label("task_id"))
        .select_from(WorkflowInstance)
        .join(
            WorkflowInstanceTask,
            WorkflowInstanceTask.workflow_instance_id == WorkflowInstance.id,
        )
        .where(and_(*sq_where))
        .order_by(WorkflowInstance.id)
    )

    task_ids = {x for x in db.execute(q1).scalars()}

    sq = (
        select(WorkflowInstance.id)
        .distinct()
        .select_from(WorkflowInstance)
        .join(
            WorkflowInstanceTask,
            WorkflowInstanceTask.workflow_instance_id == WorkflowInstance.id,
        )
        .where(and_(*sq_where))
        .order_by(WorkflowInstance.id)
    )

    q = (
        select(WorkflowInstance)
        .options(
            selectinload(WorkflowInstance.active_tasks).selectinload(
                WorkflowInstanceTask.assigned_user
            ),
            selectinload(WorkflowInstance.completed_tasks).selectinload(
                WorkflowInstanceTask.assigned_user
            ),
            selectinload(WorkflowInstance.created_by),
        )
        .where(WorkflowInstance.id.in_(sq))
    )

    bff_table = BFFTable(
        db=db,
        request_params=bff_table_request_params,
        query=q,
        field_to_dbfield_map=dict(),
        default_order_by=WorkflowInstance.created_at.desc(),
    )

    paginated_data = bff_table.get_paginated_data()

    for row in paginated_data.items:
        filtered_active_tasks = [t for t in row.active_tasks if t.id in task_ids]
        filtered_completed_tasks = [t for t in row.completed_tasks if t.id in task_ids]

        set_committed_value(row, "active_tasks", filtered_active_tasks)
        set_committed_value(row, "completed_tasks", filtered_completed_tasks)

        db.expunge(row)

    res_representation = PaginatedDataSchema(
        ITEMS=[WorkflowInstanceRepresentation.model_validate(x) for x in paginated_data.items],
        COUNT=paginated_data.count,
    )

    return res_representation


def bff_user_get_initiated_workflows(
    db: Session, bff_table_request_params: BffTableQuerySchemaBase, user_id: uuid.UUID
):
    user: WorkflowUser = db.execute(
        select(WorkflowUser).where(WorkflowUser.id == user_id)
    ).scalar_one()

    q = (
        select(WorkflowInstance)
        .options(
            selectinload(WorkflowInstance.active_tasks).selectinload(
                WorkflowInstanceTask.assigned_user
            ),
            selectinload(WorkflowInstance.completed_tasks).selectinload(
                WorkflowInstanceTask.assigned_user
            ),
            selectinload(WorkflowInstance.created_by),
        )
        .where(and_(WorkflowInstance.created_by == user))
    )

    # Create an instance of the BFFTable class which will handle the pagination and querying of workflow instances.
    # Pass the database session, request parameters, the query for workflow instances,
    # an empty dictionary for mapping field names to database fields,
    # and the default order by clause to sort the results by creation date in descending order.
    bff_table = BFFTable(
        db=db,
        request_params=bff_table_request_params,
        query=q,
        field_to_dbfield_map=dict(),
        default_order_by=WorkflowInstance.created_at.desc(),
    )

    paginated_data = bff_table.get_paginated_data()

    # Iterate through each workflow instance returned in the paginated data
    for row in paginated_data.items:
        # Filter atasks to include only those marked as manual
        filtered_active_tasks = [t for t in row.active_tasks if t.manual]
        filtered_completed_tasks = [t for t in row.completed_tasks if t.manual]

        # Commit the filtered lists of active and completed tasks back to the row object
        set_committed_value(row, "active_tasks", filtered_active_tasks)
        set_committed_value(row, "completed_tasks", filtered_completed_tasks)

        # Remove the row from the session to prevent it from being queried again
        db.expunge(row)

    res_representation = PaginatedDataSchema(
        ITEMS=[WorkflowInstanceRepresentation.model_validate(x) for x in paginated_data.items],
        COUNT=paginated_data.count,
    )

    return res_representation


def bff_admin_get_all_tasks(db: Session, bff_table_request_params: BffTableQuerySchemaBase, allowed_workflow_names: set[str] = set()):

    AssignedUser = aliased(WorkflowUser)
    TriggeredByUser = aliased(WorkflowUser)
    AssociatedWorkflow = aliased(WorkflowInstance)

    q = select(WorkflowInstanceTask)\
        .join(WorkflowInstanceTask.workflow_instance) \
        .join(AssignedUser, WorkflowInstanceTask.assigned_user_id == AssignedUser.id, isouter=True)\
        .join(TriggeredByUser, WorkflowInstanceTask.triggered_by_id == TriggeredByUser.id, isouter=True)\
        .join(AssociatedWorkflow, WorkflowInstanceTask.workflow_instance_id == AssociatedWorkflow.id, isouter=True)\
        .options(
            selectinload(WorkflowInstanceTask.workflow_instance),
            contains_eager(WorkflowInstanceTask.assigned_user, alias=AssignedUser),
            contains_eager(WorkflowInstanceTask.triggered_by, alias=TriggeredByUser),
            selectinload(WorkflowInstanceTask.lane_roles),
        )\
        .where(WorkflowInstance.name.in_(allowed_workflow_names))

    bff_table = BFFTable(
        db=db,
        request_params=bff_table_request_params,
        query=q,
        field_to_dbfield_map={
            "workflow_instance___id": WorkflowInstanceTask.workflow_instance_id,
            "assigned_user___full_name": AssignedUser.full_name,
            "workflow_instance___title": AssociatedWorkflow.title,
            "workflow_instance___subtitle": AssociatedWorkflow.subtitle,
        },
        default_order_by=[WorkflowInstanceTask.sort.desc()],
    )

    paginated_data = bff_table.get_paginated_data()

    for row in paginated_data.items:
        db.expunge(row)

    res_representation = PaginatedDataSchema(
        ITEMS=[
            WorkflowInstanceTaskAdminRepresentation.model_validate(
                dict(
                    x.__dict__,
                    lane_roles=[r.name for r in x.lane_roles],
                    workflow_instance=WorkflowInstanceWithoutTasksRepresentation.model_validate(
                        x.workflow_instance
                    ),
                )
            )
            for x in paginated_data.items
        ],
        COUNT=paginated_data.count,
    )

    return res_representation


def bff_admin_get_graph_workflow_instances(db: Session) -> ReducedWorkflowInstanceResponse:
    completed_workflows = [
        ReducedWorkflowState(id=row[0], created_at=row[1], title=row[2], name= row[3])
        for row in db.query(WorkflowInstance.id,
                            WorkflowInstance.created_at,
                            WorkflowInstance.title,
                            WorkflowInstance.name).filter(
                                WorkflowInstance.is_completed
                                )
    ]
    return ReducedWorkflowInstanceResponse(ITEMS=completed_workflows)


def bff_admin_get_all_workflow_instances(db: Session, bff_table_request_params: BffTableQuerySchemaBase, allowed_workflow_names: set[str] = set()):
    CreatedByUser = aliased(WorkflowUser)
    
    q = (
        select(WorkflowInstance)
        .join(CreatedByUser, WorkflowInstance.created_by_id == CreatedByUser.id, isouter=True)\
        .options(
            selectinload(WorkflowInstance.tasks).selectinload(
                WorkflowInstanceTask.assigned_user
            ),
            selectinload(WorkflowInstance.active_tasks),
            selectinload(WorkflowInstance.completed_tasks),
            selectinload(WorkflowInstance.created_by),
        )
        .where(
            WorkflowInstance.name.in_(allowed_workflow_names)
        )
    )

    bff_table = BFFTable(
        db=db,
        request_params=bff_table_request_params,
        query=q,
        field_to_dbfield_map={
            "created_by___full_name": CreatedByUser.full_name,
        },
        default_order_by=WorkflowInstance.created_at.desc(),
    )

    paginated_data = bff_table.get_paginated_data()

    for row in paginated_data.items:
        db.expunge(row)

    res_representation = PaginatedDataSchema(
        ITEMS=[WorkflowInstanceRepresentation.model_validate(x) for x in paginated_data.items],
        COUNT=paginated_data.count,
    )

    return res_representation


def admin_get_single_task(db: Session, task_id: uuid.UUID) -> WorkflowInstanceTaskAdminRepresentation:
    q = select(WorkflowInstanceTask).options(
        selectinload(WorkflowInstanceTask.workflow_instance),
        selectinload(WorkflowInstanceTask.assigned_user),
        selectinload(WorkflowInstanceTask.triggered_by),
        selectinload(WorkflowInstanceTask.lane_roles),
    ).filter(
        WorkflowInstanceTask.id == task_id
    )

    task = db.execute(q).scalar()

    db.expunge(task)

    if task is None:
        raise TaskNotFoundException()

    return WorkflowInstanceTaskAdminRepresentation.model_validate(
        dict(
            task.__dict__,
            lane_roles=[r.name for r in task.lane_roles],
            workflow_instance=WorkflowInstanceWithoutTasksRepresentation.model_validate(
                task.workflow_instance
            ),
        )
    )

def admin_get_task_states_per_workflow(db: Session, wf_name: str, allowed_workflow_names: set[str] = set()) -> WorkflowStateResponse:
    instances_with_tasks = db.query(WorkflowInstance).options(
        selectinload(WorkflowInstance.tasks)
    ).filter(
        WorkflowInstance.name == wf_name,
        WorkflowInstance.is_completed == False,
        WorkflowInstance.name.in_(allowed_workflow_names)
    ).all()

    workflow_summary = {}

    for instance in instances_with_tasks:
        if instance.name not in workflow_summary:
            workflow_summary[instance.name] = {}
            
        for task in instance.tasks:
            if task.name not in workflow_summary[instance.name]:
                workflow_summary[instance.name][task.name] = TaskState(title=task.title, ready_counter=0, error_counter=0)

            if task.state_ready:
                workflow_summary[instance.name][task.name].ready_counter += 1
            elif task.state_error:
                workflow_summary[instance.name][task.name].error_counter += 1

    return WorkflowStateResponse(
        workflow_name=wf_name,
        tasks=workflow_summary.get(wf_name, {})
    )

def get_workflow_spec(db: Session, name: str, version: int|None):

    q = select(WorkflowSpec).options(
        selectinload(WorkflowSpec.files),
    ).filter(
        WorkflowSpec.name == name
    )

    if version:
        q = q.filter(WorkflowSpec.version == version)
    else:
        q = q.order_by(WorkflowSpec.version.desc()).limit(1)

    spec = db.execute(q).scalar()

    db.expunge(spec)

    return spec


def get_workflows_with_usertasks(
    db: Session,
    user: WorkflowUser | UserRepresentation
):
    user_id = user.id
    if isinstance(user, WorkflowUser):
        role_names = {r.role.name for r in user.roles}
    else:
        role_names = set(user.roles)

    sq_where = [
        WorkflowInstanceTask.manual == true(),
        WorkflowInstanceTask.state_ready == true(),
        or_(
            WorkflowInstanceTask.assigned_user_id == user_id,
            and_(
                select(WorkflowInstanceTaskRole)
                .where(
                    WorkflowInstanceTaskRole.workflow_instance_task_id
                    == WorkflowInstanceTask.id,
                    WorkflowInstanceTaskRole.name.in_(role_names),
                )
                .exists(),
                WorkflowInstanceTask.assigned_user_id == null(), 
            ),
        )
    ]

    q1 = (
        select(WorkflowInstanceTask.id.label("task_id"))
        .select_from(WorkflowInstance)
        .join(
            WorkflowInstanceTask,
            WorkflowInstanceTask.workflow_instance_id == WorkflowInstance.id,
        )
        .where(and_(*sq_where))
        .order_by(WorkflowInstance.id)
    )

    task_ids = {x for x in db.execute(q1).scalars()}

    sq = (
        select(WorkflowInstance.id)
        .distinct()
        .select_from(WorkflowInstance)
        .join(
            WorkflowInstanceTask,
            WorkflowInstanceTask.workflow_instance_id == WorkflowInstance.id,
        )
        .where(and_(*sq_where))
        .order_by(WorkflowInstance.id)
    )

    q = (
        select(WorkflowInstance)
        .options(
            selectinload(WorkflowInstance.active_tasks).selectinload(
                WorkflowInstanceTask.assigned_user
            ),
            selectinload(WorkflowInstance.completed_tasks).selectinload(
                WorkflowInstanceTask.assigned_user
            ),
            selectinload(WorkflowInstance.created_by),
        )
        .where(WorkflowInstance.id.in_(sq))
    )

    q = q.order_by(WorkflowInstance.created_at.desc())
    items = list(db.execute(q).scalars())

    for row in items:
        filtered_active_tasks = [t for t in row.active_tasks if t.id in task_ids]
        filtered_completed_tasks = [t for t in row.completed_tasks if t.id in task_ids]

        set_committed_value(row, "active_tasks", filtered_active_tasks)
        set_committed_value(row, "completed_tasks", filtered_completed_tasks)

        db.expunge(row)

    return items


def get_workflow_by_instance_id(db: Session, workflow_instance_id: uuid.UUID):
    q = select(WorkflowInstance).filter(
        WorkflowInstance.id == workflow_instance_id
    )
     
    workflow_instance = db.execute(q).scalar()

    resp = WorkflowInstanceWithoutTasksRepresentation.model_validate(workflow_instance)

    db.expunge(workflow_instance)

    return resp

def get_message_subscriptions_by_instance_id(db: Session, workflow_instance_id: uuid.UUID):
    existing_subscriptions = db.execute(
        select(WorkflowMessageSubscription)
        .join(WorkflowInstanceTask, WorkflowMessageSubscription.workflow_instance_task_id == WorkflowInstanceTask.id)
        .where(
            WorkflowInstanceTask.workflow_instance_id == workflow_instance_id
        )
    ).scalars()

    ret = []
    for x in existing_subscriptions:
        ret.append(MessageSubscriptionRepresentation.model_validate(x))
        db.expunge(x)

    return ret


def get_single_task(db: Session, task_id: uuid.UUID) -> WorkflowInstanceTask:
    q = select(WorkflowInstanceTask).options(
        selectinload(WorkflowInstanceTask.workflow_instance),
        selectinload(WorkflowInstanceTask.assigned_user)
        .selectinload(WorkflowUser.roles)
        .selectinload(WorkflowUserRole.role),
        selectinload(WorkflowInstanceTask.lane_roles),
    ).filter(
        WorkflowInstanceTask.id == task_id
    )

    task = db.execute(q).scalar()

    db.expunge(task)

    if task is None:
        raise TaskNotFoundException()

    return task


def get_workflow_statistics(db: Session, workflow_name: str):
    active_instances = db.execute(
        select(func.count())
        .select_from(WorkflowInstance)
        .where(and_(
            WorkflowInstance.name == workflow_name,
            WorkflowInstance.is_completed == false()
        ))
    ).scalar_one()

    completed_instances = db.execute(
        select(func.count())
        .select_from(WorkflowInstance)
        .where(and_(
            WorkflowInstance.name == workflow_name,
            WorkflowInstance.is_completed == true()
        ))
    ).scalar_one()

    started_instance_last_60_days = db.execute(
        select(func.count())
        .select_from(WorkflowInstance)
        .where(and_(
            WorkflowInstance.name == workflow_name,
            WorkflowInstance.created_at >= (dt_now_naive().replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=60))
        ))
    ).scalar_one()

    return {
        "active_instances": active_instances,
        "completed_instances": completed_instances,
        "estimated_instances_per_year": started_instance_last_60_days * 6
    }


def get_distinct_workflow_names_from_db(db: Session):
    q = (
        select(WorkflowInstance.name).distinct()
    )

    return {name for name in db.execute(q).scalars()}
