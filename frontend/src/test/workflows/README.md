# Workflow form tests

One directory per workflow, test file and form fixtures side by side. These tests run
in a real Chromium (Vitest browser mode, project `workflows`); everything else in
`src/` runs in the fast jsdom project `unit`.

```bash
yarn test                          # both projects
yarn vitest --project workflows    # only the workflow tests, watch mode
```

## Fixtures

A fixture is the BFF response for a form: `jsonschema` + `uischema` as in the task view,
or the `options` of a select as returned by `POST user/search_property_options`. Fixtures
are committed, so the tests run without a backend, and they are generated rather than
written by hand. `fixtures.json` in this directory lists each fixture with its source: a
`.form` file under `backend/actidoo_wfe/wf/testdata/processes/`, plus the field name for
option fixtures.

```bash
yarn fixtures          # regenerate all fixtures listed in fixtures.json
yarn fixtures:check    # list stale fixtures without writing, exit 1 if there are any
```

Both run `python -m actidoo_wfe.cli export-form-fixtures` and need the backend's Python
environment (as in the devcontainer). The `Form Fixtures` GitHub workflow runs the check,
so a change to a test form or to the form transformation fails CI until the fixtures are
regenerated.

## Adding a test for another workflow

1. Create `workflows/<flow-name>/`, add the fixture(s) to `fixtures.json` and run
   `yarn fixtures`.
2. Copy the `vi.mock` block for `FetchService` from an existing flow test — it answers
   the option requests of dynamic selects from the fixture instead of the live API.
3. Use `renderTaskForm(fixture)`; it renders the form the way `SingleTask` does. The
   returned helpers fill fields (`field`, `replaceValue`, `selectOption`, `uploadFile`,
   `addListRow`), submit (`submit`, `submitted`) and check hide-if (`isFieldVisible`,
   `waitForField`, `waitForFieldHidden`). Field keys inside lists follow rjsf, e.g.
   `my_list_0_number_a`. The submit payload equals the request body of
   `POST user/submit_task_data`.
