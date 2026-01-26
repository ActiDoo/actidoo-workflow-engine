#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

set -euo pipefail

usage() {
    cat <<'EOF'
Build the workflow engine runtime image locally, then build the devcontainer image on top.

Usage:
  build-local-devcontainer-image.sh [tag]

Defaults:
  tag: local
  runtime image: workflow-engine
  devcontainer image: workflow-engine-devcontainer

Environment overrides:
  TAG=local
  RUNTIME_IMAGE=workflow-engine
  DEVCONTAINER_IMAGE=workflow-engine-devcontainer
  DOCKER_CMD=docker
  CONTEXT_DIR=/path/to/repo/root
  EXTRA_RUNTIME_BUILD_ARGS="--build-arg KEY=VALUE ..."
  EXTRA_DEVCONTAINER_BUILD_ARGS="--build-arg KEY=VALUE ..."

The devcontainer build always sets BASE_IMAGE to the runtime image ref built in the first step.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ $# -gt 1 ]]; then
    echo "Too many arguments."
    usage
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT_DIR="${CONTEXT_DIR:-${SCRIPT_DIR}}"

RUNTIME_DOCKERFILE="${CONTEXT_DIR}/docker/runtime/Dockerfile"
DEVCONTAINER_DOCKERFILE="${CONTEXT_DIR}/docker/devcontainer/Dockerfile"

if [[ ! -f "${RUNTIME_DOCKERFILE}" ]]; then
    echo "Runtime Dockerfile not found at ${RUNTIME_DOCKERFILE}"
    exit 3
fi

if [[ ! -f "${DEVCONTAINER_DOCKERFILE}" ]]; then
    echo "Devcontainer Dockerfile not found at ${DEVCONTAINER_DOCKERFILE}"
    exit 4
fi

TAG="${TAG:-${1:-local}}"
RUNTIME_IMAGE="${RUNTIME_IMAGE:-workflow-engine}"
DEVCONTAINER_IMAGE="${DEVCONTAINER_IMAGE:-workflow-engine-devcontainer}"
DOCKER_CMD="${DOCKER_CMD:-docker}"

RUNTIME_REF="${RUNTIME_IMAGE}:${TAG}"
DEVCONTAINER_REF="${DEVCONTAINER_IMAGE}:${TAG}"

RUNTIME_BUILD_ARGS=()
DEVCONTAINER_BUILD_ARGS=()

if [[ -n "${EXTRA_RUNTIME_BUILD_ARGS:-}" ]]; then
    read -r -a RUNTIME_BUILD_ARGS <<< "${EXTRA_RUNTIME_BUILD_ARGS}"
fi

if [[ -n "${EXTRA_DEVCONTAINER_BUILD_ARGS:-}" ]]; then
    read -r -a DEVCONTAINER_BUILD_ARGS <<< "${EXTRA_DEVCONTAINER_BUILD_ARGS}"
fi

echo "Building runtime image ${RUNTIME_REF}"
"${DOCKER_CMD}" build \
    -f "${RUNTIME_DOCKERFILE}" \
    -t "${RUNTIME_REF}" \
    "${RUNTIME_BUILD_ARGS[@]+"${RUNTIME_BUILD_ARGS[@]}"}" \
    "${CONTEXT_DIR}"

echo "Building devcontainer image ${DEVCONTAINER_REF} (BASE_IMAGE=${RUNTIME_REF})"
"${DOCKER_CMD}" build \
    -f "${DEVCONTAINER_DOCKERFILE}" \
    -t "${DEVCONTAINER_REF}" \
    --build-arg "BASE_IMAGE=${RUNTIME_REF}" \
    "${DEVCONTAINER_BUILD_ARGS[@]+"${DEVCONTAINER_BUILD_ARGS[@]}"}" \
    "${CONTEXT_DIR}"

echo "Done."
echo "Runtime:      ${RUNTIME_REF}"
echo "Devcontainer: ${DEVCONTAINER_REF}"
