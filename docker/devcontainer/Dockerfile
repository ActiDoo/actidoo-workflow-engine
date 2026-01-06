# syntax=docker/dockerfile:1.7

# Defaults to the workflow-engine image built from this repo; override via BASE_IMAGE for other registries/tags.
ARG BASE_IMAGE=workflow-engine:latest
FROM ${BASE_IMAGE} AS devcontainer

USER root
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

# Install lightweight dev tooling on top of the runtime image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
        iproute2 \
        less \
        procps \
        python3-venv \
        sudo \
        docker.io docker-cli docker-buildx docker-compose \
    && rm -rf /var/lib/apt/lists/*

RUN if id -u "${USERNAME}" >/dev/null 2>&1; then \
        usermod --uid "${USER_UID}" "${USERNAME}" \
        && groupmod --gid "${USER_GID}" "${USERNAME}"; \
    else \
        groupadd --gid "${USER_GID}" "${USERNAME}" \
        && useradd -s /bin/bash --uid "${USER_UID}" --gid "${USER_GID}" -m "${USERNAME}"; \
    fi \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME} \
    && mkdir -p /workspace \
    && chown -R "${USERNAME}:${USER_GID}" /workspace

COPY docker/devcontainer/wfe-post-create.sh /usr/local/bin/wfe-post-create
COPY docker/devcontainer/wfe-post-start.sh /usr/local/bin/wfe-post-start
RUN chmod +x /usr/local/bin/wfe-post-create /usr/local/bin/wfe-post-start

USER ${USERNAME}
WORKDIR /workspace
