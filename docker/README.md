# Docker assets

- `runtime/`: Production/runtime image for the workflow engine (see `runtime/README.md`).
- `devcontainer/`: Devcontainer base image and lifecycle scripts (`wfe-post-create`, `wfe-post-start`).

Common builds:
- Runtime: `docker build -f docker/runtime/Dockerfile -t workflow-engine:<tag> .`
- Devcontainer (uses the runtime image as `BASE_IMAGE`): `docker build -f docker/devcontainer/Dockerfile --build-arg BASE_IMAGE=workflow-engine:<tag> -t workflow-engine-devcontainer:<tag> .`

In CI (GitHub Actions), the base images are pushed to GHCR:
- Runtime: `ghcr.io/<owner>/<repo>:<tag>` (default branch also gets `:latest`)
- Devcontainer: `ghcr.io/<owner>/<repo>-devcontainer:<tag>` (default branch also gets `:latest`)

Note: GHCR repository names must be lowercase, so `<owner>` (and `<repo>`) should be lowercase as well.

Legacy aliases (also pushed for backwards compatibility):
- Runtime: `ghcr.io/<owner>/workflow-engine:<tag>`
- Devcontainer: `ghcr.io/<owner>/workflow-engine-devcontainer:<tag>`
