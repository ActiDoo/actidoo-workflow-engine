#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

set -euo pipefail

HTTP_PROXY="${HTTP_PROXY:-}"
HTTPS_PROXY="${HTTPS_PROXY:-}"
PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-}"
PIP_INDEX_URL="${PIP_INDEX_URL:-}"
PIP_INDEX="${PIP_INDEX:-}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
VENV_PATH="${VENV_PATH:-/opt/venv}"
BACKEND_DIR="${BACKEND_DIR:-${WORKSPACE_DIR}}"

log_section() {
    echo '------------------------------------------------------------------'
    echo "$@"
    echo '------------------------------------------------------------------'
}

if [[ ! -d "${WORKSPACE_DIR}" ]]; then
    echo "Workspace directory ${WORKSPACE_DIR} not found; set WORKSPACE_DIR if using a custom path."
    exit 20
fi

log_section "Setting up virtualenv for ${WORKSPACE_DIR}"
env | grep -E 'HTTP_PROXY|HTTPS_PROXY|PIP_' || true

if [[ -d /usr/local/share/ca-certificates/ ]]; then
    echo 'Updating certificates for custom CAs'
    sudo update-ca-certificates
fi

PIP_BIN="pip"
if [[ -x "${VENV_PATH}/bin/pip" ]]; then
    PIP_BIN="${VENV_PATH}/bin/pip"
fi

if [[ -n "${PIP_TRUSTED_HOST}" ]]; then
    "${PIP_BIN}" config set global.trusted-host "${PIP_TRUSTED_HOST}"
fi
if [[ -n "${PIP_INDEX_URL}" ]]; then
    "${PIP_BIN}" config set global.index-url "${PIP_INDEX_URL}"
fi
if [[ -n "${PIP_INDEX}" ]]; then
    "${PIP_BIN}" config set global.index "${PIP_INDEX}"
fi

PIP_PROXY_ARGS=()
if [[ -n "${HTTPS_PROXY}" ]]; then
    PIP_PROXY_ARGS+=("--proxy=${HTTPS_PROXY}")
elif [[ -n "${HTTP_PROXY}" ]]; then
    PIP_PROXY_ARGS+=("--proxy=${HTTP_PROXY}")
fi

if [[ ! -d "${VENV_PATH}" ]]; then
    echo "Expected upstream venv at ${VENV_PATH} is missing; creating one."
    python3 -m venv "${VENV_PATH}"
fi

sudo chown -R "$(id -u)":"$(id -g)" "${VENV_PATH}"
rm -rf "${WORKSPACE_DIR}/.venv"
ln -sfn "${VENV_PATH}" "${WORKSPACE_DIR}/.venv"
source "${VENV_PATH}/bin/activate"

"${PIP_BIN}" install ${PIP_PROXY_ARGS[@]+"${PIP_PROXY_ARGS[@]}"} --upgrade pip setuptools wheel

if [[ ! -f "${BACKEND_DIR}/pyproject.toml" ]]; then
    echo "Backend pyproject.toml not found at ${BACKEND_DIR}; set BACKEND_DIR if your workspace layout differs."
    exit 22
fi

"${PIP_BIN}" install ${PIP_PROXY_ARGS[@]+"${PIP_PROXY_ARGS[@]}"} --editable "${BACKEND_DIR}[dev]"

if ! grep -Fq "${VENV_PATH}/bin/activate" "${HOME}/.bashrc"; then
    echo "source ${VENV_PATH}/bin/activate" >> "${HOME}/.bashrc"
fi

echo "Virtualenv ready at ${VENV_PATH}"
exit 0
