# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from pathlib import Path

from actidoo_wfe.helpers.net import generate_instance_name

ALEMBIC_PATH = Path(__file__).parent / "alembic"
CRON_TIMEZONE = "Europe/Berlin"

INSTANCE_NAME = generate_instance_name()
