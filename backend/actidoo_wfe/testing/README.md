# Shared pytest fixtures

Fixtures and testing utilities for `actidoo_wfe` live under `actidoo_wfe.testing` so they can be reused by customer projects.

Usage in downstream projects:
- Install `actidoo-wfe` in your test environment.
- Opt in to the plugin via `pytest_plugins = ("actidoo_wfe.testing.pytest_plugin",)` in your `conftest.py` (or run `pytest -p actidoo_wfe.testing.pytest_plugin`).
- Import general-purpose helpers from `actidoo_wfe.testing.utils` (legacy imports from `actidoo_wfe.helpers.tests` still work via a shim).

Provided fixtures:
- `db_engine_ctx` – wraps tests in an isolated database lifecycle.
- `clear_cache` – autouse fixture clearing `actidoo_wfe.cache.Namespace`.
- `mock_send_text_mail` – captures outgoing text mails for assertions.

## Dynamic lists and row ids (ADR 010)

The engine stamps a technical row id onto every dynamic-list row when a task is
handed out, and rejects a list that comes back without them. Hand-written
payload literals know nothing about those ids - the test client bridges that
gap, so no concrete ids appear in test code:

- `UserDummy.submit(...)` adopts the stored row ids by position whenever the
  payload's lists are id-less and match the stored row count - what a browser
  sends when a user edits the loaded form without adding or removing rows.
- A payload whose list grew or shrank cannot be mapped by position; `submit`
  then raises `RowIdCarryError` with the options: start from the handed-out
  task data (or set the row ids yourself) to express which rows remain, or
  pass `carry_row_ids=False` to send the payload untouched (e.g. to test the
  id-less rejection itself).
- `strip_row_ids(data)` (from `actidoo_wfe.testing.utils`) removes the
  technical key at every depth before comparing task data against
  hand-written expectations; `are_dicts_equal` already ignores it.
