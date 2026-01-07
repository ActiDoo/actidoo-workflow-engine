# Development

## Prerequisites
- Python 3.10 or newer
- pip/venv
- Access to a database matching the `.env` settings (default: MySQL/MariaDB)

## Local setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e backend[dev]
```
Create a `.env` in the project root (or set `ENV_FILE`), e.g., based on `backend/.env.local`.

## Run the API
```bash
source .venv/bin/activate
ENV_FILE=backend/.env.local uvicorn actidoo_wfe.fastapi:app --reload
```
FastAPI exposes Swagger at `/api/docs` and Redoc at `/api/redoc`. Database migrations and storage setup are triggered on startup.

## Tests
```bash
source .venv/bin/activate
pytest backend
```
Additional tooling such as Ruff/Pylint is included via `backend[dev]`.

## Build the documentation locally
```bash
source .venv/bin/activate
pip install -r docs/requirements.txt
mkdocs serve
```
Changes reload live; the generated HTML lives in `site/` (already in `.gitignore`).
