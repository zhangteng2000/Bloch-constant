"""Read-only CANDIDATE: verify downloaded parts, not mathematical acceptance.

Requires separately reviewed package-manifest and original inventory SHA-256 pins.
Never opens original source paths, extracts files, runs Lean, or writes files.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path
import stream_source_package as p


def verify(package_dir, package_manifest_sha256, manifest, manifest_sha256,
           support_inventory, support_inventory_sha256):
    directory = p.safe_path(package_dir, directory=True)
    p.require(isinstance(package_manifest_sha256, str) and p.HEX.fullmatch(package_manifest_sha256)
              and isinstance(manifest_sha256, str) and p.HEX.fullmatch(manifest_sha256),
              "Explicit reviewed package and inventory SHA-256 pins are required")
    result, result_hash = p.read_json(directory / "package-manifest.json")
    p.require(result_hash == package_manifest_sha256, "Package manifest differs from explicit SHA")
    raw = p.read_bytes(manifest)
    p.require(p.sha(raw) == manifest_sha256 == result.get("manifest_sha256"), "Inventory pin differs")
    plan = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=p.strict_object)
    entries, _ = p.validate_inventory(plan, check_source_files=False)
    p.require(isinstance(support_inventory_sha256, str) and p.HEX.fullmatch(support_inventory_sha256),
              "Explicit support inventory SHA-256 pin required")
    support_bytes = p.read_bytes(support_inventory, 8 * p.BLOCK)
    p.require(p.sha(support_bytes) == support_inventory_sha256, "Support inventory pin differs")
    support_plan = json.loads(support_bytes.decode("utf-8-sig"), object_pairs_hook=p.strict_object)
    support_files = p.validate_support_inventory(support_plan, check_source_files=False)
    support_record = result.get("publication_support_inventory", {})
    p.require(isinstance(support_record.get("source_path"), str)
              and support_record.get("archive_path") == p.RESERVED_SUPPORT_INVENTORY
              and support_record.get("sha256") == support_inventory_sha256
              and support_record.get("size_bytes") == len(support_bytes)
              and support_record.get("role") == "publication_support_selection_not_acceptance_inputs"
              and result.get("publication_support_files") == support_files
              and result.get("publication_support_bytes") == sum(e["size_bytes"] for e in support_files),
              "Support inventory/result binding differs")
    notes = result.get("additional_publication_metadata", [])
    members, _, _ = p.archive_members(entries, raw, manifest_sha256, notes,
                                      support_files, support_bytes, support_inventory_sha256)
    p.require(result.get("status") == "STREAMING_PACKAGE_READBACK_VERIFIED_NOT_NEW_MATHEMATICAL_ACCEPTANCE"
              and result.get("upload_performed") is False and result.get("real_acceptance_claim_created") is False
              and result.get("payload_files") == len(entries) and result.get("archived_files") == len(members)
              and result.get("total_payload_bytes") == plan["total_payload_bytes"]
              and result.get("additional_publication_metadata_bytes") == sum(n["size_bytes"] for n in notes),
              "Incomplete or conflicting package result")
    p.require(result.get("packager_candidate_version") == 4 and result.get("publication_preparation_version") == 5, "Expected v4 package of v5 inventory")
    limit, parts = result.get("part_limit_bytes"), result.get("parts")
    p.require(type(limit) is int and 1 <= limit <= p.MAX_PART and isinstance(parts, list) and parts,
              "Invalid part size limit or list")
    for index, part in enumerate(parts, 1):
        p.require(isinstance(part, dict) and set(part) == {"index", "name", "size_bytes", "sha256"}
                  and type(part["index"]) is int and part["index"] == index
                  and part["name"] == f"source-evidence.tar.gz.part{index:05d}"
                  and type(part["size_bytes"]) is int and 0 < part["size_bytes"] <= limit
                  and isinstance(part["sha256"], str) and p.HEX.fullmatch(part["sha256"]),
                  "Invalid ordered part descriptor")
    whole = result.get("whole_stream_sha256")
    p.require(isinstance(whole, str) and p.HEX.fullmatch(whole)
              and sum(part["size_bytes"] for part in parts) == result.get("total_compressed_bytes"),
              "Invalid whole compressed stream descriptor")
    captured = p.recovery_capture(plan, entries)
    checked = p.readback(directory, parts, whole, members, metadata_capture=captured)
    recovery_binding = p.recovery_check(plan, entries, captured.__getitem__)
    p.require(result.get("recovery_inventory_binding") == recovery_binding
              and result.get("current_acceptance_binding", {}).get("recovery_inventory_binding") == recovery_binding,
              "Package result/raw recovery binding differs")
    return dict(status="DOWNLOADED_PACKAGE_BYTES_VERIFIED_NOT_MATHEMATICAL_ACCEPTANCE",
                package_manifest_sha256=result_hash, manifest_sha256=manifest_sha256,
                support_inventory_sha256=support_inventory_sha256,
                whole_stream_sha256=whole, readback=checked, recovery_inventory_binding=recovery_binding,
                original_source_paths_opened=False, files_extracted=False, files_written=False,
                lean_executed=False, mathematical_acceptance_rechecked=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--package-manifest-sha256", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--support-inventory", type=Path, required=True)
    parser.add_argument("--support-inventory-sha256", required=True)
    print(json.dumps(verify(**vars(parser.parse_args())), ensure_ascii=False))


if __name__ == "__main__":
    main()
