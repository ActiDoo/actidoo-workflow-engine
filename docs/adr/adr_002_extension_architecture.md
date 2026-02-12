# ADR 002: Extension Architecture

**Status:** Accepted
**Date:** 2026-02-11

## Context

The workflow engine needs to support project-specific functionality — custom workflows, cron jobs, user attribute enrichment, login hooks, and event handlers — without changing the engine itself. Different deployments have different requirements, and all of this must be deployable on its own release cycle.

The question is how to organize, discover, and deploy extensions.

## Decision Drivers

1. Project-specific code must live in separate repositories, not in the engine.
2. Extensions must be developed, tested, and deployed independently from the engine.
3. The deployment artifact must be self-contained and reproducible.
4. Engine upgrades should be easy — ideally a version bump.

## Considered Options

### Option 1: Fork-based Customization

Each organization forks the engine repository and modifies it directly. Gives full control, but forks diverge over time and engine upgrades require manual merging.

### Option 2: Git Submodule

The engine is included as a git submodule in each project repository. The engine version is pinned and explicit. However, dependencies and structured extension points (migrations, cron jobs, hooks) require custom wiring outside of Python packaging.

### Option 3: Docker-only Approach (Volume Mounts / COPY)

Extensions are plain directories mounted into or copied into the engine container. Simple to set up, but has the same limitations as the submodule approach regarding dependency management and extension point registration.

### Option 4: Python Entry Points + Venusian Scanning + Docker Layering

Extensions are standard Python packages, discovered via entry points and installed into the engine's Docker base image. This uses Python packaging for dependency management, versioning, and structured extension points. The tradeoff is that developers need some familiarity with entry points and Venusian.

## Decision

We use **Option 4** because it is the cleanest approach: **Python entry points** for discovery, **Venusian** for decorator-based registration, and **Docker image layering** for deployment.

### Code-level: Entry Points and Venusian

- **Extension projects** are standard Python packages that declare an `actidoo_wfe.venusian_scan` entry point in their `pyproject.toml`, pointing to the package's root module.

- **Discovery at startup:** The engine loads all modules registered under the `actidoo_wfe.venusian_scan` entry point group, combines them with its own modules, and runs a Venusian scan over all of them. The scan finds decorated functions and registers them.

- **Decorator-based extension points:** Each capability is registered via a decorator:
  - **Workflows:**
    - `@register_workflow_provider` — expose workflows from a directory on disk via `FileSystemWorkflowProvider`
    - Service task functions in workflow modules (`service_<type>()`, `options_<type>()`, `validation_<type>()`)
  - **Identity:**
    - `@register_user_attribute_provider` — enrich user profiles with custom attributes on login

- **Dual registration:** Decorators register both immediately (so direct imports work in tests) and via Venusian callback (for discovery at startup). Registries deduplicate by name, so both paths can fire safely.

- **Workflow loading:** Extensions provide a `FileSystemWorkflowProvider` pointing to a directory of BPMN files. When the engine resolves a workflow, it checks all registered providers in priority order and uses the first match.

### Deployment: Docker Image Layering

The engine publishes a base Docker image (`ghcr.io/actidoo/actidoo-workflow-engine:latest`). Extension projects build their own image `FROM` this base and `pip install` themselves on top:

```dockerfile
ARG BASE_IMAGE=ghcr.io/actidoo/actidoo-workflow-engine:latest
FROM ${BASE_IMAGE}

WORKDIR /tmp/myextension
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && rm -rf /tmp/myextension

WORKDIR /opt/app
CMD ["/opt/app/start.sh"]
```

Engine maintainers release versioned base images. An engine update is a version bump in the extension's Dockerfile. Extension developers build and deploy their own image — a single Docker image that includes everything. No volume mounts, no config files listing extensions — entry points handle discovery automatically.

### Development: Devcontainer Base Image

Each engine release also publishes a devcontainer base image (`ghcr.io/actidoo/actidoo-workflow-engine-devcontainer:<version>`). Extension projects reference this image in their `docker-compose.yml` and pin the version via a `WFE_TAG` variable. The devcontainer includes the engine, all infrastructure services (MySQL, Keycloak, Mailpit), and lifecycle scripts (`wfe-post-create`, `wfe-post-start`) that install the extension in editable mode and run migrations automatically. Developers open the project in VS Code, the container starts, and they can begin working immediately.

## Consequences

Project-specific code is cleanly separated from the engine and can be developed, tested, and deployed independently. Extensions are discovered automatically via entry points — no hardcoded imports or configuration files. Developers register capabilities by decorating functions, and direct imports make extensions testable without a running engine. Deployment produces immutable, self-contained Docker images. New extension points can be added by following the same decorator + registry pattern.
