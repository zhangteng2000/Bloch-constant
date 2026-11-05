# Bloch constant: paper, certificates, and Lean formalization

This repository accompanies the paper [Bloch-constant-linked.pdf](Bloch-constant-linked.pdf). It provides the original numerical certificates and the Lean 4 formalization of **Theorem 1.1, Corollary 1.2, and Theorem 1.3**.

The three results have passed the recorded ordinary Lean kernel checks. Their audited axiom dependencies are `propext`, `Classical.choice`, and `Quot.sound`.

| Paper result | Lean declaration | Formal statement |
| --- | --- | --- |
| Theorem 1.1 | `AGStrip.main` | `MainClaim`: a normalized Ahlfors–Grunsky function and a normalized perturbation family with a strict linear decrease of the Bloch radius |
| Corollary 1.2 | `AGStrip.blochConstant_lt_AG` | `blochConstant < ENNReal.ofReal AG` |
| Theorem 1.3 | `AGStrip.original_quantitative_bloch_bound` | `blochConstant < ENNReal.ofReal (AG - (13 : ℝ) / 10^10)` |

Start with the [formalization guide](formalization/README.md), [exact statement map](formalization/STATEMENTS.md), [recorded verification evidence](formalization/VERIFICATION.md), and [reproduction instructions](formalization/REPRODUCTION.md).

The **[complete source and evidence release](https://github.com/zhangteng2000/Bloch-constant/releases/tag/lean-formalization-2026-11-05)** contains the full proof project, local dependency sources and licenses, numerical resources, build logs, and integrity manifests. Download all six archive parts and the three accompanying manifests. The files under `formalization/entry/` are byte-identical entry points for browsing; the complete import closure is in the release.

The original [README.txt](README.txt) describes the numerical-certificate distribution predating this Lean addition. Its original files and checksums are retained.
