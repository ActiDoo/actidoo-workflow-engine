# ADR 013: Translation Catalogs Are Read at Runtime

**Status:** Implemented
**Date:** 2026-09-22

Amends [ADR 001](adr_001_form_i18n.md): decision points 3 (compilation) and 4 (runtime loads `.mo`) are replaced. The rest of ADR 001 stands.

## Decision

The engine reads the `.po` files directly. A catalog is parsed on first use and kept in memory. The file's modification time decides when it is read again. There is no `.mo` file and no compile command.

A workflow project ships its `.po` files as package data, like its forms. That is all it has to do.

The engine's pytest plugin turns every `.po` into a test of its own. A file that cannot be parsed fails the test run of the project that owns it.

## Why

- A project has nothing to remember. Installing its files is enough.
- The devcontainer and the container behave the same. A saved translation shows up on the next form load.
- Nothing is written inside the container. Read-only file systems and non-root users work.
- A broken catalog is caught by the tests, before deployment.
- The cost is small: one parse per file and process, about twenty milliseconds, on first use.

## Consequences

- The `.po` is the only catalog file. Translators and the engine read the same file.
- Workflow titles are cached per process and change with the next restart.
- A catalog that cannot be read leaves its texts untranslated and logs the cause.
