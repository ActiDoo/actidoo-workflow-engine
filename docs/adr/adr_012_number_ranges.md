# ADR 012: Number Ranges

**Status:** Implemented
**Date:** 2026-09-01

## Context

Workflows have to issue running business numbers: case numbers, ticket numbers, document numbers. The engine had nothing for this, so projects built their own: a maximum-plus-one query without locking, a counter in a file, a UUID in place of a number. None of them works. The unlocked query gives two concurrent instances the same number. The file is lost with the next release. A UUID is unique but not a number anyone reads out over the phone.

Two properties of the engine make the problem harder. A service task that raises does not roll back: the task is set to error and the request commits. And an admin can retry that task, which runs the service function again from the start. A counter that is correct under concurrency still burns a second number on every retry.

## Decision Drivers

1. A number is issued exactly once, whatever runs concurrently.
2. A retry must not consume a new number.
3. A project defines its own numbering scheme without changing the engine.
4. Who got which number, when, and from which step stays visible after the workflow instance is gone.

## Decision

**A number range is a data model whose rows are the issued numbers.** There is no counter. The next number is derived from the rows already there, and the same rows record what was issued to whom. The data model extension point ([ADR 004](adr_004_data_entity_persistence.md)) provides the rest: the project owns the table and its migration ([ADR 005](adr_005_extension_database_migrations.md)), and a workflow declares its access like for any other model.

A range is a tier of its own beside the plain, versioned and workflow-managed models. An append-only table does not need versioning. It is not exposed through the data API ([ADR 006](adr_006_data_model_rest_api.md)), because that API hides the system columns, and those columns are what the log is read for. The log has a read-only admin view of its own, scoped by workflow ownership.

**Uniqueness comes from a unique key, not from a lock.** Issuing inserts a candidate row. The database refuses a duplicate, and the engine tries the next candidate a bounded number of times. The numbering scheme belongs to the project: which rows share a sequence, how the next candidate follows from the previous one, how the number is rendered. None of these carries the guarantee. A mistake there produces an odd number, never a duplicate. The sequence is the primary key, and the reference value for a retry is read fresh. Both are explained in the code (`NumberRangeMixin`, `allocate_number`).

**The ordering key is an integer. The business number is rendered from it.** Letters, check digits and blocks are presentation. A sequence ordered as text breaks late, when a value gains a digit or a letter block rolls over.

**A repeated run is recognised at the task occurrence.** Each number is recorded against the task occurrence that issued it and the call within that step. An admin retry runs the same task and gets the number it already has. The children of a multi-instance activity and the passes of a loop are separate occurrences and get their own numbers.

## Considered Alternatives

- **A counter row that is locked, read, incremented and written back.** The familiar shape, but a second thing next to the record of what was issued, and the two can drift apart.
- **An extension point of its own for number ranges.** A fourth registry with its own storage, migration and admin view, to end up with what the data model already offers.
- **Each project writes the query that picks the next number.** The part that must not be wrong moves into project code, and nothing keeps that query and the index in agreement.

## Consequences

- Projects own the table and its migration. The engine contributes a mixin and one call on the task helper.
- The log is the range itself. Nothing has to be kept in sync.
- Rows must never be deleted. A deleted row frees its number, and it gets issued again.
- Two issues that pick the same value serialise: the loser waits for the winner to commit. The issuing step has to stay short. A step that issues a number and then calls an external system makes a concurrent issue wait for that call.
- Numbers have gaps. A scheme may skip on purpose, and a number issued to a cancelled instance stays issued.
- One table per range. A handful is fine. Many ranges would make the shape worth revisiting.
