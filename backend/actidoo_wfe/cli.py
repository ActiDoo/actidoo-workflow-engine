# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import json
import logging
import sys
import zlib
from asyncio import run
from functools import wraps
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import text

import actidoo_wfe.database as database
from actidoo_wfe.settings import settings
from actidoo_wfe.wf.form_fixtures import DEFAULT_MANIFEST, REPO_ROOT, export_form_fixtures

logging.basicConfig(
    stream=sys.stderr,
    level=settings.log_level,
    format="%(asctime)s\t[%(levelname)s]\t%(message)s",
)

log = logging.getLogger(__name__)

log.info("Starting CLI")


class AsyncTyper(typer.Typer):
    def async_command(self, *args, **kwargs):
        def decorator(async_func):
            @wraps(async_func)
            def sync_func(*_args, **_kwargs):
                return run(async_func(*_args, **_kwargs))

            self.command(*args, **kwargs)(sync_func)
            return async_func

        return decorator


app = AsyncTyper()


@app.async_command()
async def reset_db():
    database.drop_all(settings)
    database.run_migrations(settings)
    # Bundled demo data models (wf/testdata) ship no migration — their tables are
    # otherwise created only at app startup, so a plain reset would leave them missing
    # until the next server restart. Recreate them here, registered via the same scan
    # and gated on the same setting as startup (never in prod).
    if settings.show_test_workflows:
        from actidoo_wfe.venusian_scan import run_venusian_scan
        from actidoo_wfe.wf.registry_data_model import create_registered_data_model_tables

        engine = database.setup_db(settings)
        run_venusian_scan()  # registers the bundled data models
        create_registered_data_model_tables(engine)


@app.async_command()
async def run_migrations():
    database.run_migrations(settings)


@app.async_command()
async def create_revision(message: str):
    database.create_revision(settings, message)


@app.command("export-form-fixtures")
def export_form_fixtures_command(
    manifest: Annotated[Path, typer.Argument(help="Fixture manifest (fixtures.json).")] = DEFAULT_MANIFEST,
    check: Annotated[bool, typer.Option("--check", help="Only report stale fixtures, write nothing; exit 1 if any.")] = False,
):
    """Regenerate the frontend's workflow-form fixtures (see wf/form_fixtures.py)."""
    if not manifest.exists():
        typer.echo(f"no fixture manifest at {manifest}", err=True)
        raise typer.Exit(2)

    # Developer tool: the transformation's debug logging would drown the per-file report.
    logging.getLogger("actidoo_wfe.wf").setLevel(logging.WARNING)
    result = export_form_fixtures(manifest, check=check)

    def show(path: Path) -> str:
        return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)

    for path in result.updated:
        typer.echo(f"updated    {show(path)}")
    for path in result.stale:
        typer.echo(f"stale      {show(path)}")
    for path in result.unchanged:
        typer.echo(f"unchanged  {show(path)}")

    if result.stale:
        typer.echo(
            f"{len(result.stale)} fixture(s) out of date - run `yarn fixtures` (frontend/) or `python -m actidoo_wfe.cli export-form-fixtures`",
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(f"{len(result.updated)} updated, {len(result.unchanged)} unchanged")


def compress_json(json_text: str) -> bytes:
    return zlib.compress(json_text.encode("utf-8"))


@app.command()
def migrate_jsonblob():
    database.setup_db(settings)
    session: database.Session = database.SessionLocal()

    def is_compressed(data: bytes) -> bool:
        try:
            zlib.decompress(data)
            return True
        except zlib.error:
            return False

    # 1) workflow_instance_tasks
    for column in ("data", "jsonschema", "uischema"):
        rows = session.execute(
            text(f"SELECT id, `{column}` FROM workflow_instance_tasks WHERE `{column}` IS NOT NULL"),
        ).fetchall()

        for task_id, original in rows:
            text_value = None

            if isinstance(original, str):
                text_value = original

            elif isinstance(original, (bytes, bytearray)):
                if is_compressed(original):
                    continue
                text_value = original.decode("utf-8")

            if text_value is not None:
                json.loads(text_value)
                compressed = compress_json(text_value)

                session.execute(
                    text(f"UPDATE workflow_instance_tasks SET `{column}` = :c WHERE id = :id"),
                    {"c": compressed, "id": str(task_id)},
                )

    # 2) workflow_instances.data
    rows = session.execute(text("SELECT id, data FROM workflow_instances")).fetchall()
    for inst_id, original in rows:
        if isinstance(original, (bytes, bytearray)):
            if not is_compressed(original):
                text_value = original.decode("utf-8")
            else:
                continue
        elif isinstance(original, str):
            text_value = original
        else:
            continue

        json.loads(text_value)
        session.execute(
            text("UPDATE workflow_instances SET data = :c WHERE id = :id"),
            {"c": compress_json(text_value), "id": str(inst_id)},
        )

    # 3) workflow_messages.data
    rows = session.execute(text("SELECT id, data FROM workflow_messages")).fetchall()
    for msg_id, original in rows:
        if isinstance(original, (bytes, bytearray)):
            if not is_compressed(original):
                text_value = original.decode("utf-8")
            else:
                continue
        elif isinstance(original, str):
            text_value = original
        else:
            continue

        json.loads(text_value)
        session.execute(
            text("UPDATE workflow_messages SET data = :c WHERE id = :id"),
            {"c": compress_json(text_value), "id": str(msg_id)},
        )

    session.commit()


if __name__ == "__main__":
    app()
