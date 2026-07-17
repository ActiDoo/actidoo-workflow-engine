# ADR 008: Form Templates (User-Scoped Reusable Form Inputs)

**Status:** Accepted
**Date:** 2026-06-08 (accepted 2026-06-17)

## Context

When users start the same workflow repeatedly, they often fill in the same fields with the same values. We want to introduce "form templates": named presets that a user can save and later re-apply.

In one of our workflows, an earlier uncontrolled template feature led to inconsistent data ending up in the workflow. The new feature therefore has to stay controllable: workflow owners must decide per form whether and for which fields templates are allowed. In addition, later schema changes to a form must not invalidate existing user templates.

## Decision Drivers

1. Users should save effort without degrading the data quality reviewers see downstream.
2. Configuration lives where forms are already maintained, i.e. directly in the workflow owner's `.form` files.
3. Templates are stored per user.
4. Form schema changes must not break existing templates.

## Considered Options

### Activation and field selection

Who decides whether a form participates in templates and which fields are eligible.

**Opt-in per form with a per-field whitelist.** `templates_enabled: true` on the form, `templatable: true` per field.

- *Pros:* Safe defaults. New forms and new fields stay out of templates until consciously approved. Visible and traceable in the `.form` file. Fields that require explicit user attention on each run can be deliberately excluded from templates.
- *Cons:* Slightly more configuration effort for forms with many eligible fields.

**Opt-out per form with a per-field blacklist.** Templates are on by default; owners disable individual forms or fields.

- *Pros:* Less configuration when almost every field should be templatable.
- *Cons:* New fields silently leak into templates until someone notices. This already caused problems in a previous implementation of this feature.

**Global activation, no per-form configuration (rejected).** Templates always on, every field eligible.

- *Pros:* Zero configuration.
- *Cons:* No control for owners or reviewers; no mitigation for the data-consistency issue.

### Schema drift handling

What happens on apply when the form schema has changed since the template was saved.

**Lenient merging.** Only still-existing, still-eligible fields are merged. Skipped fields are either surfaced in the review step or dropped silently — see Open Questions.

- *Pros:* Templates survive normal schema evolution; users stay informed.
- *Cons:* Users must read the review to see what actually gets applied.

**Strict schema validation (rejected).** Template becomes invalid as soon as the schema diverges from the snapshot at save time.

- *Pros:* No silent partial applications.
- *Cons:* Users must recreate the template after every small change. Defeats the convenience purpose.

### Field locking after template application

After a template is applied, designated fields could become non-editable, to prevent half-edited blocks (e.g. company name changed but country forgotten).

**No locking (chosen).** Applied fields remain editable.

- *Pros:* Fits the "apply, correct, save updated template" workflow.
- *Cons:* Half-edited blocks remain possible; the user has to be diligent.

**Locking selected fields after apply (rejected).** Owner designates fields that turn read-only once filled by a template.

- *Pros:* Prevents inconsistent blocks in adversarial cases.
- *Cons:* Significant complexity (per-field RJSF override, UX for the locked state) and conflicts with "apply, correct, save again".

### Template management UI

saving, listing, applying and deleting of templates inside the UI.

**Modal inside the open form (chosen).** Two actions in the active form ("Save as template", "Apply template") which open modals that handle naming, the workflow-scoped list, the preview and deletion.

- *Pros:* User stays in the context of the workflow they are working on. The list is naturally scoped to the current form.
- *Cons:* Bulk operations across many workflows require opening a representative form first.

**Separate management menu / page (rejected).** A dedicated user-level section shows all templates across all workflows; saving and applying still happen in the form.

- *Pros:* Better for power users with many templates across workflows; bulk delete is straightforward.
- *Cons:* Adds a new navigation surface and pulls the user out of the workflow. Save and apply still need to be in the form anyway.

### Storage location

Where are the templates saved.

**Backend storage (chosen).** Templates persisted in a per-user database table, accessed via REST endpoints.

- *Pros:* Available across browsers, devices and sessions. Survives logout and cache clear. Backend can enforce the field whitelist on save, so the trust boundary stays on the server. Consistent with existing per-user data patterns.
- *Cons:* Requires migration, model, service and endpoints.

**Frontend storage (rejected).** Templates persisted in browser `localStorage` / `IndexedDB`.

- *Pros:* No backend changes. Faster to implement.
- *Cons:* Bound to a single browser and device, lost on cache clear. Whitelist filtering would run on the client and could be bypassed.

## Decision

1. **Activation: per-form, switchable `template_mode`.** A top-level `.form` key `template_mode: off | blacklist | whitelist` controls the form, with **`blacklist` as the default** (an omitted key means blacklist). Per-field eligibility is marked with `template_field: true|false` (renamed from the earlier `templatable`). In `blacklist` every field is eligible unless `template_field: false`; in `whitelist` only `template_field: true` fields are eligible; `off` disables templates for the form. This **diverges from the originally proposed opt-in/whitelist leaning**: templates are now on by default. We accept the data-consistency risk that the rejected opt-out option warned about, because owners can switch any sensitive form to `whitelist` or `off`, the per-field `template_field: false` excludes individual fields, and the server-side trust boundary (see 6) is enforced on both save and apply.
2. **Schema drift: lenient merging, skipped fields surfaced.** Only still-existing, still-eligible fields are merged. Fields that no longer exist or are no longer eligible are returned to the client as `skipped_fields` and shown in the apply preview, so the user sees exactly what a template will and will not fill.
3. **Field locking after apply: not implemented.** The added complexity is not justified given the "apply, correct, save again" workflow we want to support.
4. **Template management surface: modal inside the open form.** Two actions in the form ("Save as template", "Apply template") open modals that handle naming, the form-scoped list, the read-only preview, and deletion. No separate management page. Edits to values always happen in the form itself.
5. **Storage: backend, in a dedicated per-user table** (`workflow_user_form_templates`), with a unique constraint on `(user_id, workflow_name, task_name, template_name)`, where `task_name` is the **stable BPMN element id** of the form (`task.task_spec.name`), not the per-instance runtime task UUID. This mirrors the existing `(workflow_name, task_name)` pairing used elsewhere (e.g. the copy-data response). The table carries `created_at`/`updated_at`; saving a template whose name already exists for that scope **overwrites** it (matching the "apply, correct, save again" flow). REST endpoints (POST) live in `bff_user.py` under `/form_templates/{list,save,resolve,delete}`. The backend derives the scope (workflow name + stable task key) and the live schema from the runtime task id the client passes, so the client cannot misdeclare which form a template belongs to.
6. **Server-side eligibility filtering on save and apply.** The backend discards any field in the incoming `template_data` that is not eligible under the form's `template_mode`/`template_field`, and re-checks eligibility against the current schema on apply. A tampered frontend cannot smuggle additional fields into storage or onto a form.

### Value rule (save)

Only fields whose value is meaningful are stored: a field is dropped when its value is `null` or the empty string `""`. **Booleans are always stored** (including `false`), and `0`, empty arrays `[]`, and empty objects `{}` are kept. Within nested objects the rule is applied per scalar; empty containers are preserved, and array elements are never removed solely for being empty.

### Attachments

Attachment fields (single or multi) are **never templatable**, regardless of `template_field`. A stored data-uri is large and a stored attachment `hash`/`id` references a file bound to a specific workflow instance, which would be invalid or cross-instance on apply.

## Consequences

- Templates are on by default (`blacklist`). Owners edit their `.form` files only to restrict: `template_field: false` to exclude a field, `template_mode: whitelist` for opt-in per field, or `template_mode: off` to disable the form.
- Reviewer risk is mitigated — not eliminated — by the per-field exclusions, the `whitelist`/`off` modes, and the server-side trust boundary; owners of sensitive forms should choose `whitelist` or `off`.
- Schema changes produce visible but non-blocking hints (`skipped_fields`) in the apply preview.
- Templates are strictly user-private. Sharing and read-only locks are not part of this design.

