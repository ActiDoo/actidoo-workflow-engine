# ADR 007: Lane-Level Role Notifications

**Status:** Proposed
**Date:** 2026-05-06

## Context

The engine sends an email when a task becomes ready and is directly assigned to a specific user. Tasks that are only routed to a role - that is, tasks behind a BPMN lane with `roles="…"` and no direct assignee — produce no immediate notification. Members of the role only learn about open tasks through the weekly status mail (`personal_status_mail`, sent on Tuesdays).

This is acceptable for roles with many members, where some individual is likely to see the task and a broadcast would be noise. It is not acceptable for roles with one or a few members, who would benefit from a prompt signal but currently have to wait up to a week.

We need a way to opt in to immediate role notifications, scoped tightly enough that adding a member to a role doesn't accidentally turn a small-role channel into a mass mailing.

## Decision Drivers

1. The signal should fire promptly when a task becomes ready, like the existing direct-assignee mail.
2. A mass-mail channel must be prevented.
3. The pub-sub conventions in the engine should be preserved.
4. Idempotency should follow the engine's existing state-transition pattern, not introduce a separate "was-notified" tracking surface.
5. Configuration should live where roles are already defined.

## Considered Options

### Lane-level flag with cap and per-lane override (chosen)

A boolean BPMN extension property `notify_role_members` on the lane element, plus an optional integer `notify_role_members_max` on the same lane. The flag opts a lane in; the cap silently skips broadcasting when the role has grown past the threshold.

Configuration lives next to the existing `roles=…` lane property. One flag covers every task in the lane. A growing role is bounded by the cap rather than producing surprise mass mail.

### Task-level flag (rejected)

The same property attached to individual user-task elements via `<zeebe:property>`. More fine-grained: each task in a lane can independently opt in or out. In practice the typical use case is "all tasks of this small role's lane", which would force the designer to repeat the same property on every task in the lane. **If a per-task override becomes necessary later we can layer it on top of the lane flag** — task-level overrides lane — without breaking the present model. Not needed in the first iteration.

### Global cap via setting only (rejected)

A single environment variable controls the cap for all lanes. Simpler, but different lanes have different ideas of what counts as small (a 3-person operations team vs. a 12-person regional sales team). A per-lane override better matches reality.

## Decision

We add a BPMN lane extension property `notify_role_members` (boolean) and an optional `notify_role_members_max` (integer) per lane. When the flag is set on a lane, the engine fires `TaskReadyForRoleNotificationEvent` whenever a task in that lane becomes ready and has no direct assignee. A subscriber resolves the lane's roles to their members and sends an email to each, provided the recipient count stays at or below the cap (default `10`).

When a task has both a direct assignee and the lane flag set, only the direct mail is sent. The role broadcast is suppressed: the assignee is unambiguously responsible, so re-mailing the rest of the role is noise.

## Consequences

Designers explicitly opt in per lane. Lanes without the flag continue to behave exactly as today. The cap protects against accidental mass mailing — silently, but with a `warning`-level log entry to keep the skip discoverable.

Per-task overrides are a future option if a use case emerges. Deferring keeps the configuration surface small and the chosen mechanism easy to reason about.
