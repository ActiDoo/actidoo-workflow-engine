# Glossary

Terms used throughout the documentation. Every page uses these words in exactly this meaning. When a term has synonyms, the other names are listed with "(avoid)": do not use them in the docs.

## activated workflow

A workflow that the `WORKFLOWS` setting lists (or all workflows, when the setting contains `__ALL__`). Only activated workflows appear in the start list and can be started; other workflows are installed but invisible.

## API v1

The machine-to-machine REST endpoints under `<API_PATH>/wfe/api/v1/`, protected by a bearer token. External systems use it to send messages to workflows. Also called machine API, service API (avoid).

## attachment

A file a user uploads in a form field with the custom property `custom_type: attachment_single` or `attachment_multi`. The engine stores each file content once (by hash) and links it to the workflow instance and the task; attachments are never part of form templates.

## bearer token

An OAuth2 access token that an external client obtains from the IdP and sends in the `Authorization` header to call API v1. It must carry the client role `wf-api`; the engine represents the caller as a service user.

## BFF

"Backend for frontend": the REST endpoints under `<API_PATH>/wfe/bff/user/`, `<API_PATH>/wfe/bff/user/workflow-data/` and `<API_PATH>/wfe/bff/admin/` that the browser application calls. They are protected by the session cookie and require the role `wf-user`.

## catalog

A gettext translation catalog: a `.pot` template with all texts, one `.po` file per locale that translators edit, and the compiled `.mo` file the engine reads. Every workflow and every data model has its own catalog in its `i18n/` folder; the engine has a global catalog for mail texts. See [ADR 001](adr/adr_001_form_i18n.md).

## connector

The way workflow code talks to an external system, for example an ERP or an issue tracker. An extension registers a connector type (name, config schema, factory) with `@register_connector_type`; a deployment configures connector instances of it; service functions open a connection by type and instance name. See [ADR 003](adr/adr_003_connector_registry.md).

## connector instance

One configured connection of a connector type in a deployment, set through env vars named `CONNECTORS__<TYPE>__<INSTANCE>__<KEY>`. A deployment can have several instances of the same type, for example one per region.

## correlation key

The value that tells the engine which waiting workflow instance a message belongs to. The BPMN attribute `zeebe:subscription correlationKey` holds an expression; the engine evaluates it per instance and the sender must pass the same value with the message.

## custom property

A key/value pair a workflow author sets in the Camunda Modeler: on a process, lane or user task in the BPMN file (`zeebe:property`), or on a form field ("Custom properties" panel). The engine reads its own keywords from there, for example `roles`, `initiator`, `wf-owner`, `options_function`, `custom_type`.

## data model

A database table that an extension defines and the engine hosts in its own database. Workflows read and write it through service functions; a data model can also be shown to users on the Data page. Also called data entity, data-model entity (avoid). See [ADR 004](adr/adr_004_data_entity_persistence.md) and [ADR 006](adr/adr_006_data_model_rest_api.md).

## data model action

A follow-up workflow that a user can start from a row of a data model on the Data page. The row's data is passed into the first form of that workflow. Also called action, follow-up workflow (avoid unless the context is clearly a data model).

## devcontainer

The VS Code development container in which the engine and extensions are developed. The engine publishes a devcontainer image for extension projects; it contains the engine, MySQL, Keycloak and Mailpit and installs the extension at start.

## dynamic list

A form component that repeats a group of fields as a list of rows; the user can add and remove rows. Every row carries a row id. See [ADR 010](adr/adr_010_dynamic_list_row_identity.md).

## engine

The workflow engine itself: the backend that runs workflows, the browser application, the scheduler and the REST endpoints, shipped together as the runtime image. Extensions build on top of it. Also called workflow engine, WFE, core (avoid).

## entry point

A Python packaging entry point through which an extension announces itself to the engine. `actidoo_wfe.venusian_scan` names the modules to scan for registrations; `actidoo_wfe.alembic` names the extension's migration chain.

## erroneous task

A task of a workflow instance in state error, usually because a service function raised an exception. The branch stops there until an admin retries the task; the error is shown in the admin area and reported by mail.

## extension

A Python package that adds workflows, data models, connectors, cron tasks, hooks and migrations to the engine. The engine finds it through its entry points at startup; it is deployed by installing it into an image built from the runtime image. Also called workflow project, extension project, extension package (avoid). See [ADR 002](adr/adr_002_extension_architecture.md).

## form

The input mask of a user task. A form is a Camunda Modeler form file (`<task id>.form`) next to the BPMN file; the engine turns it into a JSON schema and a UI schema that the browser renders and validates. Also called task form, form file (avoid, unless the file itself is meant).

## form template

A named preset of form input that a user saves for a form and can apply again later. Templates are private to the user, live on the server and never contain attachments or hidden fields. See [ADR 008](adr/adr_008_form_templates.md).

## hide-if

A FEEL condition on a form field (Camunda `conditional.hide`). While it is true, the browser hides the field and the server removes the field's value from the task data, so a hidden field never blocks a submit. Also called conditional hide, hidden field condition (avoid).

## IdP

The identity provider: the external OpenID Connect server (Keycloak in the development setups) that logs users in and issues tokens. The engine has no users or passwords of its own; roles come from the IdP.

## initiator

The user who started a workflow instance. A lane with the custom property `initiator` is the initiator lane: its user tasks are assigned to the initiator automatically, and if the property lists roles, only members of those roles may start the workflow. Also called creator, starter (avoid).

## lane

A BPMN lane of a workflow. Its custom property `roles` names the roles whose members see and may take the lane's user tasks; a service function can replace these roles for a single task. Also called swimlane, pool lane (avoid).

## lane mapping

The lane settings of one workflow instance, frozen at start: per lane its roles, whether it is the initiator lane and whether role members are notified. Later changes to the BPMN do not affect running instances.

## locale

The language and region of a user, as a tag like `de-DE` or `en-US`. Forms, data model labels and mails are translated per locale through catalogs; users without a locale get `DEFAULT_LOCALE`. Also called language setting (avoid).

## message

A named payload that a service user sends to the engine through API v1. A message starts every activated workflow with a message start event of that name, and continues workflow instances waiting at a message catch event whose subscription matches name and correlation key.

## message subscription

The record that a workflow instance waits for a message: message name plus correlation key. The engine writes it for every waiting message catch event when it stores the instance and deletes it when the wait ends.

## migration chain

The ordered list of Alembic database revisions of one package. The engine has its own chain; each extension with data models has a separate chain announced by the entry point `actidoo_wfe.alembic`. The engine runs all chains at startup, its own first. See [ADR 005](adr/adr_005_extension_database_migrations.md).

## number range

A data model whose rows are the running business numbers it has issued — there is no separate counter. A service function draws one with the task helper; the same row records which workflow instance and which step received it, so the range is its own allocation log. The numbering scheme (scope, next candidate, rendering) is expressed as overridable methods on the model, while uniqueness is enforced by the engine. See [Number ranges](number-ranges.md).

## options

The choices of a select field. Static options are listed in the form file; dynamic options come from a CSV file in the `options/` folder of the workflow directory (custom property `options_file`) or from a function in the workflow module (custom property `options_function`) and are loaded while the user fills the form. Also called select values, choices, lookup values (avoid).

## role

A named group of users, for example `wf-user` or `purchasing`. Roles come from the IdP claims at login and are copied into the engine; the engine has no role management of its own. Roles control access to the application (`wf-user`, `wf-admin`, `wf-api`), to lanes, to data models and to workflow ownership. Also called realm role, workflow role, group (avoid).

## row id

A technical UUID (`_row_id`) that the engine stores in every row of a dynamic list. It identifies the row when submitted data is merged with stored data, so rows keep their identity when they are edited, reordered or removed. Also called row identity, row key (avoid). See [ADR 010](adr/adr_010_dynamic_list_row_identity.md).

## runtime image

The one Docker image that contains the engine: web server with the browser application and reverse proxy, and the backend. Deployments run it directly or build their extension image `FROM` it. Also called base image, engine image (avoid).

## service function

A Python function in the workflow module that a service task calls. It is named `service_<type>` after the `type` in the BPMN attribute `zeebe:taskDefinition`, receives a task helper and returns a JSON-serialisable value that the engine stores in the task data. Also called service handler, task implementation (avoid).

## service task

A task the engine executes itself by calling a service function; the BPMN attribute `zeebe:taskDefinition type="<type>"` names the function. When the function raises or fails, the task becomes an erroneous task. Also called script task, automated task (avoid).

## service user

The user record the engine creates for an external client that calls API v1 with a bearer token. It has no e-mail and no browser session; workflow instances started by a message have it as initiator. Also called technical user, API user, machine user (avoid).

## task

One step of a workflow instance as the engine runs it: a user task, a service task, a gateway or an event. Every task has a task state and its own task data. When a page means the step a person works on, it says user task. Also called engine task, node, activity (avoid).

## task data

The variables of one task: a dictionary the engine passes from task to task along the workflow. Forms read and write it, service functions read and write it, and expressions in the BPMN see its keys as variables. Also called process variables, workflow variables (avoid).

## task helper

The object every service, options and validation function receives as its argument. It gives access to task data, workflow data, users, attachments, mails, connectors and data models. By convention it is named `sth` in service functions, `oth` in options functions and `vth` in validation functions.

## task state

The state of a task in a workflow instance. The docs use these names:

| state | meaning |
|---|---|
| ready | The task can run now; a ready user task is shown to its users. |
| waiting | The task waits for something outside: a timer, a message, or the end of a parallel branch. |
| completed | The task has finished. |
| error | The task failed; it is an erroneous task. |
| cancelled | The task was cancelled, usually because the workflow instance was cancelled or a boundary event fired. |

A workflow instance is completed when no task is ready or waiting any more; a cancelled instance therefore counts as completed.

## timer

A BPMN timer event in a workflow: a date, a duration or a cycle. The engine stores the due time when the timer starts waiting, and a background job fires due timers every 30 seconds. Also called time event, timer task (avoid).

## user task

A task that waits for a person: it has a form, belongs to a lane and appears on the Tasks page of the users who may work on it. Also called usertask, manual task, human task (avoid).

## validation function

A function in the workflow module named in a form field's custom property `validation_function`. The engine calls it with a task helper when the form is submitted; it can reject the field's value with a message that the browser shows at the field. Also called validator, custom validation (avoid).

## Venusian scan

The pass at engine startup that imports the engine and every extension module named by the entry point `actidoo_wfe.venusian_scan` and runs their registration decorators. Everything registered by a decorator (workflow providers, data models, connector types, cron tasks, hooks) exists only after this scan. Also called startup scan, extension scan, module scan (avoid).

## versioned data model

A data model that keeps every change as a new version of the same record. The record keeps one stable id, the newest version is the current one, and older versions form its history. Data models written by workflows are versioned and remember which workflow instance wrote each version; they are the ones the Data page shows. Also called workflow-managed model, history table (avoid unless the distinction to plain versioned models matters).

## wf-admin

The role of global admins. Members see and administrate all workflows, instances, tasks and users, and receive the erroneous-task reminder for all workflows.

## wf-api

The client role a bearer token must carry to call API v1.

## wf-user

The role every user needs to open the application and to call any BFF endpoint. Without it a logged-in user is refused.

## workflow

The BPMN model together with its forms, options and workflow module, kept in one workflow directory and served by a workflow provider. Users start workflow instances of it. A workflow is identified by its workflow name. Also called workflow definition, workflow spec, process, process definition (avoid).

## workflow data

Variables that belong to the whole workflow instance instead of one task, for example who started it. Forms do not see workflow data; service functions read and write it through the task helper. Also called instance data, global variables (avoid).

## workflow directory

The folder that holds one workflow: at least one `.bpmn` file, one `<task id>.form` per user task, optional `.dmn` files, an optional `options/` folder, an optional `i18n/` folder and an optional Python module. Its name is the workflow name and must equal the BPMN process id. Also called workflow folder, process directory (avoid).

## workflow instance

One run of a workflow, from start to completion or cancellation, with its own tasks, task data and history. The UI shows it with a title and an instance id. Always say "workflow instance", never only "instance", because instance also names backend processes and connector instances.

## workflow module

The optional Python module (`__init__.py`) in a workflow directory. It holds the service functions, options functions and validation functions of the workflow and the list `DATA_MODELS` of data models the workflow may use. Also called workflow package, process module (avoid).

## workflow owner

A member of the role named in the process-level custom property `wf-owner` of a workflow. Owners administrate the instances of that workflow (retry erroneous tasks, assign, cancel) and receive its erroneous-task reminder, but have no rights on other workflows. Also called process owner (avoid).

## workflow provider

An object an extension registers with `@register_workflow_provider` to tell the engine where its workflow directories are. Each provider has a name and a priority; when two providers serve the same workflow name, the one with the higher priority wins. Also called provider, workflow source (avoid).
