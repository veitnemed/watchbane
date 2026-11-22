# Lab-only image: build context contains just this file and requirement lists.
# Official ARM64/v8 manifest for Python 3.12.16 slim-bookworm:
# https://raw.githubusercontent.com/docker-library/repo-info/master/repos/python/remote/3.12.16-slim-bookworm.md
FROM docker.io/library/python:3.12.16-slim-bookworm@sha256:df540bfd30bd380e89a349611ce42aa67bcb542d58c047706616eb6ba2f86a1b
WORKDIR /opt/watchbane-deps
COPY requirements-story.txt requirements-story-server.txt ./
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements-story-server.txt
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1
WORKDIR /opt/watchbane-source
USER 65532:65532
