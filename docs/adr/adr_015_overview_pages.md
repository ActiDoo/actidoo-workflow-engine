# ADR 015: Pages, Data Sources and Projections Defined by Extensions

**Status:** Proposed
**Date:** 2026-11-05

## Context

Those responsible for workflows have different needs when it comes to evaluating workflow data, depending on their domain. Some only want an overview of the records that workflows created, and to start follow-up workflows from them. Others want to analyse the data entered in the workflows in depth, to find where a workflow can be improved.

No page built into the engine can be precise enough for one of these needs and flexible enough for all of them. The engine therefore needs a framework in which such pages are defined, not another fixed page.

The data for such pages is also hard to query today. Which task ran when and by whom sits in internal database tables that can change with any release. What was entered sits in the task data, which the database cannot query. It only reaches a database column when a service task writes it into a data model ([ADR 004](adr_004_data_entity_persistence.md)), and that has to be built into every workflow.

Deriving and querying this data is useful beyond pages. These capabilities need to be usable independently. Projection definitions also change, and existing instances need to be rebuilt after such changes. Both ongoing updates and rebuilds need reliable background processing without making workflow changes depend on projection code.

## Decision Drivers

1. An extension builds the pages its domain needs, without frontend code and without a change to the engine.
2. The developer of the extension decides who may open a page and which data each user sees.
3. Derived data reflects a committed workflow state and catches up through background processing. Projection failures must not prevent workflow changes.
4. Derived data covers existing workflow instances, not only new ones.
5. Data models, projections and data sources can be used without a page.

## Decision

### Module boundaries

This proposal separates responsibilities into modules within the existing application. The `wf` module owns workflow execution, workflow state and its public read interfaces. The `data` module owns data models, projections and data sources. The `pages` module owns page definitions, building blocks and area navigation. The `auth` module remains responsible for authentication.

The modules share the database. Workflow changes and their data-model writes retain the shared transaction described in ADR 004; projection computation and writes happen separately in the background. The modules communicate through explicitly exported interfaces, and the application wires their implementations together. Workflow-specific integrations of data models remain in `wf`. Projections receive a stable representation of stored workflow state rather than engine objects. Import Linter will enforce these boundaries, including the BFF packages.

Projections and data sources do not depend on Pages. A data source can read workflow views or existing data models without requiring a projection. Pages consume these capabilities through their public interfaces.

Moving data-model responsibilities into `data` preserves existing extension import paths and HTTP access. It changes neither existing database tables nor their versioning and migration behaviour; those decisions remain in [ADR 004](adr_004_data_entity_persistence.md), [ADR 005](adr_005_extension_database_migrations.md) and [ADR 006](adr_006_data_model_rest_api.md).

### Pages

A page is a Python function that an extension registers. The registration names the roles that may open the page and the data sources it uses. All data displayed by the page comes from these sources. The page roles decide who may open it; the sources decide which data each user may read. The engine ships the blocks and renders every extension-defined page generically. It ships no business-specific pages.

The function describes the page by calling blocks. An input returns its current value, so the code that follows can depend on it. A table widget returns the key of the selected record.

The backend keeps no state for a page. The frontend holds the input values in the URL. When one changes, the backend runs the function again and answers with the whole page.

![Mockup of an expense dashboard with inputs, tabs, key figures, two charts, a table widget listing expenses and the detail of the selected expense.](../img/adr015-dashboard.svg)

*Mockup of a page. The selected row drives the detail on the right.*

### Menu

Extensions fill the menu through areas. An area groups related entries under a string id, and any extension can add entries to it by that id. An entry is a page, a data model ([ADR 006](adr_006_data_model_rest_api.md)) or the start of a workflow. Declarations with the same id are merged, and the engine logs a warning where they disagree.

The areas become one item in the menu. It replaces today's Data item, and the other items stay. A data model that no area lists appears in a standard area.

![Mockup of the menu: the top bar, the areas overview with tiles and the side navigation of one area.](../img/adr015-menu.svg)

*Mockup of the menu: the top bar, the areas overview and the side navigation of one area.*

### Data sources and access

A data source defines a parameterised database query and its access rules. An extension registers a function that receives the requesting user and parameters, such as a status or date range, and returns the query. The query determines the records and result fields available to that user. It can combine data from multiple declared database tables and views.

Data services execute the query to retrieve records or compute aggregates. Filtering, sorting, search, pagination and aggregation run in the database using the engine's existing query mechanisms. Both record queries and aggregates apply the source's access restrictions. These operations are independent of how a consumer presents or processes the results.

A data source declares the workflows, data models and projection database tables it reads, and whether it grants access to task data. Its query interface exposes only those resources. The same declarations and access rules apply to every consumer.

An existing data model exposed through ADR 006 can be used as a data source. This preserves its access rules, field descriptions, versions, files and workflow actions. Consumers reuse these declarations.

A data source can declare follow-up workflows for its records, as a data model does (ADR 006). The workflow module executes starts and checks the target workflow's start permissions.

Projection results may lag behind current workflow data. Access rules must use current authoritative data where a change can revoke access. Workflow actions and access to task forms and attachments are rechecked against current authoritative data when requested. A stale projection result alone cannot grant access or authorize a workflow start.

### BFF ownership and access

Workflow, Data and Pages each have their own BFF module in the same application. Their prefixes are `<API_PATH>/wfe/bff/...`, `<API_PATH>/data/bff/...` and `<API_PATH>/pages/bff/...`. They share the contract version and its handling under [ADR 011](adr_011_bff_contract_version.md). Shared HTTP infrastructure belongs outside the workflow module.

Page rendering, area navigation and page-specific source requests belong to the Pages BFF. Each source request checks the page roles and that the page declares the source, then calls Data services with the requesting user. Row, task-form and attachment access is checked again against the source; rendering a page grants no lasting access. Data-model HTTP access belongs to the Data BFF, with the existing workflow-data routes retained for compatibility.

BFF modules neither import nor call one another. They use service interfaces, including the workflow interface for starting workflows. The page-specific HTTP entry point does not make the data source depend on Pages, and registering a source does not automatically expose a general HTTP endpoint for it.

### Workflow views and projections

Facts about the run are read through workflow views owned by the workflow module. A data source needs to know, for example, the status of a workflow instance, its open user task and who worked on which task when. The module provides two database views with stable columns: one of workflow instances and one of their user tasks. These views read the internal database tables without copying their data, so data sources need not depend on the internal schema.

Cancellation information is already recorded and can be exposed through these views. The engine must additionally record when a user task becomes ready. Historical readiness times remain unknown; task creation times are not a substitute. Durations measured from readiness are available only where that time was recorded.

Data models store business records with their own identity and, where applicable, version history. Projection rows are derived read data that can be rebuilt from stored workflow state. They do not replace that business history.

An extension registers a projection function for a workflow. It receives the stored state of one workflow instance and returns rows that describe it. The rows go into projection database tables, which the extension owns and migrates ([ADR 005](adr_005_extension_database_migrations.md)). Aggregates such as monthly or yearly values are not stored. Data sources compute them when requested.

### Asynchronous updates and historical rebuilds

Whenever the engine stores a workflow instance, it durably records that its projections need updating in the same transaction as the workflow change. This applies to assignments, cancellations and background workflow processing as well as task submissions. A rollback leaves no update request. Recording the request must succeed before the workflow transaction can commit, but it runs no projection code.

After commit, background workers process this work through the existing scheduler. Pending work survives process restarts; an in-memory event after commit is not sufficient to guarantee delivery. Each projection and workflow instance has one outstanding target state. Further changes advance that target instead of appending another pending job, including when a worker is already processing an older state. Projections describe the latest committed state rather than recording every intermediate change.

Workers compute outside the workflow transaction. Publishing a projection replaces all of its rows for one instance and records the processed workflow state and projection revision in one separate transaction. Retries are safe to repeat. A worker may publish only if its input state and definition revision are still current; otherwise the result is discarded and the latest work remains pending. Work arriving during processing must not be lost. A foreign key ties each derived row to its workflow instance, and deletion removes its projection rows and pending work.

A projection failure leaves the committed workflow change and the previous projection rows intact. Other instances continue to be processed. Automatic retries are bounded and delayed; errors and unfinished work remain recorded for operator inspection and retry. Projection code does not hold the workflow instance locked while it computes.

A projection is a pure function of the stored state. Its registration includes an explicit revision, which the extension developer increases when its derivation changes. A new projection or an increased revision triggers a background rebuild of existing workflow instances. This revision is separate from the extension's database migration revisions.

Rebuilds submit work to the same processing mechanism as ongoing updates. They use bounded batches and a resumable position instead of enqueueing every historical instance at once. Worker concurrency is limited, and rebuilds leave capacity for ongoing updates. They resume after interruption and use the same checks against concurrent changes and outdated workers. Repeated rebuild or retry requests merge with existing work for the same projection and instance.

Readers see the last successfully published projection, or no projection rows until the first successful run. Workflow views continue to show current workflow data, so queries that combine the two may contain data from different points in time. During a rebuild, readers may also see rows from different projection revisions. The data layer exposes the processed state, revision and pending or failed status so consumers can distinguish complete, current results from missing or outdated projections.

A projection has to cope with missing data. Older workflow instances may lack fields that were added later. Their columns stay empty, which means not recorded.

![Workflow changes commit with a durable projection update request. Background workers process ongoing updates and rebuilds, then publish projection rows in a separate transaction after checking the workflow state and projection revision. Data sources query current workflow views and the last successfully published projection rows.](../img/adr015-projections.svg)

*Ongoing updates and historical rebuilds share background processing. Publishing is atomic per projection and workflow instance; it is separate from the original workflow transaction.*

### Operations and retention

The Admin area includes a projection overview with the active revision, rebuild progress, pending and failed instance counts, the age of the oldest pending update and the last successful processing time. Operators can inspect errors, follow a link to the affected workflow instance, retry individual or all failed updates, and request a rebuild. These operations belong to the Data Admin BFF and are also available through the CLI. The Admin view reads operational state directly and remains usable when projections fail.

![Proposed Admin projection overview with pending updates, failures, rebuild progress and backlog age. The selected projection shows failed workflow instances, an error detail and actions to retry processing or start a rebuild. A notice explains the retention of run history.](../img/adr015-admin-projections.svg)

*Mockup of Admin → Projections. The selected projection and failed instance show how operators inspect and retry processing. Names, counts and times are examples.*

Current processing state is separate from execution history. Each projection and instance retains the latest requested and successfully processed state, its revision, retry count and a size-limited summary of any unresolved error. Completion clears the pending request without losing the information needed to report freshness. Retries update that state; they do not create an unbounded list of pending requests.

Completed execution records, including failed attempts, are retained for a configurable period, with ten days as the default to match the existing scheduler's result retention. Retained history also has a configurable maximum record count, and diagnostic details have a size limit. Cleanup runs regularly in bounded batches. It removes expired or excess history without deleting current projection rows, pending work or unresolved failure state. A failure remains visible and retryable after its individual execution records expire. Deleting the workflow instance removes its associated processing state as well as its projection rows.

Backlog size and age are available for monitoring as well as in the Admin view. Retention limits execution history; it cannot compensate for workers processing less work than arrives. Outstanding work must remain visible rather than being silently discarded to meet a storage limit.

### Page building blocks

The engine ships a small set of basic blocks.

- Inputs, such as a selection, a text or a date.
- Table widgets, which display records from a data source with paging, sorting and search. Each record can offer the source's declared follow-up workflows.
- Key figures and charts, which show aggregates of a data source. The chart types are few and fixed, for example bars and lines.
- Layouts, such as tabs and columns.
- The start of a workflow, as a button.
- The read-only form of a completed user task.

A table widget's page description carries a reference to a data source and its parameters. The frontend fetches the records separately. Paging, sorting or searching reloads only those records, not the page. Key-figure and chart widgets consume aggregates from the same source services.

A page can start workflows, and changes nothing else. A start without a record is a block on the page or an entry in the menu. Blocks have no arbitrary click handlers.

Blocks can be combined into reusable components. A component is an ordinary function that calls blocks. An extension can write its own and use them on several pages, and the engine ships some as well.

The course of a workflow instance is such a component. It shows the user tasks the workflow instance reached, who worked on each and how long each took where the required timestamps are available. Where the data source grants access to task data, a completed user task opens as a read-only form. A page uses it like a block, for example for the selected record in a table widget.

![Mockup of a table widget listing workflow instances and the course of the selected workflow instance.](../img/adr015-instance-overview.svg)

*Mockup of a page with a table widget listing workflow instances and the course of the selected one.*

## Considered Alternatives

A fixed page in the engine would be the smallest step, but each new business need could require another engine change.

Keeping projections and data sources inside Pages would require fewer module interfaces initially, but other consumers would have to depend on page infrastructure.

Deriving business facts in database views would avoid separate projection writes, but extension rules would depend on the engine's internal database tables and task-data storage.

Updating projections within the workflow transaction would keep derived rows aligned with each workflow change. It would also make projection failures block workflow changes, while definition changes would still require a separate historical rebuild.

## Consequences

The frontend needs a generic renderer, and the menu moves from the frontend into the backend. Separate modules add interfaces to maintain, while allowing projections and data sources to serve consumers other than pages. They share a database, with separate transactions for workflow changes and projection updates.

Projection errors no longer block workflow changes, but consumers must tolerate delayed or missing results. Ongoing updates and rebuilds need durable work tracking, retries, an Admin view and automatic history cleanup. Outstanding work still requires capacity monitoring. Combining current workflow views with older projection rows does not provide a snapshot of the same workflow state.

The engine checks declared access boundaries, but the extension developer remains responsible for the row restrictions in each data source. An incorrect query can still disclose data to the wrong user.

