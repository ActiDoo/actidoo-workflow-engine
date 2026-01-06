#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
pip-compile --upgrade --output-file=requirements.txt pyproject.toml
