# Oracle Cloud A1.Flex Auto-Launcher

Retries launching a free-tier `VM.Standard.A1.Flex` instance every 30 minutes
via GitHub Actions, until OCI has capacity. Emails you (via Gmail) the moment
it succeeds, and won't try again afterward (it checks for an existing
instance with the same display name first).

## 1. Generate an OCI API signing key pair

You need this so the script can call the OCI API on your behalf, separate
from your console password.

1. Generate a key pair locally:
   ```bash
   mkdir -p ~/.oci
   openssl genrsa -out ~/.oci/oci_api_key.pem 2048
   openssl rsa -pubout -in ~/.oci/oci_api_key.pem -out ~/.oci/oci_api_key_public.pem
   chmod 600 ~/.oci/oci_api_key.pem
   ```
2. In the OCI Console: click your profile icon (top right) → **My profile**.
3. Under **Resources** (left side) → **API keys** → **Add API key**.
4. Choose **Paste public key**, paste the contents of
   `~/.oci/oci_api_key_public.pem`, then **Add**.
5. OCI shows a **Configuration file preview** — copy these values, you'll
   need them as GitHub secrets:
   - `user` → your user OCID
   - `fingerprint`
   - `tenancy` → your tenancy OCID
   - `region`

You also need the **private key contents** (`~/.oci/oci_api_key.pem`, the
whole PEM including `-----BEGIN/END-----` lines) for the `OCI_PRIVATE_KEY`
secret below.

## 2. Collect the other required OCIDs

From the OCI Console:

- **Compartment OCID** — Identity → Compartments (or use your tenancy/root
  compartment OCID if you're not using sub-compartments).
- **Availability domain** — the exact AD name, e.g. `<tenancy-prefix>:EU-FRANKFURT-1-AD-1`
  (shown in the error message you already hit).
- **Subnet OCID** — Networking → Virtual Cloud Networks → (your VCN) →
  Subnets. Use a public subnet if you want a public IP.
- **Image OCID** — Compute → Images, or use `oci compute image list` to find
  an Ubuntu/Oracle Linux ARM (aarch64) image OCID for A1.Flex compatibility.
- **SSH public key** — contents of e.g. `~/.ssh/id_ed25519.pub`, so you can
  log into the instance once it launches.

## 3. Create a Gmail App Password (for sending the notification email)

1. Enable 2-Step Verification on the Gmail account you want to send from.
2. Go to https://myaccount.google.com/apppasswords, create an app password
   (any name, e.g. "oci-launcher"), and copy the 16-character password.

## 4. Add GitHub repository secrets

Push this repo to GitHub, then go to **Settings → Secrets and variables →
Actions → New repository secret** and add:

| Secret | Value |
|---|---|
| `OCI_USER_OCID` | from step 1 |
| `OCI_TENANCY_OCID` | from step 1 |
| `OCI_FINGERPRINT` | from step 1 |
| `OCI_PRIVATE_KEY` | full contents of `oci_api_key.pem` |
| `OCI_REGION` | e.g. `eu-frankfurt-1` |
| `OCI_COMPARTMENT_OCID` | from step 2 |
| `OCI_AVAILABILITY_DOMAIN` | e.g. `xxxx:EU-FRANKFURT-1-AD-1` |
| `OCI_SUBNET_OCID` | from step 2 |
| `OCI_IMAGE_OCID` | from step 2 |
| `OCI_SSH_PUBLIC_KEY` | contents of your `.pub` file |
| `GMAIL_USER` | the Gmail address sending the notification |
| `GMAIL_APP_PASSWORD` | the 16-char app password from step 3 |
| `NOTIFY_EMAIL` | (optional) address to receive the notification — defaults to `GMAIL_USER` |

## 5. Enable the workflow

The workflow at [.github/workflows/launch.yml](.github/workflows/launch.yml)
runs on a `*/30 * * * *` cron schedule once it's on the default branch of a
GitHub repo (scheduled workflows only run from the default branch, and
GitHub disables them automatically after 60 days of repo inactivity — push
a commit occasionally to keep it alive).

You can test it immediately without waiting for the cron via the **Actions**
tab → **Try launch OCI A1.Flex instance** → **Run workflow** (uses the
`workflow_dispatch` trigger already in the file).

## How it avoids duplicate launches

Every run first calls `ListInstances` filtered by display name
(`free-tier-a1` by default, set via `OCI_INSTANCE_DISPLAY_NAME`). If a
non-terminated instance with that name already exists, the script exits
immediately without attempting another launch — so once you succeed, it's
safe to leave the cron running indefinitely.

## Adjusting shape size

Each run tries a **shape ladder** from biggest to smallest, stopping at the
first one OCI has capacity for:

1. 4 OCPUs / 24 GB
2. 4 OCPUs / 12 GB
3. 2 OCPUs / 12 GB
4. 2 OCPUs / 6 GB
5. 1 OCPU / 6 GB

If all five are out of capacity, the run exits cleanly and the cron retries
30 minutes later. Edit the ladder via `OCI_SHAPE_LADDER` in the workflow — a
semicolon-separated list of `ocpus,memory_gb` pairs. Free tier caps you at
4 OCPUs / 24 GB total across A1.Flex instances.

Boot volume is set to **100 GB** via `OCI_BOOT_VOLUME_GB`. Free tier includes
200 GB total block storage, so this leaves 100 GB for extra volumes. Minimum
boot volume is 50 GB.
