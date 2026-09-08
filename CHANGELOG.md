# Changelog

## [1.2.1] - 2026-09-04
### Added
- `shrinkwrap`: `Temporal Combined` mode — sweep meshes over a time range into one static
  envelope mesh (`startTime`, `endTime`, `timeStep`, `connectTimeSamples`).
- `editStageMetrics`: `stopAtSkeletonRoot` — correct a skeleton at its `SkelRoot` rather
  than at every prim beneath it.
- Performance validators: tunable parameters on `CoincidingGeometryChecker`,
  `ColocatedVerticesChecker`, `FlatHierarchiesChecker`, `HighVertexCountChecker`,
  `PrimitiveFitChecker`, `RedundantTimeSamplesChecker`, and `RtxMeshCountChecker`.
- Performance validators: mark the rule family `@multiprocess_safe`, so
  `usd-validation-nvidia --process COUNT` can pool it.
- `summarize_csv.py`: accept a `--json-output` report as well as a CSV.
- GitHub Pages workflows for the rendered docs, plus a CI doc-link checker.

### Changed
- `run-validators`: `--fix` now writes to `<stem>.fixed<ext>` (or `--fix-output <path>`);
  `--fix-in-place` overwrites the source as before.
- Performance validators: `WindingsChecker`, `ColocatedVerticesChecker`, and
  `ZeroAreaFacesChecker` declare explicit `meshCleanup` arguments instead of inheriting
  its six enabled defect categories.
- `tools/validators/run.{sh,bat}`: stop stripping `-v` / `--verbose`, which is upstream's
  own flag.
- Package `config_presets/` in the shipped drop; the docs and skills tell readers to run
  `usdOptimize -c config_presets/<name>.json`, but the presets shipped in no package.
- Pin the wheel's `usd-exchange` to `>=2.2,<3`; unpinned, it resolved 3.0.0 (OpenUSD 26.08)
  against a wheel built for 25.05.
- Raise the `usd-validation-nvidia` floor to `1.21.0` (was `1.19.3`).
- Bump `poetry` to 2.3.4 and `poetry-core` to 2.3.2 for CVE fixes.
- `merge` / `splitMeshes`: document the `mergePoint` values.
- Shorten the README, moving runbook material into `docs/`.

### Fixed
- CUDA detection on WSL: load `libcuda.so` instead of pre-checking sysfs for a PCI display
  adapter, which WSL does not expose. GPU work no longer falls back to CPU.
- Windows packages: stage the MaterialX runtime DLLs into `extraLibs`, without which any
  shader lookup failed to load.
- `usdOptimize` CLI: run shutdown callbacks on every exit, removing the
  `CUDA error: driver shutting down` abort on GPU runs.
- `usdOptimize` CLI: exit 0 from an explicit `-h` / `--help`, and stop consuming a
  flag-shaped final argument as the input path.
- `summarize_csv.py`: raise csv's field-size limit so very large fields still parse.
- Agent skills: correct validator exit codes, the `--fix` summary and folder restriction,
  an unreachable artifact-replay path, and the unknown-argument policy.
- Agent skills: move `version` under `metadata` and drop angle brackets from `description`,
  which fail frontmatter validation.
- Agent skills and guides: the `new-operation` template returned `OperationResult::eSuccess`,
  which has never existed, so the documented scaffold could not compile. Also corrected the
  validator-class naming row, `debug-operation`'s `-r`, `repo.bat ci format` (CI-only), the
  Windows `usdOptimize.bat` launcher, a stale path and a wrong "no `--fix` mode" claim in
  `interpret-validators`, and stale `PLUGINS.md` / `AGENTS.md` paths.
- `config_presets/safe-cleanup.json` and `memory-reduction.json` passed
  `considerInstanceability` to `deduplicateGeometry`, which declares no such argument.

## [1.1.2] - 2026-08-03
### Added
- `moveMaterials`: restore the operation dropped in the Kit Scene Optimizer migration,
  reimplemented Kit-free with `Sdf` namespace edits. Fixes the three presets that silently
  skipped it. Excluded roots now match exact prim names; the root prim is no longer retyped.

### Changed
- Bump `mesh_tools_lib` to `1.0.2.518900cd`.
- `findOccludedMeshes`: drop client-side zero-extent filtering and VisChecker exception
  handling now that mesh_tools handles degenerate input internally.

## [1.1.1] - 2026-07-13
### Changed
- `THIRD_PARTY_NOTICES.md`: align entries with the packman dependency pins
  (`omnimesh_ops_usd`, `mesh_tools_lib`, autouv-core, shrinkwrap_openvdb) and
  note the USD-version-specific pins.
- Ship `LICENSE` and `THIRD_PARTY_NOTICES.md` under `PACKAGE-LICENSES/` in
  published packages.

## [1.1.0] - 2026-07-13
### Fixed
- `generateScene`: skip empty clusters to avoid writing malformed prims.
- `meshCleanup`: skip zero-extent meshes during analysis to avoid a crash.

## [1.0.8] - 2026-07-10
### Added
- Standalone Python API docs for `UsdOptimizeCore`.
- Verbose per-prim reporting in performance validators — richer validator output for ops like `fitPrimitives`, `generateNormals`, `meshCleanup`, etc.

### Changed
- CI: do not gate package publish on `test_windows_1x_gpu` (backlogged Windows GPU runners).
- `flattenHierarchy`: preserve sole root prim / `defaultPrim` when flattening.

### Fixed
- `findOccludedMeshes`: skip zero-extent meshes to avoid CPU clustered-path crash.

## [1.0.4] - 2026-06-12
### Added
- Asset Validator parameters API: expose validator rule tuning so checker thresholds (e.g. `OccludedMeshesChecker`, `SmallMeshChecker`) can be configured via parameters.
- `MergeMeshes`: new spatial merge mode that welds coincident boundary vertices across seams.
- `DeduplicateGeometry`: new "Point Instancer" mode.
- `PrunePayloads`: option to avoid pruning unloaded payloads.
- `DeduplicateHierarchies`: support for nested instancing.

### Changed
- Renamed Scene Optimizer to Usd Optimize.
- Validators now register against capability requirements (e.g. `GeometryRequirements`, `HierarchyRequirements`, `MaterialsRequirements`) via the new plugin entry point instead of rule categories.
- Migrated the asset validator dependency to `usd-validation-nvidia`.
- Reduced default logging noise across operations.
- Improved performance of `PruneLeaves`.
- Reverted `repo_usd` pin to 5.0.26 (restores the stock build; the 5.0.34 exchange build trimmed link deps).
- Pin Visual Studio to 2019.
- Auto-generated documentation for Usd Optimize lib.
- Replaced unsafe sudo/rm guidance in validators skill.

### Fixed
- `DeduplicateHierarchies`: fix value variant grouping.
- `DiceMeshes`: fix irregular multi-axis cuts.
- Fix gcc13 build issues from stricter compiler checks (DGX Spark defaults to gcc13).

## [1.0.3] - 2026-05-28
### Fixed
- `FitPrimitive`: no longer incorrectly fits a cube primitive to hollow meshes (e.g. an extruded box). Such meshes are now left unchanged instead of being replaced by a solid cube.
- Remove primvar indices when removing primvars.

### Added
- Accept JSON int literals for `float`/`double` attributes.

### Changed
- Bumped `repo_usd` to 5.0.34.
- Use symlinks for Python files where possible during builds rather than copying them.

## [1.0.2] - 2026-05-27
### Fixed
- Removed `repo_kit_tools` from public facing dependencies

## [1.0.1] - 2026-05-26
### Fixed
- `DeduplicateGeometry`: preserve `MaterialBindingAPI` schemas on instance xforms so material bindings survive deduplication.
- `DeduplicateGeometry`: correct transform/pivot handling, including flipped duplicates.
- `CMakeLists.txt` corrections for consumer-side builds.
- `usd-deps` generation no longer leaves the working tree dirty in git.

### Added
- Test runner supports running individual Python tests; documented in the `testing` skill.

### Removed
- Unused `tests/` directory and `test_skill_docs.py`.

## [1.0.0] - 2026-05-22
### Changed
- Initial version.
