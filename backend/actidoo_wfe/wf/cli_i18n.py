# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import typer

from actidoo_wfe.wf import providers as workflow_providers
from actidoo_wfe.wf import service_i18n

app = typer.Typer(help="i18n CLI for WFE processes and data models")


def _scan_extensions() -> None:
    """Fill the data-model registry by scanning the engine + extension modules.

    Mirrors the app-startup venusian scan (registration happens at import via the
    ``register_data_model`` decorator); needed because the CLI runs without the
    FastAPI lifespan.
    """
    from actidoo_wfe.venusian_scan import run_venusian_scan

    run_venusian_scan()


@app.command("extract")
def extract(process: str):
    """Extract .pot file for a process"""
    pot_path = service_i18n.extract_messages_for_process(process)
    typer.echo(f"Extracted all forms & BPMN in {process} → {pot_path}")


@app.command("extract-all")
def extract_all():
    """Extract .pot files for all processes"""
    for name in workflow_providers.iter_workflow_names():
        pot_path = service_i18n.extract_messages_for_process(name)
        typer.echo(f"Extracted {name} → {pot_path}")


@app.command("extract-datamodels")
def extract_datamodels():
    """Extract .pot files with the declared labels of every API-exposed data model"""
    from actidoo_wfe.wf.registry_data_model import data_model_registry

    _scan_extensions()
    for descriptor in data_model_registry.list_models():
        if descriptor.api is None or descriptor.i18n_dir is None:
            continue
        pot_path = service_i18n.extract_messages_for_datamodel(descriptor)
        typer.echo(f"Extracted {descriptor.name} → {pot_path}")


@app.command("update")
def update(process: str, locale: str):
    """Update or create .po file for a process"""
    po_path = service_i18n.update_process(process, locale)
    typer.echo(f"Updated catalog: {po_path}")


@app.command("update-all")
def update_all(locale: str):
    """Update all .po catalogs for a locale in all processes"""
    for name in workflow_providers.iter_workflow_names():
        po_path = service_i18n.update_process(name, locale)
        typer.echo(f"Updated {name} → {po_path}")


@app.command("update-datamodel")
def update_datamodel(name: str, locale: str):
    """Update or create the .po file of a data model for a locale"""
    from actidoo_wfe.wf.registry_data_model import data_model_registry

    _scan_extensions()
    po_path = service_i18n.update_datamodel(data_model_registry.get(name), locale)
    typer.echo(f"Updated catalog: {po_path}")


@app.command("compile-all")
def compile_all():
    """Compile all .po files (processes, data models, global) to .mo files"""
    _scan_extensions()
    service_i18n.compile_all()
    typer.echo("Compiled all .po files to .mo")


if __name__ == "__main__":
    app()
