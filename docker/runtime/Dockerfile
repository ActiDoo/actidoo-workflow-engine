# syntax=docker/dockerfile:1.7

# Multi-stage image that assembles the workflow engine frontend, the FastAPI backend,
# and a thin nginx+tini runtime to run both behind the same container.
ARG BASE_IMAGE=debian:trixie-slim

# --- Frontend stage ---------------------------------------------------------
# Wir nutzen das offizielle Node Image für schnelleren Build (Build-Stage only)
FROM node:24-bookworm-slim AS frontend-build
ARG TARGETPLATFORM
ENV YARN_ENABLE_IMMUTABLE_INSTALLS=1 \
    YARN_CACHE_FOLDER=/usr/local/share/.cache/yarn

WORKDIR /opt/workspace/frontend

# Corepack aktivieren
RUN corepack enable

COPY frontend/package.json frontend/yarn.lock frontend/.yarnrc.yml ./
COPY frontend/.yarn ./.yarn
RUN --mount=type=cache,sharing=locked,id=yarn-cache-${TARGETPLATFORM},target=/usr/local/share/.cache/yarn \
    yarn install --immutable

# App sources (built artifacts are ignored via .dockerignore)
COPY frontend/ ./
RUN yarn wfe:build

# --- Backend stage ----------------------------------------------------------
# Creates Python wheels for the backend
FROM ${BASE_IMAGE} AS backend-build
ARG TARGETPLATFORM
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# FIX: sharing=locked verhindert Race-Conditions bei Multi-Arch Builds
RUN --mount=type=cache,sharing=locked,id=apt-cache-${TARGETPLATFORM},target=/var/cache/apt \
    --mount=type=cache,sharing=locked,id=apt-lists-${TARGETPLATFORM},target=/var/lib/apt/lists \
    apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-venv python3-pip python3-dev \
       build-essential git libffi-dev libssl-dev libxml2-dev libxslt1-dev pkg-config

WORKDIR /opt/workspace/backend
COPY backend/pyproject.toml backend/requirements.txt ./

# Build dependency wheels in a layer that only changes when the lockfile changes
RUN --mount=type=cache,sharing=locked,id=pip-cache-${TARGETPLATFORM},target=/root/.cache/pip \
    python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip wheel --wheel-dir /tmp/wheels -r requirements.txt

# Build the application wheel separately so code changes don't invalidate deps
COPY backend/actidoo_wfe ./actidoo_wfe
RUN --mount=type=cache,sharing=locked,id=pip-cache-${TARGETPLATFORM},target=/root/.cache/pip \
    /opt/venv/bin/pip wheel --no-deps --wheel-dir /tmp/wheels .

# --- Runtime base stage -----------------------------------------------------
# Contains system deps + prebuilt venv; stays cacheable across app changes.
FROM ${BASE_IMAGE} AS runtime-base

ARG TARGETPLATFORM

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN --mount=type=cache,sharing=locked,id=apt-cache-${TARGETPLATFORM},target=/var/cache/apt \
    --mount=type=cache,sharing=locked,id=pip-cache-${TARGETPLATFORM},target=/root/.cache/pip \
    apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-venv python3-pip nginx-light supervisor tini ca-certificates curl \
    && rm -f /etc/nginx/sites-enabled/default \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && apt-get purge -y python3-pip curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# --- Runtime stage ----------------------------------------------------------
FROM runtime-base AS runtime

ARG TARGETPLATFORM
ARG BASE_URL
ARG FRONTEND_PATH=/wfe/
ARG API_PATH=/api/
ARG RENDER_RUNTIME_AT_BUILD=false
ARG RENDER_RUNTIME_WRITE
ARG NGINX_REAL_IP_FROM

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    APP_HOME=/opt/app \
    BASE_URL=${BASE_URL} \
    FRONTEND_PATH=${FRONTEND_PATH} \
    API_PATH=${API_PATH} \
    FRONTEND_DIST=/srv/frontend \
    FRONTEND_DIST_TEMPLATE=/srv/frontend.template \
    RENDER_RUNTIME_AT_BUILD=${RENDER_RUNTIME_AT_BUILD} \
    RENDER_RUNTIME_WRITE=${RENDER_RUNTIME_WRITE} \
    NGINX_REAL_IP_FROM=${NGINX_REAL_IP_FROM}

WORKDIR ${APP_HOME}

# Backend install from wheelhouse (keeps apt layer cacheable)
COPY --from=backend-build /tmp/wheels /tmp/wheels
RUN --mount=type=cache,sharing=locked,id=pip-cache-${TARGETPLATFORM},target=/root/.cache/pip \
    /opt/venv/bin/pip install --no-index --find-links=/tmp/wheels actidoo-wfe \
    && rm -rf /tmp/wheels

RUN mkdir -p ${FRONTEND_DIST_TEMPLATE} ${FRONTEND_DIST}

# Copy Frontend
COPY --from=frontend-build /opt/workspace/frontend/dist ${FRONTEND_DIST_TEMPLATE}

# Configs & Scripts
COPY docker/runtime/nginx.conf.template /etc/nginx/conf.d/default.conf.template
COPY docker/runtime/start.sh /opt/app/start.sh
COPY docker/runtime/render-runtime-assets.py /opt/app/render-runtime-assets.py
COPY docker/runtime/runtime-paths.py /opt/app/runtime-paths.py

RUN chmod +x /opt/app/start.sh /opt/app/render-runtime-assets.py /opt/app/runtime-paths.py

RUN if [ "${RENDER_RUNTIME_AT_BUILD}" = "true" ]; then \
      echo "--> Baking runtime assets at build time"; \
      eval "$(/opt/app/runtime-paths.py)"; \
      /opt/app/render-runtime-assets.py; \
    fi

# License (helpful for redistributed artifacts like container images)
COPY LICENSE ./LICENSE
COPY NOTICE ./NOTICE
COPY THIRD_PARTY_NOTICES.md ./THIRD_PARTY_NOTICES.md

EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["/opt/app/start.sh"]
