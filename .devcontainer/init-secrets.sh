#!/usr/bin/env sh
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SECRET_FILE="$SCRIPT_DIR/.devcontainer-secrets.env"
KEYCLOAK_REALM_TEMPLATE_FILE="$SCRIPT_DIR/dev-realm.template.json"
KEYCLOAK_REALM_FILE="$SCRIPT_DIR/dev-realm.json"

if [ -f "$SECRET_FILE" ]; then
  # shellcheck disable=SC1090
  . "$SECRET_FILE"
fi

generate_secret() {
  python3 - <<'PY'
import secrets
import string

alphabet = string.ascii_letters + string.digits
print(''.join(secrets.choice(alphabet) for _ in range(48)))
PY
}

ensure_secret() {
  var_name="$1"
  # Use indirect expansion because var_name stores the *name* of the env var and we need its value
  eval current="\${$var_name-}"
  # If the variable already has a value, keep it and skip regeneration
  if [ -n "${current:-}" ]; then
    return
  fi
  # Assign a freshly generated secret to the variable name
  eval "$var_name=\$(generate_secret)"
}

ensure_secret MYSQL_ROOT_PASSWORD
ensure_secret MYSQL_PASSWORD
ensure_secret KEYCLOAK_ADMIN_PASSWORD
ensure_secret KEYCLOAK_DEFAULT_USER_PASSWORD
ensure_secret KEYCLOAK_DEV_CLIENT_SECRET
ensure_secret KEYCLOAK_OTHERAPP_CLIENT_SECRET

export MYSQL_ROOT_PASSWORD
export MYSQL_PASSWORD
export KEYCLOAK_ADMIN_PASSWORD
export KEYCLOAK_DEFAULT_USER_PASSWORD
export KEYCLOAK_DEV_CLIENT_SECRET
export KEYCLOAK_OTHERAPP_CLIENT_SECRET

umask 077
cat > "$SECRET_FILE" <<EOF
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
MYSQL_PASSWORD=$MYSQL_PASSWORD
PMA_PASSWORD=$MYSQL_ROOT_PASSWORD
KEYCLOAK_ADMIN_PASSWORD=$KEYCLOAK_ADMIN_PASSWORD
KEYCLOAK_DEFAULT_USER_PASSWORD=$KEYCLOAK_DEFAULT_USER_PASSWORD
KEYCLOAK_DEV_CLIENT_SECRET=$KEYCLOAK_DEV_CLIENT_SECRET
KEYCLOAK_OTHERAPP_CLIENT_SECRET=$KEYCLOAK_OTHERAPP_CLIENT_SECRET
EOF

if [ ! -f "$KEYCLOAK_REALM_TEMPLATE_FILE" ]; then
  echo "Keycloak template $KEYCLOAK_REALM_TEMPLATE_FILE missing. Please make sure it exists." >&2
  exit 1
fi

render_realm() {
  python3 - "$KEYCLOAK_REALM_TEMPLATE_FILE" "$KEYCLOAK_REALM_FILE" <<'PY'
import os
import sys

template_path, output_path = sys.argv[1:3]
with open(template_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    "__KEYCLOAK_DEFAULT_USER_PASSWORD__": os.environ["KEYCLOAK_DEFAULT_USER_PASSWORD"],
    "__KEYCLOAK_DEV_CLIENT_SECRET__": os.environ["KEYCLOAK_DEV_CLIENT_SECRET"],
    "__KEYCLOAK_OTHERAPP_CLIENT_SECRET__": os.environ["KEYCLOAK_OTHERAPP_CLIENT_SECRET"],
}

for placeholder, value in replacements.items():
    content = content.replace(placeholder, value)

with open(output_path, "w", encoding="utf-8") as f:
    f.write(content)
PY
}

render_realm

echo "Secrets aktualisiert in $SECRET_FILE und Keycloak realm-Datei nach $KEYCLOAK_REALM_FILE geschrieben."
