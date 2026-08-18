# Workflow form tests

One directory per workflow, test file and form fixtures side by side. These tests run
in a real Chromium (Vitest browser mode, project `browser`, see `../README.md`);
everything else in `src/` runs in the fast jsdom project `unit`.

```bash
yarn test                        # both projects
yarn vitest --project browser    # only the browser tests, watch mode
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
2. Copy the `vi.mock` line for `FetchService` from an existing flow test. If the form has
   dynamic selects, register a handler with `useFakeBackend` that answers
   `user/search_property_options` from the option fixture (see `test-flow-bff`).
3. Use `renderTaskForm(fixture)`; it renders the form the way `SingleTask` does and returns
   `field(key)` (a locator for the rjsf field `root_<key>`; inside lists e.g.
   `my_list_0_number_a`), `addListRow(label)`, `selectOption(key, label)`,
   `uploadFile(key, file)`, `submit()` and the `submitted` spy. Fill fields with
   `field(key).fill(value)`, check hide-if with `expect.element(field(key)).toBeVisible()`
   / `.not.toBeVisible()`. The submit payload equals the request body of
   `POST user/submit_task_data`.
