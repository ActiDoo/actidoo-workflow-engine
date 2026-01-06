#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""
Runtime helper for container/bootstrap scripts.

Exports normalized URLs/paths based on env BASE_URL +/- FRONTEND_PATH/API_PATH:
- FRONTEND_BASE_URL / FRONTEND_BASE_PATH
- API_BASE_URL / API_BASE_PATH
"""

import os
import shlex
from urllib.parse import urlparse


def normalize_path(path: str) -> str:
    """
    Ensures path starts and ends with a single slash.
    Input:  "api", "/api", "api/", "///api///", ""
    Output: "/api/", "/api/", "/api/", "/api/", "/"
    """
    if not path:
        return "/"
    # Strip slashes from both ends, then wrap in single slashes
    clean = path.strip("/")
    return f"/{clean}/" if clean else "/"


def join_paths(base: str, child: str) -> str:
    """Joins two paths safely into one normalized path."""
    # Simple string join, logic is handled by normalize_path
    return normalize_path(f"{base.rstrip('/')}/{child.lstrip('/')}")


def main() -> int:
    base_url_raw = os.environ.get("BASE_URL")
    if not base_url_raw:
        sys_exit("env BASE_URL must be set")

    # 1. Parse & Validate
    parsed = urlparse(base_url_raw.strip())
    if not (parsed.scheme and parsed.netloc):
        sys_exit("BASE_URL must be an absolute URL (e.g. https://example.com)")

    origin = f"{parsed.scheme}://{parsed.netloc}"
    
    # 2. Normalize Paths
    # Use defaults if env vars are missing
    base_path = normalize_path(parsed.path)
    frontend_path = join_paths(base_path, os.environ.get("FRONTEND_PATH", "/"))
    api_base_path = join_paths(base_path, os.environ.get("API_PATH", "/api/"))

    # 3. Construct Output
    # We consistently enforce trailing slashes for all base URLs
    values = {
        "BASE_URL": f"{origin}{base_path}",
        "FRONTEND_BASE_URL": f"{origin}{frontend_path}",
        "FRONTEND_BASE_PATH": frontend_path,
        "API_BASE_URL": f"{origin}{api_base_path}",
        "API_BASE_PATH": api_base_path,
    }

    for key, value in values.items():
        print(f"export {key}={shlex.quote(value)}")

    return 0


def sys_exit(msg: str) -> None:
    """Helper to print error and exit cleanly."""
    print(msg, file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    import sys
    main()
