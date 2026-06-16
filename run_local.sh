#!/usr/bin/env bash
# Load .env and run a single launch attempt locally using the venv.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "No .env found. Copy .env.example to .env and fill it in first." >&2
  exit 1
fi

# Export every non-comment line in .env into the environment.
set -a
# shellcheck disable=SC1091
source .env
set +a

exec ./.venv/bin/python launch_instance.py
