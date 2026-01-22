# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import datetime
import logging
import uuid
from typing import List, Sequence

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session, selectinload

from actidoo_wfe.database import eilike, search_uuid_by_prefix
from actidoo_wfe.helpers.time import dt_now_naive
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import repository
from actidoo_wfe.wf.models import WorkflowRole, WorkflowUser, WorkflowUserDelegate, WorkflowUserRole
from actidoo_wfe.wf.types import UserRepresentation

log = logging.getLogger(__name__)


def get_all_users(db: Session) -> Sequence[WorkflowUser]:
    """
    Returns all the users from the database.
    """
    return db.execute(select(WorkflowUser).options(selectinload(WorkflowUser.roles))).scalars().all()


def get_user(db: Session, user_id: uuid.UUID):
    user = db.execute(select(WorkflowUser).where(WorkflowUser.id == user_id)).scalar()
    return user


def get_user_by_email(db: Session, user_email: str):
    user = db.execute(select(WorkflowUser).where(WorkflowUser.email == user_email)).scalar()
    return user


def upsert_user(
    db: Session,
    idp_user_id: str | None,
    username: str | None,
    email: str | None,
    first_name: str | None,
    last_name: str | None,
    is_service_user: bool,
    initial_locale: str | None = None
) -> WorkflowUser:
    # look for ID first
    user = db.execute(
        select(WorkflowUser).where(WorkflowUser.idp_id == idp_user_id)
    ).scalar()

    # if ID is not found, look for username: if that username is found, it means that the username exists,
    # but with _another_ ID.
    # It is asserted that this can never happen in production code.
    if user is None:
        user = db.execute(
            select(WorkflowUser).where(WorkflowUser.username == username)
        ).scalar()
        if user is not None:
            # TODO log entry
            assert user.idp_id is None
            user.idp_id = idp_user_id
            db.add(user)

    if user is None:
        user = WorkflowUser()
        user.idp_id = idp_user_id 
        db.add(user)

    # "_locale" is the actual column and "locale" is a property with fallback to the default value (see WorkflowUser class in models.py)
    if user._locale is None:
        user.locale = initial_locale or settings.default_locale

    user.username = username
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.is_service_user = is_service_user

    db.flush()
    db.expire(user)

    return user


def get_role(db: Session, name: str):
    role = db.execute(select(WorkflowRole).where(WorkflowRole.name == name)).scalar()

    return role


def upsert_role(db: Session, name: str):
    role = get_role(db=db, name=name)

    if role is None:
        role = WorkflowRole()
        role.name = name
        db.add(role)

    db.flush()

    return role


def assign_roles(db: Session, user_id: uuid.UUID, role_names: List[str]):
    user = get_user(db=db, user_id=user_id)
    assert user is not None

    current_role_names = list(
        db.execute(
            select(WorkflowRole.name)
            .join(WorkflowUserRole, WorkflowUserRole.role_id == WorkflowRole.id)
            .where(WorkflowUserRole.user_id == user.id)
        ).scalars()
    )
    to_add = set(role_names) - set(current_role_names)
    to_delete = set(current_role_names) - set(role_names)

    for role_name in to_add:
        role = upsert_role(db=db, name=role_name)
        assoc = WorkflowUserRole()
        assoc.user = user
        assoc.role = role
        db.add(assoc)

    for role_name in to_delete:
        role = get_role(db=db, name=role_name)
        assert role is not None
        db.execute(
            delete(WorkflowUserRole).where(
                and_(
                    WorkflowUserRole.user_id == user.id,
                    WorkflowUserRole.role_id == role.id,
                )
            )
        )

    db.flush()
    db.expire(user)


def search_users(
    db: Session, search: str, include_value: None | str
) -> list[WorkflowUser]:
    user_by_value = None
    if include_value is not None:
        try:
            include_value_uuid = uuid.UUID(include_value)
            user_by_value = get_user(db=db, user_id=include_value_uuid)
        except ValueError:
            log.warning(f"We received an include_value {include_value} in search_users which is not a valid UUID")

    search_results = db.execute(
        select(WorkflowUser)
        .where(
            and_(
                *[
                    or_(
                        search_uuid_by_prefix(WorkflowUser.id, word),
                        eilike(WorkflowUser.email, word),
                        eilike(WorkflowUser.first_name, word),
                        eilike(WorkflowUser.last_name, word),
                    )
                    for word in search.split()
                ]
            )
        )
        .limit(15)
    ).scalars()

    results = [x for x in search_results]

    if user_by_value is not None and user_by_value not in results:
        results.append(user_by_value)

    return results


def get_users_of_role(db: Session, role_name: str):
    try:
        role = db.execute(
            select(WorkflowRole)
            .where(
                WorkflowRole.name == role_name
            )
        ).scalar_one()

        user_role_mapping = db.execute(
            select(WorkflowUserRole)
            .where(
                WorkflowUserRole.role_id == role.id
            )
        ).scalars().all()

        users: list[UserRepresentation] = []
        for i in user_role_mapping:
            users.append(repository.load_user(db=db, user_id=i.user_id))
    except Exception as error:
        log.exception(f'{type(error).__name__}: {error.args}. Raised in get_users_of_role for role_name={role_name}, returning now an empty list of users')
        return []

    return users

def set_user_delegations(
    db: Session,
    principal_user_id: uuid.UUID,
    delegations: list[tuple[uuid.UUID, datetime.datetime | None]],
) -> None:
    principal = get_user(db=db, user_id=principal_user_id)
    if principal is None:
        raise ValueError("Principal user does not exist")

    existing = {
        d.delegate_user_id: d
        for d in db.execute(
            select(WorkflowUserDelegate)
            .options(selectinload(WorkflowUserDelegate.delegate))
            .where(WorkflowUserDelegate.principal_user_id == principal_user_id)
        ).scalars()
    }

    seen: set[uuid.UUID] = set()
    for delegate_user_id, valid_until in delegations:
        if delegate_user_id == principal_user_id:
            raise ValueError("Users cannot delegate to themselves")

        delegate = get_user(db=db, user_id=delegate_user_id)
        if delegate is None:
            raise ValueError("Delegate user does not exist")

        normalized = valid_until
        if delegate_user_id in existing:
            existing[delegate_user_id].valid_until = normalized
        else:
            record = WorkflowUserDelegate()
            record.principal_user_id = principal_user_id
            record.delegate_user_id = delegate_user_id
            record.valid_until = normalized
            db.add(record)
        seen.add(delegate_user_id)

    for delegate_user_id, record in existing.items():
        if delegate_user_id not in seen:
            db.delete(record)

    db.flush()


def list_user_delegations(db: Session, principal_user_id: uuid.UUID) -> list[WorkflowUserDelegate]:
    delegations = db.execute(
        select(WorkflowUserDelegate)
        .options(selectinload(WorkflowUserDelegate.delegate))
        .where(WorkflowUserDelegate.principal_user_id == principal_user_id)
    ).scalars().all()

    for d in delegations:
        db.expunge(d)

    return delegations


def get_active_principals_for_delegate(
    db: Session, delegate_user_id: uuid.UUID, reference_time: datetime.datetime | None = None
) -> set[uuid.UUID]:
    now = reference_time or dt_now_naive()
    principal_ids = db.execute(
        select(WorkflowUserDelegate.principal_user_id)
        .where(
            WorkflowUserDelegate.delegate_user_id == delegate_user_id,
            or_(WorkflowUserDelegate.valid_until == None, WorkflowUserDelegate.valid_until >= now),
        )
    ).scalars()
    return {pid for pid in principal_ids}


def is_active_delegate_for(
    db: Session,
    delegate_user_id: uuid.UUID,
    principal_user_id: uuid.UUID,
    reference_time: datetime.datetime | None = None,
) -> bool:
    now = reference_time or dt_now_naive()
    exists = db.execute(
        select(WorkflowUserDelegate.id)
        .where(
            WorkflowUserDelegate.principal_user_id == principal_user_id,
            WorkflowUserDelegate.delegate_user_id == delegate_user_id,
            or_(WorkflowUserDelegate.valid_until == None, WorkflowUserDelegate.valid_until >= now),
        )
    ).first()
    return exists is not None


def update_user_settings(
    db: Session,
    user_id: uuid.UUID,
    locale: str,
    delegations: list[tuple[uuid.UUID, datetime.datetime | None]] | None = None,
) -> WorkflowUser:
    user = db.execute(
        select(WorkflowUser).where(WorkflowUser.id == user_id)
    ).scalar_one()

    user.locale = locale

    if delegations is not None:
        set_user_delegations(db=db, principal_user_id=user_id, delegations=delegations)

    db.flush()
    db.expire(user)

    return user

def get_user_settings(
    db: Session,
    user_id: uuid.UUID,
) -> WorkflowUser:
    # Currently just returns the user
    return db.execute(
        select(WorkflowUser).where(WorkflowUser.id == user_id)
    ).scalar_one()
