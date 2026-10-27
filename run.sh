#!/usr/bin/env sh
# Arranca Nihongo Desk desde el código fuente (Linux).
cd "$(dirname "$0")" && exec .venv/bin/python -m nihongo_desk "$@"
