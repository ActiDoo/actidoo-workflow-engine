# Docker Runtime Overview

This image bundles the workflow engine frontend (static assets + nginx) and the FastAPI backend (uvicorn) into a single container. Dockerfile: `docker/runtime/Dockerfile`. A few helper scripts prepare runtime paths and config:

- `runtime-paths.py`: normalizes `BASE_URL`, `FRONTEND_PATH`, `API_PATH` and exports the derived `*_BASE_URL`/`*_BASE_PATH` values.
- `render-runtime-assets.py`: copies the frontend template into the runtime dir, rewrites placeholders in assets and nginx, optionally applies branding (`BRAND_PRIMARY_COLOR`), and removes the nginx fallback if the frontend path is `/`.
- `start.sh`: validates required env vars, runs the two helpers above (unless rendering is skipped), then uses `supervisord` to run uvicorn + nginx (supports `--only=frontend` or `--only=backend` flags).

## Configuration

### Build-time (ARG)
- `BASE_URL` (required for baking): absolute URL (e.g. `https://example.com`).
- `FRONTEND_PATH` (default `/wfe/`): path under `BASE_URL` for the SPA.
- `API_PATH` (default `/api/`): path under `BASE_URL` for the API.
- `RENDER_RUNTIME_AT_BUILD` (default `false`): when `true`, runs path normalization + asset rendering during the image build so the resulting image is ready-only.
- `RENDER_RUNTIME_WRITE` (no default): optional override for the runtime render flag (see below). Typically leave unset and let the runtime decide.
- `NGINX_REAL_IP_FROM` (optional): space- or comma-separated CIDR list for nginx `set_real_ip_from` when baking runtime assets.

### Runtime (ENV)
- Required: `BASE_URL`, `FRONTEND_PATH`, `API_PATH`. If you set the build args above, they land in the image `ENV` and satisfy these.
- Optional:
  - `BRAND_PRIMARY_COLOR`: hex color to inject into `branding.css`.
  - `RENDER_RUNTIME_WRITE`: forces rendering at start (`1`, `true`, …) or skips it (`0`, `false`, …). If unset, `start.sh` defaults to `0` when `RENDER_RUNTIME_AT_BUILD=true`, otherwise to `1`.
  - `RENDER_RUNTIME_AT_BUILD`: persisted in the image when baking was enabled; used only for the defaulting behavior described above.
  - `RENDER_RUNTIME_WRITE=0` is recommended for read-only runtime.
  - `ENVIRONMENT_LABEL`: optional short label (e.g., `STAGING`, `Customer-QA`) injected into `env.js` and shown inside the app header for easy environment identification. Falls back to hostname heuristics when omitted.
  - `NGINX_REAL_IP_FROM`: space- or comma-separated CIDRs for nginx `set_real_ip_from`. Defaults to private ranges (`10.0.0.0/8 172.16.0.0/12 192.168.0.0/16`).
  - `PROXY_TRUSTED_NETWORKS`: JSON array of CIDRs the backend trusts for forwarded headers. Defaults to `["127.0.0.1/32"]` so only nginx inside the container is honored.

## Typical flows

- **Standard runtime-rendered container** (writes on start):\
  `docker run --rm -e BASE_URL=https://example.com -e FRONTEND_PATH=/wfe/ -e API_PATH=/wfe/api/ image`

- **Baked, read-only image** (render at build, skip at start):\
  `docker build -f docker/runtime/Dockerfile -t app-baked . --build-arg BASE_URL=https://example.com --build-arg FRONTEND_PATH=/wfe/ --build-arg API_PATH=/wfe/api/ --build-arg RENDER_RUNTIME_AT_BUILD=true --build-arg RENDER_RUNTIME_WRITE=0`\
  `docker run --rm --read-only app-baked`

- **Force re-render at runtime** (even if baked): set `RENDER_RUNTIME_WRITE=1` at container start.

- **Start a single component** (debugging/health isolation):\
  `docker run --rm ... ghcr.io/example/image /opt/app/start.sh --only=backend`\
  or `... --only=frontend`

- **Branding logo via static file** (no extra env): place or mount a file at `/srv/frontend.template/branding/logo.svg` (supported: svg/png/jpg/jpeg/webp). The runtime copy step will pick it up and serve it at `<FRONTEND_PATH>branding/logo.svg`, with a built-in Actidoo logo as the fallback when none is provided.

> Note: `render-runtime-assets.py` wipes `/srv/frontend` on each start and copies from `/srv/frontend.template`, so mount/replace assets in the template folder, not directly in `/srv/frontend`.
