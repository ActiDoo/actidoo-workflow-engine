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

### Backend
```bash
source .venv/bin/activate
pytest backend
```
Additional tooling such as Ruff/Pylint is included via `backend[dev]`.

### Frontend
The frontend uses [Vitest](https://vitest.dev/) with [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/), split into two projects: fast unit/component tests in jsdom (test files live next to their source files as `*.test.ts(x)` under `frontend/src/`), and workflow form tests in a real Chromium via Vitest browser mode (`frontend/src/test/workflows/`, one directory per workflow — see the README there). The browser needs a one-time `yarn playwright install chromium`.

```bash
cd frontend
yarn test            # run all tests once
yarn test:watch      # watch mode during development
yarn test:coverage   # with coverage report
yarn typecheck       # tsc --noEmit (vite build does not type-check)
```

Both checks also run in CI for every pull request touching `frontend/` (`.github/workflows/frontend-tests.yml`).

Notes:

- The test setup is configured in `frontend/vitest.config.ts`. It is deliberately standalone and does not reuse `vite.config.js`, whose third-party-notices plugin writes into `public/` on dev-server start.
- When writing a new test, use an existing `*.test.ts` (unit) or `*.test.tsx` (component) file as a template.
- Prefer plain unit tests for pure logic. jsdom component tests work well for RJSF/Bootstrap-based components; UI5 web components rely on Shadow DOM and do not work in jsdom — test them in the browser-mode `workflows` project instead.
- New dependencies must be committed together with their `.yarn/cache` zips (zero-installs), otherwise `yarn install --immutable` fails in CI.

## Build the documentation locally
```bash
source .venv/bin/activate
pip install -r docs/requirements.txt
mkdocs serve
```
Changes reload live; the generated HTML lives in `site/` (already in `.gitignore`).
