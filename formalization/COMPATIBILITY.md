# Windows preparation and archive compatibility

Original failed attempts and their logs remain in the evidence history. Accepted source, final acceptance records, and all six completed archive parts are unchanged.

## Publication metadata cache

The first packager rejected 2,709,112,849 logical bytes of recovery metadata against its 2 GiB aggregate bound before writing an archive. The reviewed candidate retained all 93 original member paths and verified each member separately. It shares immutable raw-byte storage only after digest, size, and full-byte equality checks: 72 distinct contents occupy 1,571,856,049 bytes. The single-file 512 MiB and distinct-content 2 GiB limits remain. This changes cache accounting, not total Python memory limits, evidence inclusion, or a mathematical check. Fourteen new component tests passed before successful real packaging.

## Windows bootstrap tool inputs

The first dependency bootstrap stopped because the selected Git and PowerShell executables had two hard links and violated its unchanged input predicate. The continuation selected byte-identical single-link installed `Git/bin/git.exe` and a verified ordinary-copy PowerShell home. All 788 copied files were read back and tested before use.

The PowerShell executable still resolves `PSHOME` to installed Windows PowerShell and uses installed Windows/.NET components. This is not a portable or isolated Windows runtime. Windows binaries are excluded from publication. The unchanged bootstrap completed all 423 commands, checked nine Git commits and tracked cleanliness, and prepared both local dependencies. It did not run a main-project build.

