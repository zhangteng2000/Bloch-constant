"""Candidate byte-callback audit of interrupted build receipts, not a proof gate.

No filesystem, subprocess, compiler, or network interface is used here.
read_bytes(path, limit) must return immutable bytes or raise. See USAGE-ENGLISH.txt.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import PurePosixPath, PureWindowsPath
import re

SCHEMA = "ahlfors-interrupted-build-lineage-audit-candidate-v1"
BUILD_OK = "LAKE_BUILD_AND_ROOT_AUDITS_PASSED_EXTRA_CHECKER_PENDING"
INTERRUPTED = {"BUILDING", "CHECKING_DEFAULT_BUILD_AND_AUDITS", "INTERRUPTED"}
RESUME_FIELDS = {
    "resumed_partial_build", "resumed_from_run", "resumed_from_status",
    "resumed_from_status_sha256", "resumed_from_journal_sha256",
    "resume_preflight", "resume_preflight_sha256", "resume_script", "resume_script_sha256",
}
HEX = re.compile(r"[0-9a-f]{64}\Z")
DEFAULT_MAX_FILE = 512 * 1024 * 1024
DEFAULT_MAX_TOTAL = 2 * 1024 * 1024 * 1024


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(value):
    require(isinstance(value, str) and HEX.fullmatch(value), "Invalid SHA-256 pin")
    return value


def logical(value):
    require(isinstance(value, str) and value and "\x00" not in value, "Invalid path")
    p = PureWindowsPath(value) if re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\") else PurePosixPath(value)
    require(p.is_absolute() and ".." not in p.parts, "Nonabsolute or traversing path")
    return str(p).casefold() if isinstance(p, PureWindowsPath) else str(p)


def parent(value):
    p = PureWindowsPath(value) if re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\") else PurePosixPath(value)
    logical(value)
    return str(p.parent)


def sibling(value, filename):
    p = PureWindowsPath(value) if re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\") else PurePosixPath(value)
    logical(value)
    return str(p.parent / filename)


def integer(value, label):
    require(type(value) is int and value >= 0, "Invalid nonnegative integer: " + label)
    return value


def strict_object(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, "Duplicate JSON object key: " + key)
        out[key] = value
    return out


def parse(raw):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=strict_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(AuditError("Nonfinite JSON number")))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AuditError("Invalid UTF-8 JSON") from error


def canonical(value):
    h = hashlib.sha256()
    for chunk in json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                                  allow_nan=False).iterencode(value):
        h.update(chunk.encode("ascii"))
    return h.hexdigest()


def rows_fingerprint(rows):
    h = hashlib.sha256()
    count = 0
    for row in rows:
        require(isinstance(row, dict), "Journal/results row is not an object")
        h.update(bytes.fromhex(canonical(row)))
        count += 1
    return count, h.hexdigest()


def verify_lineage(entry_status, expected_status_sha256, read_bytes, *,
                   allow_interrupted_end=False, expected_journal_sha256=None,
                   max_file_bytes=DEFAULT_MAX_FILE, max_total_bytes=DEFAULT_MAX_TOTAL,
                   max_resume_links=64):
    """Return a limited audit and exact inventory; never return theorem acceptance.

    Uses one bounded byte buffer at a time. Input JSON is parsed once by digest;
    status embedded arrays are reduced to fingerprints before following ancestry.
    Journals are processed oldest first; only the previous length/digest survives.
    Callback inputs are all absolute original paths, suitable for archive mapping.
    """
    logical(entry_status)
    pin(expected_status_sha256)
    if expected_journal_sha256 is not None:
        pin(expected_journal_sha256)
    for name, number in (("max_file_bytes", max_file_bytes), ("max_total_bytes", max_total_bytes),
                         ("max_resume_links", max_resume_links)):
        integer(number, name)
        require(number > 0, "Limit must be positive: " + name)
    inventory = {}
    aliases = {}
    total_bytes = 0

    def read(path, expected, role):
        nonlocal total_bytes
        key = logical(path)
        aliases.setdefault(key, set()).add(path)
        pin(expected)
        raw = read_bytes(path, max_file_bytes)
        require(type(raw) is bytes and len(raw) <= max_file_bytes, "Callback violated byte bound")
        actual = digest(raw)
        require(actual == expected, "Digest mismatch: " + path)
        if key in inventory:
            item = inventory[key]
            require(item["sha256"] == actual and item["size_bytes"] == len(raw), "Evidence alias changed")
            item["roles"].add(role)
        else:
            total_bytes += len(raw)
            require(total_bytes <= max_total_bytes, "Aggregate unique-evidence byte limit exceeded")
            inventory[key] = dict(path=path, sha256=actual, size_bytes=len(raw), roles={role})
        return raw

    nodes, seen = [], set()
    path, status_pin = entry_status, expected_status_sha256
    snapshot_pin = None
    snapshot_source_fingerprint = None
    resource_fingerprints = None
    dependencies_fingerprint = None
    build_directory = None
    child_boundary = None

    while True:
        require(len(nodes) <= max_resume_links, "Resume-link bound exceeded")
        key = logical(path)
        require(key not in seen, "Cycle in interrupted build ancestry")
        seen.add(key)
        raw = read(path, status_pin, "build_status")
        status = parse(raw)
        del raw
        require(isinstance(status, dict), "Build status is not an object")
        stage = status.get("status")
        require(stage == BUILD_OK or stage in INTERRUPTED, "Unsupported/failed build status")
        if not nodes:
            require(stage == BUILD_OK or allow_interrupted_end, "Interrupted entry requires explicit option")
        require(status.get("started_from_empty_project_build") is True, "Missing recorded empty-build origin claim")
        completed = integer(status.get("completed_modules"), "completed_modules")
        require(type(status.get("failed_modules")) is int and status["failed_modules"] == 0,
                "Failed modules or invalid failed_modules")
        current_build = logical(status["build_directory"])
        deps = status.get("dependencies")
        require(isinstance(deps, list) and deps, "Missing dependency snapshot")
        dep_fingerprint = canonical(deps)
        if build_directory is None:
            build_directory, dependencies_fingerprint = current_build, dep_fingerprint
        require(current_build == build_directory, "Build directory changed across resume")
        require(dep_fingerprint == dependencies_fingerprint, "Dependency snapshot changed across resume")
        input_path, input_pin = status["inputs_snapshot"], pin(status["inputs_snapshot_sha256"])
        require(logical(input_path) == logical(sibling(path, "inputs.json")), "Inputs path is not the run snapshot")
        require(logical(status["results_journal"]) == logical(sibling(path, "module-results.jsonl")),
                "Journal path is not the run journal")
        if snapshot_pin is None:
            snapshot_pin = input_pin
        require(input_pin == snapshot_pin, "Copied input/source/resource snapshot digest changed")
        input_raw = read(input_path, input_pin, "inputs_snapshot")
        if resource_fingerprints is None:
            inputs = parse(input_raw)
            require(isinstance(inputs, dict), "Input snapshot is not an object")
            sources, resources = inputs.get("source_sha256"), inputs.get("module_resources")
            require(isinstance(sources, dict) and sources and isinstance(resources, dict) and resources,
                    "Missing source/resource snapshot")
            for source_path, source_pin in sources.items():
                logical(source_path); pin(source_pin)
            require(all(isinstance(name, str) and name and isinstance(value, dict)
                        for name, value in resources.items()), "Malformed module resources")
            snapshot_source_fingerprint = canonical(sources)
            resource_fingerprints = {name: canonical(value) for name, value in resources.items()}
            del inputs, sources, resources
        del input_raw
        require(completed <= len(resource_fingerprints), "Completed count exceeds module universe")
        if stage == BUILD_OK:
            require(completed == len(resource_fingerprints), "Completed stage lacks all modules")
        if "source_sha256" in status:
            require(canonical(status.pop("source_sha256")) == snapshot_source_fingerprint,
                    "Embedded source map disagrees with inputs")
        embedded = None
        if "results" in status:
            results = status.pop("results")
            require(isinstance(results, list), "Embedded results is not an array")
            embedded = rows_fingerprint(results)
            del results
            require(embedded[0] == completed, "Embedded result count disagrees")
        last = canonical(status["last_result"]) if status.get("last_result") is not None else None
        has_last = "last_result" in status
        recorded_journal_pin = status.get("results_journal_sha256")
        if recorded_journal_pin is not None:
            pin(recorded_journal_pin)
        if stage == BUILD_OK:
            require(recorded_journal_pin is not None, "Completed status lacks recorded journal digest")
        if not nodes:
            require(recorded_journal_pin is not None or expected_journal_sha256 is not None,
                    "Sparse interrupted entry requires caller-supplied journal SHA-256")
            if recorded_journal_pin is not None and expected_journal_sha256 is not None:
                require(recorded_journal_pin == expected_journal_sha256, "Entry journal pins disagree")
            journal_pin = recorded_journal_pin or expected_journal_sha256
        else:
            journal_pin = child_boundary["journal_pin"]
            if recorded_journal_pin is not None:
                require(recorded_journal_pin == journal_pin, "Predecessor recorded/child journal pins disagree")
            require(child_boundary["count"] == completed, "Preflight predecessor count disagrees")
            require(child_boundary["input_pin"] == input_pin, "Preflight predecessor inputs pin disagrees")
        node = dict(path=path, sha256=status_pin, status=stage, completed_modules=completed,
                    journal_path=status["results_journal"], journal_sha256=journal_pin,
                    embedded=embedded, last=last, has_last=has_last)
        nodes.append(node)
        present = RESUME_FIELDS.intersection(status)
        if not present:
            require(status.get("started_from_empty_project_build") is True, "Origin lacks empty-build receipt")
            break
        require(present == RESUME_FIELDS and status["resumed_partial_build"] is True,
                "Partial or invalid interrupted-resume fields")
        predecessor = status["resumed_from_status"]
        predecessor_pin = pin(status["resumed_from_status_sha256"])
        require(logical(predecessor) == logical(sibling(predecessor, "status.json")), "Invalid predecessor status filename")
        require(logical(status["resumed_from_run"]) == logical(parent(predecessor)), "Predecessor run/path mismatch")
        require(logical(predecessor) not in seen, "Cycle in interrupted build ancestry")
        preflight_path = status["resume_preflight"]
        require(logical(preflight_path) == logical(sibling(path, "resume-preflight.json")), "Preflight path is not in run")
        preflight = parse(read(preflight_path, pin(status["resume_preflight_sha256"]), "resume_preflight"))
        require(isinstance(preflight, dict) and preflight.get("status") == "INTERRUPTED_RECOVERY3_RESUME_PREFLIGHT_PASSED",
                "Wrong preflight status")
        require(preflight.get("process_inventory_clean") is True, "Missing recorded preflight process check")
        require(logical(preflight["source_run"]) == logical(parent(predecessor)), "Preflight source run mismatch")
        # Preserve equivalent spellings appearing in raw receipts for later
        # original-to-portable mapping, including preflight's derived siblings.
        for filename in ("status.json", "inputs.json", "module-results.jsonl"):
            alias = preflight["source_run"].rstrip("/\\") + "/" + filename
            aliases.setdefault(logical(alias), set()).add(alias)
        require(pin(preflight["source_status_sha256"]) == predecessor_pin, "Preflight status pin mismatch")
        require(pin(preflight["source_journal_sha256"]) == pin(status["resumed_from_journal_sha256"]),
                "Preflight journal pin mismatch")
        require(pin(preflight["source_inputs_sha256"]) == input_pin, "Preflight inputs pin mismatch")
        require(logical(preflight["build_directory"]) == build_directory, "Preflight build directory mismatch")
        require(type(preflight.get("failed_modules")) is int and preflight["failed_modules"] == 0,
                "Preflight failures or invalid count")
        boundary_count = integer(preflight.get("completed_modules"), "preflight completed_modules")
        require(integer(preflight.get("total_modules"), "preflight total_modules") == len(resource_fingerprints),
                "Preflight module universe count mismatch")
        require(boundary_count <= completed, "Resume lost completed modules")
        script_pin = pin(status["resume_script_sha256"])
        require(logical(preflight["resume_script"]) == logical(status["resume_script"])
                and pin(preflight["resume_script_sha256"]) == script_pin, "Preflight script binding mismatch")
        aliases.setdefault(logical(preflight["resume_script"]), set()).add(preflight["resume_script"])
        script_raw = read(status["resume_script"], script_pin, "resume_script_integrity_only")
        del script_raw, preflight
        child_boundary = dict(count=boundary_count, journal_pin=status["resumed_from_journal_sha256"], input_pin=input_pin)
        path, status_pin = predecessor, predecessor_pin
        del status

    del status
    previous_size = previous_digest = None
    previous_count = 0
    boundaries = []
    for node in reversed(nodes):
        raw = read(node["journal_path"], node["journal_sha256"], "module_results_journal")
        if previous_size is not None:
            require(len(raw) >= previous_size and digest(memoryview(raw)[:previous_size]) == previous_digest,
                    "Journal is not the exact predecessor byte prefix")
        require(not raw or raw.endswith(b"\n"), "Journal has unterminated trailing record")
        modules = set()
        h = hashlib.sha256()
        last = None
        for line in io.BytesIO(raw):
            if not line.strip():
                continue
            row = parse(line)
            require(isinstance(row, dict), "Journal row is not an object")
            name = row.get("module")
            require(isinstance(name, str) and name in resource_fingerprints, "Journal module outside input universe")
            require(name not in modules, "Duplicate journal module")
            require(type(row.get("exit_code")) is int and row["exit_code"] == 0, "Unsuccessful journal row")
            require(canonical(row.get("resource")) == resource_fingerprints[name], "Journal resource differs from snapshot")
            modules.add(name)
            last = canonical(row)
            h.update(bytes.fromhex(last))
        count = len(modules)
        require(count == node["completed_modules"], "Journal count disagrees with build status")
        require(count >= previous_count, "Journal count decreased")
        if node["embedded"] is not None:
            require(node["embedded"] == (count, h.hexdigest()), "Embedded results disagree with journal")
        if node["has_last"]:
            require(node["last"] == last, "Embedded last_result disagrees with journal")
        if node["status"] == BUILD_OK:
            require(modules == resource_fingerprints.keys(), "Completed journal lacks exact module coverage")
        previous_size, previous_digest, previous_count = len(raw), digest(raw), count
        boundaries.append(dict(status_path=node["path"], status_sha256=node["sha256"],
                               status=node["status"], completed_modules=count,
                               journal_path=node["journal_path"], journal_sha256=previous_digest,
                               journal_size_bytes=previous_size))
        del raw, modules

    # Stable-input recheck: no raw bytes/results arrays are cached across files.
    require(set(aliases) == set(inventory), "Unresolved evidence alias")
    for key, item in inventory.items():
        for alias in sorted(aliases[key]):
            raw = read_bytes(alias, max_file_bytes)
            require(type(raw) is bytes and len(raw) == item["size_bytes"] and digest(raw) == item["sha256"],
                    "Evidence changed during audit: " + alias)
            del raw
    rows = [dict(item, roles=sorted(item["roles"]), original_paths=sorted(aliases[key]))
            for key, item in sorted(inventory.items())]
    return dict(schema=SCHEMA, status="INTERRUPTED_BUILD_LINEAGE_LIMITED_PASS",
                entry_status=entry_status, entry_status_sha256=expected_status_sha256,
                entry_build_status=nodes[0]["status"], entry_build_complete=nodes[0]["status"] == BUILD_OK,
                entry_journal_sha256=nodes[0]["journal_sha256"], interrupted_end_explicitly_allowed=allow_interrupted_end,
                resume_links=len(nodes)-1, status_records=len(nodes), module_universe_count=len(resource_fingerprints),
                boundaries_oldest_first=boundaries, required_evidence=rows, total_unique_evidence_bytes=total_bytes,
                recorded_empty_origin_claim_checked=True, physical_empty_origin_verified=False,
                all_selected_bytes_rechecked_for_stability=True, source_artifact_closure_checked=False,
                producer_semantics_verified=False, mathematical_acceptance=False,
                limits=dict(max_file_bytes=max_file_bytes, max_total_bytes=max_total_bytes, max_resume_links=max_resume_links),
                limitations=["Checks receipt hashes, snapshot consistency, successful unique journal rows and exact byte-prefix continuity only.",
                             "No Lean, source/artifact/log closure revalidation, dependency fetch, or mathematical acceptance is performed.",
                             "The empty-origin and process-clean fields are historical claims; physical directory/process history is not reconstructed.",
                             "Matching script bytes establish integrity, not approval or verification of producer semantics.",
                             "Caller-supplied pins, including an interrupted terminal journal pin, are evidence anchors, not independent proof of history.",
                             "Stable rereads detect observed changes, not a hostile actor racing every read; caller must select frozen evidence.",
                             "Buffers are byte-bounded; parsed JSON and module-name sets add overhead. This is not a streaming JSON parser."])
