# ADR 006: Workflow Data REST API

**Status:** Proposed
**Date:** 2026-02-11

## Context

With Data Models (ADR 004), workflow projects can persist structured business data. The primary use case is workflow-managed data — records that are created and modified exclusively through workflows, using `WorkflowManagedMixin`. Each modification creates a new row linked to the previous one via `child_workflow_instance_id`, forming a version chain. There is currently no way to expose this data via HTTP endpoints without writing custom API routes in the engine.

## Decision Drivers

1. Adding a new workflow-managed model should optionally make it available via the API — no engine changes.
2. Workflow projects must be able to define which roles can access a model and apply row-level filters.
3. Row-level filtering must not depend on engine-internal table schemas.
4. All list endpoints must support pagination with globally configurable defaults.
5. The API must provide column metadata so frontends can render data tables dynamically.

## Considered Options

### Custom endpoints per workflow project

Each workflow project writes its own FastAPI routes for its data models. This gives full control over the API shape, but every project must implement pagination, authorization, and serialization from scratch. There is no unified pattern for the frontend to build on, and each project is individually responsible for getting security right.

### Generated Router (one set of routes per model at startup)

The engine generates a dedicated set of routes per registered model at startup, producing typed request/response schemas in the OpenAPI spec. The tradeoff is more complex startup wiring — models must be registered before the router is mounted — and many routes to maintain.

### Dynamic Router (resolves models at runtime via registry)

Three fixed endpoints resolve models at runtime via the Data Model Registry. The tradeoff is that the OpenAPI spec only describes generic responses — no per-model types — and input validation beyond what the URL path provides must happen in application code.

## Decision

We use a **dynamic router** with three read-only endpoints scoped to workflow-managed data. Only models that use `WorkflowManagedMixin` and provide an `api` configuration are exposed.

### API configuration

The `@register_data_model` decorator accepts an optional `api` parameter with `read_roles`, `row_filter`, and `fields`. Models without `api` are not exposed. Models that provide `api` but don't use `WorkflowManagedMixin` are rejected at registration time.

### Endpoints

- `GET /bff/user/workflow-data` — list workflow-data models the current user can access, including column metadata.
- `GET /bff/user/workflow-data/{model_name}` — list rows (paginated). Always returns only the latest version of each entity (`child_workflow_instance_id IS NULL`).
- `GET /bff/user/workflow-data/{model_name}/{workflow_instance_id}` — get the full version chain for a single entity.

Column metadata (names, types, nullability) is derived from the SQLAlchemy model via inspection — no manual schema files needed. Mixin columns (`parent_workflow_instance_id`, `child_workflow_instance_id`, `action`) are excluded from the column metadata by default — they are system-level concerns, not user-facing data.

### Authorization

`read_roles` controls who can access the endpoint at all. `row_filter` narrows the result set per user — for example, managers see all rows while other roles only see rows from workflows they participated in. Access-control-relevant data (e.g. `created_by`) lives in the data model itself, written by the workflow when creating the record — no JOINs on engine tables needed.

### Fields and virtual fields

By default, the API exposes all database columns except the mixin system columns. The `fields` parameter controls which fields appear and in what order. `VirtualField` entries define computed values — each specifies a name, type, and callable.

`VirtualField` types follow the JSON Schema primitives so frontends know how to render each field:

| Type | Python output | Frontend rendering |
|------|--------------|-------------------|
| `string` | `str` | Text |
| `integer` | `int` | Number (no decimals) |
| `number` | `float` / `Decimal` | Number (with decimals) |
| `boolean` | `bool` | Yes/No, badge, checkbox |
| `datetime` | `str` (ISO 8601) | Locale-formatted date/time |
| `array` | `list[dict]` | Expandable list / subtable |

### Examples

Minimal — expose all database columns to any authenticated user:

```python
@register_data_model(
    name="PurchaseRequest",
    api=WorkflowDataApiConfig(),
)
class PurchaseRequest(MyModel, WorkflowManagedMixin):
    _ext_table = "purchase_request"
    ...
```

With role restrictions, row filtering, field selection, and virtual fields:

```python
@register_data_model(
    name="PurchaseRequest",
    api=WorkflowDataApiConfig(
        read_roles=["manager", "requester"],
        row_filter=request_row_filter,
        fields=[
            "workflow_instance_id",
            "item_description",
            "amount",
            "status",
            "created_at",
            # Computed: no DB column, type tells the frontend how to render
            VirtualField("is_high_value", type="boolean",
                         value=lambda row: row.amount > 10_000),
            VirtualField("total", type="number",
                         value=lambda row: row.amount * row.quantity),
            VirtualField("period", type="string",
                         value=lambda row:
                             f"{row.start_date:%d.%m.%Y} – {row.end_date:%d.%m.%Y}"
                             if row.start_date and row.end_date else None),
            VirtualField("line_items", type="array",
                         value=lambda row: [
                             {"description": li.description, "amount": li.amount}
                             for li in row.line_items
                         ]),
        ],
    ),
)
class PurchaseRequest(MyModel, WorkflowManagedMixin):
    _ext_table = "purchase_request"
    ...
```

Virtual fields can expose SQLAlchemy relationships; using `lazy="selectin"`, related rows are loaded in a single query for the entire page, not one per row.

### Pagination

Page size defaults and limits are configured globally in the engine settings, not per model.

## Consequences

Workflow projects expose workflow-managed data via the API by adding a parameter to the decorator — no engine changes needed. The API is scoped to `WorkflowManagedMixin` models, which means the version-chain semantics (latest version by default, full chain on detail) are built in rather than conditional. Authorization is code-based and decoupled from engine internals. All models share the same pagination settings. Frontends can render data tables dynamically from column metadata, including virtual fields. Mixin system columns are hidden by default, keeping the API focused on business data. The tradeoff is that responses are generic dictionaries, not typed per model, and models without `WorkflowManagedMixin` cannot use this API.
