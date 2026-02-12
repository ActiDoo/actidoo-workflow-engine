# ADR 005: Workflow Project Database Migrations

**Status:** Proposed
**Date:** 2026-02-11

## Context

With Data Entities (ADR 004), workflow projects bring their own tables into the engine's shared database. These tables need schema management — creation, evolution, and compatibility with the engine's existing Alembic setup.

The engine and workflow projects have independent release cycles. A workflow project is pinned to a specific engine version but iterates on its own. Engine and workflow-project migrations must therefore be independent of each other.

## Decision Drivers

1. A workflow-project update must not require an engine release, and vice versa.
2. All tables live in one database.
3. Alembic revision generation must only see tables belonging to its own project.
4. Workflow-project migrations must run automatically at application startup, after engine migrations.

## Considered Options

### Single Shared Revision Chain

The workflow project manages one Alembic chain that covers all tables — its own and the engine's. Autogeneration is straightforward because there is only one chain. But engine schema changes sometimes involve data migrations (backfills, format changes), and those are better authored by the engine core team than by each workflow project independently.

### Separate Revision Chains per Project

Each project maintains its own Alembic chain with its own version table. The chains are fully independent, and prefix-based table filtering ensures correct autogeneration. The tradeoff is that both chains must be carefully configured so they don't interfere with each other — wrong filters or a missing version table setting can cause one chain to generate migrations for the other's tables.

## Decision

Each workflow project maintains its own Alembic revision chain. The engine discovers and runs workflow-project migrations at startup via entry points.

### Separate version tables

Alembic natively supports multiple version tables in the same database via its `version_table` parameter. The engine uses the default `alembic_version`; the workflow project uses `alembic_version_{namespace}`.

### Table filtering

Since workflow-project models share the engine's Metadata, autogeneration would normally see all tables. Both engine and workflow project use Alembic's `include_name` filter to restrict their scope: the engine excludes all `ext_*` tables, the workflow project includes only `ext_{namespace}_*`. Filtering works on the table name rather than the model registry, because Alembic must also detect deleted models — a table that exists in the database but has no corresponding model should still produce a `DROP TABLE`.

### Discovery and execution

The workflow project registers its Alembic module via the `actidoo_wfe.alembic` entry point group. At startup, the engine runs its own migrations first, then discovers and runs workflow-project migrations in sequence.

### Revision creation

The workflow project provides its own CLI command for creating revisions, configured with the correct version table and table filter.

## Consequences

Engine and workflow-project migrations are fully decoupled — each project has its own revision chain, version table, and table filter. Workflow-project migrations are discovered via entry points and run automatically after the engine at startup. The `ext_{namespace}_*` table prefix (ADR 004) doubles as the filter key, making it a prerequisite for correct migration generation.
