#!/usr/bin/env python3
"""
Repeatedly-invoked (via cron / GitHub Actions) script that tries to launch an
OCI VM.Standard.A1.Flex instance. Designed to be safe to run every 5 minutes:

  - If an instance with the target display name already exists (and isn't
    terminated), it does nothing. This is what prevents the cron job from
    creating duplicate instances once one launch finally succeeds.
  - If the launch fails because of "Out of capacity" / "Out of host capacity",
    it exits cleanly (exit code 0) so the workflow doesn't show as failed —
    that's an expected, retryable condition, not an error.
  - If the launch succeeds, it sends a success email via Gmail SMTP and exits.
  - Any other (unexpected) API error exits non-zero so the GitHub Action run
    is flagged red and you notice.

All configuration is read from environment variables (populated from GitHub
Actions secrets in the workflow).
"""

import os
import sys
import smtplib
import textwrap
from email.mime.text import MIMEText

import oci


def env(name, required=True, default=None):
    val = os.environ.get(name, default)
    if required and not val:
        print(f"ERROR: missing required environment variable {name}", file=sys.stderr)
        sys.exit(1)
    return val


def read_key_material(content_var, path_var):
    """Return key text from an inline env var, or from a file path env var.

    Inline (content) is used on GitHub Actions; the *_PATH form is convenient
    for local runs where the key lives in a file like ~/.oci/oci_api_key.pem.
    """
    content = os.environ.get(content_var)
    if content:
        return content.replace("\\n", "\n")
    path = os.environ.get(path_var)
    if path:
        with open(os.path.expanduser(path)) as f:
            return f.read()
    print(
        f"ERROR: set either {content_var} or {path_var}", file=sys.stderr
    )
    sys.exit(1)


def build_oci_config():
    """Build an OCI SDK config dict from env vars (no ~/.oci/config file needed)."""
    private_key = read_key_material("OCI_PRIVATE_KEY", "OCI_PRIVATE_KEY_PATH")

    config = {
        "user": env("OCI_USER_OCID"),
        "tenancy": env("OCI_TENANCY_OCID"),
        "fingerprint": env("OCI_FINGERPRINT"),
        "key_content": private_key,
        "region": env("OCI_REGION"),
    }
    oci.config.validate_config(config)
    return config


def find_existing_instance(compute_client, compartment_id, display_name):
    instances = oci.pagination.list_call_get_all_results(
        compute_client.list_instances,
        compartment_id=compartment_id,
        display_name=display_name,
    ).data
    for inst in instances:
        if inst.lifecycle_state not in ("TERMINATED", "TERMINATING"):
            return inst
    return None


def send_email(subject, body):
    gmail_user = env("GMAIL_USER")
    gmail_app_password = env("GMAIL_APP_PASSWORD")
    to_addr = env("NOTIFY_EMAIL", required=False, default=gmail_user)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to_addr

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_app_password)
        server.sendmail(gmail_user, [to_addr], msg.as_string())
    print(f"Sent notification email to {to_addr}")


def main():
    compartment_id = env("OCI_COMPARTMENT_OCID")
    availability_domain = env("OCI_AVAILABILITY_DOMAIN")
    subnet_id = env("OCI_SUBNET_OCID")
    image_id = env("OCI_IMAGE_OCID")
    ssh_public_key = read_key_material(
        "OCI_SSH_PUBLIC_KEY", "OCI_SSH_PUBLIC_KEY_PATH"
    ).strip()
    display_name = env("OCI_INSTANCE_DISPLAY_NAME", required=False, default="free-tier-a1")
    boot_volume_gb = int(env("OCI_BOOT_VOLUME_GB", required=False, default="100"))

    # Shape ladder: try the biggest config first, fall back to progressively
    # smaller ones within the same run. Overridable via OCI_SHAPE_LADDER as a
    # semicolon-separated list of "ocpus,memory_gb" pairs.
    default_ladder = "4,24; 4,12; 2,12; 2,6; 1,6"
    ladder_raw = env("OCI_SHAPE_LADDER", required=False, default=default_ladder)
    shape_ladder = []
    for pair in ladder_raw.split(";"):
        pair = pair.strip()
        if not pair:
            continue
        o, m = pair.split(",")
        shape_ladder.append((float(o.strip()), float(m.strip())))
    shape = "VM.Standard.A1.Flex"

    config = build_oci_config()
    compute_client = oci.core.ComputeClient(config)

    existing = find_existing_instance(compute_client, compartment_id, display_name)
    if existing:
        print(
            f"Instance '{display_name}' already exists "
            f"(id={existing.id}, state={existing.lifecycle_state}). Nothing to do."
        )
        return

    for ocpus, memory_gb in shape_ladder:
        print(
            f"Attempting to launch {shape} with {ocpus:g} OCPUs / "
            f"{memory_gb:g} GB RAM in {availability_domain}..."
        )

        launch_details = oci.core.models.LaunchInstanceDetails(
            compartment_id=compartment_id,
            availability_domain=availability_domain,
            display_name=display_name,
            shape=shape,
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=ocpus,
                memory_in_gbs=memory_gb,
            ),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                image_id=image_id,
                boot_volume_size_in_gbs=boot_volume_gb,
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=subnet_id,
                assign_public_ip=True,
            ),
            metadata={"ssh_authorized_keys": ssh_public_key},
        )

        try:
            response = compute_client.launch_instance(launch_details)
            instance = response.data
            print(f"Launch succeeded ({ocpus:g} OCPUs / {memory_gb:g} GB): {instance.id}")

            send_email(
                subject="✅ Oracle Cloud A1.Flex instance launched!",
                body=textwrap.dedent(
                    f"""\
                    Your VM.Standard.A1.Flex instance was successfully launched.

                    Instance OCID: {instance.id}
                    Display name:  {instance.display_name}
                    Shape:         {ocpus:g} OCPUs / {memory_gb:g} GB RAM
                    Boot volume:   {boot_volume_gb} GB
                    AD:            {availability_domain}
                    State:         {instance.lifecycle_state}

                    Log into the OCI console to finish setup (it may still be
                    PROVISIONING for a minute or two).

                    This cron job will not attempt further launches now that an
                    instance named '{display_name}' exists.
                    """
                ),
            )
            return  # success — stop trying smaller shapes
        except oci.exceptions.ServiceError as e:
            code = str(getattr(e, "code", ""))
            message = (e.message or "") + " " + code
            is_capacity = (
                "OutOfCapacity" in code
                or "Out of capacity" in message
                or "Out of host capacity" in message
            )
            if is_capacity:
                print(
                    f"No capacity for {ocpus:g} OCPUs / {memory_gb:g} GB "
                    f"({e.status}). Trying next smaller shape..."
                )
                continue  # fall back to the next rung of the ladder
            # Unexpected API error: surface it loudly.
            print(f"Unexpected OCI API error ({e.status}): {e.message}", file=sys.stderr)
            sys.exit(1)

    print("No capacity for any shape in the ladder this run. Will retry next cron tick.")


if __name__ == "__main__":
    main()
