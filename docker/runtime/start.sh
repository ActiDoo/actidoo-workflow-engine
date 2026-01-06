#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

set -Eeuo pipefail

# Prepend venv binaries to PATH
export PATH="/opt/venv/bin:${PATH}"

usage() {
  cat <<'EOF'
Usage: /opt/app/start.sh [--only=frontend|--only=backend]

Starts the workflow engine processes under supervisord.
  --only=frontend  Start only nginx (no uvicorn backend)
  --only=backend   Start only uvicorn (no nginx frontend)
  -h, --help       Show this help message
EOF
}

ONLY_COMPONENT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --only=frontend)
      ONLY_COMPONENT="frontend"
      shift
      ;;
    --only=backend)
      ONLY_COMPONENT="backend"
      shift
      ;;
    --only)
      if [[ $# -lt 2 ]]; then
        echo "--only requires a value (frontend|backend)" >&2
        exit 64
      fi
      ONLY_COMPONENT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 64
      ;;
  esac
done

# Required runtime input
: "${BASE_URL:?env BASE_URL must be set}"
: "${FRONTEND_PATH:?env FRONTEND_PATH must be set}"
: "${API_PATH:?env API_PATH must be set}"

# Fixed defaults inside the image
FRONTEND_DIST="/srv/frontend"
FRONTEND_DIST_TEMPLATE="/srv/frontend.template"
NGINX_CONF_PATH="/etc/nginx/conf.d/default.conf"
NGINX_CONF_TEMPLATE_PATH="${NGINX_CONF_PATH}.template"
RUNTIME_PATHS_SCRIPT="/opt/app/runtime-paths.py"
RENDER_RUNTIME_ASSETS_SCRIPT="/opt/app/render-runtime-assets.py"

export BASE_URL FRONTEND_DIST NGINX_CONF_PATH NGINX_CONF_TEMPLATE_PATH FRONTEND_DIST_TEMPLATE

UVICORN_APP="actidoo_wfe.fastapi:app"
UVICORN_HOST="0.0.0.0"
UVICORN_PORT="8000"
UVICORN_FLAGS="--proxy-headers --forwarded-allow-ips=127.0.0.1"

export PROXY_TRUSTED_NETWORKS='["127.0.0.1/32"]'

ENABLE_FRONTEND=true
ENABLE_BACKEND=true
if [[ -n "${ONLY_COMPONENT}" ]]; then
  ENABLE_FRONTEND=false
  ENABLE_BACKEND=false
  case "${ONLY_COMPONENT}" in
    frontend) ENABLE_FRONTEND=true ;;
    backend) ENABLE_BACKEND=true ;;
    *)
      echo "Invalid value for --only: ${ONLY_COMPONENT}. Use frontend or backend." >&2
      exit 64
      ;;
  esac
fi

if [[ "${ENABLE_FRONTEND}" != true && "${ENABLE_BACKEND}" != true ]]; then
  echo "Nothing to start (frontend/backend both disabled)." >&2
  exit 1
fi

require_bin() {
  command -v "$1" >/dev/null || { echo "Missing: $1" >&2; exit 127; }
}
require_bin python3
require_bin supervisord
[[ "${ENABLE_FRONTEND}" == true ]] && require_bin nginx
[[ "${ENABLE_BACKEND}" == true ]] && require_bin uvicorn

ensure_runtime_paths() {
  if [[ ! -x "${RUNTIME_PATHS_SCRIPT}" ]]; then
    echo "Missing runtime paths script: ${RUNTIME_PATHS_SCRIPT}" >&2
    exit 1
  fi
  eval "$("${RUNTIME_PATHS_SCRIPT}")"
}

render_runtime_assets_if_writable() {
  # We default to rendering runtime assets, iff they were not baked at build time
  local flag="${RENDER_RUNTIME_WRITE:-}"
  if [[ -z "${flag}" ]]; then
    if [[ "${RENDER_RUNTIME_AT_BUILD:-}" == "true" ]]; then
      flag=0
    else
      flag=1
    fi
  fi
  case "${flag,,}" in
    0|false|no|off|"")
      echo "Skipping runtime asset rendering (RENDER_RUNTIME_WRITE=${flag})."
      return
      ;;
  esac
  "${RENDER_RUNTIME_ASSETS_SCRIPT}"
}

generate_supervisor_config() {
  local conf_path="$1"
  local run_dir="$2"
  local uvicorn_cmd

  uvicorn_cmd=$(printf '%q ' "${UVICORN_CMD[@]}")
  uvicorn_cmd="${uvicorn_cmd%" "}"

  cat >"${conf_path}" <<EOF
[unix_http_server]
file=${run_dir}/supervisor.sock
chmod=0700
username=dummy
password=dummy

[supervisord]
user=root
nodaemon=true
logfile=/dev/null
pidfile=${run_dir}/supervisord.pid
childlogdir=${run_dir}

[supervisorctl]
serverurl=unix://${run_dir}/supervisor.sock
username=dummy
password=dummy
EOF

  if [[ "${ENABLE_BACKEND}" == true ]]; then
    cat >>"${conf_path}" <<EOF
[program:backend]
command=${uvicorn_cmd}
directory=${APP_HOME:-/opt/app}
autostart=true
autorestart=true
killasgroup=true
stopasgroup=true
stopsignal=TERM
stdout_logfile=/dev/fd/1
stderr_logfile=/dev/fd/2
stdout_logfile_maxbytes=0
stderr_logfile_maxbytes=0
environment=PATH="/opt/venv/bin:%(ENV_PATH)s"

EOF
  fi

  if [[ "${ENABLE_FRONTEND}" == true ]]; then
    cat >>"${conf_path}" <<'EOF'
[program:frontend]
command=nginx -g "daemon off;"
autostart=true
autorestart=true
killasgroup=true
stopasgroup=true
stopsignal=QUIT
stdout_logfile=/dev/null
stderr_logfile=/dev/null
stdout_logfile_maxbytes=0
stderr_logfile_maxbytes=0

EOF
  fi
}

# 1) Generate runtime configuration
ensure_runtime_paths
if [[ "${ENABLE_FRONTEND}" == true ]]; then
  render_runtime_assets_if_writable
else
  echo "Frontend disabled (--only=${ONLY_COMPONENT}); skipping runtime asset rendering."
fi

# 2) Start processes under supervisord
UVICORN_CMD=(uvicorn "${UVICORN_APP}" --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" ${UVICORN_FLAGS})

SUPERVISOR_RUN_DIR="${SUPERVISOR_RUN_DIR:-/run/wfe-supervisor}"
if [[ -L "${SUPERVISOR_RUN_DIR}" ]]; then
  echo "Refusing symlinked supervisor run dir: ${SUPERVISOR_RUN_DIR}" >&2
  exit 1
fi
install -d -m 700 "${SUPERVISOR_RUN_DIR}"
chmod 700 "${SUPERVISOR_RUN_DIR}"

SUPERVISOR_CONF="${SUPERVISOR_RUN_DIR}/supervisord-wfe.conf"
generate_supervisor_config "${SUPERVISOR_CONF}" "${SUPERVISOR_RUN_DIR}"

exec supervisord -c "${SUPERVISOR_CONF}" -n
