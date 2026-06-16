#!/usr/bin/env bash
# Push all required secrets from .env / key files to the GitHub repo.
# Run this yourself after `gh auth login`. Nothing here is printed or logged.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "No .env found. Fill that in first." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Not logged into gh. Run: gh auth login" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

REPO="Masterchinedum/oracle_instance_launcher"

set_secret() {
  local name="$1" value="$2"
  if [[ -z "$value" || "$value" == FILL_ME* ]]; then
    echo "Skipping $name (empty/unfilled)"
    return
  fi
  echo -n "$value" | gh secret set "$name" --repo "$REPO"
  echo "Set $name"
}

# Plain values from .env
set_secret OCI_USER_OCID "$OCI_USER_OCID"
set_secret OCI_TENANCY_OCID "$OCI_TENANCY_OCID"
set_secret OCI_FINGERPRINT "$OCI_FINGERPRINT"
set_secret OCI_REGION "$OCI_REGION"
set_secret OCI_COMPARTMENT_OCID "$OCI_COMPARTMENT_OCID"
set_secret OCI_AVAILABILITY_DOMAIN "$OCI_AVAILABILITY_DOMAIN"
set_secret OCI_SUBNET_OCID "$OCI_SUBNET_OCID"
set_secret OCI_IMAGE_OCID "$OCI_IMAGE_OCID"
set_secret GMAIL_USER "$GMAIL_USER"
set_secret GMAIL_APP_PASSWORD "$GMAIL_APP_PASSWORD"
set_secret NOTIFY_EMAIL "$NOTIFY_EMAIL"

# File-backed values: read the actual file contents, not the path.
PRIVATE_KEY_PATH="${OCI_PRIVATE_KEY_PATH/#\~/$HOME}"
SSH_PUB_PATH="${OCI_SSH_PUBLIC_KEY_PATH/#\~/$HOME}"

if [[ -f "$PRIVATE_KEY_PATH" ]]; then
  gh secret set OCI_PRIVATE_KEY --repo "$REPO" < "$PRIVATE_KEY_PATH"
  echo "Set OCI_PRIVATE_KEY (from $PRIVATE_KEY_PATH)"
else
  echo "WARNING: $PRIVATE_KEY_PATH not found, OCI_PRIVATE_KEY not set" >&2
fi

if [[ -f "$SSH_PUB_PATH" ]]; then
  gh secret set OCI_SSH_PUBLIC_KEY --repo "$REPO" < "$SSH_PUB_PATH"
  echo "Set OCI_SSH_PUBLIC_KEY (from $SSH_PUB_PATH)"
else
  echo "WARNING: $SSH_PUB_PATH not found, OCI_SSH_PUBLIC_KEY not set" >&2
fi

echo
echo "Done. Verify at: https://github.com/$REPO/settings/secrets/actions"
