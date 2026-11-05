"""Explicit local dependency closure and vendor attribution checks.

Only paths named by the reviewed provenance/order/aggregate files are read.
No package cache, compiler output, or historical staging tree is traversed.
"""
import json
import re

EXTERNAL_ROOTS = {"Init", "Lean", "Std", "Lake", "Mathlib", "Batteries", "Aesop",
                  "Qq", "Plausible", "LeanSearchClient", "ImportGraph", "ProofWidgets", "Cli"}
VENDOR_FILES = {"AGStrip/Vendor/Wirtinger.lean", "AGStrip/Vendor/WeakDeriv.lean", "AGStrip/Vendor/WeylLocal.lean"}


def imports(text, require, module_pattern):
    """Read only the Lean import header, allowing nested header comments.

    Stop at the first body command: strings, raw strings and Char literals in
    declarations are not part of the import grammar and must not be lexed here.
    This is a conservative inventory reader, not a replacement Lean parser.
    """
    result = []
    depth = 0
    for line in text.lstrip("\ufeff").splitlines():
        out = []
        i = 0
        while i < len(line):
            pair = line[i:i + 2]
            if depth:
                if pair == "/-": depth += 1; i += 2; continue
                if pair == "-/": depth -= 1; i += 2; continue
                i += 1; continue
            if pair == "--": break
            if pair == "/-": depth = 1; out.append(" "); i += 2; continue
            out.append(line[i]); i += 1
        parts = "".join(out).split()
        if not parts or parts in (["prelude"], ["module"]): continue
        while parts and parts[0] in {"public", "meta"}: parts.pop(0)
        if not parts or parts[0] != "import": return result
        parts.pop(0)
        if parts and parts[0] == "all": parts.pop(0)
        require(parts and all(module_pattern.fullmatch(part) for part in parts),
                "Unsupported dependency import syntax; review it before publication")
        result.extend(parts)
    require(depth == 0, "Unterminated comment in dependency import header")
    return result


def validate_and_collect(inv, source_hashes, *, require, read_json, checked_file, portable_name, module_pattern):
    summaries = []
    mrmt_provenance = None
    for directory, root_module, local_roots in (
        ("MRMT", "MRMTFoundation", {"MRMTFoundation", "Carleson", "RiemannDynamics", "RMT4"}),
        ("Schoenflies", "Schoenflies", {"Schoenflies"}),
    ):
        base = inv.project / "dependencies" / directory
        relative_base = f"dependencies/{directory}/"

        def add(relative, role, expected=None):
            portable_name(relative)
            path = checked_file(base / relative, (base,))
            require(path == base / relative, "Dependency source/support alias is outside its declared path")
            return inv.project_file(relative_base + relative, role, expected)

        provenance_path = checked_file(base / "candidate-provenance.json", (base,))
        provenance = read_json(provenance_path)
        if directory == "MRMT": mrmt_provenance = provenance
        modules = {}
        for item in provenance["files"]:
            name = item["module"]
            require(module_pattern.fullmatch(name) and name.split(".")[0] in local_roots and name not in modules,
                    "Unexpected or duplicate dependency provenance module")
            modules[name] = add(name.replace(".", "/") + ".lean", "accepted_dependency_source", item["ported_sha256"])
        order_path = add("build-order.json", "dependency_reproduction_support")
        order = json.loads(order_path.read_text(encoding="utf-8"))
        require(isinstance(order, list) and all(isinstance(name, str) for name in order) and
                len(order) == len(set(order)) and set(order) == set(modules),
                "Dependency build order must contain every provenance module exactly once")
        supplemental = []
        if directory == "MRMT":
            name = "MRMTFoundation.AuditSupport"
            if name not in modules:
                path = add("MRMTFoundation/AuditSupport.lean", "local_dependency_audit_support")
                modules[name] = path
                supplemental.append(dict(module=name, archive_path=inv.by_original[str(path)],
                    sha256=inv.entries[inv.by_original[str(path)].casefold()]["sha256"],
                    integrity_basis="publication_capture",
                    justification="Required by both MRMTFoundation.lean and the delivered dependency build script; local audit support, not an upstream ported proof."))
        require(root_module not in modules, "Aggregate root unexpectedly appears in dependency provenance")
        modules[root_module] = add(root_module + ".lean", "dependency_reproduction_support")
        graph = {}
        for name, path in modules.items():
            dependencies = imports(path.read_text(encoding="utf-8"), require, module_pattern)
            for dependency in dependencies:
                first = dependency.split(".")[0]
                if first in local_roots:
                    require(dependency in modules, f"Missing local dependency closure module: {dependency}")
                else:
                    require(first in EXTERNAL_ROOTS, f"Unreviewed external dependency import: {dependency}")
            graph[name] = {dep for dep in dependencies if dep in modules}
        if directory == "MRMT":
            require("MRMTFoundation.AuditSupport" in graph[root_module],
                    "MRMT aggregate no longer imports the required audit support")
            support_imports = imports(modules["MRMTFoundation.AuditSupport"].read_text(encoding="utf-8"), require, module_pattern)
            require(support_imports and all(name == "Lean" or name.startswith("Lean.") for name in support_imports),
                    "Local MRMT audit support has unreviewed proof dependencies")
        # Mirrors the explicit delivered build order, including the local audit
        # helper and aggregate root that are outside the upstream file list.
        sequence = order + (["MRMTFoundation.AuditSupport"] if directory == "MRMT" and "MRMTFoundation.AuditSupport" not in order else []) + [root_module]
        seen = set()
        for name in sequence:
            require(graph[name] <= seen, f"Unordered/cyclic local dependency imports in {name}")
            seen.add(name)
        require(seen == set(modules), "Dependency reproduction sequence omits needed source")
        summaries.append(dict(dependency=directory, provenance_modules=len(provenance["files"]),
                              total_local_modules=len(modules), local_import_closure_checked=True,
                              supplemental_sources=supplemental))

    vendor_base = inv.project / "AGStrip" / "Vendor"
    for name in ("README.md", "LICENSE", "PROVENANCE.json"):
        checked_file(vendor_base / name, (vendor_base,))
        inv.project_file("AGStrip/Vendor/" + name, "vendor_license_or_provenance")
    vendor = read_json(vendor_base / "PROVENANCE.json")
    require(vendor.get("repository") == "https://github.com/will1491/RiemannDynamics" and
            isinstance(vendor.get("commit"), str) and re.fullmatch(r"[0-9a-f]{40}", vendor["commit"]),
            "Unexpected vendor repository/commit provenance")
    require(mrmt_provenance.get("pinned_commits", {}).get("RiemannDynamics") == vendor["commit"],
            "Vendor and MRMT RiemannDynamics commit provenance disagree")
    seen = set()
    for item in vendor["files"]:
        relative = portable_name(item["ported_file"])
        require(relative in VENDOR_FILES and relative not in seen, "Unexpected/duplicate vendor source path")
        seen.add(relative)
        path = checked_file(inv.project / relative, (vendor_base,))
        require(path == inv.project / relative and source_hashes.get(str(path)) == item["ported_sha256"],
                "Vendor ported source differs from the accepted build input")
        inv.project_file(relative, "accepted_vendor_source_with_provenance", item["ported_sha256"])
        portable_name(item["file"])
        require(isinstance(item.get("original_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", item["original_sha256"]),
                "Missing original upstream source digest")
    require(seen == VENDOR_FILES, "Vendor provenance omits a required source")
    return dict(dependencies=summaries, vendor_license_included=True, vendor_provenance_included=True,
                vendor_ported_sources_match_accepted_inputs=True,
                upstream_source_fetch_performed=False,
                provenance_limit="Upstream origin is preserved as recorded provenance; original upstream bytes are not refetched by this inventory tool.")
