# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import typer

from actidoo_wfe.wf import providers as workflow_providers, service_i18n

app = typer.Typer(help="i18n CLI for WFE processes")

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

@app.command("compile-all")
def compile_all():
    """Compile all .po files to .mo files"""
    service_i18n.compile_all()
    typer.echo("Compiled all .po files to .mo")

if __name__ == "__main__":
    app()
