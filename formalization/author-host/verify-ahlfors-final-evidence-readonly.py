"""Read-only evidence verification; run manually ONLY after final success.

Do not use this as a proof, build, recovery, or acceptance controller. It starts
no compiler and writes no proof or acceptance records. Run with Python -B to
disable bytecode-cache writes. Every assertion must pass before treating this
independent evidence check as successful. Extra-checker disposition is preserved.

This can read and hash the entire clean build, so allow several minutes.
"""

from pathlib import Path
import json
import re
import sys
import tomllib

sys.dont_write_bytecode = True
w = Path(r"D:\codex_data\2026-10-10\lean-4\work")
project = w.parent / "outputs/AGStrip"
sys.path.insert(0, str(w))
from outer_final_recovery import validate_build, intact, sha

read = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
norm = lambda s: " ".join(s.split())
accepted = "ORIGINAL_THEOREM_1_3_FORMALIZATION_ACCEPTED"
pointer = read(w / "outer-active-continuation.json")
finals = [
    (p, read(p))
    for p in sorted(
        w.glob("outer-final-acceptance-continuation-*/status.json"), reverse=True
    )
]
fp, f = next(
    (p, d) for p, d in finals
    if d.get("active_continuation") == pointer["continuation_status"]
)
assert f["status"] == accepted and f["theorem_1_3_complete"] is True
a = read(f["final_acceptance"])
assert a["status"] == accepted and a["theorem_1_3_complete"] is True
assert a["complete_actual_rectangles"] == 1068
intact(a["evidence_sha256"])

integration = read(f["integration_record"])
b = validate_build(Path(f["build_record"]), integration)
inputs = read(b["inputs_snapshot"])
modules = {e["module"]: e for e in b["results"]}
assert set(modules) == set(inputs["module_resources"])
assert b["completed_modules"] == len(modules) and b["failed_modules"] == 0
assert set(
    tomllib.loads((project / "lakefile.toml").read_text(encoding="utf-8"))[
        "defaultTargets"
    ]
) == {"AGStrip", "AGStripQuantitative"}

sizes = integration["rectangle_group_sizes"]
assert set(sizes) == set(map(str, range(1068)))
for i in range(1068):
    assert f"AGStripModuleLeaves.PrymOuterGenericLeafBudgeted{i:04d}" in modules
    size = sizes[str(i)]
    assert type(size) is int and size in (4, 8)
    base = f"AGStripModuleNodes.PrymOuterGenericLeafBudgeted{i:04d}PointGroup"
    expected = {base + f"{size}G{g:02d}" for g in range(64 // size)}
    assert {n for n in modules if n.startswith(base)} == expected
    for n in expected:
        assert "CURRENT_MODULE_AXIOM_AUDIT_OK:" in Path(
            modules[n]["log"]
        ).read_text(encoding="utf-8")

commands = {Path(e["log"]).stem: e for e in b["commands"]}
text = Path(commands["quantitative-axiom-and-type-audit"]["log"]).read_text(
    encoding="utf-8"
)
name = "AGStrip.original_quantitative_bloch_bound"
start = text.index(name + " :") + len(name + " :")
stop = text.index("'" + name + "'", start)
assert norm(text[start:stop]) == (
    "AGStrip.blochConstant < ENNReal.ofReal (AGStrip.AG - 13 / 10 ^ 10)"
)
axioms = re.search(
    re.escape("'" + name + "'") + r"\s+depends on axioms:\s*\[([^\]]*)\]", text
)
assert axioms, "Inspect the actual axiom print; do not infer success"
assert {s.strip() for s in axioms[1].split(",") if s.strip()} <= {
    "propext", "Classical.choice", "Quot.sound"
}
assert "CURRENT_MODULE_AXIOM_AUDIT_OK:" in text
assert "MODULE_CLOSURE_AXIOM_AUDIT_OK:" in text

baseline = (
    w / "geometry-logs/20261014-185152-AGStripModuleCore.BudgetedBridgePrototype.log"
).read_text(encoding="utf-8")


def definition(content, n):
    marker = "@[expose] def AGStrip." + n + " :"
    tail = content[content.index(marker):]
    ends = [tail.find(m, len(marker)) for m in (
        "@[expose] def ", "CURRENT_MODULE_AXIOM_AUDIT_OK:",
        "MODULE_CLOSURE_AXIOM_AUDIT_OK:"
    )]
    return norm(tail[:min((e for e in ends if e >= 0), default=len(tail))])


for n in ("Normalized", "IsInverseBranch", "blochRadius", "blochConstant", "AG"):
    assert definition(text, n) == definition(baseline, n), n

review = read(f["semantic_review"])
assert review["has_no_added_hypotheses"] and review["definitions_agree_with_paper"]
intact(review["reviewed_sources"])
extra = read(f["extra_checker_record"])
intact(extra["evidence_files"])
assert extra["build_record_sha256"] == sha(f["build_record"])
assert extra["status"] == a["extra_checker_status"]
if extra["status"] == "FRESH_CHECKER_PASSED":
    assert extra["exit_code"] == 0 and "--fresh" in extra["command"]
    assert "replaying AGStripQuantitative with --fresh" in Path(
        extra["log"]
    ).read_text(encoding="utf-8")
else:
    assert extra["status"] in {"NOT_RUN_UNAVAILABLE", "NOT_COMPLETED_RESOURCE_LIMIT"}
    assert extra["ordinary_kernel_build_passed"] is True
    assert len(extra["reason"].strip()) > 20

manifest = read(project / "DELIVERY-MANIFEST.json")
assert manifest["status"] == accepted
assert manifest["acceptance_record_sha256"] == sha(f["final_acceptance"])
assert manifest["final_report_sha256"] == sha(f["final_report"])
print(json.dumps({
    "independent_readonly_evidence_check": "PASSED",
    "complete_rectangles": 1068,
    "clean_build_modules": len(modules),
    "extra_checker_actual_status": extra["status"],
    "extra_checker_reason": extra.get("reason"),
    "acceptance_record": f["final_acceptance"],
    "acceptance_record_sha256": manifest["acceptance_record_sha256"],
    "delivery_manifest_sha256": sha(project / "DELIVERY-MANIFEST.json"),
    "verification_script_sha256": sha(Path(__file__)),
}, ensure_ascii=False))
