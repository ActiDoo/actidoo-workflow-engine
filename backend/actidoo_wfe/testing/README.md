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
