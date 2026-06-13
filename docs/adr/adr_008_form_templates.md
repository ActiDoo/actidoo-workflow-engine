# ADR 008: Form Templates (User-Scoped Reusable Form Inputs)

**Status:** Proposed
**Date:** 2026-06-08

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

1. **Activation: per-form, with per-field control — mode still open.** The leaning is opt-in with a per-field whitelist (`templatable: true`), so new fields do not silently leak into templates. Whether to expose this as a switchable `template_mode` (e.g. whitelist/blacklist) so owners can also allow all fields at once is still open — see Open Questions.
2. **Schema drift: lenient merging — surfacing still open.** Only still-existing, still-eligible fields are merged, so existing templates survive normal schema evolution. Whether skipped fields are surfaced in a review step or dropped silently is still open — see Open Questions.
3. **Field locking after apply: not implemented.** The added complexity is not justified given the "apply, correct, save again" workflow we want to support.
4. **Template management surface: modal inside the open form.** Two actions in the form ("Save as template", "Apply template") open modals that handle naming, the workflow-scoped list, the read-only preview, and deletion. No separate management page. Edits to values always happen in the form itself.
5. **Storage: backend, in a dedicated per-user table** (`workflow_user_form_templates`), with a unique constraint on `(user_id, workflow_name, template_name)`. REST endpoints in `bff_user.py`. Backend persistence ensures templates work across browsers and devices and keeps the whitelist trust boundary on the server rather than on the client.
6. **Server-side whitelist filtering on save.** The backend discards any field in the incoming `template_data` that is not `templatable: true`. A tampered frontend cannot smuggle additional fields.

## Open Questions

- **Skipped fields on apply: surface them or drop them silently?** When the schema has changed since the template was saved, fields that no longer exist or are no longer eligible can either be shown in the review step or dropped without comment. Surfacing is more transparent about what the template actually applied; dropping silently means less noise for the user.
- **An "allow all fields" activation mode.** A per-field whitelist means marking each field `templatable: true`, which is friction when an owner deliberately wants every field eligible. Activation could instead be a switchable mode — e.g. `template_mode: deactivated (default) | whitelist | blacklist` — letting owners pick an all-fields (blacklist) mode where appropriate, weighed against the data-consistency risk a blacklist carries.

## Consequences

- Owners have to edit their `.form` files to enable templates. This is intentional and makes activation visible and traceable.
- Reviewer risk is reduced because the owner explicitly controls which fields can be filled via templates.
- Schema changes produce visible but non-blocking hints in the template review step.
- Templates are strictly user-private. Sharing and read-only locks are not part of this design.

