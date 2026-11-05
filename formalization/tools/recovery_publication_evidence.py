"""Read-only collection of hash-bound fresh-recovery provenance generations.

No recovery controller is imported or executed. This consumes hash-bound raw
records only, after the caller has independently gated final acceptance.
"""
from pathlib import Path
import tomllib

SCHEMA = "ahlfors-fresh-build-recovery-v1"
REQUEST_SCHEMA = "ahlfors-fresh-build-recovery-request-v1"
MATERIALS = {"lakefile.toml.before", "final-standard-compile.json",
             "final-proposal.json", "statement-and-definition-review.json"}
MANIFEST_KEYS = {"schema", "status", "project", "work", "predecessor", "request", "review",
                 "integration", "old_config", "next_config", "materials", "repairs", "new_build_directory",
                 "predecessor_evidence", "theorem_1_3_complete"}


def collect(inv, state, integration, build, source_hashes, *,
            require, read_json, checked_file, native_path):
    """Collect a linear recovery history without replacing current source aliases.

    All validation remains conditional on the caller's accepted + independent
    three-hash gate. No controller, proof script or older recovery is executed.
    """
    project, work = inv.project, inv.work

    class Shared:
        def __init__(self):
            self.chain, self.providers, self.source_keys = {}, {}, set(source_hashes)
            self.references, self.pending_aliases = {}, []

        def add(self, value, expected, root=None):
            path = checked_file(value, (root,) if root else (project, work))
            old = inv.by_original.get(str(path))
            basis = inv.entries[old.casefold()]["integrity_basis"] if old else "recovery_controller_digest"
            result = inv.evidence(path, expected, "recovery_provenance")
            # Re-reading a historical digest must not relabel it as an accepted
            # mathematical input merely because Inventory.add saw it twice.
            inv.entries[inv.by_original[str(path)].casefold()]["integrity_basis"] = basis
            return result

        def register(self, original, digest, preserved):
            key = str(native_path(original))
            inv.verify(preserved, digest)
            self.providers.setdefault((key, digest), []).append(preserved)

        def remember(self, original, digest, preserved, generation):
            key = str(native_path(original))
            inv.verify(preserved, digest)
            destination = inv.by_original[str(preserved)]
            reference = (generation["number"], key, digest)
            existing = self.references.get(reference)
            # Two declared preserved copies may contain the identical version.
            # Keep the first scoped resolution, while both raw copies remain in
            # the inventory; neither may alter the current-source alias map.
            if existing is not None:
                return
            self.references[reference] = dict(generation=generation["number"],
                recovery_manifest=str(generation["path"]), recovery_manifest_sha256=generation["sha256"],
                original_path=key, sha256=digest, archive_path=destination)

        def historical(self, original, digest, generation):
            key = str(native_path(original))
            if key in self.source_keys:
                choices = self.providers.get((key, digest))
                require(choices, "Missing preserved historical source version")
                path = choices[0]
                self.remember(key, digest, path, generation)
                return path
            path = self.add(original, digest)
            self.remember(key, digest, path, generation)
            return path

        def alias(self, original, preserved, digest, generation):
            self.remember(original, digest, preserved, generation)
            self.pending_aliases.append((str(native_path(original)), digest, preserved))

        def finish_aliases(self):
            grouped = {}
            for original, digest, preserved in self.pending_aliases:
                grouped.setdefault(original, []).append((digest, preserved))
            for original, candidates in sorted(grouped.items()):
                # A path used for different historical bytes is deliberately
                # absent from the unversioned alias map unless it is already
                # the current source path. The scoped reference map is complete.
                if original in inv.by_original or len({h for h, _ in candidates}) != 1:
                    continue
                digest, preserved = candidates[0]
                destination = inv.by_original[str(preserved)]
                inv.by_original[original] = destination
                entry = inv.entries[destination.casefold()]
                if original not in entry["original_paths"]: entry["original_paths"].append(original)
                if "historical_reference_mapped_to_preserved_bytes" not in entry["roles"]:
                    entry["roles"].append("historical_reference_mapped_to_preserved_bytes")

    shared = Shared()
    current_mapping = {key: inv.by_original[key] for key in source_hashes}
    for key, digest in source_hashes.items():
        row = inv.entries[inv.by_original[key].casefold()]
        shared.register(key, digest, Path(row["source_path"]))

    def controller(path):
        require(path.name == "status.json" and path.parent.parent == work and
                path.parent.name.startswith("outer-final-acceptance-continuation-"),
                "Unexpected recovery controller path")

    top_rows = [entry for entry in inv.entries.values() if "final_controller" in entry["roles"]]
    require(len(top_rows) == 1, "Missing unique final controller inventory entry")
    top_path = Path(top_rows[0]["source_path"])
    nodes = [dict(path=top_path, sha256=top_rows[0]["sha256"], state=state)]
    visited = {str(top_path)}
    cursor = state
    for _ in range(64):
        linked = ("resumed_from" in cursor, "resumed_from_sha256" in cursor)
        require(linked[0] == linked[1], "Incomplete resumed-controller hash reference")
        if not linked[0]: break
        lexical = str(native_path(cursor["resumed_from"]))
        require(lexical not in visited, "Cycle in resumed-controller provenance")
        path = shared.add(cursor["resumed_from"], cursor["resumed_from_sha256"], work)
        controller(path)
        require(str(path) not in visited, "Cycle in resumed-controller provenance")
        visited.add(str(path))
        prior = read_json(path)
        shared.chain[str(path)] = (cursor["resumed_from_sha256"], prior)
        nodes.append(dict(path=path, sha256=cursor["resumed_from_sha256"], state=prior))
        cursor = prior
    else:
        require(False, "Resumed-controller chain exceeds the reviewed depth")

    generations, seen_generations, no_recovery_seen = [], set(), False
    for node in nodes:
        fields = ("fresh_build_recovery" in node["state"], "fresh_build_recovery_sha256" in node["state"])
        require(fields[0] == fields[1], "Incomplete recovery provenance in controller")
        if not fields[0]:
            if generations and "boundary" not in generations[-1]: generations[-1]["boundary"] = node
            no_recovery_seen = True
            continue
        require(not no_recovery_seen, "Final controller dropped recovery provenance or chain returned to an older generation")
        path = checked_file(node["state"]["fresh_build_recovery"], (project / "logs",))
        digest = node["state"]["fresh_build_recovery_sha256"]
        key = (str(path), digest)
        if generations and generations[-1]["key"] == key:
            generations[-1]["nodes"].append(node)
            continue
        require(key not in seen_generations, "Recovery generation cycle or backward jump")
        seen_generations.add(key)
        if generations: generations[-1]["boundary"] = node
        shared.add(path, digest, project / "logs")
        recovery = read_json(path)
        require(set(recovery) == MANIFEST_KEYS and recovery.get("schema") == SCHEMA,
                "Unreviewed recovery manifest schema")
        root = path.parent
        require(path.name == "fresh-build-recovery.json" and root.parent == project / "logs" and
                root.name.startswith("quantitative-standard-integration-"), "Unexpected recovery manifest path")
        generations.append(dict(key=key, path=path, sha256=digest, root=root, recovery=recovery, nodes=[node]))
    if not generations: return None
    require(len(generations) <= 16, "Recovery generation count exceeds the reviewed bound")
    fresh_directories = set()
    for index, generation in enumerate(generations):
        generation["number"] = len(generations) - index
        recovery, root = generation["recovery"], generation["root"]
        boundary = generation.get("boundary")
        require(boundary is not None and recovery["predecessor"]["final_status"] ==
                {"path": str(boundary["path"]), "sha256": boundary["sha256"]},
                "Fresh recovery predecessor is not the exact resume boundary")
        fresh_metadata_path = Path(recovery["new_build_directory"])
        require(fresh_metadata_path not in fresh_directories, "Recovery generations reused a build directory")
        fresh_directories.add(fresh_metadata_path)
        for node in generation["nodes"]:
            if "integration_record" in node["state"]:
                require(node["state"]["integration_record"] == recovery["integration"]["path"],
                        "Ordinary resume changed its recovered integration")
        previous = {}
        for name, ref in recovery["predecessor"].items():
            require(set(ref) == {"path", "sha256"}, "Malformed recovery predecessor reference")
            path = shared.add(ref["path"], ref["sha256"], work if name == "final_status" else project / "logs")
            previous[name] = read_json(path)
        generation["previous"] = previous
        if generation["number"] == 1:
            require(Path(previous["integration"]["build_directory"]) not in fresh_directories,
                    "Recovery generations reused the original failed build directory")
        before_build = previous["build_status"]
        before_snapshot = shared.add(before_build["inputs_snapshot"], before_build["inputs_snapshot_sha256"], project / "logs")
        before_inputs = read_json(before_snapshot)["source_sha256"]
        require(before_inputs == before_build["source_sha256"], "Failed source snapshots disagree")
        shared.source_keys.update(before_inputs)
        # Pre-register all declared preserved versions before collecting older
        # evidence. E.g. generation 1's old module 62 is generation 2's backup.
        for name, filename in (("old_config", "lakefile.toml.failed-build"), ("next_config", "lakefile.toml.next")):
            ref = recovery[name]
            require(set(ref) == {"path", "sha256"}, "Malformed configuration reference")
            path = shared.add(ref["path"], ref["sha256"], root)
            require(path == root / filename, "Unexpected preserved recovery configuration path")
            shared.register(str(project / "lakefile.toml"), ref["sha256"], path)
            shared.remember(str(project / "lakefile.toml"), ref["sha256"], path, generation)
        for repair_index, repair in enumerate(recovery["repairs"]):
            source = checked_file(repair["source"], (project / "AGStrip",))
            require(repair["source"] == str(source), "Recovery source key must be canonical")
            ref = repair["before_backup"]
            require(set(ref) == {"path", "sha256"} and ref["sha256"] == repair["before_sha256"], "Invalid preserved pre-repair source")
            path = shared.add(ref["path"], ref["sha256"], root)
            require(path == root / ("repair-%03d.before.lean" % repair_index), "Unexpected preserved repair backup path")
            shared.register(str(source), ref["sha256"], path)
            shared.remember(str(source), ref["sha256"], path, generation)

    results = []
    terminal, output_integration, output_build, output_sources = state, integration, build, source_hashes
    for generation in generations:
        result = _collect_generation(inv, terminal, output_integration, output_build, output_sources,
            require=require, read_json=read_json, checked_file=checked_file, native_path=native_path,
            shared=shared, generation=generation)
        result["generation"] = generation["number"]
        results.append(result)
        previous = generation["previous"]
        terminal, output_integration, output_build = previous["final_status"], previous["integration"], previous["build_status"]
        output_sources = output_build["source_sha256"]
    shared.finish_aliases()
    require(all(inv.by_original[key] == destination for key, destination in current_mapping.items()),
            "Historical evidence overwrote a current accepted source mapping")
    return dict(schema="ahlfors-publication-recovery-chain-v1", generation_count=len(generations),
        generations=list(reversed(results)), manifest=str(generations[0]["path"]),
        manifest_sha256=generations[0]["sha256"], preserved_repair_count=sum(r["preserved_repair_count"] for r in results),
        resumed_controller_records=len(shared.chain), recovery_status="PREPARED_FRESH_BUILD_RECOVERY_NOT_BUILT",
        theorem_acceptance_status=state["status"], all_raw_records_preserved=True,
        historical_reference_versions=[shared.references[key] for key in sorted(shared.references)],
        compiled_artifacts_included=False,
        limitations=["At most 16 linear fresh generations and 64 resumed-controller links are supported.",
                     "Historical references require generation, original path and SHA-256; the current alias map is not overwritten.",
                     "Historical prepared/failed statuses are preserved, not converted into mathematical acceptance."])


def _collect_generation(inv, state, integration, build, source_hashes, *,
            require, read_json, checked_file, native_path, shared, generation):
    project, work = inv.project, inv.work

    def add(value, expected, root=None):
        return shared.add(value, expected, root)

    def reference(value, root):
        require(isinstance(value, dict) and set(value) == {"path", "sha256"},
                "Malformed recovery file reference")
        return add(value["path"], value["sha256"], root)

    def alias(original, preserved, expected):
        shared.alias(original, preserved, expected, generation)

    def controller(path):
        require(path.name == "status.json" and path.parent.parent == work and
                path.parent.name.startswith("outer-final-acceptance-continuation-"),
                "Unexpected recovery controller path")

    def build_directory(value):
        # Metadata only: do not enter or inspect the actual .lake tree.
        path = Path(value)
        require(path.is_absolute() and ".." not in path.parts and
                all(":" not in part for part in path.parts[1:]) and
                path.parent == project / ".lake" and
                path.name.startswith("build-quantitative-"),
                "Recovery build directory escaped its fixed metadata root")
        return path

    recovery_path, recovery_sha = generation["path"], generation["sha256"]
    chain = shared.chain

    root = recovery_path.parent
    require(recovery_path.name == "fresh-build-recovery.json" and root.parent == project / "logs" and
            root.name.startswith("quantitative-standard-integration-"), "Unexpected recovery manifest path")
    add(recovery_path, recovery_sha, root)
    recovery = read_json(recovery_path)
    require(set(recovery) == {"schema", "status", "project", "work", "predecessor", "request", "review",
            "integration", "old_config", "next_config", "materials", "repairs", "new_build_directory",
            "predecessor_evidence", "theorem_1_3_complete"}, "Unreviewed recovery manifest schema")
    require(recovery["schema"] == SCHEMA and
            recovery["status"] == "PREPARED_FRESH_BUILD_RECOVERY_NOT_BUILT" and
            recovery["theorem_1_3_complete"] is False,
            "Recovery preparation must not masquerade as theorem acceptance")
    require(recovery["project"] == str(project) and recovery["work"] == str(work),
            "Recovery belongs to different project/work roots")
    require(set(recovery["predecessor"]) == {"final_status", "build_status", "integration"},
            "Incomplete recovery predecessor references")
    previous = {}
    required = {}
    for name, ref in recovery["predecessor"].items():
        path = reference(ref, work if name == "final_status" else project / "logs")
        required[str(path)] = ref["sha256"]
        previous[name] = (path, read_json(path))
    old_final_path, old_final = previous["final_status"]
    old_build_path, old_build = previous["build_status"]
    old_integration_path, old_integration = previous["integration"]
    controller(old_final_path)
    require(str(old_final_path) in chain and
            chain[str(old_final_path)][0] == recovery["predecessor"]["final_status"]["sha256"],
            "Recovery predecessor is not anchored in the final controller resume chain")
    require(old_final.get("status") == old_build.get("status") == "FAILED" and
            old_final.get("theorem_1_3_complete") is False and not old_final.get("active_process") and
            old_build.get("theorem_1_3_complete") is False and old_build.get("final_acceptance_complete") is False,
            "Recovery predecessor was not a failed incomplete build")
    require(old_build_path.name == "status.json" and old_build_path.parent.parent == project / "logs" and
            old_build_path.parent.name.startswith("quantitative-lake-reproduction-") and
            old_integration_path.name == "integration.json" and old_integration_path.parent.parent == project / "logs" and
            old_integration_path.parent.name.startswith("quantitative-standard-integration-"),
            "Unexpected failed build/installation record path")
    require(checked_file(old_final["integration_record"], (project / "logs",)) == old_integration_path,
            "Failed controller and failed integration disagree")
    installed_path = reference(recovery["integration"], root)
    require(installed_path == root / "integration.json" and
            installed_path == checked_file(state["integration_record"], (project / "logs",)),
            "Final acceptance uses a different recovered integration")
    require(read_json(installed_path) == integration and
            dict(integration, build_directory=old_integration["build_directory"],
                 lakefile_sha256=old_integration["lakefile_sha256"]) == old_integration,
            "Recovered integration changed beyond build directory/config digest")
    fresh = build_directory(recovery["new_build_directory"])
    require(fresh == build_directory(build["build_directory"]) == build_directory(integration["build_directory"]) and
            fresh != build_directory(old_integration["build_directory"]) and
            build_directory(old_build["build_directory"]) == build_directory(old_integration["build_directory"]),
            "Recovery build directory binding is inconsistent")

    old_config_path = reference(recovery["old_config"], root)
    next_config_path = reference(recovery["next_config"], root)
    require(old_config_path == root / "lakefile.toml.failed-build" and next_config_path == root / "lakefile.toml.next",
            "Unexpected preserved recovery configuration path")
    require(recovery["old_config"]["sha256"] == old_integration["lakefile_sha256"] and
            recovery["next_config"]["sha256"] == integration["lakefile_sha256"] == source_hashes[str(project / "lakefile.toml")],
            "Recovery configurations are not bound to the accepted build")
    old_toml = tomllib.loads(old_config_path.read_text(encoding="utf-8"))
    next_toml = tomllib.loads(next_config_path.read_text(encoding="utf-8"))
    require(old_toml.pop("buildDir") == build_directory(old_integration["build_directory"]).relative_to(project).as_posix() and
            next_toml.pop("buildDir") == fresh.relative_to(project).as_posix() and old_toml == next_toml,
            "Recovery changed compiler resources or configuration beyond buildDir")
    require(set(recovery["materials"]) == MATERIALS, "Incomplete preserved installation materials")
    for name, pair in recovery["materials"].items():
        require(set(pair) == {"old", "new"}, "Malformed installation material reference")
        old = reference(pair["old"], old_integration_path.parent)
        new = reference(pair["new"], root)
        require(old == old_integration_path.parent / name and new == root / name and
                pair["old"]["sha256"] == pair["new"]["sha256"], "Recovery installation material changed")
        required[str(old)] = pair["old"]["sha256"]
        required[str(new)] = pair["new"]["sha256"]
    require(recovery["materials"]["final-standard-compile.json"]["new"]["sha256"] == integration["final_record_sha256"] and
            recovery["materials"]["final-proposal.json"]["new"]["sha256"] == integration["final_proposal_sha256"],
            "Recovery final compilation/proposal copies are unanchored")
    for ref in (recovery["integration"], recovery["request"], recovery["review"], recovery["old_config"], recovery["next_config"]):
        required[str(checked_file(ref["path"], (root,)))] = ref["sha256"]

    old_inputs_path = add(old_build["inputs_snapshot"], old_build["inputs_snapshot_sha256"], old_build_path.parent)
    old_snapshot = read_json(old_inputs_path)
    old_inputs = old_snapshot["source_sha256"]
    require(old_inputs == old_build["source_sha256"] and old_build.get("started_from_empty_project_build") is True,
            "Failed build source inventory is not its empty-build snapshot")
    after_snapshot_path = add(build["inputs_snapshot"], build["inputs_snapshot_sha256"], project / "logs")
    after_snapshot = read_json(after_snapshot_path)
    require(after_snapshot["source_sha256"] == source_hashes and
            isinstance(old_snapshot.get("module_resources"), dict) and old_snapshot["module_resources"] and
            old_snapshot["module_resources"] == after_snapshot.get("module_resources"),
            "Generation module resources or output input snapshot changed")
    required[str(old_inputs_path)] = old_build["inputs_snapshot_sha256"]
    journal = add(old_build["results_journal"], old_build["results_journal_sha256"], old_build_path.parent)
    required[str(journal)] = old_build["results_journal_sha256"]
    # jsonl bytes remain unchanged; compare parsed entries with the status.
    import json
    entries = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
    require(entries == old_build["results"] and old_build.get("error") and
            sum(e["exit_code"] != 0 for e in entries) == old_build["failed_modules"] > 0 and
            sum(e["exit_code"] == 0 for e in entries) == old_build["completed_modules"],
            "Failed build journal/counts do not establish a failed build")
    for entry in entries + old_build.get("commands", []):
        path = add(entry["log"], entry["log_sha256"], old_build_path.parent)
        required[str(path)] = entry["log_sha256"]
    if old_build.get("artifact_compression"):
        entry = old_build["artifact_compression"]
        path = add(entry["log"], entry["log_sha256"], old_build_path.parent)
        required[str(path)] = entry["log_sha256"]
    steps = old_final["steps"]
    failures = [s for s in steps if s["script"] == "build_outer_standard_delivery.py" and s["exit_code"] != 0]
    require(len(failures) == 1, "Missing unique failed predecessor builder exit")
    arguments = failures[0]["arguments"]
    require("--require-empty" in arguments and "--project" in arguments and
            Path(arguments[arguments.index("--project") + 1]) == project, "Unrelated failed builder arguments")
    for entry in steps:
        path = add(entry["log"], entry["log_sha256"], old_final_path.parent)
        required[str(path)] = entry["log_sha256"]
    actual = add(old_final["actual_final_record"], old_final["actual_final_record_sha256"], work)
    require(actual == checked_file(integration["final_record"], (work,)) and
            old_final["actual_final_record_sha256"] == integration["final_record_sha256"], "Recovery changed the actual final compilation")
    required[str(actual)] = old_final["actual_final_record_sha256"]

    request_path = reference(recovery["request"], root)
    review_path = reference(recovery["review"], root)
    require(request_path == root / "request.json" and review_path == root / "review.txt", "Unexpected recovery request/review path")
    request = read_json(request_path)
    require(set(request) == {"schema", "predecessor", "repairs", "review"} and
            request["schema"] == REQUEST_SCHEMA and request["predecessor"] == recovery["predecessor"],
            "Recovery request differs from its preserved manifest")
    require(isinstance(request["review"], dict) and set(request["review"]) == {"path", "sha256"} and
            request["review"]["sha256"] == recovery["review"]["sha256"] and len(review_path.read_bytes().strip()) > 20,
            "Missing hash-bound concrete recovery review")
    alias(request["review"]["path"], review_path, request["review"]["sha256"])
    repairs = recovery["repairs"]
    require(isinstance(repairs, list) and len(repairs) == len(request["repairs"]), "Inconsistent recovery repairs")
    expected_inputs = dict(old_inputs)
    seen = set()
    for index, (repair, original) in enumerate(zip(repairs, request["repairs"])):
        require(set(repair) == set(original) == {"module", "source", "before_sha256", "before_backup", "after_sha256"},
                "Malformed recovery repair")
        require({k: v for k, v in repair.items() if k != "before_backup"} ==
                {k: v for k, v in original.items() if k != "before_backup"}, "Request and recovery repair differ")
        source = checked_file(repair["source"], (project / "AGStrip",))
        key = str(source)
        require(repair["source"] == key and key not in seen and source.suffix == ".lean" and
                repair["module"] == ".".join(source.relative_to(project).with_suffix("").parts), "Invalid/duplicate recovery source")
        seen.add(key)
        require(old_inputs.get(key) == repair["before_sha256"] != repair["after_sha256"] and
                source_hashes.get(key) == repair["after_sha256"], "Recovery repair is not bound to old and accepted sources")
        backup = reference(repair["before_backup"], root)
        require(backup == root / ("repair-%03d.before.lean" % index) and
                repair["before_backup"]["sha256"] == repair["before_sha256"] and
                set(original["before_backup"]) == {"path", "sha256"} and
                original["before_backup"]["sha256"] == repair["before_sha256"], "Invalid preserved pre-repair source")
        alias(original["before_backup"]["path"], backup, repair["before_sha256"])
        expected_inputs[key] = repair["after_sha256"]
    require(old_inputs.get(str(project / "lakefile.toml")) == old_integration["lakefile_sha256"], "Old configuration lacks input binding")
    expected_inputs[str(project / "lakefile.toml")] = integration["lakefile_sha256"]
    require(expected_inputs == source_hashes, "Generation output inputs differ from the explicit recovery repairs")
    # These exact current files were hashed by the recovery preparer. They
    # cannot be replaced by arbitrary extra files in the evidence mapping.
    for key, value in source_hashes.items():
        if Path(key).is_relative_to(project / "AGStrip") or Path(key).name in {
                "AGStrip.lean", "AGStripQuantitative.lean", "lake-manifest.json", "lean-toolchain"}:
            required[key] = value
    recorded = recovery["predecessor_evidence"]
    require(isinstance(recorded, dict) and recorded and str(project / "lakefile.toml") not in recorded,
            "Invalid recovery predecessor evidence inventory")
    require(all(recorded.get(key) == value for key, value in required.items()),
            "Recovery predecessor evidence omitted or changed a required input")
    for path, value in recorded.items():
        shared.historical(path, value, generation)
    return dict(schema=SCHEMA, manifest=str(recovery_path), manifest_sha256=recovery_sha,
                preserved_repair_count=len(repairs),
                recovery_status=recovery["status"], terminal_controller_status=state["status"],
                old_failed_build=str(old_build_path), all_raw_records_preserved=True,
                compiled_artifacts_included=False,
                limitations=["Historical references are resolved by generation, original path and exact digest.",
                             "Historical external review/backup references map to preserved bytes; originals are not opened.",
                             "The prepared recovery status is historical and is not itself mathematical acceptance."])
