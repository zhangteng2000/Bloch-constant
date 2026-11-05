"""Pure-data v5 recovery and interrupted-build checks; no local imports or IO.

read_member(archive_path) must return bytes from the selected inventory member.
The function verifies their SHA/size itself. No callback means structural checks
only, never permission to bootstrap, package, or claim mathematical acceptance.
Raw mode additionally requires an explicitly supplied, independently pinned
lineage_verifier callable. No sibling module is imported or executed here.
"""
import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath
import re
import tomllib

ACCEPTED = "ORIGINAL_THEOREM_1_3_FORMALIZATION_ACCEPTED"
PREPARED = "PREPARED_FRESH_BUILD_RECOVERY_NOT_BUILT"
CHAIN = "ahlfors-publication-recovery-chain-v1"
MANIFEST = "ahlfors-fresh-build-recovery-v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_METADATA_FILE = 512 * 1024**2
MAX_METADATA_TOTAL = 2 * 1024**3
MANIFEST_KEYS = {"schema", "status", "project", "work", "predecessor", "request", "review",
                 "integration", "old_config", "next_config", "materials", "repairs",
                 "new_build_directory", "predecessor_evidence", "theorem_1_3_complete"}
CHAIN_KEYS = {"schema", "generation_count", "generations", "manifest", "manifest_sha256",
              "preserved_repair_count", "resumed_controller_records", "recovery_status",
              "theorem_acceptance_status", "all_raw_records_preserved",
              "historical_reference_versions", "compiled_artifacts_included", "limitations"}
GEN_KEYS = {"schema", "manifest", "manifest_sha256", "preserved_repair_count", "recovery_status",
            "terminal_controller_status", "old_failed_build", "all_raw_records_preserved",
            "compiled_artifacts_included", "limitations", "generation"}
ROW_KEYS = {"generation", "recovery_manifest", "recovery_manifest_sha256", "original_path",
            "sha256", "archive_path"}
LINEAGE_SCHEMA = "ahlfors-interrupted-build-lineage-audit-candidate-v1"
LINEAGE_KEYS = {"schema", "status", "entry_status", "entry_status_sha256", "entry_build_status",
                "entry_build_complete", "entry_journal_sha256", "interrupted_end_explicitly_allowed",
                "resume_links", "status_records", "module_universe_count", "boundaries_oldest_first",
                "required_evidence", "total_unique_evidence_bytes", "recorded_empty_origin_claim_checked",
                "physical_empty_origin_verified", "all_selected_bytes_rechecked_for_stability",
                "source_artifact_closure_checked", "producer_semantics_verified", "mathematical_acceptance",
                "limits", "limitations"}
LINEAGE_ROLES = {"build_status", "inputs_snapshot", "resume_preflight", "resume_script_integrity_only",
                 "module_results_journal"}


class RecoveryInventoryError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise RecoveryInventoryError(message)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key in recovery metadata")
        result[key] = value
    return result


def logical(value):
    require(isinstance(value, str) and value, "Invalid original-path metadata")
    p = PureWindowsPath(value) if re.match(r"^[A-Za-z]:", value) else PurePosixPath(value)
    require(p.is_absolute() and ".." not in p.parts, "Nonabsolute/traversing original-path metadata")
    return p


def digest(value):
    require(isinstance(value, str) and HEX.fullmatch(value), "Malformed recovery SHA-256")
    return value


def _index(plan, entries):
    require(plan.get("publication_preparation_version") == 5 and
            type(plan.get("publication_preparation_version")) is int, "Only reviewed v5 inventories are supported")
    rows = list(entries.values()) if isinstance(entries, dict) else entries
    require(isinstance(rows, list) and rows, "Missing recovery inventory entries")
    by_name, aliases, folded = {}, {}, set()
    for entry in rows:
        name = entry["archive_path"]
        require(isinstance(name, str) and name and not any(c in name for c in "\\:") and
                not PurePosixPath(name).is_absolute() and PurePosixPath(name).as_posix() == name and
                ".." not in PurePosixPath(name).parts, "Invalid recovery archive destination")
        require(name.casefold() not in folded, "Duplicate recovery archive destination")
        folded.add(name.casefold())
        digest(entry["sha256"])
        require(type(entry["size_bytes"]) is int and entry["size_bytes"] >= 0, "Invalid recovery member size")
        require(isinstance(entry["original_paths"], list) and entry["source_path"] in entry["original_paths"],
                "Recovery member has no source alias")
        for alias in entry["original_paths"]:
            logical(alias)
            require(alias not in aliases, "Duplicate recovery original alias")
            aliases[alias] = name
        by_name[name] = entry
    require(plan.get("original_to_portable") == aliases, "Recovery current alias map differs from inventory")
    return by_name, aliases


def lineage_members(plan, by_name, aliases):
    """Validate declared completed-report structure and exact alias providers."""
    report = plan.get("interrupted_build_provenance")
    require(isinstance(report, dict) and set(report) == LINEAGE_KEYS and
            report["schema"] == LINEAGE_SCHEMA and report["status"] == "INTERRUPTED_BUILD_LINEAGE_LIMITED_PASS",
            "Missing or unsupported interrupted-build provenance")
    require(report["entry_build_status"] == "LAKE_BUILD_AND_ROOT_AUDITS_PASSED_EXTRA_CHECKER_PENDING" and
            all(report[k] is True for k in ("entry_build_complete", "recorded_empty_origin_claim_checked",
                                           "all_selected_bytes_rechecked_for_stability")) and
            all(report[k] is False for k in ("interrupted_end_explicitly_allowed", "physical_empty_origin_verified",
                "source_artifact_closure_checked", "producer_semantics_verified", "mathematical_acceptance")),
            "Interrupted-build provenance is incomplete or overclaims verification")
    for key in ("resume_links", "status_records", "module_universe_count", "total_unique_evidence_bytes"):
        require(type(report[key]) is int and report[key] >= 0, "Invalid lineage count")
    require(report["resume_links"] <= 64 and report["status_records"] == report["resume_links"] + 1 and
            report["module_universe_count"] > 0, "Invalid lineage status/module counts")
    logical(report["entry_status"]); digest(report["entry_status_sha256"]); digest(report["entry_journal_sha256"])
    require(report["limits"] == dict(max_file_bytes=512 * 1024**2, max_total_bytes=2 * 1024**3, max_resume_links=64)
            and all(type(v) is int for v in report["limits"].values()), "Unsupported lineage limits")
    require(isinstance(report["limitations"], list) and report["limitations"] and
            all(isinstance(v, str) and v for v in report["limitations"]), "Missing lineage limitations")
    boundaries = report["boundaries_oldest_first"]
    require(isinstance(boundaries, list) and len(boundaries) == report["status_records"], "Lineage boundary count differs")
    rows = report["required_evidence"]
    require(isinstance(rows, list) and rows, "Missing lineage required evidence")
    selected, seen = {}, set()
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"path", "sha256", "size_bytes", "roles", "original_paths"},
                "Unsupported lineage evidence row")
        origin = logical(row["path"])
        require(origin not in seen, "Duplicate lineage evidence origin")
        seen.add(origin); digest(row["sha256"])
        require(type(row["size_bytes"]) is int and row["size_bytes"] >= 0, "Invalid lineage evidence size")
        paths, roles = row["original_paths"], row["roles"]
        require(isinstance(paths, list) and paths == sorted(set(paths)) and row["path"] in paths and
                all(logical(path) == origin for path in paths), "Malformed lineage evidence aliases")
        require(isinstance(roles, list) and roles == sorted(set(roles)) and roles and set(roles) <= LINEAGE_ROLES,
                "Unsupported lineage evidence roles")
        require(all(path in aliases for path in paths), "Required lineage evidence alias omitted")
        names = {aliases[path] for path in paths}
        require(len(names) == 1, "Equivalent lineage aliases must use the same archived member")
        name = names.pop(); entry = by_name[name]
        require(logical(entry["source_path"]) == origin,
                "Lineage evidence member is not selected from the same logical origin")
        require(entry["sha256"] == row["sha256"] and entry["size_bytes"] == row["size_bytes"],
                "Lineage evidence member digest/size mismatch")
        require(entry["integrity_basis"] in {"accepted_digest", "recovery_controller_digest", "interrupted_build_lineage_digest"},
                "Lineage evidence lacks an explicit integrity basis")
        require("interrupted_build_lineage_evidence" in entry["roles"] and
                all("interrupted_lineage_" + role in entry["roles"] for role in roles),
                "Required lineage evidence roles omitted")
        selected[name] = entry
    require(sum(row["size_bytes"] for row in rows) == report["total_unique_evidence_bytes"], "Lineage byte total differs")
    require(report["entry_status"] in aliases and
            by_name[aliases[report["entry_status"]]]["sha256"] == report["entry_status_sha256"],
            "Lineage entry build receipt omitted or changed")
    return report, selected


def metadata_storage_budget(selected):
    """Bound distinct immutable content, retaining every selected member."""
    sizes = {}
    for entry in selected.values():
        digest(entry["sha256"])
        size = entry["size_bytes"]
        require(type(size) is int and 0 <= size <= MAX_METADATA_FILE,
                "Recovery metadata member exceeds bound")
        sizes[(entry["sha256"], size)] = size
    unique_bytes = sum(sizes.values())
    require(unique_bytes <= MAX_METADATA_TOTAL,
            "Recovery distinct metadata content exceeds bound")
    return dict(policy="VERIFIED_MEMBER_CONTENT_SHARING_V1",
                members=len(selected),
                logical_bytes=sum(e["size_bytes"] for e in selected.values()),
                distinct_contents=len(sizes), distinct_bytes=unique_bytes,
                max_member_bytes=MAX_METADATA_FILE,
                max_distinct_content_bytes=MAX_METADATA_TOTAL)


class VerifiedMetadataCache:
    """Each member is checked before sharing immutable, byte-equal content.

    The 2 GiB budget covers retained distinct raw bytes, not total process RAM.
    One bounded incoming member and parsed JSON add temporary/derived storage,
    just as in the original readback. No archive member is omitted or trusted
    solely because another member has the same declared digest.
    """
    def __init__(self, selected):
        self.budget = metadata_storage_budget(selected)
        self._entries = {name: (e["sha256"], e["size_bytes"])
                         for name, e in selected.items()}
        self._members, self._content = {}, {}
        self.resident_bytes = 0

    def __contains__(self, name):
        return name in self._entries

    def __len__(self):
        return len(self._members)

    def is_cached(self, name):
        return name in self._members

    def complete(self):
        return self._members.keys() == self._entries.keys()

    def __getitem__(self, name):
        require(name in self._members, "Metadata member not yet verified")
        return self._content[self._members[name]]

    def __setitem__(self, name, raw):
        require(name in self._entries, "Unselected metadata member")
        expected, size = self._entries[name]
        require(isinstance(raw, bytes) and len(raw) == size and
                hashlib.sha256(raw).hexdigest() == expected,
                "Recovery raw metadata SHA/size mismatch")
        key = expected, size
        if key in self._content:
            require(self._content[key] == raw,
                    "Equal metadata descriptors have unequal bytes")
        else:
            require(self.resident_bytes + len(raw) <= MAX_METADATA_TOTAL,
                    "Recovery retained metadata content exceeds bound")
            self._content[key] = raw
            self.resident_bytes += len(raw)
        self._members[name] = key


def metadata_entries(plan, entries):
    """Bounded capture selection for one-pass archived readback; no filesystem IO."""
    by_name, aliases = _index(plan, entries)
    selected = {name: e for name, e in by_name.items()
                if (PurePosixPath(name).suffix.lower() == ".json" or
                    PurePosixPath(name).name in {"lakefile.toml.failed-build", "lakefile.toml.next"} or
                    any(r in e["roles"] for r in ("final_controller", "accepted_delivery_manifest")))}
    _, lineage = lineage_members(plan, by_name, aliases)
    selected.update(lineage)  # JSONL journals and script bytes are mandatory offline inputs too.
    require(all(e["size_bytes"] <= MAX_METADATA_FILE for e in selected.values()), "Recovery metadata member exceeds bound")
    metadata_storage_budget(selected)
    return selected


def validate_recovery_inventory(plan, entries, read_member=None, final_state=None, *, lineage_verifier=None):
    by_name, aliases = _index(plan, entries)
    metadata = metadata_entries(plan, entries)
    lineage_report, lineage_metadata = lineage_members(plan, by_name, aliases)
    require("recovery_provenance" in plan, "Missing explicit recovery provenance field")
    provenance = plan["recovery_provenance"]
    generations, versions = [], {}
    if provenance is not None:
        require(isinstance(provenance, dict) and set(provenance) == CHAIN_KEYS and provenance["schema"] == CHAIN,
                "Unsupported recovery-chain metadata")
        count = provenance["generation_count"]
        require(type(count) is int and 1 <= count <= 16, "Invalid recovery generation count")
        generations = provenance["generations"]
        require(isinstance(generations, list) and len(generations) == count, "Recovery generation list/count mismatch")
        seen_manifests = set()
        for number, generation in enumerate(generations, 1):
            require(isinstance(generation, dict) and set(generation) == GEN_KEYS and generation["schema"] == MANIFEST and
                    type(generation["generation"]) is int and generation["generation"] == number,
                    "Recovery generations are missing, reordered, or unsupported")
            path, pin = generation["manifest"], digest(generation["manifest_sha256"])
            require(path not in seen_manifests and path in aliases and by_name[aliases[path]]["sha256"] == pin,
                    "Recovery manifest missing, duplicated, or unbound")
            seen_manifests.add(path)
            require(generation["recovery_status"] == PREPARED and generation["all_raw_records_preserved"] is True and
                    generation["compiled_artifacts_included"] is False and
                    type(generation["preserved_repair_count"]) is int and generation["preserved_repair_count"] >= 1,
                    "Incorrect historical recovery status/count/flags")
            require(generation["terminal_controller_status"] == (ACCEPTED if number == count else "FAILED"),
                    "Historical failed controller relabeled or latest acceptance missing")
            require(generation["old_failed_build"] in aliases, "Old failed build omitted")
        require(provenance["manifest"] == generations[-1]["manifest"] and
                provenance["manifest_sha256"] == generations[-1]["manifest_sha256"] and
                provenance["preserved_repair_count"] == sum(g["preserved_repair_count"] for g in generations) and
                type(provenance["resumed_controller_records"]) is int and
                count <= provenance["resumed_controller_records"] <= 64 and
                provenance["recovery_status"] == PREPARED and provenance["theorem_acceptance_status"] == ACCEPTED and
                provenance["all_raw_records_preserved"] is True and provenance["compiled_artifacts_included"] is False,
                "Recovery-chain summary binding differs")
        rows = provenance["historical_reference_versions"]
        require(isinstance(rows, list) and rows, "Missing historical version map")
        for row in rows:
            require(isinstance(row, dict) and set(row) == ROW_KEYS and type(row["generation"]) is int and
                    1 <= row["generation"] <= count, "Unsupported historical version row")
            generation = generations[row["generation"] - 1]
            require(row["recovery_manifest"] == generation["manifest"] and
                    row["recovery_manifest_sha256"] == generation["manifest_sha256"], "Historical version has wrong generation manifest")
            logical(row["original_path"])
            pin = digest(row["sha256"])
            require(row["archive_path"] in by_name and by_name[row["archive_path"]]["sha256"] == pin,
                    "Historical version member missing or digest differs")
            key = row["generation"], row["original_path"], pin
            require(key not in versions, "Duplicate historical version row")
            versions[key] = row["archive_path"]
    summary = dict(status="RECOVERY_INVENTORY_STRUCTURE_ONLY_NOT_RAW_CHAIN_VERIFIED", generation_count=len(generations),
                   historical_reference_count=len(versions), publication_preparation_version=5,
                   interrupted_build_lineage_verified=False,
                   interrupted_build_provenance_sha256=hashlib.sha256(json.dumps(lineage_report, sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest(),
                   recovery_provenance_sha256=hashlib.sha256(json.dumps(provenance, sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False).encode()).hexdigest())
    if read_member is None:
        return summary
    require(callable(lineage_verifier), "Raw verification requires an explicitly supplied pinned lineage verifier")

    objects, raw_cache = {}, VerifiedMetadataCache(metadata)
    def raw_name(name):
        require(name in metadata, "Unselected or oversized recovery metadata")
        if not raw_cache.is_cached(name):
            raw = read_member(name)
            require(isinstance(raw, bytes) and len(raw) == by_name[name]["size_bytes"] and
                    hashlib.sha256(raw).hexdigest() == by_name[name]["sha256"], "Recovery raw metadata SHA/size mismatch")
            raw_cache[name] = raw
        return raw_cache[name]
    def record(path, pin=None):
        require(path in aliases, "Required raw recovery record omitted")
        name = aliases[path]
        require(pin is None or by_name[name]["sha256"] == digest(pin), "Recovery raw record reference digest mismatch")
        if name not in objects:
            objects[name] = json.loads(raw_name(name).decode("utf-8-sig"), object_pairs_hook=strict_object)
        require(isinstance(objects[name], dict), "Recovery raw record is not an object")
        return objects[name]
    def bound(ref):
        require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}, "Malformed raw recovery reference")
        require(ref["path"] in aliases and by_name[aliases[ref["path"]]]["sha256"] == digest(ref["sha256"]),
                "Required recovery member reference missing/changed")
        return aliases[ref["path"]]
    def role(name):
        matches = [e for e in by_name.values() if name in e["roles"]]
        require(len(matches) == 1, "Missing unique recovery gate role: " + name)
        return matches[0]
    fe, de = role("final_controller"), role("accepted_delivery_manifest")
    state, delivery = record(fe["source_path"]), record(de["source_path"])
    require(final_state is None or final_state == state, "Provided final controller differs from archived raw record")
    require(state.get("status") == delivery.get("status") == ACCEPTED and state.get("theorem_1_3_complete") is True,
            "Recovery mapping is not anchored to accepted current records")
    sources = delivery.get("source_sha256")
    require(isinstance(sources, dict) and sources, "Missing accepted current source map")
    for path, pin in sources.items():
        require(path in aliases and by_name[aliases[path]]["sha256"] == digest(pin) and
                by_name[aliases[path]]["integrity_basis"] == "accepted_digest", "Historical mapping overwrote an accepted current source")
    nodes, seen = [(fe["source_path"], fe["sha256"], state)], {fe["source_path"]}
    cursor = state
    while "resumed_from" in cursor or "resumed_from_sha256" in cursor:
        require("resumed_from" in cursor and "resumed_from_sha256" in cursor and len(nodes) <= 64,
                "Incomplete or excessive controller resume chain")
        path, pin = cursor["resumed_from"], cursor["resumed_from_sha256"]
        require(path not in seen, "Cycle in controller resume chain")
        prior = record(path, pin)
        seen.add(path); nodes.append((path, pin, prior)); cursor = prior
    groups, no_recovery, seen_groups = [], False, set()
    for node in nodes:
        st = node[2]
        fields = ("fresh_build_recovery" in st, "fresh_build_recovery_sha256" in st)
        require(fields[0] == fields[1], "Partial controller recovery reference")
        if not fields[0]:
            if groups and groups[-1].get("boundary") is None: groups[-1]["boundary"] = node
            no_recovery = True
            continue
        require(not no_recovery, "Dropped or returned-to recovery provenance")
        key = st["fresh_build_recovery"], digest(st["fresh_build_recovery_sha256"])
        if groups and groups[-1]["key"] == key:
            groups[-1]["nodes"].append(node); continue
        require(key not in seen_groups, "Reordered/cyclic recovery generations")
        if groups: groups[-1]["boundary"] = node
        groups.append(dict(key=key, nodes=[node])); seen_groups.add(key)
    require(len(groups) == len(generations), "Recovery generations dropped or fabricated")
    if provenance is not None:
        require(provenance["resumed_controller_records"] == len(nodes) - 1, "Resume-chain count differs")
    expected_versions, seen_builds = set(), set()
    providers, source_keys = {}, set(sources)
    def provide(original, pin, destination):
        require(destination in by_name and by_name[destination]["sha256"] == digest(pin), "Invalid historical provider")
        providers.setdefault((original, pin), set()).add(destination)
    for path, pin in sources.items(): provide(path, pin, aliases[path])
    # Register all explicitly preserved source versions before traversing old
    # generations. A later generation can hold an earlier generation's output.
    for generation in generations:
        m = record(generation["manifest"], generation["manifest_sha256"])
        require(set(m) == MANIFEST_KEYS, "Unsupported historical manifest fields")
        old = m["predecessor"]["build_status"]
        old_build = record(old["path"], old["sha256"])
        source_keys.update(old_build["source_sha256"])
        config_source = str(logical(m["project"]) / "lakefile.toml")
        for key in ("old_config", "next_config"):
            provide(config_source, m[key]["sha256"], bound(m[key]))
        for repair in m["repairs"]:
            provide(repair["source"], repair["before_sha256"], bound(repair["before_backup"]))
    after_sources = sources
    after_integration = record(state["integration_record"]) if generations else None
    after_build = record(state["build_record"]) if generations else None
    for group, generation in zip(groups, reversed(generations)):
        number = generation["generation"]
        require(group["key"] == (generation["manifest"], generation["manifest_sha256"]), "Generation order differs from raw controller chain")
        m = record(*group["key"])
        require(set(m) == MANIFEST_KEYS and m["schema"] == MANIFEST and m["status"] == PREPARED and
                m["theorem_1_3_complete"] is False, "Unsupported or relabeled historical manifest")
        require(set(m["predecessor"]) == {"final_status", "build_status", "integration"}, "Incomplete predecessor")
        boundary = group.get("boundary")
        require(boundary is not None and m["predecessor"]["final_status"] == {"path": boundary[0], "sha256": boundary[1]},
                "Fresh generation predecessor is not exact controller boundary")
        previous = {}
        for key, ref in m["predecessor"].items():
            bound(ref); previous[key] = record(ref["path"], ref["sha256"])
        old_final, old_build, old_integration = (previous[k] for k in ("final_status", "build_status", "integration"))
        require(old_final.get("status") == old_build.get("status") == "FAILED" and
                old_final.get("theorem_1_3_complete") is False and old_build.get("theorem_1_3_complete") is False and
                old_build.get("final_acceptance_complete") is False and not old_final.get("active_process"),
                "Historical predecessor is not failed/incomplete")
        require(generation["old_failed_build"] == m["predecessor"]["build_status"]["path"] and
                generation["terminal_controller_status"] == group["nodes"][0][2]["status"], "Generation summary differs from raw records")
        bound(m["integration"])
        installed = record(m["integration"]["path"], m["integration"]["sha256"])
        require(installed == after_integration and
                dict(installed, build_directory=old_integration["build_directory"],
                     lakefile_sha256=old_integration["lakefile_sha256"]) == old_integration,
                "Generation integration differs beyond build directory/config")
        require(all(node[2].get("integration_record", m["integration"]["path"]) == m["integration"]["path"] for node in group["nodes"]),
                "Ordinary resume changed recovered integration")
        require(old_final["integration_record"] == m["predecessor"]["integration"]["path"] and
                after_build["build_directory"] == installed["build_directory"] == m["new_build_directory"] and
                old_build["build_directory"] == old_integration["build_directory"], "Generation build/integration links differ")
        fresh = m["new_build_directory"]
        fresh_key, old_key = logical(fresh), logical(old_build["build_directory"])
        require(fresh_key not in seen_builds and fresh_key != old_key, "Recovery reused a build directory")
        seen_builds.add(fresh_key)
        if number == 1: require(old_key not in seen_builds, "Recovery reused original failed build")
        project = logical(m["project"])
        require(project == logical(de["source_path"]).parent and
                logical(m["work"]) == project.parent.parent / "work", "Recovery project/work identity differs")
        config_source = str(project / "lakefile.toml")
        configs = []
        for key in ("old_config", "next_config"):
            name = bound(m[key]); configs.append(tomllib.loads(raw_name(name).decode("utf-8")))
            expected_versions.add((number, config_source, m[key]["sha256"]))
        old_toml, next_toml = configs
        require(set(old_toml) == set(next_toml) and
                {k for k in old_toml if old_toml[k] != next_toml[k]} == {"buildDir"}, "Recovery configuration changed beyond buildDir")
        require(str(project / old_toml["buildDir"]) == old_build["build_directory"] and
                str(project / next_toml["buildDir"]) == fresh, "TOML buildDir binding differs")
        require(m["old_config"]["sha256"] == old_integration["lakefile_sha256"] and
                m["next_config"]["sha256"] == installed["lakefile_sha256"] == after_sources.get(config_source),
                "Recovery configuration digest not bound to source maps")
        for ref in (m["request"], m["review"]): bound(ref)
        request = record(m["request"]["path"], m["request"]["sha256"])
        require(set(request) == {"schema", "predecessor", "repairs", "review"} and
                request["schema"] == "ahlfors-fresh-build-recovery-request-v1" and request["predecessor"] == m["predecessor"],
                "Recovery request differs")
        require(request["review"]["sha256"] == m["review"]["sha256"], "Historical review digest differs")
        expected_versions.add((number, request["review"]["path"], request["review"]["sha256"]))
        provide(request["review"]["path"], request["review"]["sha256"], bound(m["review"]))
        old_inputs = record(old_build["inputs_snapshot"], old_build["inputs_snapshot_sha256"])
        require(old_inputs["source_sha256"] == old_build["source_sha256"], "Historical build/input maps differ")
        after_inputs = record(after_build["inputs_snapshot"], after_build["inputs_snapshot_sha256"])
        require(after_build["source_sha256"] == after_inputs["source_sha256"] == after_sources,
                "Generation output build/input/source maps differ")
        require(isinstance(old_inputs.get("module_resources"), dict) and old_inputs["module_resources"] and
                old_inputs["module_resources"] == after_inputs.get("module_resources"), "Generation module resources changed")
        expected_sources = dict(old_inputs["source_sha256"])
        require(len(m["repairs"]) == len(request["repairs"]) == generation["preserved_repair_count"], "Repair count differs")
        seen_sources = set()
        for repair, declared in zip(m["repairs"], request["repairs"]):
            keys = {"module", "source", "before_sha256", "before_backup", "after_sha256"}
            require(set(repair) == set(declared) == keys and
                    {k:v for k,v in repair.items() if k != "before_backup"} ==
                    {k:v for k,v in declared.items() if k != "before_backup"}, "Repair declaration differs")
            path = repair["source"]
            require(path not in seen_sources and expected_sources.get(path) == repair["before_sha256"] != repair["after_sha256"] and
                    after_sources.get(path) == repair["after_sha256"], "Repair is not bound to before/after inputs")
            seen_sources.add(path); bound(repair["before_backup"])
            require(repair["before_backup"]["sha256"] == declared["before_backup"]["sha256"] == repair["before_sha256"],
                    "Historical original backup digest differs")
            provide(declared["before_backup"]["path"], repair["before_sha256"], bound(repair["before_backup"]))
            expected_versions.update(((number, path, repair["before_sha256"]),
                                      (number, declared["before_backup"]["path"], repair["before_sha256"])))
            expected_sources[path] = repair["after_sha256"]
        expected_sources[config_source] = m["next_config"]["sha256"]
        require(expected_sources == after_sources, "Recovery changed undeclared current source inputs")
        recorded = m["predecessor_evidence"]
        require(isinstance(recorded, dict) and recorded and config_source not in recorded, "Invalid predecessor evidence map")
        for ref in m["predecessor"].values(): require(recorded.get(ref["path"]) == ref["sha256"], "Predecessor digest missing from manifest")
        require(recorded.get(old_build["inputs_snapshot"]) == old_build["inputs_snapshot_sha256"], "Old input digest omitted")
        required_raw = list(m["predecessor"].values()) + [dict(path=old_build["inputs_snapshot"], sha256=old_build["inputs_snapshot_sha256"]),
            dict(path=old_build["results_journal"], sha256=old_build["results_journal_sha256"]),
            dict(path=old_final["actual_final_record"], sha256=old_final["actual_final_record_sha256"])]
        log_records = list(old_build["results"]) + list(old_build["commands"]) + list(old_final["steps"])
        if old_build.get("artifact_compression"): log_records.append(old_build["artifact_compression"])
        required_raw.extend(dict(path=item["log"], sha256=item["log_sha256"]) for item in log_records)
        failures = [s for s in old_final["steps"] if s["script"] == "build_outer_standard_delivery.py" and s["exit_code"] != 0]
        require(len(failures) == 1 and "--require-empty" in failures[0]["arguments"], "Missing failed fresh-builder exit evidence")
        for ref in required_raw:
            bound(ref)
            require(recorded.get(ref["path"]) == ref["sha256"], "Required historical raw log/record omitted")
        for path, pin in recorded.items():
            logical(path); digest(pin); expected_versions.add((number, path, pin))
            if path not in source_keys:
                require(path in aliases and by_name[aliases[path]]["sha256"] == pin, "Historical raw record has no exact provider")
                provide(path, pin, aliases[path])
        for path, pin in after_sources.items():
            lp = logical(path)
            if lp.is_relative_to(project / "AGStrip") or lp.name in {"AGStrip.lean", "AGStripQuantitative.lean", "lake-manifest.json", "lean-toolchain"}:
                require(recorded.get(path) == pin, "Required generation source omitted from predecessor evidence")
        require(set(m["materials"]) == {"lakefile.toml.before", "final-standard-compile.json", "final-proposal.json", "statement-and-definition-review.json"},
                "Missing recovery installation materials")
        for pair in m["materials"].values():
            require(set(pair) == {"old", "new"}, "Malformed recovery material pair")
            bound(pair["old"]); bound(pair["new"])
            require(pair["old"]["sha256"] == pair["new"]["sha256"], "Preserved material digest differs")
        after_sources, after_integration, after_build = old_inputs["source_sha256"], old_integration, old_build
    require(set(versions) == expected_versions, "Historical version map is missing required rows or adds unbound rows")
    for (_, original, pin), destination in versions.items():
        require(destination in providers.get((original, pin), set()), "Historical member is not a declared provider for the same origin")
    # Independently bind the completed lineage entry to the final controller and
    # accepted build digest, then recompute every byte-bound report field.
    require(state.get("build_record") == lineage_report["entry_status"], "Lineage entry differs from final controller build")
    accepted = record(state["final_acceptance"])
    require(accepted.get("status") == ACCEPTED and accepted.get("theorem_1_3_complete") is True and
            plan.get("acceptance_record") == state["final_acceptance"] == delivery.get("acceptance_record") and
            by_name[aliases[state["final_acceptance"]]]["sha256"] == delivery.get("acceptance_record_sha256"),
            "Lineage acceptance anchor differs")
    require(accepted.get("evidence_sha256", {}).get(state["build_record"]) == lineage_report["entry_status_sha256"],
            "Lineage build digest is not anchored to accepted evidence")
    def lineage_bytes(path, limit):
        require(path in aliases and aliases[path] in lineage_metadata, "Lineage requested an unlisted evidence alias")
        raw = raw_name(aliases[path])
        require(len(raw) <= limit, "Lineage callback byte bound exceeded")
        return raw
    try:
        recomputed = lineage_verifier(lineage_report["entry_status"], lineage_report["entry_status_sha256"], lineage_bytes)
    except Exception as error:
        raise RecoveryInventoryError("Interrupted-build lineage verification failed: " + str(error)) from error
    require(json.dumps(recomputed, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) ==
            json.dumps(lineage_report, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False),
            "Recomputed interrupted-build provenance differs from the full published report")
    summary.update(status="V5_RECOVERY_RAW_CHAIN_AND_INTERRUPTED_BUILD_LINEAGE_VERIFIED_NOT_MATHEMATICAL_ACCEPTANCE",
                   interrupted_build_lineage_verified=True, lineage_resume_links=lineage_report["resume_links"],
                   lineage_required_evidence_count=len(lineage_report["required_evidence"]),
                   resumed_controller_records=len(nodes)-1, metadata_members_checked=len(raw_cache),
                   original_paths_opened=False, mathematical_acceptance_rechecked=False)
    return summary
