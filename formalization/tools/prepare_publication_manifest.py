"""Prepare an inventory after independent final acceptance; never package or upload.

No Lean process is started. No proof, accepted record, cache, or remote is changed.
The resulting inventory is not a new mathematical acceptance decision.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tomllib
from recovery_publication_evidence import collect as collect_recovery_evidence
from publication_dependency_closure import validate_and_collect as collect_dependency_closure
from publication_interrupted_build_evidence import collect as collect_interrupted_build_evidence

ACCEPTED = "ORIGINAL_THEOREM_1_3_FORMALIZATION_ACCEPTED"
BUILD_OK = "LAKE_BUILD_AND_ROOT_AUDITS_PASSED_EXTRA_CHECKER_PENDING"
INSTALLED = "INSTALLED_SOURCES_PENDING_CLEAN_BUILD_AND_ACCEPTANCE"
TARGET = "blochConstant < ENNReal.ofReal (AG - (13 : ℝ) / 10^10)"
PREFIXES = ("AGStripModuleCore.", "AGStripModuleNodes.",
            "AGStripModuleAnalytic.", "AGStripModuleLeaves.")
OWN_ROOTS = {"AGStrip", "AGStripQuantitative"}
OWN_DIRS = {"AGStrip", *(p[:-1] for p in PREFIXES)}
HERE = Path(__file__).resolve().parent
HEX = re.compile(r"[0-9a-f]{64}\Z")
MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")


class PreparationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PreparationError(message)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        value = json.load(stream, object_pairs_hook=strict_object)
    require(isinstance(value, dict), f"Expected JSON object: {path}")
    return value


def native_path(value):
    require(isinstance(value, (str, Path)), "Expected a native absolute path")
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts,
            f"Relative path or path traversal is not permitted: {path}")
    require(not any(part.lower() in {".lake", ".git"} for part in path.parts),
            f"Cache/repository metadata path is not a publication input: {path}")
    # On Windows reject alternate data streams after the drive component.
    require(all(":" not in part for part in path.parts[1:]),
            f"Alternate data stream is not permitted: {path}")
    return path


def inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def checked_file(value, roots):
    path = native_path(value).resolve(strict=True)
    require(any(inside(path, root) for root in roots), f"Path escapes allowed roots: {path}")
    require(path.is_file(), f"Missing regular file: {path}")
    require(not any(part.lower() in {".lake", ".git"} for part in path.parts),
            f"Resolved input points into a cache: {path}")
    return path


def portable_name(value):
    require(isinstance(value, str) and "\\" not in value and ":" not in value,
            f"Nonportable archive path: {value}")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.parts and
            all(part not in {".", "..", ".lake", ".git"} for part in path.parts),
            f"Unsafe archive path: {value}")
    require(path.as_posix() == value, f"Noncanonical archive path: {value}")
    return value


class Inventory:
    def __init__(self, project, work):
        self.project, self.work = project, work
        self.entries = {}
        self.by_original = {}
        self.stamps = {}
        self.external = []

    def verify(self, path, expected=None):
        if expected is not None:
            require(isinstance(expected, str) and HEX.fullmatch(expected),
                    f"Invalid SHA-256 for {path}")
        stat = path.stat()
        stamp = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if path in self.stamps:
            old_stamp, actual = self.stamps[path]
            require(old_stamp == stamp, f"Input changed during preparation: {path}")
        else:
            actual = digest(path)
            after = path.stat()
            require(stamp == (after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                    f"Input changed while hashing: {path}")
            self.stamps[path] = (stamp, actual)
        require(expected is None or actual == expected, f"SHA-256 mismatch: {path}")
        return actual, stat.st_size

    def add(self, value, archive, role, expected=None):
        path = checked_file(value, (self.project, self.work, HERE))
        require(not inside(path, self.work / "module-replay-stage"),
                "Read the installed closure, not historical staging")
        archive = portable_name(archive)
        actual, size = self.verify(path, expected)
        key = archive.casefold()
        if key in self.entries:
            entry = self.entries[key]
            require(entry["archive_path"] == archive and entry["sha256"] == actual,
                    f"Conflicting portable destination: {archive}")
            if str(path) not in entry["original_paths"]:
                entry["original_paths"].append(str(path))
            if role not in entry["roles"]:
                entry["roles"].append(role)
        else:
            entry = dict(source_path=str(path), original_paths=[str(path)],
                         archive_path=archive, sha256=actual, size_bytes=size,
                         roles=[role], integrity_basis=("accepted_digest" if expected else
                                                       "publication_capture"))
            self.entries[key] = entry
        if expected is not None:
            entry["integrity_basis"] = "accepted_digest"
        self.by_original[str(path)] = archive
        return path

    def project_file(self, relative, role, expected=None):
        portable_name(relative)
        path = checked_file(self.project / relative, (self.project,))
        return self.add(path, "AGStrip/" + relative, role, expected)

    def evidence(self, value, expected=None, role="raw_evidence"):
        roots = ((self.project, self.work, HERE) if role == "prior_independent_verification_report"
                 else (self.project, self.work))
        path = checked_file(value, roots)
        if inside(path, self.project):
            archive = "AGStrip/" + path.relative_to(self.project).as_posix()
        elif inside(path, self.work):
            archive = "evidence/work/" + path.relative_to(self.work).as_posix()
        else:
            archive = "evidence/independent/" + path.name
        return self.add(path, archive, role, expected)

    def ensure_stable(self):
        for path, (stamp, _) in self.stamps.items():
            stat = path.stat()
            require(stamp == (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns),
                    f"Input changed before inventory completion: {path}")


def prepare(final_status, project, independent_report, toolchain_root=None):
    project = native_path(project).resolve(strict=True)
    require(project.is_dir(), "Project directory is missing")
    work = (project.parent.parent / "work").resolve(strict=True)
    status_path = checked_file(final_status, (work,))
    inv = Inventory(project, work)
    inv.evidence(status_path, role="final_controller")
    state = read_json(status_path)
    require(state.get("status") == ACCEPTED and state.get("theorem_1_3_complete") is True,
            "Final controller is pending, partial, or not accepted")
    manifest_path = checked_file(project / "DELIVERY-MANIFEST.json", (project,))
    inv.evidence(manifest_path, role="accepted_delivery_manifest")
    manifest = read_json(manifest_path)
    require(manifest.get("status") == ACCEPTED, "Partial delivery manifest")
    require(manifest.get("target") == TARGET, "Delivery target changed")
    acceptance_path = checked_file(state["final_acceptance"], (project,))
    require(checked_file(manifest["acceptance_record"], (project,)) == acceptance_path,
            "Controller and delivery acceptance records differ")
    inv.evidence(acceptance_path, manifest["acceptance_record_sha256"])
    acceptance = read_json(acceptance_path)
    require(acceptance.get("status") == ACCEPTED and
            acceptance.get("theorem_1_3_complete") is True and
            acceptance.get("target") == TARGET and
            acceptance.get("complete_actual_rectangles") == 1068 and
            acceptance.get("clean_build_complete") is True and
            acceptance.get("semantic_review_complete") is True,
            "Final acceptance fields are incomplete or inconsistent")
    evidence = acceptance["evidence_sha256"]
    require(isinstance(evidence, dict) and evidence, "Missing acceptance evidence hashes")
    for path, sha in evidence.items():
        inv.evidence(path, sha)

    records = {}
    for key in ("integration_record", "build_record", "semantic_review", "extra_checker_record"):
        path = checked_file(state[key], (project,))
        require(str(path) in evidence, f"Unanchored acceptance record: {key}")
        inv.evidence(path, evidence[str(path)])
        records[key] = read_json(path)
    integration = records["integration_record"]
    build = records["build_record"]
    semantic = records["semantic_review"]
    extra = records["extra_checker_record"]
    require(integration.get("status") == INSTALLED, "Wrong installed-source record")
    require(build.get("status") == BUILD_OK and
            build.get("started_from_empty_project_build") is True,
            "Missing successful clean build")
    # Build artifacts are deliberately not opened: their independent audit is a prerequisite.
    require(Path(build["build_directory"]).resolve() ==
            Path(integration["build_directory"]).resolve(), "Build directory mismatch")
    require(semantic.get("status") == "FINAL_UNCONDITIONAL_STATEMENT_AND_DEFINITIONS_REVIEWED"
            and semantic.get("target") == TARGET
            and semantic.get("has_no_added_hypotheses") is True
            and semantic.get("definitions_agree_with_paper") is True,
            "Missing exact unconditional type/definition review")
    require(extra.get("status") in {"FRESH_CHECKER_PASSED", "NOT_RUN_UNAVAILABLE",
                                    "NOT_COMPLETED_RESOURCE_LIMIT"}, "Unaccepted extra-checker outcome")
    require(extra["status"] == acceptance["extra_checker_status"] == manifest["extra_checker_status"],
            "Extra-checker statuses disagree")
    require(extra["build_record_sha256"] == evidence[str(checked_file(state["build_record"], (project,)))],
            "Extra checker belongs to another build")
    if extra["status"] == "FRESH_CHECKER_PASSED":
        require(extra.get("exit_code") == 0 and "--fresh" in extra.get("command", [])
                and extra.get("module") == "AGStripQuantitative", "Missing fresh-checker success fields")
    else:
        require(extra.get("ordinary_kernel_build_passed") is True and
                isinstance(extra.get("reason"), str) and len(extra["reason"].strip()) > 20,
                "Missing honest extra-checker disposition")

    report_path = checked_file(independent_report, (HERE, project, work))
    inv.evidence(report_path, role="prior_independent_verification_report")
    report = read_json(report_path)
    require(report.get("independent_readonly_evidence_check") == "PASSED" and
            checked_file(report["acceptance_record"], (project,)) == acceptance_path and
            report.get("complete_rectangles") == 1068 and
            report.get("extra_checker_actual_status") == extra["status"],
            "A matching prior independent evidence-check report is required")
    require(report.get("acceptance_record_sha256") == digest(acceptance_path) and
            report.get("delivery_manifest_sha256") == digest(manifest_path),
            "Independent verification report is stale or lacks exact record hashes")
    verifier = HERE.parent / "verify-ahlfors-final-evidence-readonly.py"
    require(verifier.is_file() and report.get("verification_script_sha256") == digest(verifier),
            "Independent verification script differs from the saved PASS report")

    source_hashes = build["source_sha256"]
    require(source_hashes and source_hashes == manifest["source_sha256"],
            "Build and delivery source inventories disagree")
    inputs_path = inv.evidence(build["inputs_snapshot"], build["inputs_snapshot_sha256"])
    inputs = read_json(inputs_path)
    require(inputs["source_sha256"] == source_hashes, "Build input snapshot differs")
    inv.evidence(build["results_journal"], build["results_journal_sha256"])
    result_modules = {}
    for item in build["results"]:
        name = item["module"]
        require(name not in result_modules and MODULE.fullmatch(name), "Duplicate/invalid build module")
        require(item.get("exit_code") == 0, f"Failed build module: {name}")
        inv.evidence(item["log"], item["log_sha256"], "accepted_module_log")
        result_modules[name] = item
    require(set(inputs["module_resources"]) == set(result_modules), "Incomplete build input graph")
    require(manifest["module_count"] == report["clean_build_modules"] == len(result_modules),
            "Module counts differ from independent verification")

    own_modules = {}
    script_map = {
        work / "build_outer_standard_delivery.py": "scripts/build-quantitative.py",
        work / "outer_delivery_build_support.py": "scripts/outer_delivery_build_support.py",
    }
    for value, sha in source_hashes.items():
        path = checked_file(value, (project, work))
        if inside(path, project):
            relative = path.relative_to(project).as_posix()
            if path.suffix == ".lean":
                parts = path.relative_to(project).with_suffix("").parts
                require((len(parts) == 1 and parts[0] in OWN_ROOTS) or
                        (len(parts) > 1 and parts[0] in OWN_DIRS),
                        f"Unexpected own-source path: {path}")
                module = ".".join(parts)
                require(MODULE.fullmatch(module) and module not in own_modules,
                        "Invalid or duplicate source module")
                own_modules[module] = (path, sha)
            else:
                require(relative in {"lakefile.toml", "lake-manifest.json", "lean-toolchain",
                                     *script_map.values()}, f"Unexpected build input: {path}")
            inv.project_file(relative, "accepted_build_input", sha)
        else:
            require(path in script_map, f"Unpermitted external build source: {path}")
            relative = script_map[path]
            inv.add(path, "AGStrip/" + relative, "accepted_build_script", sha)
            inv.project_file(relative, "installed_build_script", sha)
    for relative in ("lakefile.toml", "lake-manifest.json", "lean-toolchain", *script_map.values()):
        entry = inv.entries.get(("AGStrip/" + relative).casefold())
        require(entry is not None and entry["integrity_basis"] == "accepted_digest",
                f"Required build configuration/script lacks accepted source digest: {relative}")
    require(set(own_modules) == set(result_modules), "Build results do not cover exactly the delivered Lean sources")
    require(OWN_ROOTS | {"AGStripModuleLeaves.BudgetedFinal"} <= own_modules.keys(),
            "Missing final root/module")
    installed = integration["modules"]
    require(isinstance(installed, dict) and installed and
            set(installed) == {name for name in own_modules if name.startswith(PREFIXES)},
            "Final integration and quantitative source closure differ")
    require(integration["source_count"] == len(installed), "Integration source count mismatch")
    for name, item in installed.items():
        require(MODULE.fullmatch(name), "Invalid integration module")
        expected_path = project / (name.replace(".", "/") + ".lean")
        path = checked_file(item["delivered_source"], (project,))
        require(path == expected_path.resolve() and own_modules[name] == (path, item["sha256"]),
                f"Installed source mismatch: {name}")
    for relative, key in (("AGStripQuantitative.lean", "root_source_sha256"),
                          ("lakefile.toml", "lakefile_sha256"),
                          ("scripts/build-quantitative.py", "build_script_sha256"),
                          ("scripts/outer_delivery_build_support.py", "build_support_sha256")):
        inv.project_file(relative, "accepted_installation_input", integration[key])
    config = tomllib.loads((project / "lakefile.toml").read_text(encoding="utf-8"))
    require(set(config["defaultTargets"]) == OWN_ROOTS and
            set(manifest["default_targets"]) == OWN_ROOTS, "Wrong default build roots")

    commands = {}
    for command in build["commands"]:
        path = inv.evidence(command["log"], command["log_sha256"], "accepted_build_command_log")
        commands[path.stem] = command
    for key in ("default-lake-build", "original-axiom-audit", "quantitative-axiom-and-type-audit"):
        require(key in commands and commands[key]["exit_code"] == 0, f"Missing successful {key}")
    proof_path = checked_file(integration["final_record"], (work,))
    require(evidence.get(str(proof_path)) == integration["final_record_sha256"],
            "Final module compilation record is not anchored")
    inv.evidence(proof_path, integration["final_record_sha256"])
    integration_dir = Path(state["integration_record"]).parent
    inv.evidence(integration_dir / "final-standard-compile.json", integration["final_record_sha256"])
    inv.evidence(integration_dir / "final-proposal.json", integration["final_proposal_sha256"])
    inv.evidence(state["final_report"], manifest["final_report_sha256"], "accepted_final_report")

    # Map reviewed development-source paths to accepted installed bytes without
    # traversing or reading the historical staging tree.
    staging = work / "module-replay-stage"
    for value, sha in semantic["reviewed_sources"].items():
        lexical = native_path(value)
        if inside(lexical, staging):
            relative = lexical.relative_to(staging)
            require(relative.suffix == ".lean", "Only reviewed Lean sources can map from staging")
            module = ".".join(relative.with_suffix("").parts)
            require(module in installed and installed[module]["sha256"] == sha,
                    "Reviewed staging source has no matching installed proof")
            entry = inv.entries[("AGStrip/" + relative.as_posix()).casefold()]
            entry["original_paths"].append(str(lexical))
            inv.by_original[str(lexical)] = entry["archive_path"]
        else:
            inv.evidence(value, sha, "accepted_semantic_evidence")

    for value, sha in extra["evidence_files"].items():
        lexical = native_path(value)
        resolved = lexical.resolve(strict=True)
        if inside(resolved, project) or inside(resolved, work):
            inv.evidence(value, sha, "accepted_extra_checker_evidence")
        else:
            require(toolchain_root is not None, "Supply --toolchain-root for external checker evidence")
            root = native_path(toolchain_root).resolve(strict=True)
            path = checked_file(value, (root,))
            relative = path.relative_to(root).as_posix()
            require(relative in {"bin/leanchecker", "bin/leanchecker.exe", "src/lean/LeanChecker.lean"},
                    "Unexpected external checker evidence path")
            actual, size = inv.verify(path, sha)
            inv.external.append(dict(original_path=str(path), toolchain_relative_path=relative,
                                     sha256=actual, size_bytes=size, included_in_payload=False,
                                     reason="Pinned external toolchain; fetch separately"))

    lock = read_json(project / "lake-manifest.json")
    dependency_checks = {d["name"]: d for d in build["dependencies"]}
    path_deps = {p["name"]: p for p in lock["packages"] if p["type"] == "path"}
    require(set(path_deps) == {"mrmtfoundation", "schoenfliesfoundation"}, "Unexpected path dependencies")
    git_dependencies = []
    for package in lock["packages"]:
        if package["type"] == "git":
            require(re.fullmatch(r"[0-9a-f]{40}", package["rev"]) and
                    dependency_checks.get(package["name"], {}).get("revision") == package["rev"],
                    "Unpinned Git dependency")
            git_dependencies.append({k: package[k] for k in ("name", "url", "rev")})
        else:
            require(package["type"] == "path", "Unknown dependency type")
    for name, directory, root_module in (("mrmtfoundation", "MRMT", "MRMTFoundation"),
                                         ("schoenfliesfoundation", "Schoenflies", "Schoenflies")):
        base = f"dependencies/{directory}"
        require(path_deps[name]["dir"] == base, "Path dependency escaped its fixed directory")
        expected = dependency_checks[name]["provenance_sha256"]
        provenance_path = inv.project_file(base + "/candidate-provenance.json", "accepted_dependency_provenance", expected)
        provenance = read_json(provenance_path)
        require(provenance["files"] and
                len(provenance["files"]) == dependency_checks[name]["fixed_source_files"],
                "Incomplete path-dependency provenance")
        seen = set()
        for item in provenance["files"]:
            module = item["module"]
            require(MODULE.fullmatch(module) and module not in seen, "Invalid dependency module")
            seen.add(module)
            inv.project_file(base + "/" + module.replace(".", "/") + ".lean",
                             "accepted_dependency_source", item["ported_sha256"])
        # Aggregate roots and reproduction metadata are captured explicitly;
        # their digest basis is labelled separately from accepted source hashes.
        for relative in (root_module + ".lean", "lakefile.toml", "lake-manifest.json",
                         "lean-toolchain", "build-order.json", "scripts/build-sequential.ps1"):
            inv.project_file(base + "/" + relative, "dependency_reproduction_support")
        for relative in ("README.md", "port-changes.patch"):
            if (project / base / relative).exists():
                inv.project_file(base + "/" + relative, "dependency_provenance_support")
        licenses = (["licenses/Carleson-LICENSE", "licenses/RiemannDynamics-LICENSE", "licenses/RMT4-LICENSE"]
                    if directory == "MRMT" else ["LICENSE"])
        for relative in licenses:
            inv.project_file(base + "/" + relative, "license")
    for relative in ("scripts/bootstrap.ps1", "scripts/build-sequential.ps1"):
        inv.project_file(relative, "reproduction_support")
    for relative in ("AGStrip/Vendor/README.md", "LICENSE", "LICENSE.md", "LICENSE.txt"):
        if (project / relative).exists():
            inv.project_file(relative, "license_or_attribution")
    dependency_closure = collect_dependency_closure(
        inv, source_hashes, require=require, read_json=read_json,
        checked_file=checked_file, portable_name=portable_name, module_pattern=MODULE)
    recovery_provenance = collect_recovery_evidence(
        inv, state, integration, build, source_hashes, require=require,
        read_json=read_json, checked_file=checked_file, native_path=native_path)
    # Keep the existing acceptance/PASS gates above unchanged. This additional
    # completed-mode audit preserves build resumes distinct from controller
    # resumes and fresh failed-build recovery generations.
    interrupted_build_provenance = collect_interrupted_build_evidence(
        inv, checked_file(state["build_record"], (project,)),
        evidence[str(checked_file(state["build_record"], (project,)))],
        require=require, checked_file=checked_file)
    entries = sorted(inv.entries.values(), key=lambda e: e["archive_path"])
    result = dict(status="PUBLICATION_INVENTORY_ONLY_NOT_NEW_MATHEMATICAL_ACCEPTANCE",
                  publication_preparation_version=5,
                  prepared_at_utc=datetime.now(timezone.utc).isoformat(),
                  repository="zhangteng2000/Bloch-constant", target=TARGET,
                  accepted_status=ACCEPTED, independent_report=str(report_path),
                  acceptance_record=str(acceptance_path), acceptance_time=acceptance["time"],
                  lean_module_count=len(own_modules), quantitative_module_count=len(installed),
                  complete_rectangles=1068, nodes_per_rectangle=64,
                  extra_checker_actual_status=extra["status"], extra_checker_reason=extra.get("reason"),
                  recovery_provenance=recovery_provenance,
                  interrupted_build_provenance=interrupted_build_provenance,
                  dependency_closure=dependency_closure,
                  lean_toolchain=(project / "lean-toolchain").read_text(encoding="utf-8").strip(),
                  git_dependencies=git_dependencies, files=entries,
                  original_to_portable=inv.by_original, external_toolchain_evidence=inv.external,
                  total_payload_bytes=sum(e["size_bytes"] for e in entries),
                  compiled_artifacts_included=False, packaging_performed=False, upload_performed=False,
                  limitations=["Requires a prior matching independent evidence check.",
                               "Does not rerun Lean or the mathematical acceptance gate.",
                               "Does not archive compiled artifacts, caches, or historical staging.",
                               "Supporting aggregate roots/configurations/licenses marked publication_capture are not relabelled as accepted-source hashes.",
                               "The packager must recheck every listed hash while copying bytes."])
    inv.ensure_stable()
    return result


def english_summary(plan):
    extra = plan["extra_checker_actual_status"]
    reason = plan["extra_checker_reason"] or "The accepted record reports a successful additional fresh check."
    recovery = plan.get("recovery_provenance")
    lineage = plan["interrupted_build_provenance"]
    lineage_note = (
        f"Build history: a recorded empty-origin build continued {lineage['resume_links']} times.\n"
        f"Preserved {lineage['status_records']} build status records and their complete lineage evidence subset.\n"
        "Receipt hashes, copied snapshots, successful unique journal rows and exact byte-prefix continuity were checked.\n"
        "This limited lineage integrity check is separate from mathematical acceptance; it does not attest\n"
        "past physical directory/process state or execution/semantics of the pinned producer scripts.\n"
        "Lineage-only evidence has a historical digest basis, not an accepted proof-input label.\n")
    recovery_note = (f"Recovery provenance: preserved {recovery['generation_count']} linear recovery generations, "
                     f"{recovery['preserved_repair_count']} reviewed source repairs, all predecessor failed builds, "
                     f"and {recovery['resumed_controller_records']} prior controller records.\n"
                     "Historical recovery manifests remain PREPARED_FRESH_BUILD_RECOVERY_NOT_BUILT; "
                     "the separate final acceptance above establishes completion.\n"
                     "Historical path versions are resolved by generation, original path and SHA-256; "
                     "the current accepted-source mapping is never overwritten.\n"
                     if recovery else "Recovery provenance: no fresh-build recovery is recorded by the final controller.\n")
    return f"""PUBLICATION INVENTORY — AFTER PRIOR INDEPENDENT ACCEPTANCE VERIFICATION

This document summarizes existing accepted records. Preparing this inventory
does not create a new proof or a new mathematical acceptance decision.

Repository: https://github.com/{plan['repository']}
Theorem: AGStrip.original_quantitative_bloch_bound
Exact target: {plan['target']}
Manuscript statement: Theorem 1.3 (thm:main2)
Acceptance time as recorded: {plan['acceptance_time']}
Acceptance status: {plan['accepted_status']}
Independent verification report: {plan['independent_report']}
Lean toolchain: {plan['lean_toolchain']}
Checked project modules: {plan['lean_module_count']}
Installed quantitative modules: {plan['quantitative_module_count']}
Actual rectangles: 1068; quadrature nodes per rectangle: 64.
Additional fresh kernel checker: {extra}
Additional checker explanation: {reason}
{recovery_note}
{lineage_note}

The complete source inventory is derived from the accepted build's source hashes
and the final installed module map. Included path-dependency sources are checked
against their accepted provenance. Supporting files labelled publication_capture
have new publication hashes and are not presented as previously accepted hashes.
The complete local dependency import/build-order closure is checked. The local
MRMT audit helper and vendor license/provenance are included; supplemental
support bytes remain labelled publication_capture, not accepted proof inputs.
Raw evidence files are unchanged; original_to_portable maps their machine paths.
Files labelled recovery_controller_digest are historical recovery evidence
bound to the accepted controller's recovery reference, not new proof claims.

No archive has been created and nothing has been uploaded. The packager must
verify every file's SHA-256 again while copying it. Compiled artifacts and shared
package caches are excluded. External toolchain evidence is listed separately.
"""


REPRODUCTION_NOTES = """REPRODUCTION ORDER — PUBLICATION PREPARATION NOTES

Use the exact delivered lean-toolchain and lake-manifest.json revisions. Obtain
the pinned Git packages and prepare the included MRMT and Schoenflies path
dependencies first. Preserve their source/provenance/license files.

Important ordering requirement: the existing scripts/bootstrap.ps1 ends by
building the main project. Do NOT run the complete bootstrap and then expect
--require-empty to succeed: that can populate the quantitative build directory.
Prepare only the fixed packages and the two path dependencies first; leave the
main project's configured build directory genuinely empty.

Then, from the extracted project root, use the accepted quantitative builder:

  lake env python scripts/build-quantitative.py --jobs 3 --require-empty

The script uses Python tomllib (Python 3.11+; the development runtime is 3.12.14).
On Windows/NTFS, --compress-new-artifacts is an optional disk setting. Do not
copy development .olean files or delete local evidence to manufacture an empty
build. Use a new extraction directory. Do not claim unperformed cross-platform
bootstrap tests. Source and evidence checksums must match the publication list.

This inventory tool does not test a downloaded archive, create an archive, run
Lean, upload files, or replace the separate final mathematical acceptance gate.
"""


def write_outputs(plan, output_dir):
    output = native_path(output_dir).resolve()
    require(inside(output, HERE) and output != HERE,
            "Preparation outputs must stay inside this tool's directory")
    require(not output.exists(), "Refusing to overwrite an existing preparation directory")
    output.mkdir(parents=True)
    (output / "publication-manifest.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "ACCEPTANCE-SUMMARY-ENGLISH.txt").write_text(english_summary(plan), encoding="utf-8")
    (output / "REPRODUCTION-NOTES-ENGLISH.txt").write_text(REPRODUCTION_NOTES, encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-status", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--independent-report", type=Path, required=True,
                        help="JSON stdout saved from the prior independent evidence verifier")
    parser.add_argument("--toolchain-root", type=Path,
                        help="Explicit pinned toolchain root for checker evidence outside the project")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    plan = prepare(args.final_status, args.project, args.independent_report, args.toolchain_root)
    output = write_outputs(plan, args.output_dir)
    print(json.dumps(dict(status=plan["status"], output_directory=str(output),
                          files=len(plan["files"]), payload_bytes=plan["total_payload_bytes"],
                          packaging_performed=False, upload_performed=False)))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except (PreparationError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"PUBLICATION_PREPARATION_REJECTED: {error}", file=sys.stderr)
        raise SystemExit(1)
