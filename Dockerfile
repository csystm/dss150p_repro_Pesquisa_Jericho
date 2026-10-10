# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: build tools for wheels that need them, libpq for psycopg2 at runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
 && rm -rf /var/lib/apt/lists/*

# Non-root user
ARG UID=1000
ARG GID=1000
RUN groupadd -g "${GID}" app \
 && useradd  -m -u "${UID}" -g "${GID}" -s /bin/bash app

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# Copy project sources
COPY --chown=app:app src/          ./src/
COPY --chown=app:app sql/          ./sql/
COPY --chown=app:app scripts/      ./scripts/
COPY --chown=app:app config/       ./config/
COPY --chown=app:app metadata/     ./metadata/
COPY --chown=app:app data/source/  ./data/source/
COPY --chown=app:app README.md ATTRIBUTION.md ./

# Data/outputs are mounted at runtime; create the directories so imports don't fail
RUN mkdir -p data/raw data/staging data/curated data/partitioned data/quarantine outputs \
 && chown -R app:app data outputs

USER app

# Default command keeps the container alive so we can `docker compose exec` into it.
# The pipeline itself is invoked explicitly.
CMD ["tail", "-f", "/dev/null"]