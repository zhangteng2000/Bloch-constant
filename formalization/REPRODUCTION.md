# Archive verification and reproduction

Use Python 3.11 or later and pinned Lean `leanprover/lean4:v4.34.0-rc1`. The author's recorded Python runtime was 3.12.14. Supplied bootstrap execution is Windows-specific; no cross-platform reproduction result is claimed.

Download all six `source-evidence.tar.gz.partNNNNN` assets, `package-manifest.json`, `publication-manifest.json`, and `support-inventory-complete.json` into one new directory. The optional `ordinary-kernel-check-evidence.zip` provides convenient access to the principal ordinary build logs. Inspect the checksums and support source before execution.

## 1. Verify without original source paths

From a repository checkout, set your absolute download path in this PowerShell example:

```powershell
$agPackage = 'E:/your-new-download-directory'
python -B formalization/tools/verify_source_package.py --package-dir $agPackage --package-manifest-sha256 36bb615d937d818e722fa158943b389f70e4a26f31e7fcb6b84ac8a086c83af2 --manifest "$agPackage/publication-manifest.json" --manifest-sha256 2c58f195e352bed324f67304a9211fce2160dfb3b7fe4638fed4ebd5af4bc82f --support-inventory "$agPackage/support-inventory-complete.json" --support-inventory-sha256 279e5aa84b892630772422005b0951e5464586a7e32d4b70c32a59b76bf66d79
```

This verifies archive bytes, members, recovery metadata, and historical bindings. It does not run Lean or extract files.

## 2. Extract and read back every written byte

Choose an absent extraction directory with room for 43,158,256,451 extracted bytes plus later dependencies and builds. Supply the reviewed repository tools as a trusted runtime.

```powershell
$agTools = (Resolve-Path 'formalization/tools').Path
$agExtract = 'E:/your-new-extraction-directory'
python -B formalization/tools/safe_extract_package.py --package-dir $agPackage --package-manifest-sha256 36bb615d937d818e722fa158943b389f70e4a26f31e7fcb6b84ac8a086c83af2 --manifest "$agPackage/publication-manifest.json" --manifest-sha256 2c58f195e352bed324f67304a9211fce2160dfb3b7fe4638fed4ebd5af4bc82f --support-inventory "$agPackage/support-inventory-complete.json" --support-inventory-sha256 279e5aa84b892630772422005b0951e5464586a7e32d4b70c32a59b76bf66d79 --packager-v4-dir $agTools --output-dir $agExtract
```

The complete project is at `$agExtract/payload/AGStrip`. The extractor rejects unsafe paths, links, overwrites, missing members, and incorrect bytes, then reads back all written members.

## 3. Prepare locked dependencies

The bootstrap validates the extracted inventory and raw recovery chain. Without `--execute` it only emits a plan. Choose a new report directory outside the extraction:

```powershell
$agVerifier = (Resolve-Path 'formalization/author-host/verify-ahlfors-final-evidence-readonly.py').Path
$agDependencyReport = 'E:/your-new-dependency-report'
python -B formalization/tools/dependency_bootstrap.py --extraction-root "$agExtract/payload" --manifest "$agPackage/publication-manifest.json" --manifest-sha256 2c58f195e352bed324f67304a9211fce2160dfb3b7fe4638fed4ebd5af4bc82f --verification-script $agVerifier --recovery-validator "$agTools/publication_recovery_inventory.py" --lineage-verifier "$agTools/interrupted_build_lineage.py" --report-dir $agDependencyReport
```

For actual preparation, choose a different new report directory and add `--execute --git-exe ABS_GIT_EXE --lake-exe ABS_LAKE_EXE --powershell-exe ABS_POWERSHELL_EXE` with inspected absolute installed tool paths. Git, PowerShell, Lake, and adjacent Lean must meet unchanged input checks, including single-link files. Read [Windows input limitations](COMPATIBILITY.md). The verifier argument authenticates historical bindings; the bootstrap does not execute that author-host verifier.

Nine external Git dependencies are fetched at exact lock commits. MRMT and Schoenflies sources and licenses are already in the archive. The bootstrap prepares dependencies only and requires main build directories to stay absent. The original bootstrap wrapper also runs a main build, so it is a different operation.

## 4. Reproduce the mathematical build separately

After dependency preparation, use the complete extracted project in a new working directory. Leave its configured main build directory empty, then run from `payload/AGStrip`:

```powershell
lake env python scripts/build-quantitative.py --jobs 3 --require-empty
```

The builder checks the mathematical modules and invokes the root audits. On Windows/NTFS, `--compress-new-artifacts` is an optional disk setting. The recorded full build contains 79,902 module results and can require substantial time and disk space.

Do not run the original `scripts/bootstrap.ps1` first and then expect `--require-empty` to succeed: that wrapper also builds the main project. Prepare dependencies separately as above. Use a new extraction or working directory instead of deleting existing proof artifacts or evidence.

The delivered acceptance is a recorded author-host result. Archive verification and dependency preparation are independently documented operations; a new full Lean build is the proof check in the recipient's environment. No unperformed cross-platform or second-machine build is claimed.
