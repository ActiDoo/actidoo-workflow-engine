# Third-Party Notices

This project is licensed under the Apache License 2.0 (see `LICENSE`).

It depends on third-party components that are licensed under their respective licenses.

## Frontend (bpmn-js)

The frontend uses `bpmn-js` to render BPMN diagrams. Its license (distributed with the npm package and copied into `frontend/dist/licenses/` during builds) includes an additional condition that the bpmn.io project watermark/link shown as part of rendered diagrams **must not be removed or changed** and **must remain visible**.

When distributing the frontend build output, ensure third-party license texts are included. This repo generates a bundled notices file and copies license texts into `frontend/dist/licenses/` during `yarn wfe:build`.

## Vendored dependencies (.yarn/cache)

This repository vendors npm package archives in `.yarn/cache` (Yarn offline cache). These archives are third-party software and remain licensed under their respective licenses. When redistributing the source repository (including `.yarn/cache`), you are also redistributing those third-party components; ensure the corresponding license texts/notices are preserved and/or made available as required.

## Backend

Backend dependencies include licenses beyond Apache-2.0 (for example LGPL components). Ensure you comply with their requirements when distributing binaries/containers.

## SBOM (Software Bill of Materials)

For container releases, this repository generates CycloneDX SBOM files for the published images and attaches them to the GitHub Release as:
- `sbom-runtime.cdx.json`
- `sbom-devcontainer.cdx.json`
