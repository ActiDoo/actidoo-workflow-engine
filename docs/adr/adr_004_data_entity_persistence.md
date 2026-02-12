# ADR 004: Data Model Persistence

**Status:** Proposed
**Date:** 2026-02-11

## Context

Workflow projects often need to store business data alongside their workflows — for example, approval records or service requests. This data outlives individual workflow instances and may need to be queried on its own. Projects should be able to define their own data models without changing the engine.

## Decision Drivers

1. Project data should live in the same database and transaction as the engine — if a service task fails, all writes roll back together.
2. Project tables must not collide with engine tables or tables from other projects.
3. Workflows should explicitly declare which data models they access.

## Considered Options

### Separate Database for Business Data

Projects store their business data in a second database, separate from the engine. This gives full isolation, but adds operational overhead (connection pooling, backup, monitoring) and makes shared transactions with the engine difficult.

### Shared Database with Table Prefixing and Registry

Project tables live in the engine's database with a naming convention to avoid collisions. Simpler to operate and keeps everything in one transaction, but requires discipline around table naming.

## Decision

We introduce a **Data Model** extension point. All project data lives in the engine's database, in prefixed tables that don't collide with engine tables. Writes share the request transaction — if a service task fails, everything rolls back. Projects work directly with SQLAlchemy for all data access.

### Example

**1. Define a model** — create a base class with a namespace, then define models using SQLAlchemy:

```python
# models/__init__.py
from actidoo_wfe.data_models import extension_model_base

# All models in this project get the "mycompany" namespace
MyModel = extension_model_base("mycompany")
```

```python
# models/approval.py
from actidoo_wfe.data_models import register_data_model
from myworkflows.models import MyModel

@register_data_model(name="Approval")
class Approval(MyModel):
    _ext_table = "approval"       # → table name: ext_mycompany_approval

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

**2. Use it in a workflow** — declare dependencies and use SQLAlchemy via the task helper's database session:

```python
# workflows/ApprovalProcess/__init__.py

# Declare which data models this workflow uses.
# Access to undeclared models raises an error.
DATA_MODELS = ["Approval"]

def service_create_approval(sth: ServiceTaskHelper):
    Approval = sth.get_model("Approval")

    sth.db.add(Approval(
        id=str(sth.workflow_instance_id),
        status="pending",
        created_at=datetime.now(),
    ))
```

`sth.get_model()` returns the SQLAlchemy model class after checking that the workflow has declared access. All queries and writes go through `sth.db`, the request-scoped SQLAlchemy session.

### Mixins for common patterns

The base data model is intentionally minimal — just prefixed tables and a registry. For recurring patterns, the engine provides optional mixins that add standard columns and behavior.

The first mixin is `WorkflowManagedMixin`. It covers data that is produced exclusively by workflows — results or intermediate results of workflow steps that can only be modified by subsequent workflows. Because every change originates from a workflow, the data has a built-in audit trail and is protected from external modification.

A typical example is a purchase request: an initial workflow creates it, a correction workflow produces a revised version, and an approval workflow finalizes it. Each iteration creates a new row. The mixin adds `workflow_instance_id` (the primary key, linking the row to the workflow that created it), `parent_workflow_instance_id`, `child_workflow_instance_id`, `action`, and `created_at` columns that link these iterations into a chain.

```python
from actidoo_wfe.data_models import register_data_model, WorkflowManagedMixin
from myworkflows.models import MyModel

@register_data_model(name="PurchaseRequest")
class PurchaseRequest(MyModel, WorkflowManagedMixin):
    _ext_table = "purchase_request"  # → table name: ext_mycompany_purchase_request

    # workflow_instance_id, parent/child_workflow_instance_id, action, created_at come from the mixin
    item_description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

Future requirements might call for different behavior — additional mixins can extend the base model without duplicating registry logic.

## Consequences

Project data lives in one database with consistent transactions — no separate infrastructure needed. Table naming conventions prevent collisions. Projects use standard SQLAlchemy for all data access — no extra API to learn. Dependency declaration makes it explicit which workflows access which data. Optional mixins provide standard columns for common patterns, keeping models concise and consistent.
