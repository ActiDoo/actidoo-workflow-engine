#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

set -euo pipefail

HTTP_PROXY="${HTTP_PROXY:-}"
HTTPS_PROXY="${HTTPS_PROXY:-}"
PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-}"
PIP_INDEX_URL="${PIP_INDEX_URL:-}"
PIP_INDEX="${PIP_INDEX:-}"
YARN_NPM_REGISTRY_SERVER="${YARN_NPM_REGISTRY_SERVER:-https://registry.npmjs.org}"
YARN_UNSAFE_HTTP_WHITELIST="${YARN_UNSAFE_HTTP_WHITELIST:-}"

cd /workspace

echo '------------------------------------------------------------------'
echo 'Make sure the env variables are properly set:'
env |grep proxy || true
env |grep PIP || true
env |grep YARN || true
echo '------------------------------------------------------------------'

# Update certificates if mounted
if [ -d /usr/local/share/ca-certificates/ ]; then
    echo 'Updating certificates, needed for git-go etc.'
    ls /usr/local/share/ca-certificates/
    sudo update-ca-certificates
    echo 'Certificates up to date'
    echo '------------------------------------------------------------------'
fi

# Ensure the non-root user can talk to the host docker daemon (for image builds)
if [ -S /var/run/docker.sock ]; then
    DOCKER_SOCKET_GID=$(stat -c '%g' /var/run/docker.sock)
    SOCKET_GROUP=$(getent group "${DOCKER_SOCKET_GID}" | cut -d: -f1 || true)

    if [ -n "${SOCKET_GROUP}" ]; then
        TARGET_DOCKER_GROUP="${SOCKET_GROUP}"
    elif getent group docker >/dev/null; then
        sudo groupmod -g "${DOCKER_SOCKET_GID}" docker
        TARGET_DOCKER_GROUP="docker"
    else
        sudo groupadd -g "${DOCKER_SOCKET_GID}" docker
        TARGET_DOCKER_GROUP="docker"
    fi

    sudo usermod -aG "${TARGET_DOCKER_GROUP}" "$(whoami)"
    echo "Docker socket available; user $(whoami) added to group ${TARGET_DOCKER_GROUP} (gid ${DOCKER_SOCKET_GID})."
    echo '------------------------------------------------------------------'
else
    echo 'Docker socket not found in devcontainer; docker builds will fail until it is mounted.'
    echo '------------------------------------------------------------------'
fi

# Install pip tools for dependency management
pip config set global.trusted-host "${PIP_TRUSTED_HOST}"
pip config set global.index-url "${PIP_INDEX_URL}"
pip config set global.index "${PIP_INDEX}"

PIP_PROXY_ARGS=()
if [ -n "${HTTP_PROXY}" ]; then
    PIP_PROXY_ARGS+=("--proxy=${HTTP_PROXY}")
fi

pip install --timeout=5 "${PIP_PROXY_ARGS[@]}" --upgrade pip setuptools wheel pip-tools

rm -rf .venv
rm -rf backend/.venv
python3 -m venv backend/.venv
# Keep a workspace-level .venv symlink so VS Code auto-detection finds the backend env
ln -sfn backend/.venv .venv
source backend/.venv/bin/activate

export PYTHONPATH=/workspace/backend:${PYTHONPATH:-}

pip config list
pip install "${PIP_PROXY_ARGS[@]}" --upgrade pip setuptools
pip install "${PIP_PROXY_ARGS[@]}" -e "./backend[dev]"

if [ -d frontend ]; then
    echo '------------------------------------------------------------------'
    echo 'Installing frontend dependencies with yarn'
    pushd frontend >/dev/null
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 yarn install
    popd >/dev/null
fi
