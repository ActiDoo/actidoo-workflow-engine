import logging
import uuid
from typing import List, Sequence

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session, selectinload

from actidoo_wfe.database import eilike, search_uuid_by_prefix
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import repository
from actidoo_wfe.wf.models import WorkflowRole, WorkflowUser, WorkflowUserRole
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


def update_user_settings(
    db: Session,
    user_id: uuid.UUID,
    locale: str
) -> WorkflowUser:
    user = db.execute(
        select(WorkflowUser).where(WorkflowUser.id == user_id)
    ).scalar_one()

    user.locale = locale

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
