#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

set -euo pipefail

LOG_FILE="${LOG_FILE:-/tmp/wfe-frontend.log}"
START_CMD="${START_CMD:-/opt/app/start.sh --only=frontend}"
CHECK_PATTERN="${CHECK_PATTERN:-supervisord|nginx: master process}"
APP_HOME="${APP_HOME:-/opt/app}"

sudo -n touch "${LOG_FILE}"
sudo -n chown root:root "${LOG_FILE}"
sudo -n chmod 644 "${LOG_FILE}"

if [[ ! -d "${APP_HOME}" ]]; then
    echo "App home ${APP_HOME} not found; aborting frontend autostart."
    exit 21
fi

cd "${APP_HOME}"

if pgrep -f "${CHECK_PATTERN}" >/dev/null 2>&1; then
    echo "Frontend already running (match for ${CHECK_PATTERN}), skipping autostart."
    exit 0
fi

echo "Starting frontend via '${START_CMD}'; logging to ${LOG_FILE}"
sudo -E bash -lc "${START_CMD} >>\"${LOG_FILE}\" 2>&1" &
start_pid=$!

for _ in {1..5}; do
    sleep 2
    if pgrep -f "${CHECK_PATTERN}" >/dev/null 2>&1; then
        echo "Frontend started; logs at ${LOG_FILE}"
        exit 0
    fi
done

if ps -p "${start_pid}" >/dev/null 2>&1; then
    echo "Frontend process still starting; not confirming readiness. Tail ${LOG_FILE} for status."
    exit 0
fi

echo "Frontend failed to start; last log lines:"
tail -n 50 "${LOG_FILE}" || true
exit 1
