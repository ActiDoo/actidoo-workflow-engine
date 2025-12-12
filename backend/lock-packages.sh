#!/bin/bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
pip-compile --upgrade --output-file=requirements.txt pyproject.toml
