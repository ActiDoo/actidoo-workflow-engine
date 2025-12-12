import json
import logging
import uuid

import pytest

import actidoo_wfe.wf.bff.bff_user_schema as bff_user_schema
from actidoo_wfe.database import SessionLocal, setup_db
from actidoo_wfe.settings import settings
from actidoo_wfe.wf import service_form, service_user, service_i18n
from actidoo_wfe.wf.tests.helpers.client import Client
from actidoo_wfe.wf.tests.helpers.workflow_dummy import WorkflowDummy
from sqlalchemy.exc import StatementError

log: logging.Logger = logging.getLogger(__name__)

setup_db(settings=settings)


# TODO out-commented for now, because get_workflow now expects a user-authorization
# def test_get_workflows(db_engine_ctx):
#     with db_engine_ctx():
#         client = Client()
#         status, json_resp = client.get("get_workflows", bff_user_schema.GetWorkflowsResponse)
#         assert len(json_resp.workflows) > 0


def test_user_roles(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"user1": ["role1", "role2"], "user2": ["role2"]},
        )

        user1 = service_user.get_user(db=db, user_id=workflow.user("user1").user.id)
        assert user1 is not None
        assert "role1" in [r.role.name for r in user1.roles]
        assert "role2" in [r.role.name for r in user1.roles]

        user2 = service_user.get_user(db=db, user_id=workflow.user("user2").user.id)
        assert user2 is not None
        assert "role1" not in [r.role.name for r in user2.roles]
        assert "role2" in [r.role.name for r in user2.roles]

        service_user.assign_roles(db=db, user_id=user1.id, role_names=["role2", "role3"])

        user1 = service_user.get_user(db=db, user_id=workflow.user("user1").user.id)
        assert user1 is not None
        assert "role1" not in [r.role.name for r in user1.roles]
        assert "role2" in [r.role.name for r in user1.roles]
        assert "role3" in [r.role.name for r in user1.roles]

        user2 = service_user.get_user(db=db, user_id=workflow.user("user2").user.id)
        assert user2 is not None
        assert "role1" not in [r.role.name for r in user2.roles]
        assert "role2" in [r.role.name for r in user2.roles]


def test_search_users(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={
                "userA1": [],
                "userA2": [],
                "userA3": [],
                "userB4": [],
                "userB5": [],
                "userB6": [],
                "user kurt": [],
            },
        )

        results = service_user.search_users(db=db, search="user", include_value=None)

        # alle finden
        assert any(r.id == workflow.user("userA1").user.id for r in results)
        assert len(results) == 7

        # kein ergebnis
        results = service_user.search_users(db=db, search="abcdef", include_value=None)
        assert len(results) == 0

        # prefix suche
        results = service_user.search_users(db=db, search="userA", include_value=None)
        assert len(results) == 3

        # contains
        results = service_user.search_users(db=db, search="A3", include_value=None)
        assert len(results) == 1

        # multi word suche
        results = service_user.search_users(db=db, search="user kur", include_value=None)
        assert len(results) == 1

        # ID prefix suche
        results = service_user.search_users(
            db=db,
            search=str(workflow.user("userA1").user.id)[:5],
            include_value=None,
        )
        assert len(results) == 1

        # kein suchergebnis, aber include_value
        results = service_user.search_users(
            db=db,
            search="mööööh",
            include_value=str(workflow.user("userA1").user.id),
        )
        assert len(results) == 1

        # suchergebnis + include_value, aber nur ein result darf gefunden werden
        results = service_user.search_users(
            db=db,
            search=str(workflow.user("userA1").user.id)[:5],
            include_value=str(workflow.user("userA1").user.id),
        )
        assert len(results) == 1


def test_remove_datauri(db_engine_ctx):
    # This is an adjusted source from real data.
    # I kept it deeply nested and kept a lot more than the 'datauri' field,
    # with lists/objects/strings/bools as values, to thoroughly test the correct parsing.
    schema = {
        "definitions": {},
        "type": "object",
        "properties": {
            "travel_approver": True,
            "attachments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "datauri": {"type": "string", "format": "data-url"},  # this must be removed
                        "filename": {"type": "string"},
                        "hash": {"type": "string"},
                        "id": {"type": "string"},
                        "mimetype": {"type": "string"},
                    },
                },
            },
            "department_approver": {
                "type": "string",
                "title": "Select your department.",
            },
        },
        "required": [
            "mail_header",
            "travel_region",
        ],
        "allOf": [
            {
                "if": {
                    "not": {
                        "not": {
                            "type": "object",
                            "properties": {"travel_region": {"const": "sonstiges", "default": ""}},
                        }
                    }
                },
                "else": {
                    "properties": {"travel_approver": {"type": "null"}},
                    "type": "object",
                },
            }
        ],
    }

    expected_transformation = {
        "definitions": {},
        "type": "object",
        "properties": {
            "travel_approver": True,
            "attachments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        # "datauri": {"type": "string", "format": "data-url"},
                        "filename": {"type": "string"},
                        "hash": {"type": "string"},
                        "id": {"type": "string"},
                        "mimetype": {"type": "string"},
                    },
                },
            },
            "department_approver": {
                "type": "string",
                "title": "Select your department.",
            },
        },
        "required": [
            "mail_header",
            "travel_region",
        ],
        "allOf": [
            {
                "if": {
                    "not": {
                        "not": {
                            "type": "object",
                            "properties": {"travel_region": {"const": "sonstiges", "default": ""}},
                        }
                    }
                },
                "else": {
                    "properties": {"travel_approver": {"type": "null"}},
                    "type": "object",
                },
            }
        ],
    }

    service_form.remove_data_uri_fields(schema)

    assert expected_transformation == schema


def test_update_user_settings_success(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        # set up two users with roles (roles not used here, but WorkflowDummy creates users)
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"user1": ["role1", "role2"], "user2": ["role2"]},
        )
        user = workflow.user("user1").user  # get the WorkflowUser model
        # perform the update
        updated = service_user.update_user_settings(
            db=db,
            user_id=user.id,
            locale="fr-FR",
        )
        # assertions
        assert updated.id == user.id
        assert updated.locale == "fr-FR"

        # verify persisted
        reloaded = service_user.get_user_settings(db=db, user_id=user.id)
        assert reloaded.locale == "fr-FR"


def test_update_user_settings_invalid_locale(db_engine_ctx):
    with db_engine_ctx():
        db = SessionLocal()
        workflow = WorkflowDummy(
            db_session=db,
            users_with_roles={"userA": []},
        )
        user = workflow.user("userA").user

        with pytest.raises(ValueError):
            service_user.update_user_settings(
                db=db,
                user_id=user.id,
                locale="xx-XX",  # invalid # type: ignore
            )

@pytest.mark.parametrize(
    "header,expected",
    [
        # exact primary extraction
        ("en-US,en;q=0.9", "en-US"),
        ("de-DE;q=0.9,en;q=0.8", "de-DE"),
        # without country will not match any
        ("fr;q=0.9,en;q=0.8", None),
        # no valid entries
        ("es,pt;q=0.9", None),
        ("", None),
        ("not-a-header", None),
        # without country will not match any
        ("en;q=0.5,en;q=0.9", None), 
        # case preserved
        ("EN-US,en;q=0.9", "en-US"),
        ("DE-DE,de;q=0.9", "de-DE"),
        # malformed segments ignored
        (" , ;q=,de-DE;q=not,aabb;;q=0.5,en-US", "en-US"),
    ],
)
def test_extract_primary_locale(header, expected):
    assert service_i18n.extract_primary_locale(header) == expected


@pytest.mark.parametrize(
    "user_locale,available,default,expected",
    [
        # 1. exact match
        ("en-US", ["en", "de"], "de", "en"),
        # 2. fallback region→base
        ("de-DE", ["de", "en"], "en", "de"),
        # 3. language-only match
        ("fr", ["en", "fr"], "en", "fr"),
        # 4. no match→default
        ("es", ["en", "de"], "en", "en"),
        # 5. direct base match
        ("de", ["de", "en"], "en", "de"),
        # 6. single available
        ("en", ["en"], "de", "en"),
        # 7. region-specific supported
        ("en-GB", ["en-GB", "en"], "en", "en-GB"),
        # 8. case-insensitive fallback
        ("EN-us", ["en-US", "en"], "en", "en-US"),
    ],
)
def test_match_translation(user_locale, available, default, expected, monkeypatch):
    # configure default fallback
    monkeypatch.setattr(settings, "default_locale", default)

    result = service_i18n.match_translation(user_locale=user_locale, available=available)
    assert result == expected, (
        f"match_translation({user_locale!r}, {available}, default={default!r}) -> {result!r}, "
        f"expected {expected!r}"
    )