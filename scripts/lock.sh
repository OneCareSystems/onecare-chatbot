#!/usr/bin/env bash
set -euo pipefail
docker run --rm -v "$PWD":/app -w /app python:3.11.9-slim bash -c '
  apt-get update -qq &&
  apt-get install -y -qq build-essential pkg-config default-libmysqlclient-dev &&
  pip install -q pip-tools==7.4.1 &&
  pip-compile requirements.in -o requirements.txt --strip-extras &&
  pip-compile requirements-dev.in -o requirements-dev.txt --strip-extras'