#!/usr/bin/env python3
"""List platform images compatible with VM.Standard.A1.Flex (ARM) so you can
pick an OCI_IMAGE_OCID for .env. Uses the same credentials as the launcher."""

import os
import sys
import oci
from launch_instance import build_oci_config, env

os_name = os.environ.get("IMAGE_OS", "Canonical Ubuntu")

config = build_oci_config()
compute = oci.core.ComputeClient(config)
compartment_id = env("OCI_COMPARTMENT_OCID")

images = oci.pagination.list_call_get_all_results(
    compute.list_images,
    compartment_id=compartment_id,
    shape="VM.Standard.A1.Flex",
    operating_system=os_name,
    sort_by="TIMECREATED",
    sort_order="DESC",
).data

if not images:
    print(f"No A1.Flex-compatible images found for OS '{os_name}'.", file=sys.stderr)
    print("Try: IMAGE_OS='Oracle Linux' ./.venv/bin/python list_images.py", file=sys.stderr)
    sys.exit(1)

print(f"\nA1.Flex (ARM) images for '{os_name}' — newest first:\n")
for img in images[:15]:
    print(f"  {img.display_name}")
    print(f"      {img.id}\n")
print("Copy the OCID of the newest one into OCI_IMAGE_OCID in .env\n")
