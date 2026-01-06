# My Workflows Template

Lean template to bundle private BPMN assets and Python helpers into the Actidoo Workflow Engine. The package metadata is intentionally minimal because it's meant to be copied and baked into Docker images, not published.

## What's inside

- Minimal `pyproject.toml` defining the `myworkflows` package and entry point `actidoo_wfe.workflow_providers`.
- `src/myworkflows/providers.py` registers the packaged workflows with the engine.
- `src/myworkflows/workflows/CustomerOnboarding` contains a small sample workflow plus optional Python helpers.
- `docker/runtime/Dockerfile` layers this extension onto the official engine image.
- `.devcontainer/` and `.github/workflows/build-extension.yml` are optional convenience tooling (editable install in devcontainer, CI image build). The devcontainer consumes the shared base image from this project's container registry (default: `ghcr.io/<owner>/<repo>-devcontainer`; set `WFE_TAG` to pin a tag).
- `conftest.py` enables the shared `actidoo_wfe.testing.pytest_plugin` fixtures (DB lifecycle, cache reset, mail mocking) and mirrors the engine’s test setup (sets the `sys._called_from_test` flag, runs the venusian scanner, and cleans storage) so you can test your workflows easily.

## Add your workflows

1. Create `src/myworkflows/workflows/<WorkflowName>/`.
2. Drop your BPMN/form/JSON files there; add Python helpers in `__init__.py` if needed.
3. Install locally with `pip install --editable .` or let the Docker build copy and install the package.

## Build and run

```bash
docker build -f docker/runtime/Dockerfile -t myworkflows:dev .
docker run --rm \
  -e BASE_URL=https://example.com \
  -e FRONTEND_PATH=/wfe/ \
  -e API_PATH=/api/ \
  myworkflows:dev
```

`BASE_IMAGE` in `docker/runtime/Dockerfile` (and in `.github/workflows/build-extension.yml`) points to the upstream engine image; adjust it to the version you want to extend.

## Test your workflows

- Install the package in editable mode: `pip install -e .`
- Add tests under `tests/` and use the fixtures from `actidoo_wfe.testing.pytest_plugin` (already enabled by `conftest.py`).
- Run `pytest` to execute your workflow tests with the shared database/cache/mail test helpers.
