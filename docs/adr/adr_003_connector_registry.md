# ADR 003: Connector Registry

**Status:** Proposed
**Date:** 2026-02-11

## Context

Workflow extensions need to integrate with external systems (issue trackers, data warehouses, ERP systems, etc.). Following the extension architecture (ADR 002), extensions should be able to register new connector types without changing the engine.

## Decision Drivers

1. Must support both standard and custom integrations.
2. Projects should not be blocked on engine releases for connector changes.
3. Connector implementations should be reusable across projects.
4. Connector credentials must be configurable per deployment.

## Considered Options

### Connector Library in the Engine

The engine ships a large collection of built-in connectors that can be parametrized per deployment. This avoids the need for an extension mechanism, but custom integrations don't fit in. Projects are blocked on engine releases for new or updated connectors, and all projects pull in the full dependency tree — even for connectors they don't use.

### Hardcoded Connections per Project

Each project implements its own connector logic directly, without a shared abstraction. This works, but there is no way to reuse connector implementations across projects.

### Connector Registry (Extension Point)

Extensions register connector types via a decorator. The engine resolves instances at runtime from configuration. This keeps projects flexible: standard connectors can be published as reusable packages, custom connectors follow the same structure, and the engine can provide shared mechanisms (validation, logging, configuration) without knowing about specific connector types.

## Decision

We introduce a **Connector Registry** as a new extension point.

Extensions register connector types via `@register_connector_type`, providing a name, a Pydantic config schema, and a context manager factory. 

Connector instances are configured per deployment via Pydantic Settings — environment variables, `.env` files, or Docker secrets — using a naming convention (e.g. `CONNECTORS__JIRA__EUROPE__URL=...`).

Resolution is lazy: config is validated on first use via `get_connector(type_name, instance_name)`, not at startup. An optional validation function runs at startup and logs warnings for misconfigured connectors, but does not block the application from starting.

All task helpers (`ServiceTaskHelper`, `OptionTaskHelper`, `ValidationTaskHelper`) expose `get_connector()` as a thin pass-through.

## Consequences

Extensions can add new connector types by decorating a context manager factory — no engine changes needed. Connector credentials stay in environment variables, separate from code. Multiple instances per type allow different departments or regions to have their own configuration. Tests register mock types and call `clear()` on the registry in teardown.
