#!/usr/bin/env bash
# Load .env and list A1.Flex-compatible images so you can pick OCI_IMAGE_OCID.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "No .env found. Copy .env.example to .env and fill it in first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

exec ./.venv/bin/python list_images.py
