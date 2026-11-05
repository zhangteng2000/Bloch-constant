# Recorded ordinary Lean kernel checks

Theorem 1.1, Corollary 1.2, and Theorem 1.3 passed the recorded ordinary Lean compilation and root audits. This publication reports those mathematical build results with their source bindings and original logs.

| Check | Recorded result | Evidence |
| --- | --- | --- |
| Full mathematical module build | 79,902 unique module results; every exit code 0; zero failed modules | Complete archive `status.json`, input inventory, and module journals |
| Theorem 1.1 module | `lake --no-cache build +AGStrip.Main:olean`, exit 0 | `AGStrip.Main.log` in the evidence ZIP |
| Corollary 1.2 module | `lake --no-cache build +AGStrip.SurfaceAGRadiusDescent:olean`, exit 0 | `AGStrip.SurfaceAGRadiusDescent.log` in the evidence ZIP |
| Theorem 1.3 root | `lake --no-cache build +AGStripQuantitative:olean`, exit 0 | `AGStripQuantitative.log` in the evidence ZIP |
| Default Lake build | `lake --no-cache build`, exit 0 | `default-lake-build.log` in the evidence ZIP |
| Original theorem axiom audit | exit 0; 60,937 declarations audited | `original-axiom-audit.log` in the evidence ZIP and complete archive |
| Quantitative statement and axiom audit | exit 0; 82,259 declarations in the audited module closure | [quantitative-axiom-and-type-audit.log](evidence/quantitative-axiom-and-type-audit.log) |

The original-root audit command was:

```text
lake env lean -j2 -M6144 -DautoImplicit=false -DmaxHeartbeats=100000000 -DmaxRecDepth=1000000 AGStrip/AxiomAudit.lean
```

The quantitative statement and audit command was:

```text
lake env lean -j2 -M6144 -DautoImplicit=false -DmaxHeartbeats=100000000 -DmaxRecDepth=1000000 AGStripQuantitative.lean
```

Both commands returned exit code 0. The complete quantitative rectangle assembly has 1,068 rectangles with 64 numeric nodes per rectangle. The final mathematical acceptance record is dated November 2, 2026 and identifies the original `13 / 10^10` theorem.

The [ordinary-build record extract](evidence/ordinary-build-records.json) retains the exact recorded command arrays, exits, log hashes, source hashes, and dependency bindings. It is explicitly a derived index. Unmodified full logs are provided in [`ordinary-kernel-check-evidence.zip`](https://github.com/zhangteng2000/Bloch-constant/releases/download/lean-formalization-2026-11-05/ordinary-kernel-check-evidence.zip); the complete raw history is in the six-part archive.

After extraction, the principal raw evidence is under:

```text
payload/AGStrip/logs/quantitative-lake-reproduction-20261101-001326-290592-recovery3-resume/
    status.json
    inputs.json
    module-results.jsonl
    final-acceptance.json
    final-statement-review.json
    original-axiom-audit.log
    quantitative-axiom-and-type-audit.log
```

The build began with an empty project build directory and continued through recorded interruption/resume boundaries. Earlier logs and failed historical attempts are preserved in the archive. The source manifest and recovery-chain validators bind this history to the delivered source; no historical exit code or log has been rewritten for publication.

`propext`, `Classical.choice`, and `Quot.sound` are the allowed standard axioms. The audited final declarations do not depend on `sorryAx` or additional mathematical axioms. The original Lean version output is included in [lean-version.log](evidence/lean-version.log).
