# Pinned proof environment

The toolchain is `leanprover/lean4:v4.34.0-rc1`, commit `3447a668783dbce1a8fdb97101dd067687b2b418`. The lock file is [lake-manifest.json](entry/lake-manifest.json).

| Dependency | Repository | Exact revision |
| --- | --- | --- |
| mathlib | https://github.com/leanprover-community/mathlib4 | `de5ce8a9a66a4aa68a9bdbb35b63a06d34d9ca11` |
| plausible | https://github.com/leanprover-community/plausible | `38e9c3ce15cbb63c92e90bb9a92e4eb82131f669` |
| LeanSearchClient | https://github.com/leanprover-community/LeanSearchClient | `2bc7cf064315b26bc38dac2e9612fb581be9b75f` |
| importGraph | https://github.com/leanprover-community/import-graph | `978b7ec9fbbf9a535114f1de8fe5b3778b358870` |
| proofwidgets | https://github.com/leanprover-community/ProofWidgets4 | `99e8adeea3c3cd86b6b79ba01a1383bf2d31d055` |
| aesop | https://github.com/leanprover-community/aesop | `c1c4362a130f12e632d252180a6c2a31d8fd4726` |
| Qq | https://github.com/leanprover-community/quote4 | `3b55e9d00c6b0018e5d984eb011b6f93c09bd163` |
| batteries | https://github.com/leanprover-community/batteries | `01bc479e7432594821ba3fb0ca465211941de86d` |
| Cli | https://github.com/leanprover/lean4-cli | `af8bc067a4cc6c6df472a68909a3f40b1c76c43e` |

The archive also includes the MRMT and Schoenflies local dependency closures and licenses, with 214 and 128 provenance-bound proof modules respectively. Publication support modules required by those closures are identified separately in the manifest.

The recorded extracted-project dependency bootstrap completed 423 commands with exit code 0, verified the nine Git revisions and tracked cleanliness, and prepared both local dependencies. Dependency preparation precedes the main Lean build. See [reproduction](REPRODUCTION.md) and [Windows input requirements](COMPATIBILITY.md).
