#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# Supply-chain defense: only resolve package versions uploaded ≥7 days ago
export PIP_UPLOADED_PRIOR_TO="$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)"

pip-compile --upgrade --no-strip-extras --output-file=requirements.txt pyproject.toml
