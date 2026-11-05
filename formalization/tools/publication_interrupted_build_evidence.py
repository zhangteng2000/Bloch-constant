"""Collect the frozen completed-build lineage audit without changing acceptance.

The report is a limited metadata/byte-lineage check. Its evidence subset must be
combined with accepted sources, fresh-recovery history and runtime support.
"""
import hashlib
from pathlib import Path
import types

LINEAGE_PIN = "1603a4784aed7c373f748bfe6517a1e602b7325b06607e49ac9dfc0619299af1"
LINEAGE_FILENAME = "interrupted_build_lineage.py"
HISTORICAL_BASIS = "interrupted_build_lineage_digest"


def load_lineage(require):
    path = Path(__file__).resolve().parent / LINEAGE_FILENAME
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == LINEAGE_PIN, "Frozen interrupted-lineage verifier changed")
    module = types.ModuleType("pinned_interrupted_build_lineage")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def collect(inv, build_path, expected_build_sha256, *, require, checked_file):
    """Default completed mode only; entry pin comes from accepted evidence."""
    lineage = load_lineage(require)
    roots = (inv.project, inv.work)

    def read_bytes(value, limit):
        path = checked_file(value, roots)
        require(not path.is_relative_to(inv.work / "module-replay-stage"), "Lineage input points into historical staging")
        require(path.stat().st_size <= limit, "Lineage evidence exceeds byte bound")
        with path.open("rb") as source:
            raw = source.read(limit + 1)
        require(len(raw) <= limit, "Lineage evidence grew beyond byte bound")
        return raw

    try:
        report = lineage.verify_lineage(str(build_path), expected_build_sha256, read_bytes)
    except lineage.AuditError as error:
        require(False, "Interrupted build lineage rejected: " + str(error))
    require(report["entry_build_complete"] is True
            and report["interrupted_end_explicitly_allowed"] is False
            and report["mathematical_acceptance"] is False, "Unexpected limited lineage report mode")

    # Canonical filesystem aliases may already share a destination with accepted
    # proof evidence. Preserve that destination and its stronger integrity basis.
    destinations = {}
    for entry in inv.entries.values():
        for original in entry["original_paths"]:
            key = lineage.logical(original)
            require(key not in destinations or destinations[key] == entry["archive_path"],
                    "Conflicting existing original-path alias")
            destinations[key] = entry["archive_path"]
    for item in report["required_evidence"]:
        path = checked_file(item["path"], roots)
        originals = set(item["original_paths"]) | {item["path"], str(path)}
        matches = {destinations[lineage.logical(alias)] for alias in originals
                   if lineage.logical(alias) in destinations}
        require(len(matches) <= 1, "Conflicting interrupted-lineage alias destinations")
        archive = next(iter(matches)) if matches else None
        previous = inv.entries.get(archive.casefold()) if archive else None
        previous_basis = previous["integrity_basis"] if previous else None
        if archive:
            inv.add(path, archive, "interrupted_build_lineage_evidence", item["sha256"])
        else:
            inv.evidence(path, item["sha256"], "interrupted_build_lineage_evidence")
            archive = inv.by_original[str(path)]
        entry = inv.entries[archive.casefold()]
        require(entry["sha256"] == item["sha256"] and entry["size_bytes"] == item["size_bytes"],
                "Lineage evidence changed before inventory insertion")
        entry["integrity_basis"] = (previous_basis if previous_basis in
            {"accepted_digest", "recovery_controller_digest", HISTORICAL_BASIS} else HISTORICAL_BASIS)
        for role in item["roles"]:
            name = "interrupted_lineage_" + role
            if name not in entry["roles"]:
                entry["roles"].append(name)
        for alias in sorted(originals):
            require(alias not in inv.by_original or inv.by_original[alias] == archive,
                    "Interrupted lineage would overwrite an original alias")
            key = lineage.logical(alias)
            require(key not in destinations or destinations[key] == archive,
                    "Interrupted lineage has conflicting equivalent aliases")
            if alias not in entry["original_paths"]:
                entry["original_paths"].append(alias)
            inv.by_original[alias] = archive
            destinations[key] = archive
        entry["original_paths"].sort()
        entry["roles"].sort()
    return report
