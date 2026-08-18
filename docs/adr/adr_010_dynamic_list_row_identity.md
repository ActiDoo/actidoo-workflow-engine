# ADR 010: Row Identity and Data Ownership in Dynamic Lists

**Status:** Implemented
**Date:** 2026-08-09

## Context

When a user task is submitted, the engine cleans the payload and deep-merges it into the stored task data. The merge exists because task data has two owners: the **frontend** owns what the current form shows as visible and editable; the **backend** owns everything else - hidden values, disabled fields, and data written by service tasks. The merge restores the backend-owned part that the frontend cannot or must not send back.

For dynamic lists the merge matches rows **by index**, and that breaks the ownership model:

- A **newly added row** has no stored counterpart, so everything the cleaning strips from it (notably disabled fields) is lost - while existing rows are refilled from stored data and look fine.
- **Deleting a middle row** shifts its successors onto the stored data of the wrong rows: backend-owned values (e.g. asset numbers) migrate onto neighbors. A shorter list is ambiguous - the engine cannot tell *which* row was deleted.

The loss stays invisible for a long time: disabled fields carry form defaults, so the UI shows a plausible value that was never persisted, and the inconsistency only surfaces when a service task crashes on the missing data.

## Decision Drivers

1. Row identity must survive the frontend round trip without relying on list order; deleting and reordering must not corrupt neighboring rows.
2. Ownership must hold per row: backend-owned values return to *their own* row only, and the frontend must not be able to graft foreign data onto a row by forging identity.
3. What the frontend displays must be what the backend persists - and a user must never be blocked over data they cannot edit.
4. Running instances keep working without an offline migration.

## Decision

**1. Rows get a technical identity.** Every dynamic-list row carries a hidden `_row_id` (UUID) in the task data - no stored form schema ever contains the technical field, so it stays renamable and invisible to form authors; the engine admits it transparently during submission validation, and the frontend generates it for new rows. The merge matches rows by ID: IDs only in the submission mean "new row", stored IDs missing from it mean "deleted", and order follows the submission - which makes reordering legal for the first time. Unknown IDs are never matched against stored data, so a forged ID cannot pull another row's values.

Rows are stamped when a task is handed to the frontend, so a form is never rendered from rows without identity and both sides always share the same ids - a submission that comes back without any is rejected rather than guessed at by position. Lists a service task writes carry no identity and keep the index merge. IDs survive completion, so archived instances stay auditable, and they are exposed as a supported row reference for service tasks and API consumers - carried in the task data itself for now.

**2. Defaults on disabled fields are forced assignments.** A disabled field is backend-owned, but the process definition may declare its value: whenever the backend has nothing stored, the schema default becomes the value during the merge. The same resolution feeds hide-if evaluation, so frontend and backend always agree on the effective value - stored value, else default. Every configuration now has a defined meaning: disabled with a default is guaranteed to be filled (the value that necessarily results from the user's action), disabled without a default may stay absent until the backend fills it. Nothing can be misconfigured into an impossible state anymore, so no separate check is needed.

**3. `required` on disabled fields is information, not a constraint.** The user cannot supply the value, so validation never demands it - but the marking stays visible and tells the user that the field is mandatory in the process, e.g. in the original request.

## Considered Alternatives

- **Stripping defaults and `required` from disabled renderings** - makes the display truthful by removing it, but then a forced assignment cannot be expressed at all, and configurations that can only produce incomplete rows would need a separate lint to catch. The fallback gives every configuration a meaning instead of forbidding some.

## Consequences

- Dynamic lists behave as users expect: what a row shows is what gets stored, and deleting or reordering rows no longer corrupts their neighbors.
- Forms that already declare defaults on disabled fields start working correctly without being touched; rows that are already incomplete heal on their next submission.
- `_row_id` is a public part of task data and exports and may be relied on downstream - relocating it later is a breaking change.
- Form authors own consistency: the forced default depends on the step that creates the row, and a disabled field without a default may legitimately stay empty - consumers must accept absence.
- Running instances need no one-time migration; it is achieved on-the-fly.
