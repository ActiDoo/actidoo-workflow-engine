# ADR 006: Workflow Data REST API

**Status:** Proposed
**Date:** 2026-02-11
**Updated:** 2026-06-11

## Context

With Data Models (ADR 004) and their migrations (ADR 005), workflow projects can persist structured business data. The first use case is workflow-managed data — records created and modified exclusively through workflows, where every change is kept as a new version. Further use cases will follow, for example workflow configuration maintained by the workflow's owner, or lookup lists feeding form dropdowns; these are edited directly and need no version history.

This data has no HTTP surface of its own; without one, every frontend feature on top of it requires custom routes in the engine. What a model exposes must be configurable per data model, by the workflow project that owns it: who may read it, which fields it presents and how, and what can be done with its rows. The first consumer is a generic data viewer that renders models as tables. Across all these use cases a record needs a stable identity of its own — one that does not change when it is edited and does not depend on a workflow — while only some of them are versioned.

## Decision Drivers

1. Adding a new workflow-managed model should optionally make it available via the API — no engine changes.
2. Access is defined per model by the owning workflow project — read roles plus row-level filters — and is deny-by-default: exposing a model, even to all workflow users, must be an explicit decision.
3. The API must deliver the field schema alongside the rows, so frontends can render any model generically.
4. There must be one central, typed, reviewable declaration point for the model's presentation and its follow-up workflows — co-located with the model, with the same lifecycle.
5. Whether a follow-up workflow is available must be decidable per row at the DB level, so eligibility can drive filtering, counts and pagination rather than being a post-hoc per-row check.
6. Every exposed record needs a stable identity of its own that survives edits; versioning is needed for workflow-managed data but not for every data model.

## Considered Options

### Router shape

**Custom endpoints per workflow project.** Each workflow project writes its own FastAPI routes for its data models. This gives full control over the API shape, but every project must implement pagination, authorization, and serialization from scratch. There is no unified pattern for the frontend to build on, and each project is individually responsible for getting security right.

**Generated router (one set of routes per model at startup).** The engine generates a dedicated set of routes per registered model at startup, producing typed request/response schemas in the OpenAPI spec. The tradeoff is more complex startup wiring — models must be registered before the router is mounted — and many routes to maintain.

**Dynamic router (resolves models at runtime via registry).** Fixed endpoints resolve models at runtime via the Data Model Registry. The tradeoff is that the OpenAPI spec only describes generic responses — no per-model types — and input validation beyond what the URL path provides must happen in application code.

### Declaration of presentation and actions

**Separate UI-schema JSON files.** The presentation/table schema lives in standalone JSON files per model and is shipped to the frontend as-is. This decouples the schema from the model definition: it drifts from the actual columns over time, and server-evaluated concerns — such as whether a follow-up workflow is allowed on a given row — cannot be expressed in a static file.

**Declaration at the data model.** The field schema and the follow-up workflows are declared, typed, in the model's `api` configuration, next to the model and with the same lifecycle. There is one source of truth; the wire schema the frontend receives is projected from it.

### Record identity and versioning

**Identity is the writing workflow instance.** A workflow-managed row is keyed by the workflow instance that wrote it, and history is a chain of such rows linked by parent/child pointers. Identity costs no extra column, but it is not stable — every edit yields a new key, so nothing outside can refer to "the record" — and the pointer chain is a bespoke structure to walk and to guard against cycles. It also only fits workflow-managed data; a config table has no workflow instance to borrow a key from.

**Stable surrogate id, versioning opt-in.** Every data model carries its own surrogate `id`; workflow-managed models additionally version themselves by appending rows that share that `id`. Identity is stable across edits and uniform across all model kinds, and history is an ordered set of versions instead of a pointer chain. The cost is one extra column plus, for versioned models, a small write-time bookkeeping step.

## Decision

We use a **dynamic router** with read-only endpoints over the data models. Only models that provide an `api` configuration are exposed; they must use `DataModelMixin` (so every exposed record has a stable `id`). The model is resolved from the registry at request time, and each request builds its sortable/filterable query schema from the typed field schema — the declaration drives the frontend through the projected wire schema rather than through a per-model route surface, so no startup route-generation step is needed.

### Identity and versioning

Every exposed model uses `DataModelMixin`, giving it a stable surrogate `id` — its own identity, independent of any workflow. Workflow-managed models additionally use `VersionedMixin`: each change appends a row sharing the record's `id` with the next `version`, the current row is flagged `is_current`, and the workflow instance that produced a version is kept as provenance rather than as identity. Versioning is additive — a non-versioned model (a config or lookup table) is just `DataModelMixin`, one row per `id`.

The API exposes `id` uniformly for every model; the listing returns the current row and the detail endpoint returns the version history, both branching on whether the model is versioned. Writers use plain ORM — adding a row with a new `id` creates a record, adding one with an existing `id` appends a version — and a flush-time hook assigns `version`/`is_current`, so service code never hand-rolls the versioning bookkeeping.

### Record title

Besides the surrogate `id`, every data model carries a reserved, nullable `title` column on `DataModelMixin` — the record's human-readable name. Workflows write it like any business column; the API always projects it into the row data and always includes it in the global search and sorting, even when the model does not declare it as a display field, so every record stays speakable and findable. A model declaring its own `title` column would silently shadow the reserved one, so registration rejects it (fail-fast with a clear message) — for existing extension models this is a breaking change: own `title` columns must be renamed, and models without one need a migration (ADR 005) to add the column.

### Endpoints

- `GET /bff/user/workflow-data` — list the data models the current user can access, including the field schema.
- `GET /bff/user/workflow-data/{model_name}` — list rows (paginated). Returns the current row per record (the head version, for versioned models).
- `GET /bff/user/workflow-data/{model_name}/{id}` — the version history for one record (a single row for non-versioned models).

Executing an action is conceptually a workflow start that happens to be seeded with an existing row's data, so it lives with the workflow-start endpoints rather than in the data API, and it reuses the existing start service — the target workflow's own initiator roles still apply on top of the action's `row_filter`.

System columns — `version`, `is_current`, the provenance workflow instance, `action`, `created_at` — are excluded from the field schema by default. The stable `id` stays, since it is the record's identity.

### Label localization

Declared labels (model, fields, actions) are gettext msgids, resolved server-side to the requesting user's locale against the data model's own Babel catalog (`i18n/locales/<locale>/LC_MESSAGES/<name>.mo` next to the model module) — the same extraction/update/compile toolchain the workflows use, extended by data-model CLI commands. The alternative, per-locale dicts at the declaration, was rejected: it would introduce a second i18n mechanism beside gettext and move translations out of the `.po` files translators work with. The wire schema always carries plain strings; a missing catalog or translation falls back to the msgid.

### Authorization

Read access is **deny-by-default**. `read_roles` is mandatory and must not be empty: either it names the roles that may read the model, or it opens the model to every workflow user explicitly via the wildcard `*`. A forgotten declaration fails at import time, an empty list at registration — a model can never become readable to everyone by accident; opening it is a greppable, reviewable statement.

`row_filter` narrows the result set per user — for example, managers see all rows while other roles only see rows from workflows they participated in. Access-control-relevant data (e.g. `created_by`) lives in the data model itself, written by the workflow when creating the record — no JOINs on engine tables needed.

### Examples

Minimal — expose all database columns, readable by every workflow user (explicitly):

```python
@register_data_model(
    name="PurchaseRequest",
    api=WorkflowDataApiConfig(read_roles=[READ_ALL_WORKFLOW_USERS]),
)
class PurchaseRequest(MyModel, VersionedMixin):
    _ext_table = "purchase_request"
    ...
```

With role restrictions, row filtering, typed fields, and a follow-up action:

```python
@register_data_model(
    name="PurchaseRequest",
    api=WorkflowDataApiConfig(
        read_roles=["manager", "requester"],
        row_filter=request_row_filter,
        # declared properties are authoritative, everything else is inferred from
        # the column; types are semantic (decimal, file, ...), not database types
        fields=[
            FieldDef("id", label="Request"),
            FieldDef("item_description", label="Item"),
            # format: presentation hint a DB type can't express
            FieldDef("amount", type="decimal", format="currency:EUR", label="Amount"),
            FieldDef("attachments", type="file", label="Documents"),
            # computed — no DB column
            FieldDef("is_high_value", type="boolean", label="High value",
                     compute=lambda row: (row.amount or 0) > 10_000),
        ],
        # follow-up workflows, delivered per row; availability is decided by the
        # same (query, db, user) -> query filter shape as the read row_filter
        actions=[
            ActionDef(key="approve", label="Approve", target="PurchaseApproval",
                      row_filter=lambda q, db, user: requires_role("approver")(q, db, user)
                      .where(PurchaseRequest.status == "open")),
        ],
    ),
)
class PurchaseRequest(MyModel, VersionedMixin):
    _ext_table = "purchase_request"
    ...
```

### Pagination

Page size defaults and limits are configured globally in the engine settings, not per model.

## Consequences

Workflow projects expose data via the API by adding a parameter to the decorator — no engine changes needed. Every record carries a stable `id`, so the frontend, deep links and integrations can refer to it across edits; identity is uniform whether or not a model is versioned, so config and lookup models — not just workflow-managed ones — can use the same API. Workflow-managed models get versioning for free: writers add plain rows and a flush-time hook maintains the chain, so there is no bespoke pointer bookkeeping to get wrong. Authorization is code-based, deny-by-default, and decoupled from engine internals; a model cannot become readable to everyone by accident. All models share the same pagination settings.

The frontend receives a semantic, typed field schema and, per row, the follow-up workflows available on it; data tables render dynamically from the declaration, including computed fields. System columns are hidden by default, keeping the API focused on business data.

The tradeoff of the dynamic router is that responses are generic dictionaries, not typed per model; the query schema is built per request from the declaration instead of being part of the OpenAPI specification.
