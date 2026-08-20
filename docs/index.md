# Actidoo Workflow Engine

The Actidoo Workflow Engine runs BPMN workflows with user tasks, forms, service functions and mail notifications. You build your own workflows in a *workflow project* — a Python package that layers on top of the engine — and deploy it as a single Docker image.

This handbook is for the people who build and operate such a project. It is short on purpose: how to use the engine, not how it works inside. Terms are used as defined in the [glossary](glossary.md).

## Where to go

| I want to … | Page |
|---|---|
| understand how the engine is put together | [Architecture](architecture.md) |
| create a workflow project and run it locally | [Workflow project](workflow-project.md) |
| model processes, build forms, write service tasks and tests | [Developing workflows](workflows.md) |
| store and query structured data | [Data models](data-models.md) |
| integrate an external system | [Connectors](connectors.md) |
| build the Docker image, deploy, configure settings, identity provider and storage | [Operations](operations.md) |
| know why something is built the way it is | the [ADRs](adr/adr_002_extension_architecture.md) |

## The short version

A workflow is a folder of BPMN, form and (optional) Python files inside your workflow project. The engine parses the BPMN once per workflow instance, shows user tasks with their forms in the web UI, runs your Python service functions between them, and stores everything in MySQL. Your project registers itself with the engine through an entry point and is shipped as a Docker image built on top of the engine's base image. Start with [Architecture](architecture.md) for the mental model, then [Workflow project](workflow-project.md) to set one up.
