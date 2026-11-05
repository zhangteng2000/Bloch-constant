"""V4 CANDIDATE: complete v5 source inventory plus explicitly pinned support selection.

No inventory generation, Lean execution, extraction, deletion, or upload occurs.
Fixtures are not mathematical acceptance or a real publication package.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile
import unicodedata
import zlib
import types
sys.dont_write_bytecode = True

RECOVERY_VALIDATOR_PIN = "f12f823a5e5827556b83b4ac035cab81084132a3f69d20f740f3da199accfbd7"
LINEAGE_VERIFIER_PIN = "1603a4784aed7c373f748bfe6517a1e602b7325b06607e49ac9dfc0619299af1"
_validator_path = Path(__file__).resolve().parent / "publication_recovery_inventory.py"
_validator_bytes = _validator_path.read_bytes()
_lineage_path = Path(__file__).resolve().parent / "interrupted_build_lineage.py"
_lineage_bytes = _lineage_path.read_bytes()
if hashlib.sha256(_validator_bytes).hexdigest() != RECOVERY_VALIDATOR_PIN:
    raise ValueError("Reviewed recovery validator source digest mismatch")
if hashlib.sha256(_lineage_bytes).hexdigest() != LINEAGE_VERIFIER_PIN:
    raise ValueError("Reviewed interrupted-build lineage verifier source digest mismatch")
# Both source pins are checked before either helper is executed.
recovery = types.ModuleType("reviewed_publication_recovery_inventory")
recovery.__file__ = str(_validator_path)
exec(compile(_validator_bytes, str(_validator_path), "exec"), recovery.__dict__)
lineage = types.ModuleType("reviewed_interrupted_build_lineage")
lineage.__file__ = str(_lineage_path)
exec(compile(_lineage_bytes, str(_lineage_path), "exec"), lineage.__dict__)

HERE = Path(__file__).resolve().parent
ACCEPTED = "ORIGINAL_THEOREM_1_3_FORMALIZATION_ACCEPTED"
TARGET = "blochConstant < ENNReal.ofReal (AG - (13 : ℝ) / 10^10)"
INVENTORY = "PUBLICATION_INVENTORY_ONLY_NOT_NEW_MATHEMATICAL_ACCEPTANCE"
BLOCK = 1024 * 1024
MAX_PART = 2**31 - 1
HEX = re.compile(r"[0-9a-f]{64}\Z")
PRODUCER_PINS = {
    'prepare_publication_manifest.py': '1f07b98089604d5599e3d57dae95cf995dd603462a323b953b4d57b7f11c0f64',
    'recovery_publication_evidence.py': '5696102f89d230d7662727e887afbddf7fd5bcd867e0ba76b242a9e5866dae35',
    'publication_dependency_closure.py': 'fee106fb2be16151e1940fa355eb322fd8134f886db18930eb9dffb78fe8e6b0',
    'publication_interrupted_build_evidence.py': '8cdd4de1117f20a22364f00896a0d5d671c309711eb9eaaae7977fea1df1b886',
    'interrupted_build_lineage.py': '1603a4784aed7c373f748bfe6517a1e602b7325b06607e49ac9dfc0619299af1',
}
RESERVED_MANIFEST = "publication/publication-manifest.json"
RESERVED_SUPPORT_INVENTORY = "publication/support/support-inventory.json"
SUPPORT_STATUS = "REVIEWED_PUBLICATION_SUPPORT_SELECTION_NOT_ACCEPTANCE_INPUTS"
SUPPORT_KINDS = {"independent_evidence_verifier", "dependency_bootstrap", "offline_package_verifier",
                 "python_module", "instructions", "license", "review_record"}


class PackageError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PackageError(message)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def sha(data):
    return hashlib.sha256(data).hexdigest()


def within(path, root):
    return path == root or root in path.parents


def safe_path(value, directory=False, excluded=True):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, f"Nonabsolute/traversing path: {path}")
    require(all(":" not in p for p in path.parts[1:]), f"Alternate stream path: {path}")
    if excluded:
        require(not any(p.casefold() in {".lake", ".git", "module-replay-stage"} for p in path.parts),
                f"Cache/staging input is forbidden: {path}")
    for component in reversed((path, *path.parents)):
        st = component.lstat()
        require(not stat.S_ISLNK(st.st_mode) and not (getattr(st, "st_file_attributes", 0) & 0x400),
                f"Link/reparse point is forbidden: {component}")
    st = path.stat()
    require(stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode), f"Wrong file type: {path}")
    if not directory:
        require(st.st_nlink == 1, f"Hard-linked input is forbidden: {path}")
    return path


def stamp(st):
    # Windows path.stat and fstat disagree on ctime; compare ctime only within one API.
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns


def read_bytes(path, limit=256 * 1024 * 1024):
    path = safe_path(path)
    before = path.stat()
    require(before.st_size <= limit, f"Metadata exceeds bounded read limit: {path}")
    with path.open("rb") as stream:
        fd_before = os.fstat(stream.fileno())
        require(stamp(before) == stamp(fd_before), f"Input identity changed: {path}")
        data = stream.read(limit + 1)
        fd_after = os.fstat(stream.fileno())
    require(len(data) == before.st_size and stamp(fd_before) == stamp(fd_after)
            and fd_before.st_ctime_ns == fd_after.st_ctime_ns
            and stamp(before) == stamp(safe_path(path).stat()), f"Input changed while reading: {path}")
    return data


def read_json(path):
    data = read_bytes(path)
    obj = json.loads(data.decode("utf-8-sig"), object_pairs_hook=strict_object)
    require(isinstance(obj, dict), f"Expected JSON object: {path}")
    return obj, sha(data)


def portable(value):
    require(isinstance(value, str) and value and not any(c in value for c in '\\:<>|?*"'),
            f"Invalid archive path: {value!r}")
    require(unicodedata.normalize("NFC", value) == value, "Archive path must be NFC canonical")
    p = PurePosixPath(value)
    require(p.parts and not p.is_absolute() and p.as_posix() == value, f"Noncanonical archive path: {value}")
    for part in p.parts:
        require(part not in {".", ".."} and part.casefold() not in {".lake", ".git", "module-replay-stage"}
                and not part.endswith((".", " ")) and not any(ord(c) < 32 or ord(c) == 127 for c in part),
                f"Unsafe archive path: {value}")
        require(not re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?", part),
                f"Reserved Windows destination: {value}")
    return value


def recovery_check(plan, entries, read_member=None, final_state=None):
    try:
        return recovery.validate_recovery_inventory(plan, entries, read_member, final_state,
                                                    lineage_verifier=lineage.verify_lineage)
    except recovery.RecoveryInventoryError as exc:
        raise PackageError(str(exc)) from exc


def recovery_capture(plan, entries):
    try:
        return recovery.VerifiedMetadataCache(recovery.metadata_entries(plan, entries))
    except recovery.RecoveryInventoryError as exc:
        raise PackageError(str(exc)) from exc


def validate_inventory(plan, check_source_files=True):
    require(plan.get("status") == INVENTORY and plan.get("publication_preparation_version") == 5,
            "Only the complete v5 publication inventory schema is supported")
    require(plan.get("accepted_status") == ACCEPTED and plan.get("target") == TARGET
            and plan.get("repository") == "zhangteng2000/Bloch-constant"
            and plan.get("complete_rectangles") == 1068 and plan.get("nodes_per_rectangle") == 64,
            "Wrong acceptance/target/inventory identity")
    require(all(plan.get(k) is False for k in
                ("compiled_artifacts_included", "packaging_performed", "upload_performed")),
            "Inventory inclusion/activity flags are not the reviewed v5 values")
    closure = plan.get("dependency_closure", {})
    require(all(closure.get(k) is True for k in ("vendor_license_included", "vendor_provenance_included",
                                                "vendor_ported_sources_match_accepted_inputs"))
            and closure.get("dependencies") and
            all(d.get("local_import_closure_checked") is True for d in closure["dependencies"]),
            "Missing complete v5 dependency/attribution capture")
    entries = plan.get("files")
    require(isinstance(entries, list) and entries, "Empty inventory")
    required = {"source_path", "original_paths", "archive_path", "sha256", "size_bytes", "roles", "integrity_basis"}
    destinations, sources, aliases, identities = {}, set(), {}, set()
    for e in entries:
        require(isinstance(e, dict) and set(e) == required, "Unsupported v5 file-entry fields")
        name = portable(e["archive_path"])
        key = name.casefold()
        require(key not in destinations and key != RESERVED_MANIFEST.casefold(), "Duplicate/reserved destination")
        require(HEX.fullmatch(e["sha256"]) and type(e["size_bytes"]) is int and e["size_bytes"] >= 0,
                "Invalid file digest or size")
        require(e["integrity_basis"] in {"accepted_digest", "publication_capture", "recovery_controller_digest",
                                         "interrupted_build_lineage_digest"}
                and isinstance(e["roles"], list) and e["roles"] and all(isinstance(r, str) for r in e["roles"]),
                "Invalid integrity basis or role set")
        require(isinstance(e["source_path"], str), "Invalid selected source metadata")
        path = safe_path(e["source_path"]) if check_source_files else Path(e["source_path"])
        require(str(path).casefold() not in sources, f"Duplicate selected source: {path}")
        if check_source_files:
            st = path.stat()
            identity = st.st_dev, st.st_ino
            require(identity not in identities, f"Duplicate selected file identity: {path}")
            require(st.st_size == e["size_bytes"], f"Selected size changed: {path}")
            identities.add(identity)
        sources.add(str(path).casefold())
        destinations[key] = e
        require(isinstance(e["original_paths"], list) and str(path) in e["original_paths"], "Source alias missing")
        for alias in e["original_paths"]:
            require(isinstance(alias, str) and alias not in aliases, f"Duplicate source alias: {alias}")
            aliases[alias] = name
    require(plan.get("original_to_portable") == aliases, "Incomplete/conflicting original-to-portable map")
    require(type(plan.get("total_payload_bytes")) is int and
            sum(e["size_bytes"] for e in entries) == plan["total_payload_bytes"], "Payload total mismatch")
    names = set(destinations) | {RESERVED_MANIFEST.casefold()}
    for name in names:
        require(not any(str(parent) in names for parent in PurePosixPath(name).parents if str(parent) != "."),
                f"File/directory destination collision: {name}")
    recovery_check(plan, entries)
    return sorted(entries, key=lambda e: e["archive_path"]), destinations


PUBLICATION_NOTES = ("ACCEPTANCE-SUMMARY-ENGLISH.txt", "REPRODUCTION-NOTES-ENGLISH.txt")


def checked_notes(manifest, entries, summary, summary_sha256, reproduction_notes, reproduction_notes_sha256):
    """Pin explanatory v4 outputs without relabelling them as accepted proof inputs."""
    result = []
    selected = {str(Path(e["source_path"])).casefold() for e in entries}
    for filename, path, expected in zip(PUBLICATION_NOTES, (summary, reproduction_notes),
                                        (summary_sha256, reproduction_notes_sha256)):
        require(isinstance(expected, str) and HEX.fullmatch(expected), "Explicit publication note SHA required")
        path = safe_path(path)
        require(path.parent == manifest.parent and path.name == filename,
                "Publication notes must be the named outputs beside the pinned v4 manifest")
        require(str(path).casefold() not in selected, "Publication note duplicates an inventory source")
        data = read_bytes(path, 2 * BLOCK)
        require(sha(data) == expected, f"Publication note differs from explicit SHA: {filename}")
        result.append(dict(source_path=str(path), archive_path="publication/" + filename,
                           sha256=expected, size_bytes=len(data),
                           role="publication_explanatory_metadata_not_acceptance_inputs"))
    return result


def validate_support_inventory(value, check_source_files=True):
    require(isinstance(value, dict) and set(value) == {"status", "version", "files"}
            and value["status"] == SUPPORT_STATUS and type(value["version"]) is int and value["version"] == 1,
            "Unsupported publication support inventory schema")
    files = value["files"]
    require(isinstance(files, list) and files, "Support inventory is required and must not be empty")
    for entry in files:
        require(isinstance(entry, dict) and set(entry) == {"source_path", "archive_path", "sha256", "size_bytes", "kind"},
                "Unsupported support file fields")
        name = portable(entry["archive_path"])
        require(name.startswith("publication/support/") and name != RESERVED_SUPPORT_INVENTORY,
                "Support destinations must be beneath publication/support/ and not its reserved inventory")
        require(isinstance(entry["source_path"], str) and isinstance(entry["sha256"], str)
                and HEX.fullmatch(entry["sha256"]) and type(entry["size_bytes"]) is int
                and 0 <= entry["size_bytes"] <= 32 * BLOCK and entry["kind"] in SUPPORT_KINDS,
                "Invalid support file descriptor")
        if check_source_files:
            path = safe_path(entry["source_path"])
            require(path.stat().st_size == entry["size_bytes"], f"Support file size changed: {path}")
    for kind in ("independent_evidence_verifier", "dependency_bootstrap", "offline_package_verifier"):
        require(sum(e["kind"] == kind for e in files) == 1, f"Exactly one required support script missing: {kind}")
    require(any(e["kind"] == "python_module" for e in files), "Reviewed local Python import support is missing")
    helpers = [e for e in files if PurePosixPath(e["archive_path"]).name == "publication_recovery_inventory.py"]
    require(len(helpers) == 1 and helpers[0]["kind"] == "python_module"
            and helpers[0]["sha256"] == RECOVERY_VALIDATOR_PIN,
            "Exact reviewed recovery validator must be selected as support")
    lineage_helpers = [e for e in files if PurePosixPath(e["archive_path"]).name == "interrupted_build_lineage.py"]
    require(len(lineage_helpers) == 1 and lineage_helpers[0]["kind"] == "python_module"
            and lineage_helpers[0]["sha256"] == LINEAGE_VERIFIER_PIN,
            "Exact reviewed interrupted-build lineage verifier must be selected as support")
    require(PurePosixPath(helpers[0]["archive_path"]).parent ==
            PurePosixPath(lineage_helpers[0]["archive_path"]).parent,
            "Shared recovery and lineage helpers must share one archived runtime directory")
    return sorted(files, key=lambda e: e["archive_path"])


def checked_support(path, expected, verification_script, gate):
    require(isinstance(expected, str) and HEX.fullmatch(expected), "Explicit support inventory SHA required")
    path = safe_path(path)
    raw = read_bytes(path, 8 * BLOCK)
    require(sha(raw) == expected, "Support inventory differs from explicit reviewed SHA")
    selection = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=strict_object)
    files = validate_support_inventory(selection)
    evidence_verifier = next(e for e in files if e["kind"] == "independent_evidence_verifier")
    require(Path(evidence_verifier["source_path"]) == Path(verification_script)
            and evidence_verifier["sha256"] == gate["verification_script_sha256"],
            "Support evidence verifier differs from the current independent PASS binding")
    return path, raw, files


def archive_members(entries, manifest_bytes, manifest_sha256, notes,
                    support_files, support_bytes, support_sha256):
    require(len(notes) == 2 and {n.get("archive_path") for n in notes} ==
            {"publication/" + n for n in PUBLICATION_NOTES}, "Missing/extra publication note metadata")
    for note in notes:
        require(set(note) == {"source_path", "archive_path", "sha256", "size_bytes", "role"}
                and note["role"] == "publication_explanatory_metadata_not_acceptance_inputs"
                and isinstance(note["source_path"], str) and isinstance(note["sha256"], str)
                and HEX.fullmatch(note["sha256"]) and type(note["size_bytes"]) is int
                and 0 <= note["size_bytes"] <= 2 * BLOCK, "Invalid publication note descriptor")
    meta = dict(archive_path=RESERVED_MANIFEST, size_bytes=len(manifest_bytes), sha256=manifest_sha256)
    support_meta = dict(archive_path=RESERVED_SUPPORT_INVENTORY, size_bytes=len(support_bytes), sha256=support_sha256)
    members = sorted([*entries, meta, *notes, *support_files, support_meta], key=lambda e: e["archive_path"])
    names = [portable(e["archive_path"]).casefold() for e in members]
    require(len(set(names)) == len(names), "Publication metadata/inventory destination collision")
    source_names = [str(Path(e["source_path"])).casefold() for e in [*entries, *notes, *support_files]]
    require(len(set(source_names)) == len(source_names), "Publication metadata duplicates a selected source")
    all_names = set(names)
    for name in names:
        require(not any(str(parent) in all_names for parent in PurePosixPath(name).parents if str(parent) != "."),
                "Publication metadata file/directory collision")
    return members, meta, support_meta


def current_gate(plan, entries, final_status, independent_report, producer_dir, verification_script):
    producer_dir = safe_path(producer_dir, directory=True)
    producer_hashes = {}
    for name, expected in PRODUCER_PINS.items():
        actual = sha(read_bytes(producer_dir / name, 2 * BLOCK))
        require(actual == expected, f"Reviewed v5 producer code changed: {name}")
        producer_hashes[name] = actual
    by_source = {str(Path(e["source_path"])): e for e in entries}
    by_alias = {alias: e for e in entries for alias in e["original_paths"]}
    gate_hashes = {}

    def record(path, role=None, expected=None):
        path = safe_path(path)
        require(str(path) in by_source, f"Current gate record omitted from complete manifest: {path}")
        e = by_source[str(path)]
        require(role is None or role in e["roles"], f"Missing record role: {role}")
        obj, digest = read_json(path)
        require(digest == e["sha256"] and (expected is None or digest == expected), f"Stale gate record: {path}")
        gate_hashes[str(path)] = digest
        return obj, digest

    state, _ = record(final_status, "final_controller")
    require(state.get("status") == ACCEPTED and state.get("theorem_1_3_complete") is True,
            "Actual final controller is not genuinely accepted")
    delivery_rows = [e for e in entries if "accepted_delivery_manifest" in e["roles"]]
    require(len(delivery_rows) == 1, "Expected exactly one accepted delivery manifest")
    delivery_path = safe_path(delivery_rows[0]["source_path"])
    require(delivery_path.name == "DELIVERY-MANIFEST.json", "Wrong delivery manifest filename")
    project = delivery_path.parent
    work = project.parent.parent / "work"
    require(within(safe_path(final_status), work), "Final controller is outside the expected work root")
    for e in entries:
        p = Path(e["source_path"])
        require(any(within(p, root) for root in (project, work, producer_dir)), f"Selected source escapes v5 roots: {p}")
    delivery, delivery_hash = record(delivery_path, "accepted_delivery_manifest")
    acceptance, acceptance_hash = record(state["final_acceptance"])
    require(delivery.get("status") == ACCEPTED and delivery.get("target") == TARGET
            and delivery.get("acceptance_record") == state["final_acceptance"]
            and delivery.get("acceptance_record_sha256") == acceptance_hash,
            "Delivery acceptance binding differs")
    require(acceptance.get("status") == ACCEPTED and acceptance.get("theorem_1_3_complete") is True
            and acceptance.get("target") == TARGET and acceptance.get("complete_actual_rectangles") == 1068
            and acceptance.get("clean_build_complete") is True and acceptance.get("semantic_review_complete") is True,
            "Incomplete acceptance fields")
    require(plan.get("acceptance_record") == state["final_acceptance"]
            and plan.get("acceptance_time") == acceptance.get("time"), "Inventory acceptance binding differs")
    evidence = acceptance.get("evidence_sha256", {})
    require(evidence, "Acceptance has no evidence digests")
    for path, digest in evidence.items():
        require(path in by_alias and by_alias[path]["sha256"] == digest, f"Accepted evidence omitted/changed: {path}")
    records = {}
    for name in ("integration_record", "build_record", "semantic_review", "extra_checker_record"):
        require(state[name] in evidence, f"Unbound acceptance record: {name}")
        records[name], _ = record(state[name], expected=evidence[state[name]])
    build, integration = records["build_record"], records["integration_record"]
    semantic, extra = records["semantic_review"], records["extra_checker_record"]
    require(build.get("status") == "LAKE_BUILD_AND_ROOT_AUDITS_PASSED_EXTRA_CHECKER_PENDING"
            and build.get("started_from_empty_project_build") is True, "No accepted empty-directory build")
    require(integration.get("status") == "INSTALLED_SOURCES_PENDING_CLEAN_BUILD_AND_ACCEPTANCE"
            and build.get("build_directory") == integration.get("build_directory"), "Installed/build records disagree")
    require(semantic.get("status") == "FINAL_UNCONDITIONAL_STATEMENT_AND_DEFINITIONS_REVIEWED"
            and semantic.get("target") == TARGET and semantic.get("has_no_added_hypotheses") is True
            and semantic.get("definitions_agree_with_paper") is True, "Missing exact mathematical statement review")
    require(extra.get("status") in {"FRESH_CHECKER_PASSED", "NOT_RUN_UNAVAILABLE", "NOT_COMPLETED_RESOURCE_LIMIT"}
            and extra["status"] == acceptance.get("extra_checker_status") == delivery.get("extra_checker_status")
            == plan.get("extra_checker_actual_status")
            and extra.get("build_record_sha256") == evidence[state["build_record"]], "Checker status/build binding differs")
    if extra["status"] == "FRESH_CHECKER_PASSED":
        require(extra.get("exit_code") == 0 and "--fresh" in extra.get("command", [])
                and extra.get("module") == "AGStripQuantitative", "Missing fresh-checker success fields")
    else:
        require(extra.get("ordinary_kernel_build_passed") is True
                and isinstance(extra.get("reason"), str) and len(extra["reason"].strip()) > 20,
                "Missing honest extra-checker disposition")
    require(plan.get("extra_checker_reason") == extra.get("reason"), "Inventory checker reason differs")
    report, _ = record(independent_report, "prior_independent_verification_report")
    require(plan.get("independent_report") == str(Path(independent_report)), "Inventory independent report differs")
    verifier_path = safe_path(verification_script)
    require(verifier_path == producer_dir.parent / "verify-ahlfors-final-evidence-readonly.py", "Unexpected verifier location")
    verifier_hash = sha(read_bytes(verifier_path, 2 * BLOCK))
    require(report.get("independent_readonly_evidence_check") == "PASSED"
            and report.get("acceptance_record") == state["final_acceptance"]
            and report.get("acceptance_record_sha256") == acceptance_hash
            and report.get("delivery_manifest_sha256") == delivery_hash
            and report.get("verification_script_sha256") == verifier_hash
            and report.get("complete_rectangles") == 1068
            and report.get("extra_checker_actual_status") == extra["status"], "Independent PASS/current three-hash binding failed")
    hashes = build.get("source_sha256")
    require(isinstance(hashes, dict) and hashes and hashes == delivery.get("source_sha256"), "Accepted source inventories differ")
    inputs, _ = record(build["inputs_snapshot"], expected=build["inputs_snapshot_sha256"])
    require(inputs.get("source_sha256") == hashes, "Accepted build inputs differ")
    for original, digest in hashes.items():
        require(original in by_alias and by_alias[original]["sha256"] == digest
                and by_alias[original]["integrity_basis"] == "accepted_digest", "Accepted source omitted or changed")
    results = build.get("results", [])
    modules = [r.get("module") for r in results]
    require(results and len(set(modules)) == len(modules) and all(r.get("exit_code") == 0 for r in results)
            and set(inputs.get("module_resources", {})) == set(modules)
            and len(modules) == delivery.get("module_count") == report.get("clean_build_modules")
            == plan.get("lean_module_count"), "Complete module coverage differs")
    by_archive = {e["archive_path"]: e for e in entries}
    recovery_binding = recovery_check(plan, entries,
        lambda name: read_bytes(by_archive[name]["source_path"], recovery.MAX_METADATA_FILE), state)
    return dict(recovery_inventory_binding=recovery_binding,
                record_hashes=gate_hashes, verification_script_sha256=verifier_hash,
                producer_hashes=producer_hashes, project=str(project), work=str(work),
                extra_checker_actual_status=extra["status"])


class SplitWriter:
    def __init__(self, output, part_bytes):
        self.output, self.limit = output, part_bytes
        self.parts, self.total = [], 0
        self.whole, self.part_hash = hashlib.sha256(), None
        self.handle, self.part_size = None, 0

    def _close_part(self):
        if self.handle is not None:
            self.handle.flush()
            os.fsync(self.handle.fileno())
            self.handle.close()
            self.parts.append(dict(index=len(self.parts) + 1, name=self.name,
                                   size_bytes=self.part_size, sha256=self.part_hash.hexdigest()))
            self.handle = None

    def write(self, data):
        view = memoryview(data)
        self.whole.update(view)
        self.total += len(view)
        written = len(view)
        while view:
            if self.handle is None:
                self.name = f"source-evidence.tar.gz.part{len(self.parts)+1:05d}"
                self.handle = (self.output / self.name).open("xb")
                self.part_hash, self.part_size = hashlib.sha256(), 0
            amount = min(len(view), self.limit - self.part_size)
            self.handle.write(view[:amount])
            self.part_hash.update(view[:amount])
            self.part_size += amount
            view = view[amount:]
            if self.part_size == self.limit:
                self._close_part()
        return written

    def tell(self):
        return self.total

    def flush(self):
        if self.handle:
            self.handle.flush()

    def finish(self):
        self._close_part()


class CheckedSource:
    def __init__(self, entry):
        self.entry, self.path = entry, safe_path(entry["source_path"])
        self.before = self.path.stat()
        require(self.before.st_size == entry["size_bytes"], f"Changed size: {self.path}")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        self.stream = os.fdopen(os.open(self.path, flags), "rb")
        self.fd_before = os.fstat(self.stream.fileno())
        require(stamp(self.before) == stamp(self.fd_before), f"Changed source identity: {self.path}")
        self.digest, self.count = hashlib.sha256(), 0

    def read(self, count=-1):
        data = self.stream.read(min(count, BLOCK) if count >= 0 else BLOCK)
        self.digest.update(data)
        self.count += len(data)
        return data

    def finish(self):
        fd_after = os.fstat(self.stream.fileno())
        require(self.count == self.entry["size_bytes"] and self.digest.hexdigest() == self.entry["sha256"],
                f"Source bytes/hash changed: {self.path}")
        require(not self.stream.read(1) and stamp(self.fd_before) == stamp(fd_after)
                and self.fd_before.st_ctime_ns == fd_after.st_ctime_ns
                and stamp(self.before) == stamp(safe_path(self.path).stat()), f"Source changed during copy: {self.path}")

    def close(self):
        self.stream.close()


def tar_info(entry):
    info = tarfile.TarInfo(entry["archive_path"])
    info.size, info.mode, info.mtime = entry["size_bytes"], 0o644, 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


class PartReader(io.RawIOBase):
    def __init__(self, output, parts):
        self.output, self.parts = output, parts
        self.index, self.handle, self.count = 0, None, 0
        self.whole, self.part_hash = hashlib.sha256(), None
        self.total = 0

    def readable(self):
        return True

    def readinto(self, buffer):
        if not buffer:
            return 0
        while self.index < len(self.parts):
            part = self.parts[self.index]
            if self.handle is None:
                require(part["index"] == self.index + 1 and part["name"] == f"source-evidence.tar.gz.part{self.index+1:05d}",
                        "Part order/name mismatch")
                path = safe_path(self.output / part["name"])
                require(path.stat().st_size == part["size_bytes"], "Part size mismatch")
                self.handle = path.open("rb")
                self.count, self.part_hash = 0, hashlib.sha256()
            data = self.handle.read(min(len(buffer), BLOCK))
            if data:
                buffer[:len(data)] = data
                self.count += len(data)
                self.total += len(data)
                self.part_hash.update(data)
                self.whole.update(data)
                return len(data)
            self.handle.close()
            self.handle = None
            require(self.count == part["size_bytes"] and self.part_hash.hexdigest() == part["sha256"], "Part SHA/size mismatch")
            self.index += 1
        return 0

    def close(self):
        if self.handle:
            self.handle.close()
            self.handle = None
        super().close()


def read_exact(stream, count):
    result = bytearray()
    while len(result) < count:
        data = stream.read(min(BLOCK, count - len(result)))
        require(data, "Truncated archive stream")
        result.extend(data)
    return bytes(result)


def readback(output, parts, whole_sha256, expected_entries, *, metadata_capture=None):
    require(metadata_capture is None or isinstance(metadata_capture, recovery.VerifiedMetadataCache),
            "Readback requires the reviewed bounded metadata cache")
    reader = PartReader(Path(output), parts)
    verified, tar_bytes = [], 0
    try:
        with gzip.GzipFile(fileobj=reader, mode="rb") as stream:
            for entry in expected_entries:
                header = tar_info(entry).tobuf(format=tarfile.PAX_FORMAT)
                require(read_exact(stream, len(header)) == header, f"Noncanonical/unsafe tar header: {entry['archive_path']}")
                digest, remaining = hashlib.sha256(), entry["size_bytes"]
                capture = bytearray() if metadata_capture is not None and entry["archive_path"] in metadata_capture else None
                while remaining:
                    data = read_exact(stream, min(BLOCK, remaining))
                    digest.update(data)
                    if capture is not None:
                        capture.extend(data)
                    remaining -= len(data)
                require(digest.hexdigest() == entry["sha256"], f"Archived file mismatch: {entry['archive_path']}")
                if capture is not None:
                    metadata_capture[entry["archive_path"]] = bytes(capture)
                padding = -entry["size_bytes"] % 512
                require(read_exact(stream, padding) == b"\0" * padding, "Nonzero tar file padding")
                tar_bytes += len(header) + entry["size_bytes"] + padding
                verified.append(entry["archive_path"])
            end_padding = 1024 + (-(tar_bytes + 1024) % tarfile.RECORDSIZE)
            require(read_exact(stream, end_padding) == b"\0" * end_padding, "Noncanonical tar ending")
            require(stream.read(1) == b"", "Unexpected extra archive content")
        require(reader.read(1) == b"" and reader.index == len(parts), "Unread compressed parts remain")
        require(reader.whole.hexdigest() == whole_sha256, "Whole compressed stream SHA mismatch")
        require(metadata_capture is None or metadata_capture.complete(), "Captured metadata is incomplete")
    finally:
        reader.close()
    return dict(status="ALL_ARCHIVED_FILES_STREAM_READBACK_VERIFIED", files_verified=len(verified),
                total_compressed_bytes=reader.total)


def package(manifest, manifest_sha256, final_status, independent_report, producer_dir,
            verification_script, output_dir, part_bytes=1024**3, *, summary=None, summary_sha256=None,
            reproduction_notes=None, reproduction_notes_sha256=None,
            support_inventory=None, support_inventory_sha256=None):
    require(type(part_bytes) is int and 1 <= part_bytes <= MAX_PART, "Parts must be strictly smaller than 2 GiB")
    require(HEX.fullmatch(manifest_sha256), "Explicit reviewed manifest SHA-256 required")
    manifest = safe_path(manifest)
    manifest_bytes = read_bytes(manifest)
    require(sha(manifest_bytes) == manifest_sha256, "Manifest differs from explicit reviewed SHA")
    plan = json.loads(manifest_bytes.decode("utf-8-sig"), object_pairs_hook=strict_object)
    entries, _ = validate_inventory(plan)
    gate = current_gate(plan, entries, final_status, independent_report, producer_dir, verification_script)
    notes = checked_notes(manifest, entries, summary, summary_sha256, reproduction_notes, reproduction_notes_sha256)
    support_path, support_bytes, support_files = checked_support(support_inventory, support_inventory_sha256,
                                                                verification_script, gate)
    selected = [*entries, *notes, *support_files]
    source_names = [str(safe_path(e["source_path"])).casefold() for e in selected]
    all_sources = [*source_names, str(manifest).casefold(), str(support_path).casefold()]
    require(len(set(all_sources)) == len(all_sources), "Inventory/source/support inputs overlap")
    identities = [(p.stat().st_dev, p.stat().st_ino) for p in
                  [*(Path(e["source_path"]) for e in selected), manifest, support_path]]
    require(len(set(identities)) == len(identities), "Duplicate publication input file identity")
    members, meta, support_meta = archive_members(entries, manifest_bytes, manifest_sha256, notes,
                                                 support_files, support_bytes, support_inventory_sha256)
    output = Path(output_dir)
    require(output.is_absolute() and ".." not in output.parts and not os.path.lexists(output), "Output must be a new absolute directory")
    safe_path(output.parent, directory=True)
    require(not any(within(output, Path(root)) for root in (gate["project"], gate["work"], str(producer_dir))),
            "Package output must be outside input project/work/producer roots")
    os.mkdir(output)
    writer = SplitWriter(output, part_bytes)
    try:
        stamps = {e["source_path"]: stamp(safe_path(e["source_path"]).stat()) for e in selected}
        with gzip.GzipFile(filename="", mode="wb", fileobj=writer, compresslevel=6, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w|", format=tarfile.PAX_FORMAT, bufsize=BLOCK) as archive:
                for e in members:
                    if e is meta:
                        archive.addfile(tar_info(e), io.BytesIO(manifest_bytes))
                    elif e is support_meta:
                        archive.addfile(tar_info(e), io.BytesIO(support_bytes))
                    else:
                        source = CheckedSource(e)
                        try:
                            archive.addfile(tar_info(e), source)
                            source.finish()
                        finally:
                            source.close()
        writer.finish()
        for path, old in stamps.items():
            require(stamp(safe_path(path).stat()) == old, f"Source changed before package completion: {path}")
        require(read_bytes(manifest) == manifest_bytes, "Manifest changed during packaging")
        require(read_bytes(support_path, 8 * BLOCK) == support_bytes, "Support inventory changed during packaging")
        require(current_gate(plan, entries, final_status, independent_report, producer_dir, verification_script) == gate,
                "Acceptance/independent verification binding changed during packaging")
        captured = recovery_capture(plan, entries)
        verification = readback(output, writer.parts, writer.whole.hexdigest(), members, metadata_capture=captured)
        recovery_binding = recovery_check(plan, entries, captured.__getitem__)
        require(recovery_binding == gate["recovery_inventory_binding"], "Archived recovery metadata differs from current gate")
        result = dict(status="STREAMING_PACKAGE_READBACK_VERIFIED_NOT_NEW_MATHEMATICAL_ACCEPTANCE",
                      candidate_tool=True, upload_performed=False, real_acceptance_claim_created=False,
                      manifest_sha256=manifest_sha256, part_limit_bytes=part_bytes,
                      parts=writer.parts, whole_stream_sha256=writer.whole.hexdigest(),
                      total_compressed_bytes=writer.total, payload_files=len(entries),
                      archived_files=len(members), total_payload_bytes=plan["total_payload_bytes"],
                      additional_publication_metadata=notes,
                      additional_publication_metadata_bytes=sum(n["size_bytes"] for n in notes),
                      packager_candidate_version=4, publication_preparation_version=5,
                      recovery_inventory_binding=recovery_binding,
                      metadata_storage=captured.budget,
                      publication_support_inventory=dict(source_path=str(support_path),
                          archive_path=RESERVED_SUPPORT_INVENTORY, sha256=support_inventory_sha256,
                          size_bytes=len(support_bytes), role="publication_support_selection_not_acceptance_inputs"),
                      publication_support_files=support_files,
                      publication_support_bytes=sum(e["size_bytes"] for e in support_files),
                      deterministic_format="PAX tar (uid/gid/mtime=0, mode=0644), gzip mtime=0, level=6",
                      runtime=dict(python=sys.version, zlib_build=zlib.ZLIB_VERSION,
                                   zlib_runtime=zlib.ZLIB_RUNTIME_VERSION),
                      current_acceptance_binding=gate, readback=verification)
        (output / "package-manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result
    except BaseException as ex:
        writer.finish()
        failure = dict(status="PACKAGE_FAILED_PARTIAL_OUTPUTS_PRESERVED", error=str(ex),
                       manifest_sha256=manifest_sha256, parts=writer.parts,
                       upload_performed=False, mathematical_acceptance_claim=False)
        (output / "PACKAGING-FAILED.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "final-status", "independent-report", "producer-dir", "verification-script", "output-dir",
                 "summary", "reproduction-notes"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--summary-sha256", required=True)
    parser.add_argument("--reproduction-notes-sha256", required=True)
    parser.add_argument("--support-inventory", type=Path, required=True)
    parser.add_argument("--support-inventory-sha256", required=True)
    parser.add_argument("--part-bytes", type=int, default=1024**3)
    args = vars(parser.parse_args())
    result = package(**args)
    print(json.dumps({k: v for k, v in result.items() if k not in {"current_acceptance_binding", "parts"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
