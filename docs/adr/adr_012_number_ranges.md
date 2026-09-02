# ADR 012: Number Ranges

**Status:** Implemented
**Date:** 2026-09-01

## Context

Workflows regularly have to issue a running business number — a case, ticket or document number people quote outside the system. The engine offered nothing for this, so projects improvised: a maximum-plus-one query without locking, a counter in a file shipped with the project, a UUID standing in for a number. None of them holds. The unlocked counter hands the same number to two concurrent instances, the shipped counter is lost with the next release, and a UUID is unique but not a number anyone reads out over the phone.

Two properties of the engine make this harder than it looks. A service task that raises does not roll back: the task is marked erroneous and the surrounding request commits. And an administrator can re-run that task, which starts the service function again from the beginning. A counter that is correct under concurrency still burns a second number on every such retry.

## Decision Drivers

1. A number is issued exactly once, whatever runs concurrently.
2. Repeating the same work must not consume a new number.
3. A project must be able to express its own numbering scheme without changing the engine.
4. Who received which number, when, and from which step must stay visible after the workflow instance is gone.

## Decision

**A number range is a data model whose rows are the issued numbers.** There is no counter to keep: the next number is derived from the rows already there, and those same rows are the record of what was issued to whom. The data model extension point ([ADR 004](adr_004_data_entity_persistence.md)) provides everything around it — the project owns the table and its migration ([ADR 005](adr_005_extension_database_migrations.md)), and a workflow declares its access like for any other model.

It is a tier of its own, beside the plain, versioned and workflow-managed ones: an append-only ledger has no use for versioning. It is not exposed through the data API ([ADR 006](adr_006_data_model_rest_api.md)), which is built for business records and hides provenance — the one thing an allocation log is read for. The log gets a read-only administrative view of its own, scoped by workflow ownership.

**Uniqueness comes from a unique key, never from a lock.** Issuing inserts a candidate row; the database refuses a duplicate and the engine tries the next candidate, a bounded number of times. The numbering scheme — which rows share a sequence, how the next candidate follows from the previous one, how the number is rendered — belongs to the project, and none of it carries the guarantee: a mistake there produces a poor number, never a duplicate one. The sequence is the primary key, and the reference value a retry needs is read freshly; both are concurrency decisions, explained where they are made (`NumberRangeMixin`, `allocate_number`).

**The ordering key is an integer; the business number is rendered from it.** Letters, check digits and grouped blocks are presentation. A sequence ordered as text breaks quietly and late — the moment a value grows a digit or a letter block rolls over.

**Repetition is recognised at the task occurrence, not at the instance.** A claim is remembered against the task occurrence that made it and against which draw within that step it was. An administrator's retry runs the same task and receives the number it already got; the children of a multi-instance activity and the passes of a loop are separate occurrences and each receive their own.

## Considered Alternatives

- **A counter row that is locked, read, incremented and written back** — the familiar shape, but a second thing to keep beside the record of what was issued, and the two can drift apart.
- **A number range extension point of its own** — a fourth registry with its own storage, migration and administrative view, to arrive at what the data model already offers.
- **Letting each project write the query that picks the next number** — it moves the part that must not be wrong into project code, and nothing keeps that query and the index guarding it in agreement.

## Consequences

- Projects own the table and its migration; the engine contributes a mixin and one call on the task helper.
- The allocation log is the range itself, with nothing to keep in sync, read in an administrative view scoped by workflow ownership.
- Rows must never be deleted: a deleted row releases its number to be issued a second time.
- Two issues that pick the same value serialise — the loser waits for the winner to commit. The issuing step therefore has to stay short; a step that issues and then calls an external system turns a concurrent issue into a failed task.
- Numbers are not promised to be contiguous: a scheme may skip deliberately, and a number issued to an instance that is later cancelled stays issued.
- One table per range. A handful is comfortable; a large number of ranges would make the shape worth revisiting.
