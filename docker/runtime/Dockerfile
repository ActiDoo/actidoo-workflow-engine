# syntax=docker/dockerfile:1

# Multi-stage image that assembles the workflow engine frontend, the FastAPI backend,
# and a thin nginx+tini runtime to run both behind the same container.
ARG BASE_IMAGE=debian:trixie-slim

# --- Frontend stage ---------------------------------------------------------
# Wir nutzen das offizielle Node Image für schnelleren Build (Build-Stage only)
FROM node:24-bookworm-slim AS frontend-build
ENV YARN_ENABLE_IMMUTABLE_INSTALLS=1

WORKDIR /opt/workspace/frontend

# Corepack aktivieren
RUN corepack enable

COPY frontend/package.json frontend/yarn.lock frontend/.yarnrc.yml ./
COPY frontend/.yarn ./.yarn
RUN yarn install --immutable

# Hier wird das Syntax-Feature genutzt
COPY --exclude=dist frontend/ ./
RUN yarn wfe:build

# --- Backend stage ----------------------------------------------------------
# Creates Python wheels for the backend
FROM ${BASE_IMAGE} AS backend-build
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# FIX: sharing=locked verhindert Race-Conditions bei Multi-Arch Builds
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,sharing=locked,target=/var/lib/apt/lists \
    apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-venv python3-pip python3-dev \
       build-essential git libffi-dev libssl-dev libxml2-dev libxslt1-dev pkg-config

WORKDIR /opt/workspace/backend
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/actidoo_wfe ./actidoo_wfe

# FIX: sharing=locked auch für pip cache
RUN --mount=type=cache,sharing=locked,target=/root/.cache/pip \
    python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip wheel --wheel-dir /tmp/wheels .

# --- Runtime stage ----------------------------------------------------------
FROM ${BASE_IMAGE} AS runtime

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

# License (helpful for redistributed artifacts like container images)
COPY LICENSE ./LICENSE
COPY NOTICE ./NOTICE
COPY THIRD_PARTY_NOTICES.md ./THIRD_PARTY_NOTICES.md

# Copy wheels EARLY so they are available for the single RUN block
COPY --from=backend-build /tmp/wheels /tmp/wheels

# OPTIMIZED RUN BLOCK
# 1. Installiert System-Deps
# 2. Installiert Python-App (im selben Layer)
# 3. Löscht Build-Tools (im selben Layer) -> Spart Speicherplatz
# FIX: sharing=locked hinzugefügt
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    --mount=type=cache,sharing=locked,target=/var/lib/apt/lists \
    --mount=type=cache,sharing=locked,target=/root/.cache/pip \
    apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-venv python3-pip nginx-light supervisor tini ca-certificates curl \
    && rm -f /etc/nginx/sites-enabled/default \
    # --- Backend Installation ---
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install --no-index --find-links=/tmp/wheels actidoo-wfe \
    # --- Cleanup ---
    && apt-get purge -y python3-pip curl \
    && apt-get autoremove -y \
    && rm -rf /tmp/wheels \
    && rm -rf /var/lib/apt/lists/*

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

EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["/opt/app/start.sh"]
