# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from __future__ import annotations

import inspect
import logging
import pathlib
from dataclasses import dataclass
from typing import Callable, Dict, List

import venusian
from sqlalchemy import inspect as sa_inspect

from actidoo_wfe.wf.config_data_model import WorkflowDataApiConfig
from actidoo_wfe.wf.exceptions import DataModelNotFoundError
from actidoo_wfe.wf.models import VersionedMixin, WorkflowManagedMixin

log = logging.getLogger(__name__)


# eq=False keeps object-identity ``__eq__``/``__hash__``: ``api`` holds lists and
# callables, so a field-based hash is impossible — and identity is the semantics
# callers rely on (descriptors are registry-managed singletons; per-descriptor
# lru_caches must invalidate when a re-registration creates a new instance).
@dataclass(frozen=True, eq=False)
class DataModelDescriptor:
    name: str
    model_class: type
    namespace: str
    api: WorkflowDataApiConfig | None = None
    # Whether the model is versioned (``VersionedMixin``): drives head selection
    # (``is_current``) and the version-chain endpoint. Non-versioned models have a
    # single row per ``id`` and no history.
    is_versioned: bool = False
    # Directory of the module declaring the model. Its ``i18n/locales/<locale>/
    # LC_MESSAGES/<name>.mo`` catalog resolves the declared labels (msgids) to the
    # requesting user's locale — same toolchain as the per-workflow catalogs.
    i18n_dir: pathlib.Path | None = None


class DataModelRegistry:
    def __init__(self) -> None:
        self._models: Dict[str, DataModelDescriptor] = {}

    def register(self, descriptor: DataModelDescriptor) -> None:
        existing = self._models.get(descriptor.name)
        if existing is not None:
            if existing.model_class is descriptor.model_class:
                return  # dedup
            raise ValueError(
                f"Data model '{descriptor.name}' already registered with a different model class (existing: {existing.model_class.__name__}, new: {descriptor.model_class.__name__})",
            )
        self._models[descriptor.name] = descriptor
        log.debug("Registered data model %r (namespace=%s, table=%s)", descriptor.name, descriptor.namespace, getattr(descriptor.model_class, "__tablename__", "?"))

    def get(self, name: str) -> DataModelDescriptor:
        try:
            return self._models[name]
        except KeyError:
            raise DataModelNotFoundError(
                f"Data model '{name}' is not registered. Available: {sorted(self._models)}",
            ) from None

    def list_names(self) -> List[str]:
        return sorted(self._models)

    def list_models(self) -> List[DataModelDescriptor]:
        return list(self._models.values())

    def descriptors_for_class(self, model_class: type) -> List[DataModelDescriptor]:
        """All descriptors registered for exactly this class (identity match).

        A class may be registered under several names; subclasses are excluded.
        Used by the data-model file materializer to resolve a row's registered
        name(s) at flush time.
        """
        return [d for d in self._models.values() if d.model_class is model_class]

    def name_for_class(self, model_class: type) -> str | None:
        """The registered name of *model_class*, or ``None`` if unregistered.

        When a class is registered under several names the first is returned;
        file fields are model-scoped, so the common single-registration case is
        unambiguous.
        """
        descriptors = self.descriptors_for_class(model_class)
        return descriptors[0].name if descriptors else None

    def validate_action_targets(self, *, workflow_exists: Callable[[str], bool]) -> List[str]:
        """Return an error string for every ``ActionDef`` whose target cannot be loaded.

        The api config is validated at registration time (``_validate_api``),
        but an action's ``target`` references another workflow that may not be
        scanned yet, so it is checked post-scan instead — called from the app
        lifespan, with ``workflow_exists`` injected so the registry stays free of
        the workflow domain. A non-empty result is a fail-fast configuration error
        (a mistyped target would otherwise only surface as a 500 when the action
        is triggered).
        """
        errors: List[str] = []
        for data_model in self.list_models():
            actions = data_model.api.actions if data_model.api else []
            for action in actions:
                if not workflow_exists(action.target):
                    errors.append(
                        f"Data model '{data_model.name}' action '{action.key}' targets "
                        f"unknown workflow '{action.target}'.",
                    )
        return errors

    def clear(self) -> None:
        self._models.clear()


data_model_registry = DataModelRegistry()


def create_registered_data_model_tables(engine) -> None:
    """Create the DB tables of all currently registered data models (idempotent).

    Used for dev/test only: bundled demo data models (under ``wf/testdata``) have
    no Alembic migration, and the main ``create_all`` runs before the venusian
    scan registers them. Real extension models ship their own migrations and are
    a no-op here thanks to ``checkfirst=True``. Callers must gate this on
    ``settings.show_test_workflows`` so it never runs in production.
    """
    for descriptor in data_model_registry.list_models():
        descriptor.model_class.__table__.create(bind=engine, checkfirst=True)


def _validate_api(name: str, model_class: type, api: WorkflowDataApiConfig | None) -> None:
    """Fail fast on an invalid API config.

    ``read_roles``: read access is deny-by-default — the list must name roles or
    contain ``READ_ALL_WORKFLOW_USERS`` explicitly, so a model can never become
    readable to everyone by accident.

    ``fields``: a mistyped field name would otherwise drop silently from the
    schema while still surfacing as ``None`` in the row data — exactly the drift
    a single typed declaration is meant to prevent. Computed fields
    (``compute=...``) have no column and are skipped.
    """
    if api is None:
        return
    if not api.read_roles:
        raise ValueError(
            f"Data model '{name}': read_roles must not be empty — name the roles that may read "
            f"the model, or open it to every workflow user explicitly with "
            f"read_roles=[READ_ALL_WORKFLOW_USERS].",
        )
    if api.fields is None:
        return
    columns = {col.key for col in sa_inspect(model_class).columns}
    for field in api.fields:
        if field.type == "file" and field.is_computed:
            raise ValueError(
                f"Data model '{name}': FieldDef('{field.name}') is a computed file field. "
                f"File fields are framework-managed (their references live in the "
                f"data_model_files side table and are written via sth.attach_files); they "
                f"cannot be computed. Remove compute=... or change the field type.",
            )
        if field.is_computed:
            continue
        if field.type == "file":
            # File fields are framework-managed virtual fields with no backing column.
            continue
        if field.name not in columns:
            raise ValueError(
                f"Data model '{name}': FieldDef('{field.name}') matches no column of "
                f"{model_class.__name__} (columns: {sorted(columns)}). Fix the name or set "
                f"compute=... for a computed field.",
            )


def register_data_model(
    *,
    name: str,
    api: WorkflowDataApiConfig | None = None,
):
    """Decorator to register a data model class.

    Usage::

        @register_data_model(name="OrderApproval")
        class OrderApproval(AcmeModel):
            _ext_table = "order_approval"
            ...

    If *api* is provided, the model must use ``WorkflowManagedMixin`` — BFF
    exposure is for workflow-produced, displayable records (stable ``id`` +
    versioning + provenance + reserved ``title``). Plain ``DataModelMixin`` /
    ``VersionedMixin`` models stay internal (no api).
    """

    def decorator(model_class: type) -> type:
        if api is not None and not issubclass(model_class, WorkflowManagedMixin):
            raise TypeError(
                f"Data model '{name}' provides an api config but does not use WorkflowManagedMixin. "
                f"Only workflow-managed data models (stable id + versioning + provenance + title) "
                f"can be exposed via the BFF API.",
            )

        if issubclass(model_class, WorkflowManagedMixin):
            # ``title`` is the reserved record title from WorkflowManagedMixin. A
            # model declaring its own ``title`` column wins via MRO and silently
            # shadows it (different type/length, not projected/searched as
            # intended) — fail fast at registration instead.
            title_col = sa_inspect(model_class).columns["title"]
            if not title_col.info.get("wfe_reserved_title"):
                raise TypeError(
                    f"Data model '{name}': {model_class.__name__} declares its own 'title' column, "
                    f"which shadows the reserved record title from WorkflowManagedMixin (String(200), "
                    f"nullable). Remove the model's own column and write the mixin's 'title' "
                    f"instead, or rename the business column.",
                )

        _validate_api(name, model_class, api)

        namespace = getattr(model_class, "_ext_namespace", "")
        try:
            i18n_dir = pathlib.Path(inspect.getfile(model_class)).parent
        except (TypeError, OSError):  # dynamically created classes (tests)
            i18n_dir = None
        descriptor = DataModelDescriptor(
            name=name,
            model_class=model_class,
            namespace=namespace,
            api=api,
            is_versioned=issubclass(model_class, VersionedMixin),
            i18n_dir=i18n_dir,
        )

        def callback(scanner, _name, _ob):
            data_model_registry.register(descriptor)

        venusian.attach(model_class, callback)
        data_model_registry.register(descriptor)
        return model_class

    return decorator


# Importing the registry is the one thing every data-model definition does (the
# decorator and sth.get_model both live off it), so importing the file
# materializer here makes its before_flush listener present in every process that
# can write data-model rows. ``models`` is imported at the top of this module, so
# ``_assign_versions`` registers before the materializer — the ordering its
# (id, version) read depends on.
import actidoo_wfe.wf.data_model_files  # noqa: E402,F401
