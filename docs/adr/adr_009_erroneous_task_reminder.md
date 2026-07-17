# ADR 009: Daily Reminder Mail for Erroneous Tasks

**Status:** Proposed
**Date:** 2026-07-03

## Context

When a task enters the error state, the engine sends a single real-time mail (`TaskBecameErroneousEvent` → `send_task_became_erroneous_mail`) to the configured error receivers and the workflow's owner role. After that one signal, an unresolved error produces no further notification. Erroneous tasks that are not fixed immediately are easily forgotten and can block workflow instances indefinitely.

We want a daily digest mail listing all tasks currently in error state, visually distinguishing failures that are new since the last digest from failures that were already reported. Admins should receive a global overview; workflow owners should receive the errors of their own workflows.

## Decision Drivers

1. New failures must stand out from already-known failures, across daily runs and engine restarts — this requires persisted state, not an in-memory or event-based signal.
2. Admins need a cross-workflow overview; workflow owners only care about their own workflows.
3. Recipients must be able to unsubscribe individually without an operator changing configuration.
4. No mail when there is nothing to report.
5. The existing conventions should be reused: the cron system (`@cron_task`), Mako mail templates with per-recipient locale, `wf-owner` resolution, and the `wf-admin` role.

## Considered Options

### New-vs-known tracking via a nullable column on the task (chosen)

A nullable timestamp `error_reported_at` on `workflow_instance_tasks`. A task is "new" while the column is `NULL`; it is stamped once the task was included in at least one sent digest, and reset to `NULL` when the task leaves the error state (so a re-failure counts as new again). The classification is global per task: all recipients of one run see the same new/known split.

The reset hook fits naturally into `save_workflow_instance`, where `state_error` is already synchronized on every engine save.

### Notification-log side table (rejected)

A separate table recording which task was reported when. Allows per-recipient tracking and a full history, but neither is needed: the digest is a snapshot, and per-recipient "new" markers would make the same task bold for one reader and normal for another for no benefit. The side table adds a join and lifecycle management (cleanup of stale rows) that the column avoids.

### HTML mail with bold markup (rejected)

Rendering new failures in bold requires HTML mail, which the transport layer does not support today (SMTP sends `text/plain`, Graph sends `contentType: Text`). An HTML extension was prototyped but rejected: every other mail the engine sends is plain text, so a single HTML mail is inconsistent, and the Graph API can only carry one body, dropping the plain-text alternative entirely. New failures are marked with a `* NEW *` text prefix instead, keeping the transport layer untouched.

## Decision

A daily cron task (`@cron_task`, schedule from the new setting `email_erroneous_tasks_reminder_cron`, default `0 7 * * *`, empty string disables the feature; configurable via environment like all settings) sends two digest variants built from one snapshot of all tasks with `state_error`:

- **Admin digest:** all erroneous tasks of all workflows, sent to members of the `wf-admin` role and to the addresses in `email_receivers_erroneous_tasks`.
- **Owner digest:** only the erroneous tasks of the workflows owned via the `wf-owner` role, one mail per owner covering all workflows they own.

A user who qualifies for both receives only the admin digest — it is a superset of their owner digest. Users who are neither admin nor owner receive nothing, and recipients whose task list is empty are skipped.

Role-based recipients can opt out through a new per-user flag `receive_error_task_reminder` (default on), exposed in the existing user-settings endpoint and frontend page. The statically configured address list is exempt from the opt-out.

New failures are marked with a `* NEW *` prefix and each entry shows the date the task entered the error state (new column `error_at`, set on the error transition and reset on recovery); `error_reported_at` is stamped only for tasks that were actually included in at least one sent mail.

## Consequences

- Unresolved errors resurface every day instead of being mentioned once; the new/known split keeps repeated digests scannable.
- Three schema additions (two task columns, one user flag) via one migration; the user-settings API and page gain one field.
- The real-time erroneous-task mail remains unchanged; the digest complements it.
- Owner digests reuse the existing `wf-owner` convention — workflows without an owner role are covered by the admin digest only.
