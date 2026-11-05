# Lean 4 formalization

This directory documents the completed ordinary Lean kernel checks for Theorem 1.1, Corollary 1.2, and Theorem 1.3 of the accompanying paper.

The pinned toolchain is `leanprover/lean4:v4.34.0-rc1`, Lean commit `3447a668783dbce1a8fdb97101dd067687b2b418`. The recorded author environment was `x86_64-w64-windows-gnu`, Release. All three final declarations use only `propext`, `Classical.choice`, and `Quot.sound`; the axiom audits exclude `sorryAx` and additional mathematical axioms from the audited declarations.

- [Statements and definitions](STATEMENTS.md)
- [Commands, exits, and evidence](VERIFICATION.md)
- [Download, verify, extract, and rebuild](REPRODUCTION.md)
- [Dependency revisions](DEPENDENCIES.md)
- [Windows preparation details](COMPATIBILITY.md)
- [Complete release](https://github.com/zhangteng2000/Bloch-constant/releases/tag/lean-formalization-2026-11-05) and [asset SHA-256 checksums](SHA256SUMS.txt)

The complete archive contains 160,985 payload files, 50 support files, and four metadata members. Its six compressed parts total 6,341,244,083 bytes; extraction writes 43,158,256,451 bytes. Nine Git dependencies are locked to exact commits. MRMT and Schoenflies local sources, provenance, and licenses are included. Compiled caches and installed Windows toolchain binaries are obtained or built separately.

The archive preserves the original evidence and its chronology. Current explanatory documents in this directory identify the ordinary kernel-checked mathematical results and the procedure for reproducing them. A checksum or extraction check verifies the delivered bytes; an independent Lean build checks the proofs in the recipient's environment.
