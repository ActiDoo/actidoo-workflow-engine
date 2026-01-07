# Architecture Overview

The application combines several components into a workflow platform.

## Backend
- **API layer:** `actidoo_wfe.fastapi:app` exposes FastAPI endpoints (OpenAPI at `/api/openapi.json`, Swagger/Redoc enabled).
- **Workflows:** The `actidoo_wfe.wf` package uses SpiffWorkflow for BPMN processes. Scheduler logic (`async_scheduling.py`) drives recurring tasks.
- **Authentication & sessions:** OIDC/OAuth via `actidoo_wfe.auth`, session handling through `SessionMiddleware`.
- **Database:** SQLAlchemy + Alembic (`database.py`, `alembic/`) manage migrations and models (`database_models.py`).
- **Storage:** Abstraction in `storage.py` (local or Azure Blob variants). Upload path is configurable via settings.
- **Observability:** Sentry support can be enabled via environment variables; correlation IDs are attached to requests.

## Configuration
- Settings class in `actidoo_wfe/settings.py`, driven by `.env` (default: `.env`, or set `ENV_FILE`).
- Key variables: `API_PATH`, `CORS_ORIGINS`, `DB_*` for the database, `STORAGE_*` for uploads, `OIDC_*`/`OAUTH_*` for auth, `SENTRY_*` for monitoring.

## Extensibility
- Venusianscan (`venusian_scan.py`) dynamically registers modules that follow the naming scheme.
- Workflows, forms, and templates are shipped as package data (see `pyproject.toml` under `tool.setuptools.package-data`).
