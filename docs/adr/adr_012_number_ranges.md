# ADR 012: Number Ranges

**Status:** Implemented
**Date:** 2026-09-01

## Context

Workflows regularly have to issue a running business number — a case, ticket or document number that people quote outside the system. The engine offers nothing for this, so projects improvise: a maximum-plus-one query without locking, a counter kept in a file shipped with the project, or a UUID standing in for a number. None of them holds. An unlocked counter hands the same number to two concurrent instances, a counter inside the deployed artifact is lost with the next release, and a UUID is unique but is not a number anyone can read out over the phone.

Two properties of the engine make this harder than it looks. A service task that raises does not roll back: the exception is caught, the task is marked erroneous, and the surrounding request commits anyway. And an administrator can re-run an erroneous task, which starts the service function again from the beginning. A counter that is merely correct under concurrency still burns a second number on every such retry.

## Decision Drivers

1. A number is issued exactly once, whatever runs concurrently.
2. Repeating the same work must not consume a new number.
3. A project must be able to express its own numbering scheme without changing the engine.
4. Who received which number, when, and from which step must stay visible after the workflow instance is gone.

## Decision

**A number range is a data model whose rows are the issued numbers.** There is no counter to keep: the next number is derived from the rows already there, and those same rows are the record of what was issued. The data model extension point ([ADR 004](adr_004_data_entity_persistence.md)) then provides everything around it — the project owns the table and its migration ([ADR 005](adr_005_extension_database_migrations.md)), and the workflow declares its access like any other model.

It is a **tier of its own**, beside the plain, versioned and workflow-managed ones, not a layer on top of the last. A range is an append-only ledger: every row is issued once and never revised, so the versioning columns of the tiers above would be permanently at their initial value and their write hook would cost a query per allocation for an answer that never changes. A range is also not exposed through the data API ([ADR 006](adr_006_data_model_rest_api.md)): that surface is for the business records a workflow produces, and it hides record provenance as a system column — the one thing an allocation log is read for. The log gets a view of its own instead: a read-only administrative page built for what an allocation log is read for, scoped by workflow ownership — a global administrator sees every range, a workflow owner the ranges a workflow of theirs declares.

**Uniqueness comes from unique keys, never from a lock.** Issuing a number inserts a candidate row; the database refuses a duplicate and the engine tries the next candidate, within a bounded number of attempts.

The sequence itself is the primary key, and a range carries no surrogate id. That is a concurrency decision rather than a modelling preference: when a duplicate is caught on a secondary index, the database gap-locks the conflicting row in the clustered index, so a random surrogate key scatters those locks and concurrent allocations block each other's insert positions crosswise until the retries deadlock. Measured, that failed roughly one allocation in seven under five-way contention on one sequence. With the sequence as the clustered index every contender queues at the same end in the same order, and the cycles become ordinary waits.

What the retry needs in order to terminate is a *fresh* reference value. The engine runs at an isolation level where a transaction's ordinary reads keep returning the snapshot they began with, so a loop reading only from its own transaction would recompute the rejected candidate until it gave up. The reference is therefore read from two sources: the issuing transaction, for numbers it has itself issued and not yet committed, and — once a collision has shown that somebody else is active — a second pooled connection, for what everyone else has committed since. That second read is the engine's, not the scheme's, and it is deferred to the retry on purpose: an uncontended allocation never holds two connections at once, so the nested checkout that could starve a saturated pool occurs only where contention is real. Taking a lock to get the same freshness in a single read was tried and rejected — on a range with no rows yet it locks the gap rather than a row, and two concurrent issues then deadlock on their inserts, which is precisely the first two numbers of every new scope.

That separation is what makes the numbering scheme safe to hand to projects. A project supplies the scope that decides which rows compete for one sequence, the rule that turns the previous value into the next candidate, and the rendering of the number people see. A mistake in any of them can produce a poor candidate; it cannot produce a duplicate.

**The ordering key stays an integer; the business number is rendered from it.** Letters, check digits and grouped blocks are presentation. Ordering a sequence lexicographically breaks quietly and late — the moment a value grows a digit, or a letter block rolls over.

**Repetition is recognised at the step, not at the instance.** A claim is remembered against the task occurrence that made it, and against which draw within that step it was. An administrator's retry runs the same task and receives the number it already got. The children of a multi-instance activity and the passes of a loop are separate occurrences and each receive their own — which a claim recorded per instance would get wrong, by handing all of them the same number.

## Considered Alternatives

- **A counter row that is locked, read, incremented and written back** — the familiar shape, but it adds a second thing to keep alongside the record of what was issued, and the two can drift apart. It also places a mutable value inside a mechanism whose records are otherwise only ever appended.
- **A number range extension point of its own** — a fourth registry beside workflow providers, connectors and data models, with its own storage, its own migration and its own administrative view, in order to arrive at what the data model already offers.
- **Letting each project write the query that picks the next number** — the flexibility is real, but it moves the part that must not be wrong into project code, and nothing keeps that query and the index guarding it in agreement. Exposing the scheme as functions above a guarantee the engine holds gives the same freedom without the risk.

## Consequences

- Projects own the table and its migration; the engine contributes a mixin and one call on the task helper.
- The allocation log is the number range itself: which instance and which step received which number is in the same table as the numbers, with nothing to keep in sync, and a read-only administrative view scoped by workflow ownership.
- Rows must never be deleted. Deleting one releases its number to be issued a second time.
- Two issues that pick the same value serialise: the loser waits for the winning transaction to commit before it can retry. The step that issues therefore has to stay short — a step that issues a number and then calls an external system turns a concurrent issue into a failed task that only an administrator can resume.
- No number is silently consumed, but numbers are not promised to be contiguous: a scheme may skip deliberately, and a number issued to an instance that is later cancelled stays issued.
- One table per range. A handful is comfortable; a large number of ranges would make the shape worth revisiting.
