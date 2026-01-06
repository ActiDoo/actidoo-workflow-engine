# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Sequence, Set

import venusian
from sqlalchemy import select
from sqlalchemy.orm import Session

from actidoo_wfe.helpers.time import dt_now_naive
from actidoo_wfe.wf.models import WorkflowUser, WorkflowUserClaim

log = logging.getLogger(__name__)

ProviderCallable = Callable[["AttributeProviderContext"], dict[str, Any] | None]


@dataclass
class AttributeProviderContext:
    user: WorkflowUser
    claims: dict[str, Any]
    access_token: dict[str, Any] | None
    db: Session


@dataclass
class RegisteredProvider:
    keys: Set[str]
    needs: Set[str]
    source_name: str
    fn: ProviderCallable


_providers: list[RegisteredProvider] = []


def clear_user_attribute_providers() -> None:
    """Testing helper to reset provider registry."""
    _providers.clear()


def _register_provider(keys: Set[str], needs: Set[str], source_name: str, fn: ProviderCallable) -> None:
    if any(entry.fn is fn for entry in _providers):
        return
    _providers.append(
        RegisteredProvider(
            keys=keys,
            needs=needs,
            source_name=source_name,
            fn=fn,
        )
    )


def register_user_attribute_provider(
    *,
    keys: Sequence[str],
    needs: Sequence[str] | None = None,
    source_name: str | None = None,
) -> Callable[[ProviderCallable], ProviderCallable]:
    """Register a provider that can enrich users with additional attributes on login.

    Registration happens twice:
    - immediately (for tests/direct imports)
    - deferred via venusian (picked up when the engine scans extension modules)
    """
    if not keys:
        raise ValueError("keys must contain at least one entry")
    needs_set = {entry for entry in (needs or []) if entry}
    keys_set = {entry for entry in keys if entry}

    def decorator(fn: ProviderCallable) -> ProviderCallable:
        name = source_name or fn.__name__

        def callback(scanner, _name, _ob):
            _register_provider(keys=keys_set, needs=needs_set, source_name=name, fn=fn)

        venusian.attach(fn, callback)
        _register_provider(keys=keys_set, needs=needs_set, source_name=name, fn=fn)
        return fn

    return decorator


def _available_needs(access_token: dict[str, Any] | None) -> Set[str]:
    available = set()
    if access_token:
        available.add("access_token")
    return available


def resolve_user_attributes_on_login(
    *,
    db: Session,
    user: WorkflowUser,
    claims: dict[str, Any],
    access_token: dict[str, Any] | None,
) -> None:
    """Execute registered providers and persist returned user attributes."""
    context = AttributeProviderContext(
        user=user, claims=claims or {}, access_token=access_token, db=db
    )
    available = _available_needs(access_token)
    for provider in list(_providers):
        missing = provider.needs - available
        if missing:
            log.debug(
                "Skipping user attribute provider %s (missing needs: %s)",
                provider.source_name,
                ",".join(sorted(missing)),
            )
            continue

        try:
            data = provider.fn(context)
        except Exception:
            log.exception("User attribute provider %s failed", provider.source_name)
            continue

        if not data:
            continue
        if not isinstance(data, dict):
            log.warning(
                "User attribute provider %s returned non-dict %r",
                provider.source_name,
                type(data),
            )
            continue

        filtered = _filter_keys(data=data, allowed_keys=provider.keys)
        if not filtered:
            continue
        _persist_claims(
            db=db,
            user_id=user.id,
            values=filtered,
            source_name=provider.source_name,
        )


def _filter_keys(data: Dict[str, Any], allowed_keys: Iterable[str]) -> Dict[str, Any]:
    allowed = set(allowed_keys)
    return {
        key: value
        for key, value in data.items()
        if value is not None and (not allowed or key in allowed)
    }


def _persist_claims(
    *,
    db: Session,
    user_id,
    values: Dict[str, Any],
    source_name: str,
) -> None:
    keys = list(values.keys())
    existing = {
        claim.claim_key: claim
        for claim in db.execute(
            select(WorkflowUserClaim).where(
                WorkflowUserClaim.user_id == user_id,
                WorkflowUserClaim.claim_key.in_(keys),
            )
        ).scalars()
    }

    now = dt_now_naive()

    for key, value in values.items():
        claim = existing.get(key)
        if claim is None:
            claim = WorkflowUserClaim(user_id=user_id, claim_key=key)
            db.add(claim)
        claim.claim_value = value
        claim.source_name = source_name
        claim.fetched_at = now

    db.flush()
