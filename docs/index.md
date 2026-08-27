# Actidoo Workflow Engine

The Actidoo Workflow Engine runs BPMN workflows with user tasks, forms, service functions and mail notifications. You build your own workflows in a *workflow project* — a Python package that layers on top of the engine — and deploy it as a single Docker image.

## Contents

1. [Architecture](architecture.md) — the parts of the engine, where state lives, and how a workflow reaches the user.
2. [Workflow project](workflow-project.md) — create a workflow project and run it locally.
3. [Workflows](workflows.md) — model the BPMN process, build forms, write service tasks, react to messages and timers, translate and test.
4. [Data models](data-models.md) — define, expose and migrate records that outlive a workflow instance.
5. [Connectors](connectors.md) — connect workflows to external systems.
6. [Operations](operations.md) — build the Docker image, deploy it, and configure settings, identity provider, storage and mail.
7. [ADRs](adr/index.md) — the architecture decisions behind the engine.
8. [Glossary](glossary.md) — the terms used throughout.

## The short version

A workflow is a folder of BPMN, form and (optional) Python files inside your workflow project. The engine parses the BPMN once per workflow instance, shows user tasks with their forms in the web UI, runs your Python service functions between them, and stores everything in MySQL. Your project registers itself with the engine through an entry point and is shipped as a Docker image built on top of the engine's base image. Start with [Architecture](architecture.md) for the mental model, then [Workflow project](workflow-project.md) to set one up.

```{toctree}
:hidden:
:maxdepth: 2

architecture
workflow-project
workflows
data-models
connectors
operations
adr/index
glossary
```
