# Workflow project

This page is for a developer about to build their first workflow project. A workflow project is a Python package that holds your workflows and plugs into the engine; you scaffold it from a template, develop it in a devcontainer, and later bake it into a Docker image on top of the engine. The running example is an expense-approval workflow: an employee submits an expense, small amounts are auto-approved, and larger ones go to a finance approver. Here it is `ExpenseApproval`, the first workflow in the `acme` project — the package that will hold every process of that organisation. This page gets that project created and running locally, up to the moment its first task appears in the browser. What goes *inside* a workflow — the process model, forms, service tasks, tests, translations — is covered in [workflows.md](workflows.md).

## What a workflow project is

A workflow project is a normal Python package that depends on the engine and is installed next to it. The engine has no list of projects and no configuration for them; the package announces itself through an [entry point](glossary.md#entry-point). At startup the engine scans every module named by the entry point group `actidoo_wfe.venusian_scan` and runs the registration decorators it finds. The most important registration is a [workflow provider](glossary.md#workflow-provider): an object with a name and a priority that tells the engine which folders hold your workflows.

Registering a workflow only installs it. A workflow appears in the start list and can be started only when the `WORKFLOWS` setting lists it (an [activated workflow](glossary.md#activated-workflow)).

Create one project per organisation and put all of its processes in it, rather than one project per process. Workflows in the same package share its data models, connectors and background jobs, so an `o365` connector defined once serves every process that needs the Excel API. Our `acme` project starts with a single `ExpenseApproval` workflow, but it will later grow an `Expense` data model (see [data-models.md](data-models.md)) and exactly that `o365` connector (see [connectors.md](connectors.md)) — all in the same package. It is released and versioned on its own; the engine version it runs on is fixed by the base image it is built from (see [ADR 002](adr/adr_002_extension_architecture.md)).

## Create one from the template

The canonical starting point is `examples/workflow-extension-template` in the engine repository. It contains the package metadata, the provider, a devcontainer and a Dockerfile. Copy it into a new repository — this becomes the `acme` project:

```
pyproject.toml            package name, entry point, package data
workflow-engine.version   WFE_TAG=<engine image tag>
conftest.py               enables the engine's pytest plugin
docker/Dockerfile         extension image FROM the runtime image
.devcontainer/            engine, MySQL, Keycloak, Mailpit
.env.devcontainer         devcontainer backend settings (WORKFLOWS=...)
.vscode/launch.json       "Workflow Engine (devcontainer)", "Reset Database"
src/acme/
├── providers.py          registers the workflow provider
└── workflows/            one workflow directory per workflow
```

The template ships with the placeholder package name `myworkflows`; the steps below rename it to `acme`.

1. Copy the template into a new repository and pick your package name — here, `acme`.

2. Rename the package everywhere it appears: the `name` in `pyproject.toml`, the entry point value, the package-data key, the folder `src/acme`, and the provider's module base (step 3). Do not put the substring `test_` in a package or module name — the [Venusian scan](glossary.md#venusian-scan) skips such modules, so their registrations never happen.

    ```toml
    [project]
    name = "acme"
    dependencies = ["actidoo-wfe"]

    [project.entry-points."actidoo_wfe.venusian_scan"]
    acme = "acme"
    ```

    The entry point value is the root package. The scan imports every submodule below it at startup, so nothing else has to be listed.

3. Set the workflow provider in `src/acme/providers.py`. The template registers the engine's file-system provider with `@register_workflow_provider`; set its `name` (usually the package name, `acme`), its `priority` (the template uses `100` — when two providers serve the same workflow name, the higher priority wins) and its `module_base` (`acme.workflows`, the package that holds the [workflow modules](glossary.md#workflow-module)). Leave the base path — the `workflows` folder — as it is.

4. Complete the package data. Non-Python files are installed only when a `[tool.setuptools.package-data]` pattern matches them. The template lists `*.bpmn`, `*.form`, `*.json` and `*.csv`; add every other file type your workflows contain, for example compiled translation catalogs (`workflows/**/*.mo`) and DMN files. A file that is missing here is missing from the image.

5. Pin the engine version. Three places name the engine tag and must stay in sync: `workflow-engine.version` (`WFE_TAG`), the build argument `BASE_IMAGE` in `docker/Dockerfile`, and `${WFE_TAG}` in `.devcontainer/docker-compose.yml`. Upgrading the engine means changing the tag and rebuilding.

## Drop in the ExpenseApproval workflow

Each workflow lives in its own [workflow directory](glossary.md#workflow-directory) under `workflows/`. The folder name is the [workflow name](glossary.md#workflow) and must equal the BPMN process id — so the expense-approval process, whose process id is `ExpenseApproval`, goes in a folder of exactly that name:

```
workflows/
└── ExpenseApproval/          folder name = BPMN process id
    ├── ExpenseApproval.bpmn  the process model
    ├── EnterExpense.form     one form per user task, named <task id>.form
    ├── ApproveExpense.form   the approver's form
    ├── options/              optional: CSV files for select options
    ├── i18n/                 optional: translation catalogs
    ├── __init__.py           optional workflow module: service, options and validation functions
    └── tests/                optional: pytest tests
```

Every subfolder of `workflows/` that has at least one `.bpmn` file directly inside is a workflow. `ExpenseApproval` has two user tasks — `EnterExpense`, the employee's submit form, and `ApproveExpense`, the finance approver's form — so it carries two `.form` files, each named after its task id. Its service tasks and the amount gateway live in the process model and the `__init__.py` module; a workflow with no service, options or validation functions would need no `__init__.py` at all. How to fill this folder — modelling the process, writing the forms, the `check_policy` and `post_expense` service tasks, options, translations and tests — is the subject of [workflows.md](workflows.md).

## Run it locally

The template ships a [devcontainer](glossary.md#devcontainer) that runs the engine next to MySQL, Keycloak (realm `workflow`) and Mailpit (mail UI on port 8025). With `ExpenseApproval` in place, a few steps take you from source to a live task in the browser.

1. Open the project in VS Code and choose "Reopen in Container". On create, the devcontainer installs your package in editable mode into the engine's environment; on start, it starts the web server that serves the browser application on port 8080. Run `pip install -e .` again after you change `pyproject.toml`.

2. List your workflows in `WORKFLOWS` in `.env.devcontainer`, here `WORKFLOWS='["ExpenseApproval"]'`. Only activated workflows appear in the start list. Set `WORKFLOWS='["__ALL__"]'` to activate every workflow the project serves.

3. Start the backend with the launch configuration "Workflow Engine (devcontainer)". It reads `.env.devcontainer`, waits for MySQL, runs the database migrations, scans your package and serves behind the web server. It reloads when a `.py`, `.form` or `.bpmn` file changes.

4. Open `http://localhost:8080/wfe/` and log in as `wf-user` with password `wf-password`. Click "Start workflow", pick "Expense approval" and start it — the `EnterExpense` form opens as the first task, and the `acme` project is running.

The launch configuration "Reset Database" drops and recreates the database. To also see the engine's bundled demo workflows next to yours, set `SHOW_TEST_WORKFLOWS=True` and activate them (for example `WORKFLOWS='["__ALL__"]'`); they are otherwise absent.

| When | Then |
|---|---|
| `ExpenseApproval` is not in the start list | It is not listed in `WORKFLOWS`, or it could not be parsed. The backend log names the cause, for example a form file that matches no user task id, or a process id that differs from the folder name. |
| The backend stops during startup with an import error | A module of your package failed to import; the scan aborts startup. Fix the module and start again. |
| A `WORKFLOWS` change has no effect | The setting is read at startup. Restart the backend. |

## Build and deploy

For production you build a Docker image `FROM` the [runtime image](glossary.md#runtime-image): `docker/Dockerfile` installs your package with `pip install` and keeps the engine's start command. Because discovery works through the entry point, no further configuration is needed; the container just needs its database, identity provider, storage and URL settings. Building the image, the required settings and deployment — including creating the `expense-approver` role in the identity provider — are covered in [operations.md](operations.md).

## Related

- [workflows.md](workflows.md) — model the `ExpenseApproval` process, its forms, service tasks, options, translations, tests
- [data-models.md](data-models.md) — the `Expense` table your project owns, and its migrations
- [connectors.md](connectors.md) — talk to external systems, such as writing to an Excel workbook in O365, from workflow code
- [operations.md](operations.md) — build the image, settings, identity provider, storage, deploy
- [ADR 002](adr/adr_002_extension_architecture.md) — entry points, Venusian scan, image layering
- [ADR 005](adr/adr_005_extension_database_migrations.md) — how a project brings its own database tables
