"""CANDIDATE: dependency-only preparation of a fresh, verified extraction.

Default mode emits a plan. --execute is a distinct, future Windows operation:
it downloads pinned Git packages and builds only the two local dependencies.
It never invokes the main proof build or creates a new mathematical acceptance.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tomllib
import unicodedata

ACCEPTED = "ORIGINAL_THEOREM_1_3_FORMALIZATION_ACCEPTED"
INVENTORY = "PUBLICATION_INVENTORY_ONLY_NOT_NEW_MATHEMATICAL_ACCEPTANCE"
TARGET = "blochConstant < ENNReal.ofReal (AG - (13 : ℝ) / 10^10)"
TOOLCHAIN = "leanprover/lean4:v4.34.0-rc1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")
GIT_NAMES = {"mathlib", "plausible", "LeanSearchClient", "importGraph", "proofwidgets",
             "aesop", "Qq", "batteries", "Cli"}
DEPENDENCIES = {"MRMT": "mrmtfoundation", "Schoenflies": "schoenfliesfoundation"}
BLOCK = 1024 * 1024
# Shared packager-v4 pure-data validator. These reviewed source pins are never
# user-provided override; a different helper requires a new reviewed candidate.
RECOVERY_VALIDATOR_SHA256 = "f12f823a5e5827556b83b4ac035cab81084132a3f69d20f740f3da199accfbd7"
LINEAGE_VERIFIER_SHA256 = "1603a4784aed7c373f748bfe6517a1e602b7325b06607e49ac9dfc0619299af1"
RECOVERY_VALIDATED = "V5_RECOVERY_RAW_CHAIN_AND_INTERRUPTED_BUILD_LINEAGE_VERIFIED_NOT_MATHEMATICAL_ACCEPTANCE"


class BootstrapError(ValueError): pass


def require(value, message):
    if not value: raise BootstrapError(message)


def object_pairs(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, "Duplicate JSON key")
        obj[key] = value
    return obj


def decode(raw): return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=object_pairs)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def inside(path, root): return path == root or root in path.parents


def portable(value, allow_cache=False):
    require(isinstance(value, str) and value and value != "." and
            unicodedata.normalize("NFC", value) == value and not any(c in value for c in '\\:<>|?*"'), "Unsafe relative path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value and
            all(p not in {".", ".."} and not p.endswith((".", " ")) and
                not any(ord(c) < 32 or ord(c) == 127 for c in p) and
                not re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?", p)
                for p in path.parts), "Unsafe relative path")
    require(allow_cache or not any(p.casefold() in {".lake", ".git", "module-replay-stage"} for p in path.parts),
            "Cached/staged files are not source input")
    return path


def safe_path(value, directory=False):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts and
            all(":" not in p for p in path.parts[1:]), "Unsafe absolute path")
    for part in reversed((path, *path.parents)):
        st = part.lstat()
        require(not stat.S_ISLNK(st.st_mode) and not getattr(st, "st_file_attributes", 0) & 0x400,
                "Source/extraction reparse point or symlink is forbidden")
    require(path.is_dir() if directory else path.is_file(), "Wrong input file type")
    require(directory or path.stat().st_nlink == 1, "Hard-linked source/tool input is forbidden")
    return path


def file_hash(path):
    path = safe_path(path)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        initial = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns), "File identity changed")
        for block in iter(lambda: stream.read(BLOCK), b""): digest.update(block)
        final = os.fstat(stream.fileno())
    after = safe_path(path).stat()
    require((initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns, initial.st_ctime_ns) ==
            (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_ctime_ns) and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "File changed while hashing")
    return digest.hexdigest()


def load_recovery_validator(path, lineage_path):
    """Authenticate both pure runtime sources before executing either one."""
    sources = []
    for value, expected, interface in (
        (path, RECOVERY_VALIDATOR_SHA256, "validate_recovery_inventory"),
        (lineage_path, LINEAGE_VERIFIER_SHA256, "verify_lineage"),
    ):
        selected = safe_path(value)
        require(HEX.fullmatch(expected), "Reviewed runtime pin is not finalized")
        require(selected.stat().st_size <= 2 * BLOCK, "Reviewed runtime unexpectedly large")
        require(file_hash(selected) == expected, "Reviewed runtime digest mismatch")
        raw = selected.read_bytes()
        require(sha(raw) == expected, "Reviewed runtime changed before loading")
        sources.append((selected, raw, interface))
    loaded = []
    for selected, raw, interface in sources:
        namespace = {"__name__": "_reviewed_" + selected.stem, "__file__": str(selected)}
        # Both helpers use standard-library imports only. Execute the exact
        # authenticated bytes, never a discovered module or cached .pyc.
        exec(compile(raw, str(selected), "exec"), namespace)
        function = namespace.get(interface)
        require(callable(function), "Reviewed runtime interface is missing")
        loaded.append((selected, function))
    return loaded[0][0], loaded[0][1], loaded[1][0], loaded[1][1]


class Extraction:
    def __init__(self, root, manifest, expected, verification_script, recovery_validator, lineage_verifier):
        self.root = safe_path(root, directory=True)
        self.manifest = safe_path(manifest)
        require(HEX.fullmatch(expected or ""), "Explicit reviewed manifest SHA-256 required")
        require(file_hash(self.manifest) == expected, "Publication manifest digest mismatch")
        raw = self.manifest.read_bytes()
        require(sha(raw) == expected, "Manifest changed before parse")
        self.expected = expected
        self.plan = decode(raw)
        require(self.plan.get("status") == INVENTORY and self.plan.get("publication_preparation_version") == 5 and
                self.plan.get("accepted_status") == ACCEPTED and
                self.plan.get("repository") == "zhangteng2000/Bloch-constant" and
                self.plan.get("target") == TARGET and self.plan.get("complete_rectangles") == 1068,
                "Not the accepted v5 publication inventory")
        self.entries, self.aliases, self.names = {}, {}, {}
        for entry in self.plan["files"]:
            name = str(portable(entry["archive_path"]))
            require(name.casefold() not in self.names and HEX.fullmatch(entry["sha256"]) and
                    type(entry["size_bytes"]) is int and entry["size_bytes"] >= 0, "Duplicate/invalid inventory entry")
            self.names[name.casefold()] = name
            target = self.root.joinpath(*PurePosixPath(name).parts)
            require(str(target).casefold() != str(Path(entry["source_path"])).casefold(), "Refusing the live original source tree")
            self.entries[name] = entry
            for alias in entry["original_paths"]:
                require(alias not in self.aliases, "Duplicate original alias")
                self.aliases[alias] = name
        require(self.aliases == self.plan["original_to_portable"], "Incomplete original path mapping")
        self.project = safe_path(self.root / "AGStrip", directory=True)
        self.reject_alternate_configs()
        self.check_files()
        self.verifier = safe_path(verification_script)
        self.verifier_sha = file_hash(self.verifier)
        self.verify_evidence()
        self.verify_recovery_evidence(recovery_validator, lineage_verifier)
        self.config = self.toml("lakefile.toml")
        require(self.config.get("name") == "agstrip", "Unexpected root package")
        relative_build = str(portable(self.config["buildDir"], allow_cache=True))
        require(relative_build.startswith(".lake/build-quantitative-") and len(PurePosixPath(relative_build).parts) == 2,
                "Unexpected main build directory")
        self.main_build = self.project.joinpath(*PurePosixPath(relative_build).parts)
        self.require_main_absent()
        require(self.bytes("lean-toolchain").decode("utf-8").strip() == TOOLCHAIN, "Unreviewed Lean toolchain")
        self.git = self.lock(self.json("lake-manifest.json"), main=True)
        self.orders = {}
        self.controls = {"lakefile.toml", "lake-manifest.json", "lean-toolchain"}
        for directory, package in DEPENDENCIES.items():
            prefix = f"dependencies/{directory}/"
            config = self.toml(prefix + "lakefile.toml")
            require(config.get("name") == package and config.get("buildDir", ".lake/build") == ".lake/build",
                    "Dependency buildDir must stay inside its own package")
            require(self.bytes(prefix + "lean-toolchain").decode("utf-8").strip() == TOOLCHAIN, "Dependency toolchain differs")
            require(self.lock(self.json(prefix + "lake-manifest.json")) == self.git, "Dependency lock differs from root lock")
            requires = config.get("require", [])
            require(len(requires) == 1 and requires[0].get("name") == "mathlib" and
                    requires[0].get("git") == self.git["mathlib"]["url"] and
                    requires[0].get("rev") == self.git["mathlib"]["rev"], "Unexpected dependency requirement")
            order = self.json(prefix + "build-order.json")
            provenance = self.json(prefix + "candidate-provenance.json")
            modules = [item["module"] for item in provenance["files"]]
            require(isinstance(order, list) and len(order) == len(set(order)) and
                    len(modules) == len(set(modules)) and set(order) == set(modules), "Incomplete dependency build order")
            roots = {"Carleson", "RiemannDynamics", "RMT4"} if directory == "MRMT" else {"Schoenflies"}
            require(all(MODULE.fullmatch(m) and m.split(".")[0] in roots for m in order), "Invalid dependency module")
            tail = ["MRMTFoundation.AuditSupport", "MRMTFoundation"] if directory == "MRMT" else ["Schoenflies"]
            self.orders[directory] = order + tail
            for module in self.orders[directory]: self.entry(prefix + module.replace(".", "/") + ".lean")
            self.controls.update(prefix + name for name in ("lakefile.toml", "lake-manifest.json", "lean-toolchain", "build-order.json", "candidate-provenance.json"))
        requires = {r["name"]: r for r in self.config.get("require", [])}
        require(len(requires) == 3 and set(requires) == {"mathlib", *DEPENDENCIES.values()}, "Unexpected root dependencies")
        for directory, package in DEPENDENCIES.items():
            require(requires[package].get("path") == f"dependencies/{directory}", "Nonlocal dependency path")
        require(requires["mathlib"].get("git") == self.git["mathlib"]["url"] and
                requires["mathlib"].get("rev") == self.git["mathlib"]["rev"], "Root Mathlib pin differs")
        self.mathlib_imports = self.find_mathlib_imports()
        require(self.mathlib_imports, "No Mathlib cache targets found; investigate extraction")
        self.check_files()
        require(file_hash(self.verifier) == self.verifier_sha and
                file_hash(self.recovery_validator_path) == RECOVERY_VALIDATOR_SHA256 and
                file_hash(self.lineage_verifier_path) == LINEAGE_VERIFIER_SHA256,
                "Binding file changed during extraction validation")

    def entry(self, relative):
        name = "AGStrip/" + str(portable(relative))
        require(name in self.entries, f"Required project file omitted: {relative}")
        return self.entries[name]

    def bytes(self, relative):
        entry = self.entry(relative)
        raw = safe_path(self.project.joinpath(*PurePosixPath(relative).parts)).read_bytes()
        require(sha(raw) == entry["sha256"], f"Project input changed: {relative}")
        return raw

    def json(self, relative): return decode(self.bytes(relative))
    def toml(self, relative): return tomllib.loads(self.bytes(relative).decode("utf-8"))

    def mapped(self, original):
        require(original in self.aliases, "Missing mapped raw evidence")
        name = self.aliases[original]
        raw = safe_path(self.root.joinpath(*PurePosixPath(name).parts)).read_bytes()
        require(sha(raw) == self.entries[name]["sha256"], "Mapped evidence changed")
        return decode(raw), self.entries[name]["sha256"]

    def member_bytes(self, name):
        name = str(portable(name))
        require(name in self.entries, "Recovery evidence member is missing")
        entry = self.entries[name]
        raw = safe_path(self.root.joinpath(*PurePosixPath(name).parts)).read_bytes()
        require(len(raw) == entry["size_bytes"] and sha(raw) == entry["sha256"],
                "Recovery evidence member changed")
        return raw

    def verify_recovery_evidence(self, recovery_validator, lineage_verifier):
        (self.recovery_validator_path, validator, self.lineage_verifier_path,
         verify_lineage) = load_recovery_validator(recovery_validator, lineage_verifier)
        try:
            result = validator(self.plan, self.entries, read_member=self.member_bytes,
                               final_state=self.final_state, lineage_verifier=verify_lineage)
        except ValueError as error:
            raise BootstrapError("Recovery inventory validation failed: " + str(error)) from error
        require(isinstance(result, dict) and result.get("status") == RECOVERY_VALIDATED and
                result.get("interrupted_build_lineage_verified") is True,
                "Shared recovery validator did not complete raw evidence validation")
        self.recovery_validation = result

    def role(self, role):
        rows = [e for e in self.entries.values() if role in e["roles"]]
        require(len(rows) == 1, f"Expected exactly one {role}")
        return self.mapped(rows[0]["source_path"])

    def verify_evidence(self):
        state, _ = self.role("final_controller")
        delivery, delivery_sha = self.role("accepted_delivery_manifest")
        report, _ = self.role("prior_independent_verification_report")
        acceptance, acceptance_sha = self.mapped(state["final_acceptance"])
        require(state.get("status") == acceptance.get("status") == delivery.get("status") == ACCEPTED and
                state.get("theorem_1_3_complete") is True and acceptance.get("theorem_1_3_complete") is True and
                acceptance.get("target") == delivery.get("target") == TARGET and
                acceptance.get("complete_actual_rectangles") == report.get("complete_rectangles") == 1068,
                "Historical records are not genuinely accepted")
        require(delivery.get("acceptance_record") == state["final_acceptance"] == report.get("acceptance_record") and
                delivery.get("acceptance_record_sha256") == acceptance_sha and
                report.get("independent_readonly_evidence_check") == "PASSED" and
                report.get("acceptance_record_sha256") == acceptance_sha and
                report.get("delivery_manifest_sha256") == delivery_sha and
                report.get("verification_script_sha256") == self.verifier_sha, "Archived independent three-hash binding failed")
        require(report.get("extra_checker_actual_status") == acceptance.get("extra_checker_status") ==
                delivery.get("extra_checker_status") == self.plan.get("extra_checker_actual_status"), "Checker status differs")
        for original, digest in delivery["source_sha256"].items():
            require(original in self.aliases and self.entries[self.aliases[original]]["sha256"] == digest and
                    self.entries[self.aliases[original]]["integrity_basis"] == "accepted_digest", "Accepted source input omitted")
        self.acceptance_sha, self.delivery_sha = acceptance_sha, delivery_sha
        self.final_state = state

    def lock(self, lock, main=False):
        require(lock.get("packagesDir") == ".lake/packages", "Nonlocal package store")
        result, paths = {}, {}
        for package in lock["packages"]:
            if package["type"] == "path":
                require(main and package["name"] not in paths, "Unexpected path dependency")
                paths[package["name"]] = package["dir"]
                continue
            require(package["type"] == "git" and package["name"] in GIT_NAMES and package["name"] not in result,
                    "Unsupported or duplicate Git package")
            require(re.fullmatch(r"[0-9a-f]{40}", package["rev"]) and package["inputRev"] == package["rev"] and
                    re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", package["url"]) and
                    package.get("subDir") is None, "Unpinned or unsupported Git dependency")
            result[package["name"]] = {k: package[k] for k in ("url", "rev")}
        require(set(result) == GIT_NAMES, "Incomplete Git dependency lock")
        require(paths == ({p: f"dependencies/{d}" for d, p in DEPENDENCIES.items()} if main else {}), "Path dependency mapping differs")
        return result

    def check_files(self):
        require(file_hash(self.manifest) == self.expected, "Manifest changed")
        for name, entry in self.entries.items():
            path = safe_path(self.root.joinpath(*PurePosixPath(name).parts))
            require(path.stat().st_size == entry["size_bytes"] and file_hash(path) == entry["sha256"], f"Extracted file differs: {name}")

    def require_main_absent(self):
        require(not os.path.lexists(self.main_build), "Main quantitative build directory must remain absent")

    def reject_alternate_configs(self):
        for base in (self.project, *(self.project / "dependencies" / d for d in DEPENDENCIES)):
            require(not os.path.lexists(base / "lakefile.lean"), "Alternate lakefile.lean could override the verified TOML")

    def check_controls(self):
        self.require_main_absent()
        self.reject_alternate_configs()
        require(file_hash(self.manifest) == self.expected and file_hash(self.verifier) == self.verifier_sha and
                file_hash(self.recovery_validator_path) == RECOVERY_VALIDATOR_SHA256 and
                file_hash(self.lineage_verifier_path) == LINEAGE_VERIFIER_SHA256, "Binding file changed")
        for name in self.controls: self.bytes(name)

    def find_mathlib_imports(self):
        found = set()
        for name in self.entries:
            if not name.startswith("AGStrip/") or not name.endswith(".lean"): continue
            depth = 0
            with self.root.joinpath(*PurePosixPath(name).parts).open(encoding="utf-8-sig") as stream:
                for line in stream:
                    out, i = [], 0
                    while i < len(line):
                        pair = line[i:i+2]
                        if depth:
                            if pair == "/-": depth += 1; i += 2; continue
                            if pair == "-/": depth -= 1; i += 2; continue
                            i += 1; continue
                        if pair == "--": break
                        if pair == "/-": depth = 1; out.append(" "); i += 2; continue
                        out.append(line[i]); i += 1
                    parts = "".join(out).split()
                    if not parts or parts in (["module"], ["prelude"]): continue
                    while parts and parts[0] in {"public", "meta"}: parts.pop(0)
                    if not parts or parts.pop(0) != "import": break
                    if parts and parts[0] == "all": parts.pop(0)
                    require(parts and all(MODULE.fullmatch(p) for p in parts), "Unsupported import header")
                    found.update(p for p in parts if p == "Mathlib" or p.startswith("Mathlib."))
        return sorted(found)

    def command_plan(self):
        return dict(status="DEPENDENCY_ONLY_PLAN_NOT_EXECUTED_NOT_THEOREM_ACCEPTANCE", candidate=True,
                    bootstrap_candidate_version=3, publication_preparation_version=5,
                    manifest_sha256=self.expected, extraction_root=str(self.root), project=str(self.project),
                    recovery_validator_sha256=RECOVERY_VALIDATOR_SHA256,
                    lineage_verifier_sha256=LINEAGE_VERIFIER_SHA256,
                    recovery_validation=self.recovery_validation,
                    preserved_main_build_directory=str(self.main_build), toolchain=TOOLCHAIN,
                    git_packages=self.git, dependency_builds=self.orders, mathlib_cache_targets=self.mathlib_imports,
                    cache_cwd=str(self.project / "dependencies/MRMT"),
                    build_cwds={d: str(self.project / "dependencies" / d) for d in DEPENDENCIES},
                    original_bootstrap_invoked=False, original_schoenflies_wrapper_invoked=False,
                    main_project_build_invoked=False, theorem_acceptance_created=False)


def batches(values, limit=12000):
    current, count = [], 0
    for value in values:
        require(len(value) < limit, "Cache target argument is too long")
        if current and count + len(value) + 1 > limit:
            yield current
            current, count = [], 0
        current.append(value); count += len(value) + 1
    if current: yield current


class Runner:
    def __init__(self, report): self.report, self.commands = report, []

    def run(self, argv, cwd, env=None):
        output = self.report / f"command-{len(self.commands)+1:05d}.log"
        with output.open("xb") as log:
            result = subprocess.run([str(x) for x in argv], cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.commands.append(dict(argv=[str(x) for x in argv], cwd=str(cwd), exit_code=result.returncode,
                                  log=str(output), log_sha256=file_hash(output)))
        require(result.returncode == 0, f"Dependency command failed; preserved log: {output}")
        if any(str(x) in {"--version", "rev-parse", "status"} for x in argv):
            require(output.stat().st_size <= BLOCK, "Unexpectedly large version/Git status response")
            return output.read_bytes().decode("utf-8", errors="replace").strip()
        return ""


def verify_junction(link, target):
    require(link.is_dir() and link.resolve(strict=True) == target and
            getattr(link.lstat(), "st_file_attributes", 0) & 0x400, "Dependency package mapping escaped extraction")


def execute(extraction, report, git_exe, lake_exe, powershell_exe, runner=None):
    require(os.name == "nt", "Execution candidate is Windows-only; no cross-platform claim")
    tools = [safe_path(p) for p in (git_exe, lake_exe, powershell_exe)]
    git_exe, lake_exe, powershell_exe = tools
    require(lake_exe.name.lower() == "lake.exe", "Pass the installed toolchain's lake.exe")
    lean_exe = safe_path(lake_exe.parent / "lean.exe")
    tools.append(lean_exe)
    tool_hashes = {str(p): file_hash(p) for p in tools}
    runner = runner or Runner(report)
    root = extraction.project
    for base in (root, *(root / "dependencies" / d for d in DEPENDENCIES)):
        require(not os.path.lexists(base / ".lake"), "Fresh extraction required; existing .lake must be reviewed, never deleted")
    extraction.check_files()
    extraction.check_controls()
    (root / ".lake").mkdir()
    packages = root / ".lake/packages"
    packages.mkdir()
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["ELAN_TOOLCHAIN"] = TOOLCHAIN
    for key in list(env):
        if key.startswith("GIT_CONFIG_KEY_") or key.startswith("GIT_CONFIG_VALUE_") or key in {"GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_TEMPLATE_DIR", "GIT_EXEC_PATH", "LEAN_PATH", "LEAN_SRC_PATH", "LAKE_PACKAGES_DIR", "LAKE_HOME", "LEAN_SYSROOT"}:
            del env[key]
    git_prefix = [git_exe, "-c", "core.autocrlf=false", "-c", "core.hooksPath=" + os.devnull]

    def run(argv, cwd, extra=None):
        extraction.check_controls()
        result = runner.run(argv, cwd, env if extra is None else {**env, **extra})
        extraction.check_controls()
        return result

    def verify_git(name, pin):
        path = safe_path(packages / name, directory=True)
        safe_path(path / ".git", directory=True)
        require(run(git_prefix + ["rev-parse", "HEAD"], path).lower() == pin["rev"], "Git HEAD differs from pinned commit")
        require(run(git_prefix + ["status", "--porcelain=v1", "--untracked-files=no"], path) == "", "Git tracked source files changed")

    for executable in (lake_exe, lean_exe):
        require(re.search(r"4\.34\.0-rc1(?:\D|$)", run([executable, "--version"], root / "dependencies/MRMT")),
                "Installed Lake/Lean version differs")
    for name, pin in sorted(extraction.git.items()):
        destination = packages / name
        destination.mkdir()
        run(git_prefix + ["init", "--quiet", str(destination)], packages)
        run(git_prefix + ["remote", "add", "origin", pin["url"]], destination)
        run(git_prefix + ["fetch", "--depth=1", "--no-tags", "origin", pin["rev"]], destination)
        run(git_prefix + ["checkout", "--detach", pin["rev"]], destination)
        verify_git(name, pin)
    junctions = []
    for directory in DEPENDENCIES:
        base = root / "dependencies" / directory
        (base / ".lake").mkdir()
        link = base / ".lake/packages"
        run([powershell_exe, "-NoProfile", "-NonInteractive", "-Command",
             "New-Item -ItemType Junction -Path $env:AG_DEP_LINK -Target $env:AG_DEP_TARGET -ErrorAction Stop | Out-Null"],
            base, {"AG_DEP_LINK": str(link), "AG_DEP_TARGET": str(packages)})
        verify_junction(link, packages)
        junctions.append(link)
    for targets in batches(extraction.mathlib_imports):
        run([lake_exe, "--keep-toolchain", "exe", "cache", "get", *targets], root / "dependencies/MRMT")
    for directory, modules in extraction.orders.items():
        for module in modules:
            run([lake_exe, "--keep-toolchain", "build", module], root / "dependencies" / directory)
    for name, pin in extraction.git.items(): verify_git(name, pin)
    for link in junctions: verify_junction(link, packages)
    extraction.check_files()
    extraction.check_controls()
    require(all(file_hash(Path(p)) == digest for p, digest in tool_hashes.items()), "Executable bytes changed")
    return dict(status="DEPENDENCIES_PREPARED_MAIN_BUILD_NOT_RUN_NOT_THEOREM_ACCEPTANCE", tool_hashes=tool_hashes,
                commands=runner.commands, git_heads_verified=True, accepted_source_bytes_unchanged=True,
                main_build_directory_absent=True, original_bootstrap_invoked=False,
                main_project_build_invoked=False, mathematical_acceptance_created=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("extraction-root", "manifest", "verification-script", "recovery-validator", "lineage-verifier", "report-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--execute", action="store_true")
    for name in ("git-exe", "lake-exe", "powershell-exe"): parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    extraction = Extraction(args.extraction_root, args.manifest, args.manifest_sha256,
                            args.verification_script, args.recovery_validator, args.lineage_verifier)
    report = args.report_dir
    require(report.is_absolute() and ".." not in report.parts and not os.path.lexists(report), "Report directory must be new")
    safe_path(report.parent, directory=True)
    require(not inside(report, extraction.root), "Reports must stay outside extraction")
    report.mkdir()
    plan = extraction.command_plan()
    (report / "dependency-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    if not args.execute:
        print(json.dumps({"status": plan["status"], "report": str(report)})); return
    runner = Runner(report)
    try:
        require(all((args.git_exe, args.lake_exe, args.powershell_exe)), "Execution requires explicit installed executable paths")
        result = execute(extraction, report, args.git_exe, args.lake_exe, args.powershell_exe, runner)
        (report / "dependency-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "report": str(report)}))
    except BaseException as error:
        failure = dict(status="DEPENDENCY_PREPARATION_FAILED_PARTIAL_FILES_PRESERVED", error=str(error),
                       commands=runner.commands, mathematical_acceptance_created=False)
        (report / "DEPENDENCIES-FAILED.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        raise


if __name__ == "__main__": main()
