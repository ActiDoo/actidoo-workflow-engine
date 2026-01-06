# syntax=docker/dockerfile:1.6

ARG BASE_IMAGE=ghcr.io/actidoo/actidoo-workflow-engine:latest
FROM ${BASE_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /tmp/myworkflows
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && rm -rf /tmp/myworkflows

WORKDIR /opt/app
CMD ["/opt/app/start.sh"]
