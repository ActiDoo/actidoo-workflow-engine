#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Render runtime assets for the frontend.

Prepares the Docker container for execution by:
1. Copy build template so runtime directories
2. Injecting runtime-specific configurations (paths, APIs).
3. Applying optional branding/theming overrides.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from ipaddress import ip_network
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

# Markers used during the build process that need replacement at runtime
FRONTEND_PATH_PLACEHOLDER = "/__WFE_FRONTEND__/"
API_PATH_PLACEHOLDER = "/__WFE_API__/"
TEXT_EXTENSIONS = {".conf", ".html", ".js", ".css", ".json", ".map", ".txt", ".webmanifest"}
DEFAULT_REAL_IP_SOURCES = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
REAL_IP_BLOCK_START = "# __REAL_IP_FROM_START__"
REAL_IP_BLOCK_END = "# __REAL_IP_FROM_END__"
TRUSTED_SOURCE_BLOCK_START = "# __TRUSTED_SOURCE_START__"
TRUSTED_SOURCE_BLOCK_END = "# __TRUSTED_SOURCE_END__"


@dataclass
class RuntimeContext:
    """Holds the context for the current deployment environment."""
    # Filesystem paths
    frontend_dist: Path  # e.g., Path("/opt/actidoo/frontend")
    frontend_dist_template: Path  # e.g., Path("/opt/actidoo/frontend.template")
    nginx_conf: Path  # e.g., Path("/etc/nginx/conf.d/default.conf")
    nginx_template: Path  # e.g., Path("/etc/nginx/conf.d/default.conf.template")
    
    # URLs and Paths
    frontend_base_url: str  # e.g., "https://example.com/wfe/"
    frontend_base_path: str  # e.g., "/wfe/"
    api_base_url: str  # e.g., "https://example.com/wfe/api/"
    api_base_path: str  # e.g., "/wfe/api/"
    
    # Visuals
    brand_primary_color: Optional[str]  # e.g., "ff6600"
    environment_label: Optional[str]  # e.g., "QAS" or "Staging"

    @property
    def frontend_env_js_path(self) -> Path:
        return self.frontend_dist / "env.js"


def get_config(key: str, default: Optional[str] = None, required: bool = False) -> str:
    val = os.environ.get(key, default)
    if required and not val:
        sys.exit(f"CRITICAL: Environment variable '{key}' is required but missing.")
    return val or ""


def initialize_runtime_artifacts(ctx: RuntimeContext) -> None:
    """
    Resets the runtime environment by restoring artifacts from read-only templates.
    
    This ensures that every container restart begins with a clean state, preventing
    cumulative placeholder replacements or corrupted config files.
    """
    # 1. Restore Frontend Assets
    # We must ensure we are not trying to overwrite the template with itself
    if ctx.frontend_dist.resolve() == ctx.frontend_dist_template.resolve():
        sys.exit("Configuration Error: FRONTEND_DIST cannot be the same as FRONTEND_DIST_TEMPLATE.")
    
    if not ctx.frontend_dist_template.is_dir():
        sys.exit(f"Missing template source: {ctx.frontend_dist_template}")

    # Wipe the existing runtime directory to remove stale files
    if ctx.frontend_dist.exists():
        shutil.rmtree(ctx.frontend_dist)
    
    shutil.copytree(ctx.frontend_dist_template, ctx.frontend_dist)

    # 2. Restore NGINX Config
    if not ctx.nginx_template.is_file():
        sys.exit(f"Missing NGINX template: {ctx.nginx_template}")
        
    ctx.nginx_conf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ctx.nginx_template, ctx.nginx_conf)


def apply_visual_branding(dist_path: Path, primary_color: Optional[str]) -> None:
    """
    Generates a branding override CSS file if a primary color is provided.
    
    Calculates color variations (strong/soft) and appends them to the branding CSS
    so the frontend picks up the customer's CI colors immediately.
    """
    if not primary_color:
        return

    css_target = dist_path / "branding.css"
    if not css_target.is_file():
        return

    # --- Internal Helpers for Color Math ---
    def parse_hex(value: str) -> Tuple[int, int, int]:
        clean = value.strip().lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", clean):
            raise ValueError(f"Invalid hex color: {value}")
        return tuple(int(clean[i:i+2], 16) for i in (0, 2, 4))

    def mix(hex1: str, hex2: str, weight: float) -> str:
        # Blends two colors: weight 1.0 is fully hex1, 0.0 is fully hex2
        rgb1, rgb2 = parse_hex(hex1), parse_hex(hex2)
        w1, w2 = weight, 1.0 - weight
        blended = (
            round(rgb1[0] * w1 + rgb2[0] * w2),
            round(rgb1[1] * w1 + rgb2[1] * w2),
            round(rgb1[2] * w1 + rgb2[2] * w2),
        )
        return f"#{blended[0]:02x}{blended[1]:02x}{blended[2]:02x}"

    # --- Main Branding Logic ---
    try:
        # Normalize input
        base_hex = f"#{primary_color.strip().lstrip('#').lower()}"
        
        # Generate semantic shades based on the primary color
        color_vars = {
            "primary": base_hex,
            "strong": mix(base_hex, "#000000", 0.92),
            "soft": mix(base_hex, "#ffffff", 0.90),
        }
        
        css_content = (
            "\n/* Runtime Branding Overrides */\n"
            ":root {\n"
            f"  --color-brand-primary: {color_vars['primary']};\n"
            f"  --color-brand-primary-strong: {color_vars['strong']};\n"
            f"  --color-brand-primary-soft: {color_vars['soft']};\n"
            f"  --color-focus-ring: {color_vars['strong']};\n"
            "}\n"
        )
        
        with css_target.open("a", encoding="utf-8") as f:
            f.write(css_content)
            
    except ValueError as e:
        print(f"WARNING: Branding skipped. {e}", file=sys.stderr)


def write_frontend_env_js(
    target_path: Path,
    frontend_base_url: str,
    api_base_url: str,
    environment_label: Optional[str],
) -> None:
    """Generates the window.__ACTIDOO_RUNTIME_CONFIG__ object for the SPA."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    config_payload = json.dumps(
        {
            "FRONTEND_BASE_URL": frontend_base_url,
            "API_BASE_URL": api_base_url,
            "ENVIRONMENT_LABEL": environment_label or "",
        },
        separators=(",", ":"),
    )
    
    # We dispatch an event so the app knows when config is available
    script_content = (
        f"window.__ACTIDOO_RUNTIME_CONFIG__={config_payload};"
        "window.dispatchEvent(new Event('actidoo:runtime-config-ready'));"
    )
    target_path.write_text(script_content, encoding="utf-8")


def hydrate_frontend_paths(target: Path, replacements: dict[str, str]) -> None:
    """
    Recursively scans frontend assets to replace build-time path placeholders.
    """
    files_to_process = (target,) if target.is_file() else target.rglob("*")

    for file_path in files_to_process:
        if not file_path.is_file() or file_path.suffix not in TEXT_EXTENSIONS:
            continue

        try:
            original_content = file_path.read_text(encoding="utf-8", errors="ignore")
            updated_content = original_content
            for placeholder, value in replacements.items():
                if placeholder in updated_content:
                    updated_content = updated_content.replace(placeholder, value)
            if updated_content != original_content:
                file_path.write_text(updated_content, encoding="utf-8")
        except IOError as e:
            print(f"WARNING: Failed to process {file_path}: {e}", file=sys.stderr)


def parse_real_ip_sources(raw_value: Optional[str]) -> tuple[list[str], list[str], bool]:
    """
    Parses NGINX_REAL_IP_FROM into normalized CIDR strings.
    Returns (valid_entries, invalid_entries, using_default_flag).
    """
    using_default = False
    if raw_value is None or not raw_value.strip():
        candidates = DEFAULT_REAL_IP_SOURCES
        using_default = True
    else:
        candidates = tuple(part.strip() for part in re.split(r"[,\s]+", raw_value) if part.strip())

    valid: list[str] = []
    invalid: list[str] = []
    for entry in candidates:
        try:
            network = ip_network(entry, strict=False)
            normalized = str(network)
        except ValueError:
            invalid.append(entry)
            continue
        if normalized not in valid:
            valid.append(normalized)

    return valid, invalid, using_default


def render_real_ip_block(networks: list[str], indent: str) -> str:
    """Builds the set_real_ip_from block with the desired indentation."""
    lines = [f"{indent}{REAL_IP_BLOCK_START}"]
    if networks:
        lines.extend(f"{indent}set_real_ip_from {network};" for network in networks)
    else:
        lines.append(f"{indent}# set_real_ip_from disabled")
    lines.append(f"{indent}{REAL_IP_BLOCK_END}")
    return "\n".join(lines)


def render_trusted_source_block(networks: list[str], indent: str) -> str:
    """Builds the geo trusted-source block with the desired indentation."""
    lines = [f"{indent}{TRUSTED_SOURCE_BLOCK_START}"]
    if networks:
        width = max(len(network) for network in networks) + 2
        for network in networks:
            padded = network.ljust(width)
            lines.append(f"{indent}{padded}1;")
    else:
        lines.append(f"{indent}# trusted source list disabled")
    lines.append(f"{indent}{TRUSTED_SOURCE_BLOCK_END}")
    return "\n".join(lines)


def apply_real_ip_sources(config_content: str, networks: list[str]) -> str:
    """Injects the set_real_ip_from lines into the templated block."""
    pattern = re.compile(
        r"(?P<indent>[ \t]*)# __REAL_IP_FROM_START__\n(?P<body>.*?)(?P=indent)# __REAL_IP_FROM_END__",
        re.DOTALL,
    )
    match = pattern.search(config_content)
    if not match:
        print("WARNING: NGINX real_ip_from markers not found; skipping injection.", file=sys.stderr)
        return config_content

    replacement = render_real_ip_block(networks, match.group("indent"))
    return config_content[:match.start()] + replacement + config_content[match.end():]


def apply_trusted_source_networks(config_content: str, networks: list[str]) -> str:
    """Injects the trusted source entries into the geo block."""
    pattern = re.compile(
        r"(?P<indent>[ \t]*)# __TRUSTED_SOURCE_START__\n(?P<body>.*?)(?P=indent)# __TRUSTED_SOURCE_END__",
        re.DOTALL,
    )
    match = pattern.search(config_content)
    if not match:
        print("WARNING: NGINX trusted source markers not found; skipping injection.", file=sys.stderr)
        return config_content

    replacement = render_trusted_source_block(networks, match.group("indent"))
    return config_content[:match.start()] + replacement + config_content[match.end():]


def hydrate_nginx_config(
    config_path: Path,
    replacements: dict[str, str],
    frontend_base_path: str,
    real_ip_sources: list[str],
) -> None:
    """Applies path placeholders to NGINX config and removes fallback when needed."""
    try:
        original_content = config_path.read_text(encoding="utf-8", errors="ignore")
    except IOError as e:
        print(f"WARNING: Failed to read NGINX config {config_path}: {e}", file=sys.stderr)
        return

    updated_content = original_content
    for placeholder, value in replacements.items():
        if placeholder in updated_content:
            updated_content = updated_content.replace(placeholder, value)

    updated_content = apply_real_ip_sources(updated_content, real_ip_sources)
    updated_content = apply_trusted_source_networks(updated_content, real_ip_sources)

    if frontend_base_path == "/":
        # Strip nginx Fallback, because Frontend is directly served under "/", otherwise nginx won't start because of duplicate locations
        pattern = re.compile(r"#__FALLBACK_START__.*?#__FALBACK_END__\n?", re.DOTALL)
        updated_content = re.sub(pattern, "", updated_content)

    if updated_content != original_content:
        try:
            config_path.write_text(updated_content, encoding="utf-8")
        except IOError as e:
            print(f"WARNING: Failed to write NGINX config {config_path}: {e}", file=sys.stderr)


def main() -> int:
    # 1. Gather Configuration
    frontend_dist = Path(get_config("FRONTEND_DIST", required=True))
    nginx_conf = Path(get_config("NGINX_CONF_PATH", "/etc/nginx/conf.d/default.conf"))

    ctx = RuntimeContext(
        frontend_dist=frontend_dist,
        frontend_dist_template=Path(get_config("FRONTEND_DIST_TEMPLATE", f"{frontend_dist}.template")),
        nginx_conf=nginx_conf,
        nginx_template=Path(get_config("NGINX_CONF_TEMPLATE_PATH", f"{nginx_conf}.template")),
        
        frontend_base_url=get_config("FRONTEND_BASE_URL", required=True),
        frontend_base_path=get_config("FRONTEND_BASE_PATH", required=True),
        api_base_url=get_config("API_BASE_URL", required=True),
        api_base_path=get_config("API_BASE_PATH", required=True),
        brand_primary_color=get_config("BRAND_PRIMARY_COLOR"),
        environment_label=get_config("ENVIRONMENT_LABEL"),
    )

    real_ip_raw = os.environ.get("NGINX_REAL_IP_FROM")
    real_ip_sources, invalid_real_ip_entries, using_default_real_ip = parse_real_ip_sources(real_ip_raw)
    if invalid_real_ip_entries:
        print(
            f"WARNING: Ignoring invalid NGINX_REAL_IP_FROM entries: {', '.join(invalid_real_ip_entries)}",
            file=sys.stderr,
        )
    if not real_ip_sources:
        print("WARNING: No valid NGINX_REAL_IP_FROM entries; nginx will not rewrite client IPs.", file=sys.stderr)
    real_ip_label = "default" if using_default_real_ip else "custom"
    print(f"--> Configuring nginx real_ip_from ({real_ip_label}): {', '.join(real_ip_sources) or 'none'}")

    # 2. Execute Steps
    print(f"--> Initializing runtime assets in {ctx.frontend_dist}...")
    initialize_runtime_artifacts(ctx)

    print(f"--> Applying branding ({ctx.brand_primary_color or 'Default'})...")
    apply_visual_branding(ctx.frontend_dist, ctx.brand_primary_color)

    print("--> Generating runtime environment config...")
    write_frontend_env_js(
        ctx.frontend_env_js_path,
        ctx.frontend_base_url,
        ctx.api_base_url,
        ctx.environment_label,
    )

    replacements = {
        FRONTEND_PATH_PLACEHOLDER: ctx.frontend_base_path,
        API_PATH_PLACEHOLDER: ctx.api_base_path,
    }
    print(f"--> Hydrating path placeholders (FE: '{ctx.frontend_base_path}', API: '{ctx.api_base_path}')...")
    hydrate_frontend_paths(ctx.frontend_dist, replacements)
    hydrate_nginx_config(ctx.nginx_conf, replacements, ctx.frontend_base_path, real_ip_sources)

    print("--> Runtime preparation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
