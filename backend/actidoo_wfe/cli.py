import json
import logging
import sys
import zlib
from asyncio import run
from functools import wraps

import typer
from sqlalchemy import and_, null, text
from sqlalchemy_file import File

import actidoo_wfe.database as database
from actidoo_wfe.settings import settings

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


@app.async_command()
async def run_migrations():
    database.run_migrations(settings)


@app.async_command()
async def create_revision(message: str):
    database.create_revision(settings, message)


@app.command()
def migrate_storage():
    from actidoo_wfe.storage import setup_storage
    
    setup_storage(settings)
    database.setup_db(settings)


    BATCH_SIZE = 1
    from actidoo_wfe.wf.models import WorkflowAttachment
    session: database.Session = database.SessionLocal()
    
    migrated_count = 0
    offset = 0

    while True:
        # Fetch small batch without server-side cursor
        attachments = (
            session.query(WorkflowAttachment)
            .filter(and_(
                WorkflowAttachment.data != null(),
                WorkflowAttachment.file == null(),
            ))
            .limit(BATCH_SIZE)
            .offset(offset)
            .all()
        )

        if not attachments:
            break

        for attachment in attachments:
            if attachment.data and not attachment.file:
                try:
                    attachment.file = File(
                        content=attachment.data,
                        filename=attachment.first_filename or "unnamed",
                        content_type=attachment.mimetype or "application/octet-stream"
                    )
                    #attachment.data = None
                    migrated_count += 1
                    log.debug(f"Migrated attachment ID {attachment.id}")
                except Exception as e:
                    log.warning(f"Failed to migrate attachment ID {attachment.id}: {e}")

        session.commit()
        log.info(f"Committed batch at offset {offset}, total migrated so far: {migrated_count}")
        offset += BATCH_SIZE

    log.info(f"Migration complete. Total migrated: {migrated_count}")


def compress_json(json_text: str) -> bytes:
    return zlib.compress(json_text.encode('utf-8'))

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
            text(f"SELECT id, `{column}` FROM workflow_instance_tasks WHERE `{column}` IS NOT NULL")
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
                    {"c": compressed, "id": str(task_id)}
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
            {"c": compress_json(text_value), "id": str(inst_id)}
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
            {"c": compress_json(text_value), "id": str(msg_id)}
        )

    session.commit()
if __name__ == "__main__":
    app()
