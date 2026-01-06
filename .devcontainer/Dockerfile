ARG VARIANT=3.13-trixie
FROM mcr.microsoft.com/vscode/devcontainers/python:${VARIANT}

ENV PYTHONUNBUFFERED 1

RUN mkdir -p /run/secrets

# Node.js + Yarn
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg docker.io docker-cli docker-buildx docker-compose \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_24.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        nodejs \
    && COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack enable \
    && corepack prepare yarn@stable --activate \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
    
