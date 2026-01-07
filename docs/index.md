# Actidoo Workflow Engine

This documentation collects the essentials of the project. The application provides a FastAPI-based workflow engine (BPMN via SpiffWorkflow) with authentication, persistence through SQLAlchemy/Alembic, storage integration, and Sentry support.

## What you find here
- Architecture overview and core modules.
- Development and operations notes for local testing and CI.
- How the MkDocs publishing pipeline works.

## Quickstart for the docs
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r docs/requirements.txt
mkdocs serve
```
The site runs locally at `http://127.0.0.1:8000`.

## Contents
- `Architecture`: How FastAPI, the workflow engine, database, and storage fit together.
- `Development`: Local setup, tests, and useful scripts.

## Deployment via GitHub Pages
A GitHub Actions workflow builds and publishes the MkDocs site after each push to the default branch. Once the workflow has run once, point GitHub Pages to the `gh-pages` branch in the repository settings.
