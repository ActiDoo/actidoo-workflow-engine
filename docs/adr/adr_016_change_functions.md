# ADR 016: Change Functions for Derived Form Values

**Status:** Implemented
**Date:** 2026-11-25

## Context

Forms need values that follow from other fields while the user fills them in: the price of the chosen product, the product manager of the chosen product, all prices again when the company changes. Until now a form could only react with hide-if and with dependent select options. Workflows worked around this by putting the extra information into option labels.

Such values are usually shown in `disabled` fields. Disabled fields belong to the backend: on submit the engine ignores the browser's value and keeps the stored one ([ADR 010](adr_010_dynamic_list_row_identity.md)). A value that only the browser wrote into a disabled field would be lost on submit, and accepting it would let the user set it.

## Decision Drivers

1. The user sees the derived value before submitting.
2. A derived value in a disabled field cannot be manipulated from the browser.
3. The workflow developer writes the rule once, in Python, with access to connectors and data models.
4. It works inside dynamic lists without touching row identity.

## Decision

**A field names a change function; the server runs it on change and again on submit.** The custom property `change_function: <name>` on a field names a function `<name>(cth)` in the workflow module, next to options and validation functions. The function receives the form data and the path of the changed field and changes the form data in place.

**While filling, the result is a preview.** The browser sends the form data and the path of the changed field to the BFF. The answer contains only the values that differ, as path and value. The browser applies them to its current data, so input made during the request and uploaded files are not overwritten. Values set this way do not trigger further change functions.

**On submit, the server is the authority for disabled fields.** After the disabled fields have been reset to their stored values, the engine runs every change function, once per occurrence of its field, and takes the values of disabled fields from the result. Editable fields keep what the user submitted; for them the function result is a suggestion. This extends the rule "disabled fields belong to the backend" by a second source: stored, or derived by a change function from the submitted data.

**A change function may only change values.** A result in which rows of a dynamic list were added, removed or reordered is discarded. Rows without an id and reordered ids would have to go through the matching rules of ADR 010; that is left out until a workflow needs it.

## Considered Alternatives

- **Evaluate the rule in the browser (FEEL)** — no access to connectors and data models, and the server would need a second implementation to protect disabled fields, as with hide-if.
- **Trust the browser's value for disabled fields set by a change function** — the user could send any price.
- **Return the whole form data from the endpoint** — overwrites what the user typed during the request and drops file contents that were not sent along.

## Consequences

Change functions run more than once and in no order the developer controls across requests, so they must derive values from the current form data only. On submit they run once per row; a function that calls a connector does so for every row. A client that never calls the endpoint still gets correct disabled values on submit, so the BFF contract version ([ADR 011](adr_011_bff_contract_version.md)) is not raised. Copying a workflow runs the functions on the copied data, so a copy starts with current derived values; a function that fails there is skipped. Forms are frozen with the instance: the property takes effect for instances started after it was added.

## Open Questions

Change functions do not run when a form is opened, except for a field that a default value fills in at that moment; other values needed from the start come from a service task. Adding rows from a change function is not supported.
