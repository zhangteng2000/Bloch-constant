"""CANDIDATE: verify a pinned v4 package, then extract exact regular members.

No real extraction, mathematical acceptance, build, upload or reproduction is
implied by preparing this candidate. Extracted scripts are never executed.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import types

V4_PINS = {
    "publication_recovery_inventory.py": "f12f823a5e5827556b83b4ac035cab81084132a3f69d20f740f3da199accfbd7",
    "interrupted_build_lineage.py": "1603a4784aed7c373f748bfe6517a1e602b7325b06607e49ac9dfc0619299af1",
    "stream_source_package.py": "2e350874c5c7b80b9306e644f11f5e7697938c1c952074035b8933bebceb0d6d",
    "verify_source_package.py": "815980deb848eecb2cad03daf73dc5fff426233e81321fbc990654f5cddfeda5",
}
BLOCK = 1024 * 1024
RECOVERY_VALIDATED = "V5_RECOVERY_RAW_CHAIN_AND_INTERRUPTED_BUILD_LINEAGE_VERIFIED_NOT_MATHEMATICAL_ACCEPTANCE"


class ExtractionError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ExtractionError(message)


def ordinary(path, directory=False):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, f"Unsafe absolute path: {path}")
    require(all(":" not in part for part in path.parts[1:]), f"Alternate stream path: {path}")
    for item in reversed((path, *path.parents)):
        st = item.lstat()
        require(not stat.S_ISLNK(st.st_mode) and not (getattr(st, "st_file_attributes", 0) & 0x400),
                f"Link or reparse point rejected: {item}")
    st = path.stat()
    require(stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode), f"Wrong file type: {path}")
    require(directory or st.st_nlink == 1, f"Hard-linked file rejected: {path}")
    return path


def identity(path):
    st = path.stat()
    return st.st_dev, st.st_ino


def load_reviewed_v4(directory):
    """Compile the pinned source bytes directly; never trust cached .pyc files."""
    directory = ordinary(directory, directory=True)
    sources = []
    for filename, expected in V4_PINS.items():
        require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected),
                "Reviewed v4 runtime pins are not finalized")
        path = ordinary(directory / filename)
        require(path.stat().st_size <= 2 * BLOCK, "Reviewed helper unexpectedly large")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, f"Reviewed v4 helper digest mismatch: {filename}")
        sources.append((path, raw))
    # Authenticate the complete runtime closure before executing any helper.
    modules = []
    for path, raw in sources:
        name = path.stem
        module = types.ModuleType(name)
        module.__file__, module.__package__ = str(path), ""
        # Register both pure validators before the stream module and verifier.
        previous = sys.modules.get(name)
        sys.modules[name] = module
        try:
            exec(compile(raw, str(path), "exec"), module.__dict__)
        except BaseException:
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
            raise
        modules.append(module)
    return modules[2:]


def pinned_member_plan(p, package_dir, package_pin, manifest, manifest_pin, support_inventory, support_pin):
    result, digest = p.read_json(Path(package_dir) / "package-manifest.json")
    require(digest == package_pin, "Package manifest changed after full verification")
    raw = p.read_bytes(manifest)
    support_raw = p.read_bytes(support_inventory, 8 * BLOCK)
    require(p.sha(raw) == manifest_pin and p.sha(support_raw) == support_pin,
            "A pinned inventory changed after full verification")
    plan = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=p.strict_object)
    support = json.loads(support_raw.decode("utf-8-sig"), object_pairs_hook=p.strict_object)
    entries, _ = p.validate_inventory(plan, check_source_files=False)
    support_files = p.validate_support_inventory(support, check_source_files=False)
    members, _, _ = p.archive_members(entries, raw, manifest_pin, result["additional_publication_metadata"],
                                      support_files, support_raw, support_pin)
    return result, members


class NewDestination:
    def __init__(self, output):
        self.output = Path(output)
        self.payload = self.output / "payload"
        self.directories = {}
        self.files = {}

    def create(self):
        require(self.output.is_absolute() and ".." not in self.output.parts, "Output must be a new absolute path")
        ordinary(self.output.parent, directory=True)
        require(not os.path.lexists(self.output), "Refusing any preexisting output directory or link")
        self.output.mkdir()
        self.directories[self.output] = identity(self.output)
        self.payload.mkdir()
        self.directories[self.payload] = identity(self.payload)

    def check_directories(self, parent):
        require(parent == self.payload or self.payload in parent.parents, "Destination escaped payload root")
        for path in reversed((parent, *parent.parents)):
            if path == self.output or self.output in path.parents:
                ordinary(path, directory=True)
                require(path in self.directories and identity(path) == self.directories[path],
                        f"Destination directory identity changed or was not created by us: {path}")

    def new_file(self, archive_name):
        parts = PurePosixPath(archive_name).parts
        parent = self.payload
        for part in parts[:-1]:
            self.check_directories(parent)
            child = parent / part
            if child not in self.directories:
                require(not os.path.lexists(child), f"Unexpected preexisting destination: {child}")
                child.mkdir()
                ordinary(child, directory=True)
                self.directories[child] = identity(child)
            parent = child
        self.check_directories(parent)
        target = parent / parts[-1]
        require(not os.path.lexists(target), f"Refusing to overwrite a destination: {target}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        stream = os.fdopen(os.open(target, flags, 0o644), "wb")
        self.files[target] = os.fstat(stream.fileno()).st_dev, os.fstat(stream.fileno()).st_ino
        return target, stream

    def validate_file(self, target):
        self.check_directories(target.parent)
        ordinary(target)
        require(identity(target) == self.files[target], f"Extracted file identity changed: {target}")

    def record(self, name, value):
        # Diagnostics sit outside payload, whose files are exactly archive members.
        ordinary(self.output, directory=True)
        require(identity(self.output) == self.directories[self.output], "Output root identity changed")
        with (self.output / name).open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")

    def check_exact_tree(self, expected_files):
        """Scan only our new payload; reject unexpected files/directories/links."""
        expected = set(expected_files)
        seen = set()
        pending = [self.payload]
        while pending:
            parent = pending.pop()
            self.check_directories(parent)
            with os.scandir(parent) as children:
                for child in children:
                    target = parent / child.name
                    st = child.stat(follow_symlinks=False)
                    require(not stat.S_ISLNK(st.st_mode) and not (getattr(st, "st_file_attributes", 0) & 0x400),
                            "Unexpected link/reparse point in new payload")
                    if stat.S_ISDIR(st.st_mode):
                        self.check_directories(target)
                        pending.append(target)
                    else:
                        require(target in expected, f"Unexpected file in new payload: {target}")
                        self.validate_file(target)
                        seen.add(target)
        require(seen == expected, "New payload member set differs from the complete inventory")


def extract(package_dir, package_manifest_sha256, manifest, manifest_sha256, support_inventory,
            support_inventory_sha256, packager_v4_dir, output_dir):
    p, verifier = load_reviewed_v4(packager_v4_dir)
    output = Path(output_dir)
    require(output.is_absolute() and ".." not in output.parts and not os.path.lexists(output),
            "Output must be new and nonexistent")
    ordinary(output.parent, directory=True)
    # This completes the independent full-package pass BEFORE creating output.
    first_pass = verifier.verify(package_dir, package_manifest_sha256, manifest, manifest_sha256,
                                 support_inventory, support_inventory_sha256)
    binding = first_pass.get("recovery_inventory_binding") if isinstance(first_pass, dict) else None
    require(isinstance(binding, dict) and binding.get("status") == RECOVERY_VALIDATED and
            binding.get("interrupted_build_lineage_verified") is True,
            "Full package verification did not include completed interrupted-build lineage")
    result, members = pinned_member_plan(p, package_dir, package_manifest_sha256, manifest, manifest_sha256,
                                         support_inventory, support_inventory_sha256)
    destination = NewDestination(output)
    reader = None
    completed = []
    try:
        destination.create()
        reader = p.PartReader(Path(package_dir), result["parts"])
        tar_bytes = 0
        with gzip.GzipFile(fileobj=reader, mode="rb") as archived:
            for entry in members:
                name = p.portable(entry["archive_path"])
                header = p.tar_info(entry).tobuf(format=p.tarfile.PAX_FORMAT)
                require(p.read_exact(archived, len(header)) == header, f"Changed/noncanonical tar header: {name}")
                target, stream = destination.new_file(name)
                digest, remaining = hashlib.sha256(), entry["size_bytes"]
                with stream:
                    while remaining:
                        block = p.read_exact(archived, min(BLOCK, remaining))
                        stream.write(block)
                        digest.update(block)
                        remaining -= len(block)
                    stream.flush()
                    os.fsync(stream.fileno())
                require(digest.hexdigest() == entry["sha256"], f"Changed extracted member bytes: {name}")
                destination.validate_file(target)
                padding = -entry["size_bytes"] % 512
                require(p.read_exact(archived, padding) == b"\0" * padding, "Noncanonical tar member padding")
                tar_bytes += len(header) + entry["size_bytes"] + padding
                completed.append(name)
            tail = 1024 + (-(tar_bytes + 1024) % p.tarfile.RECORDSIZE)
            require(p.read_exact(archived, tail) == b"\0" * tail and archived.read(1) == b"",
                    "Noncanonical tar ending or extra members")
        require(reader.read(1) == b"" and reader.index == len(result["parts"])
                and reader.whole.hexdigest() == result["whole_stream_sha256"],
                "Second-pass compressed stream changed")
        # Recheck actual written bytes, not merely buffers handed to write().
        for entry in members:
            target = destination.payload.joinpath(*PurePosixPath(entry["archive_path"]).parts)
            destination.validate_file(target)
            require(target.stat().st_size == entry["size_bytes"], "Extracted file size changed")
            digest = hashlib.sha256()
            with target.open("rb") as stream:
                for block in iter(lambda: stream.read(BLOCK), b""):
                    digest.update(block)
            destination.validate_file(target)
            require(digest.hexdigest() == entry["sha256"], "Written file readback SHA mismatch")
        destination.check_exact_tree(destination.payload.joinpath(*PurePosixPath(e["archive_path"]).parts)
                                     for e in members)
        # Pins remain current; source files are never opened by this step.
        pinned_member_plan(p, package_dir, package_manifest_sha256, manifest, manifest_sha256,
                            support_inventory, support_inventory_sha256)
        success = dict(status="PINNED_PACKAGE_EXTRACTED_AND_READBACK_VERIFIED_NOT_MATHEMATICAL_ACCEPTANCE",
                       candidate=True, payload_directory=str(destination.payload), files_extracted=len(completed),
                       total_extracted_bytes=sum(e["size_bytes"] for e in members),
                       first_full_package_verification=first_pass, reviewed_v4_code_sha256=V4_PINS,
                       second_stream_sha256=reader.whole.hexdigest(), written_file_readback="ALL_MEMBERS_PASSED",
                       extracted_files_executed=False, network_used=False, lean_executed=False,
                       mathematical_acceptance_rechecked=False)
        destination.record("EXTRACTION-RESULT.json", success)
        return success
    except BaseException as error:
        if destination.output in destination.directories:
            try:
                destination.record("EXTRACTION-FAILED.json", dict(
                    status="EXTRACTION_FAILED_PARTIAL_OUTPUT_PRESERVED", error=str(error),
                    completed_files=completed, reviewed_v4_code_sha256=V4_PINS,
                    package_manifest_sha256=package_manifest_sha256, manifest_sha256=manifest_sha256,
                    support_inventory_sha256=support_inventory_sha256, extracted_files_executed=False))
            except Exception:
                pass  # Disk failure/replaced root can prevent diagnostics; preserve original error.
        raise
    finally:
        if reader is not None:
            reader.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("package-dir", "manifest", "support-inventory", "packager-v4-dir", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("package-manifest-sha256", "manifest-sha256", "support-inventory-sha256"):
        parser.add_argument("--" + name, required=True)
    print(json.dumps(extract(**vars(parser.parse_args())), ensure_ascii=False))


if __name__ == "__main__":
    main()
