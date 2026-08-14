# Workflow form tests

One directory per workflow, test file and form fixtures side by side. These tests run
in a real Chromium (Vitest browser mode, project `workflows`); everything else in
`src/` runs in the fast jsdom project `unit`.

```bash
yarn test                          # both projects
yarn vitest --project workflows    # only the workflow tests, watch mode
```

Fixtures are generated with the real backend code, not written by hand: form fixtures
via `transform_camunda_form_from_file()` (`backend/actidoo_wfe/wf/form_transformation.py`),
option fixtures for dynamic selects via `get_options()` (`backend/actidoo_wfe/wf/service_form.py`).
Regenerate them whenever the workflow's `.form` file, its options, or those functions change.

Adding a test for another workflow:

1. Create `workflows/<flow-name>/` and generate the fixture(s).
2. Copy the `vi.mock` block for `FetchService` from an existing flow test — it answers
   the option requests of dynamic selects from the fixture instead of the live API.
3. Use `renderTaskForm(fixture)` with `field(key)`, `selectOption(key, label)`,
   `uploadFile(key, file)` and `submit()`, then assert the submit payload — it equals
   the request body of `POST user/submit_task_data`.
