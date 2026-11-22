---

description: "Task list for Building Landmark Visibility"
---

# Tasks: Building Landmark Visibility

**Input**: Design documents from `/specs/001-building-visibility/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. Constitution Principle II requires tests to be written first, and the spec
requires hand-worked fixtures (FR-019, SC-001). Within each story, write the tests first and
confirm they fail before implementing.

**Organization**: Tasks are grouped by user story, so each story can be built and tested on its
own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are relative to the repository root, using the single-project layout from plan.md.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies, tooling and directory layout

- [x] T001 Add `rasterio` as a runtime dependency and `mypy` as a dev dependency with `uv add rasterio` and `uv add --dev mypy`, updating `pyproject.toml` and `uv.lock` (research R8)
- [x] T002 Add `[project.scripts] bridgeview = "bridgeview.cli:main"` and a `[tool.mypy]` section (`strict = true`, `files = ["src"]`, and ignore missing imports for `rasterio.*` and `shapely.*` only if their stubs are missing) to `pyproject.toml`
- [x] T003 [P] Add a `uv run mypy` step after `uv sync --locked` in `.github/workflows/ci.yml`. This closes pre-merge gate 3 (plan, Constitution Check V).
- [x] T004 [P] Add `data/` to `.gitignore`
- [x] T005 [P] Create the test layout `tests/unit/`, `tests/property/`, `tests/acceptance/` and `tests/fixtures/scenes/`, with a shared `tests/conftest.py` that exposes a `scenes_dir` fixture path

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The CLI shell and version plumbing that every story builds on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Write `tests/unit/test_cli.py`, testing that unknown subcommands and missing required options exit `2`, and that an `error:` line goes to stderr (contracts/cli.md)
- [x] T007 Implement the argparse skeleton in `src/bridgeview/cli.py`, with `main(argv: list[str] | None = None) -> int`. It has `download`, `compute` and `snapshot-buildings` subcommands, stub handlers that raise `NotImplementedError`, and a shared error handler that prints `error: <message>` to stderr and returns exit codes 0, 1 or 2 per contracts/cli.md.
- [x] T008 [P] Expose `__version__` in `src/bridgeview/__init__.py` from `importlib.metadata.version("bridgeview")`. Remove the placeholder `hello()` and update `tests/test_smoke.py` to assert that `__version__` is a non-empty string.

**Checkpoint**: `uv run bridgeview --help` works, and CI is green with mypy.

---

## Phase 3: User Story 1 - Visibility for a small, hand-checkable scene (Priority: P1) 🎯 MVP

**Goal**: Compute per-building, per-landmark visibility for a fixture scene and write the
results CSV.

**Independent Test**: `uv run pytest tests/acceptance` passes on all 10 fixture scenes with no
downloaded data (quickstart §1).

### Tests for User Story 1 ⚠️ (write first, confirm they fail)

Each fixture is a pair of files, `tests/fixtures/scenes/<name>.toml` and
`<name>.expected.csv`, in the format of contracts/scene-fixture.md. Each `.toml` starts with a
comment block showing the full hand calculation. Use `curvature = false` except in the
`curvature` scene.

- [x] T009 [P] [US1] Fixture `three_boxes_blocked`: A, B and C in a row, with B above the A→t1 line, so A is `not_visible` with `t1=building:B` (US1 scenario 1)
- [x] T010 [P] [US1] Fixture `three_boxes_clear`: the same row with B below the line, so A is `visible` (US1 scenarios 2 and 3)
- [x] T011 [P] [US1] Fixture `grazing`: the A→t1 line passes exactly through B's top edge, so it is not blocked (FR-006)
- [x] T012 [P] [US1] Fixture `self_block`: the observer's `top_z` is above its `viewpoint_z`, and it is still `visible` (FR-005, US1 scenario 4)
- [x] T013 [P] [US1] Fixture `two_points`: one landmark with points t1 (blocked by B) and t2 (clear), so it is `visible`, `visible_points=t2` and `blockers=t1=building:B` (US1 scenario 5)
- [x] T014 [P] [US1] Fixture `ground_ridge`: a ground grid with a ridge above the line, so the blocker is `ground` (US1 scenario 6, FR-004)
- [x] T015 [P] [US1] Fixture `courtyard`: a U-shaped footprint whose centroid falls in the courtyard. The viewpoint is at the centroid, and a neighbour in the courtyard blocks as normal (clarification Q2, spec Edge Cases).
- [x] T016 [P] [US1] Fixture `curvature`: flat ground at 0 with observer and target at 1 m and 10 km apart, so the ground blocks only because of curvature. The hand calculation is `(1−k)·D²/(8R) ≈ 1.71 m > 1 m` (FR-007, research R4).
- [x] T017 [P] [US1] Fixture `target_in_footprint`: t1 lies inside building L, whose `top_z` is above t1. A's view of t1 is not blocked by L, while a taller building M between A and L does block it (spec Edge Cases: a landmark's own structure).
- [x] T018 [P] [US1] Fixture `zero_height`: building Z has `viewpoint_z = ground_z`, so it is `not_evaluated` with `missing_height`, and it doesn't block A, even though its `top_z` is above the A→t1 line (spec Edge Cases: missing or invalid height; data-model.md `Building.evaluable`)
- [x] T019 [US1] Write the acceptance test `tests/acceptance/test_fixture_scenes.py`. It is parametrised over every `*.toml` in `tests/fixtures/scenes/`, runs `cli.main(["compute", "--scene", …, "--out", tmp])`, and asserts the output is byte-identical to `<name>.expected.csv`, ignoring the `software_version` column.
- [x] T020 [P] [US1] Write unit tests in `tests/unit/test_sightline.py` for the curvature drop, the corrected target height, and the exact maximum of the downward-curving clearance over a stretch, including a peak inside the stretch (data-model.md SightLine; research R6)
- [x] T021 [P] [US1] Write unit tests in `tests/unit/test_ground.py` for bilinear sampling on a small grid, the constant plane, and NaN outside the grid or on nodata (data-model.md `GroundModel.origin_x`, `GroundModel.origin_y`, `GroundModel.resolution`, `GroundModel.z`)
- [x] T022 [P] [US1] Write unit tests in `tests/unit/test_results.py` for the column order, fixed decimals, sorting, `;` and `=` encoding, and every invariant in contracts/results-csv.md (data-model.md `VisibilityResult.status`, `VisibilityResult.visible_points`, `VisibilityResult.blockers`)
- [x] T023 [P] [US1] Write Hypothesis properties in `tests/property/test_monotonicity.py` on random box scenes. Raising any non-observer building's `top_z` never turns blocked into visible. Removing a building never turns visible into blocked. Raising the observer's `viewpoint_z` never turns visible into blocked. A building never appears in its own blockers (plan, Constitution Check II).

### Implementation for User Story 1

- [x] T024 [P] [US1] Implement `Building`, `Landmark`, `ReferencePoint` and `Scene` as frozen dataclasses in `src/bridgeview/scene.py`, with `load_scene(path) -> Scene` for the fixture TOML format. Each field follows data-model.md: `Building.building_id`, `Building.footprint`, `Building.viewpoint_z`, `Building.top_z`, `Building.ground_z`, `Landmark.id`, `Landmark.name`, `ReferencePoint.id`, `ReferencePoint.lat`, `ReferencePoint.lon`, `ReferencePoint.z`, `ReferencePoint.source` and `landmarks_version`. Fixtures give `x` and `y` in place of `lat` and `lon`, per contracts/scene-fixture.md. Compute data-model.md `Building.viewpoint` (the centroid, even when outside the footprint) and `Building.evaluable` (reasons `invalid_geometry` or `missing_height`). Set data-model.md `Scene.dataset_version` and `Scene.landmarks_version`; for fixtures, `landmarks_version` is optional and defaults to `"fixture"`. Reject a missing `crs` or any `crs` other than EPSG:26910 (Constitution IV).
- [x] T025 [P] [US1] Implement `GroundModel` in `src/bridgeview/ground.py`, with `constant(z)` and `from_grid(origin_x, origin_y, resolution, z)` constructors and a vectorised `sample(x, y) -> ndarray` (data-model.md `GroundModel.origin_x`, `GroundModel.origin_y`, `GroundModel.resolution`, `GroundModel.z`)
- [x] T026 [US1] Implement the sight-line maths and building blocking in `src/bridgeview/visibility.py`:
  - The constants k = 0.13, R = 6,371,000 m and margin = 0.001 m.
  - Build an `STRtree` over the evaluable footprints and run a vectorised `query` against the lines.
  - For each crossed footprint, find the stretch of line inside it and the exact maximum clearance over that stretch.
  - Exclude the observer's own footprint (FR-005), and any footprint that contains the target's x and y (spec Edge Cases: a landmark's own structure).
  - Not-evaluated buildings are not obstructions.

  (data-model.md SightLine; research R6 step 1)
- [x] T027 [US1] Add ground blocking to `src/bridgeview/visibility.py`: sample every 1 m from 2 m to `d_total − 2 m`, and block when the corrected ground is more than the margin above the line. Choose the first blocker as the one nearest the observer, then combine the points into per-landmark results (data-model.md `VisibilityResult.status`, `VisibilityResult.visible_points`, `VisibilityResult.blockers`; research R6 steps 2 and 3). Expose `compute_visibility(scene, workers=None)`, which runs serially for now.
- [x] T028 [P] [US1] Implement `BuildingResult`, `RunMeta` and `write_results_csv` in `src/bridgeview/results.py`, following contracts/results-csv.md exactly. Reproject viewpoints from EPSG:26910 to EPSG:4326 with pyproj (`always_xy=True`), and write to `path.tmp` before renaming.
- [x] T029 [US1] Wire `compute --scene FILE --out FILE` in `src/bridgeview/cli.py`. Write data-model.md `Scene.dataset_version` and `Scene.landmarks_version` into `RunMeta`.
- [x] T030 [US1] Re-export the public API (`load_scene`, `compute_visibility`, `write_results_csv`, `Scene`, `BuildingResult` and `RunMeta`) from `src/bridgeview/__init__.py`, with typed docstrings that state units (Constitution V)

**Checkpoint**: All fixture, unit and property tests pass, and the MVP is usable on any
hand-built scene.

---

## Phase 4: User Story 2 - Obtain the city data reproducibly (Priority: P2)

**Goal**: `bridgeview download` fetches the pinned building snapshot and four elevation tiles,
then verifies their sizes and SHA-256 hashes.

**Independent Test**: quickstart §2. The first run prints `ok` for every pin, the second prints
`skip`, and a tampered file fails with a checksum error.

### Tests for User Story 2 ⚠️

- [ ] T031 [P] [US2] Write unit tests in `tests/unit/test_pins.py` against a local `http.server` fixture serving small files. They cover: a fresh download prints `ok`; a second run prints `skip` with no request made; a size mismatch and a hash mismatch both exit 1 and leave no `.part` or final file; `verify_pins` raises `ChecksumError` on a tampered file; and a malformed `datasets.toml` is rejected. The rejection cases are a bad `sha256` length, a non-HTTPS `url`, and a missing provenance field (data-model.md `DatasetPin.id`, `DatasetPin.url`, `DatasetPin.sha256`, `DatasetPin.size`, `DatasetPin.filename`, `DatasetPin.source`, `DatasetPin.license`, `DatasetPin.retrieved`).
- [ ] T032 [P] [US2] Write unit tests in `tests/unit/test_snapshot.py` for `snapshot-buildings`, against a local `http.server` fixture standing in for the DataSF export URL, with the URL made configurable for tests. Running it twice on the same input gives byte-identical gzip output with the same printed size and SHA-256, because `mtime=0`. An HTTP error exits 1 and leaves no output file.

### Implementation for User Story 2

- [ ] T033 [US2] Implement `src/bridgeview/pins.py`. It loads and validates `datasets.toml` with `tomllib` (data-model.md `DatasetPin.id`, `DatasetPin.url`, `DatasetPin.sha256`, `DatasetPin.size`, `DatasetPin.filename`, `DatasetPin.source`, `DatasetPin.license`, `DatasetPin.retrieved`). `download_all(data_dir)` streams each file to `.part`, checks the size and then the SHA-256, and renames on success. `verify_pins(data_dir)` raises `ChecksumError`. Network access uses `urllib.request` only, with a generic `User-Agent: bridgeview/<version>`.
- [ ] T034 [US2] Wire `download [--data-dir DIR]` in `src/bridgeview/cli.py`, with the output lines and error messages from contracts/cli.md
- [ ] T035 [US2] Implement the maintainer command `snapshot-buildings --out FILE` in `src/bridgeview/pins.py` and `src/bridgeview/cli.py`. It downloads the DataSF `ynuv-fyni` GeoJSON export, writes it gzip-compressed with `mtime=0`, and prints its size and SHA-256 (contracts/cli.md).
- [ ] T036 [P] [US2] Write `docs/data-sources.md`, covering each dataset's source URL, version or date, license (PDDL 1.0 or public domain), retrieval date and purpose. Also credit OpenStreetMap (ODbL) for the landmark positions (FR-012; research R1, R2 and R5).
- [ ] T037 [US2] Once T036 has recorded provenance (constitution: provenance comes before use), create the data pins in `datasets.toml`:
  1. Run `snapshot-buildings`.
  2. **With the owner's approval**, publish the file as a GitHub Release asset under the tag `data-buildings-<YYYYMMDD>`.
  3. Download the four USGS tiles listed in research R2 and record their sizes and SHA-256 hashes.

  Fill in every field (data-model.md `DatasetPin.id`, `DatasetPin.url`, `DatasetPin.sha256`, `DatasetPin.size`, `DatasetPin.filename`, `DatasetPin.source`, `DatasetPin.license`, `DatasetPin.retrieved`).
- [ ] T038 [US2] Run quickstart §2 by hand and record the outcome in the PR description

**Checkpoint**: The city data can be reproduced on any machine, and tampering is detected.

---

## Phase 5: User Story 3 - City-wide visibility results (Priority: P3)

**Goal**: `bridgeview compute --city` produces the full 177,023-row results CSV in under 1
hour, and reruns are byte-identical.

**Independent Test**: quickstart §3 and §4.

**Depends on**: US1, for the engine and CSV writer, and US2, for the pinned data.

### Tests for User Story 3 ⚠️

- [ ] T039 [P] [US3] Write unit tests in `tests/unit/test_city_loader.py` against a tiny synthetic gzip GeoJSON using DataSF field names. They cover the reprojection from EPSG:4326 to EPSG:26910 and the field mapping (`median_1st_m` → data-model.md `Building.viewpoint_z`, `peak_1st_m` → `Building.top_z`, `gnd_min_m` → `Building.ground_z`, `sf16_bldgid` → `Building.building_id`). They also cover `top_z < viewpoint_z` being raised with a warning, and the reasons `invalid_geometry`, `missing_height` (including a zero-height building where `median_1st_m` equals `gnd_min_m`), `viewpoint_outside_elevation_model` and `viewpoint_below_ground`. The mapping also sets data-model.md `Scene.dataset_version` to the pin ids joined with `+`.
- [ ] T040 [P] [US3] Write unit tests in `tests/unit/test_ground_tiles.py` that write two small adjacent GeoTIFFs with rasterio, then check that the mosaic, the crop to the extent plus a buffer, the `.npy` cache reuse, and nodata-to-NaN all work (data-model.md GroundModel)
- [ ] T041 [P] [US3] Write a determinism test in `tests/acceptance/test_determinism.py` that runs a generated scene of 200 random boxes with `workers=1` and `workers=3`, and asserts byte-identical output (FR-018, SC-005)
- [ ] T042 [P] [US3] Write unit tests in `tests/unit/test_landmarks.py` for the packaged `landmarks.toml` loader. It loads exactly 13 points across `golden_gate`, `alcatraz` and `bay_bridge`, with unique ids that contain no `;`, `=` or `,`, and every point has a non-empty `source`. The WGS84 → EPSG:26910 conversion of `ggb_south_tower` round-trips to within 1 cm (data-model.md `ReferencePoint.id`, `ReferencePoint.lat`, `ReferencePoint.lon`, `ReferencePoint.source`, `landmarks_version`).
- [ ] T043 [P] [US3] Write CLI tests in `tests/unit/test_cli_city.py` for `compute --city` against a temporary data directory with a tiny `datasets.toml` and matching files. One appended byte to a pinned file makes it exit 1 with `error: checksum mismatch`, and neither `--out` nor `--out.tmp` is created (SC-006, FR-010).

### Implementation for User Story 3

- [ ] T044 [US3] Implement `GroundModel.from_tiles(paths, extent, cache_dir)` in `src/bridgeview/ground.py`. It mosaics the GeoTIFFs with rasterio, asserting that their CRS is EPSG:26910 (research R3). It crops to the buildings' extent plus 500 m, converts nodata to NaN, and saves `data/cache/ground_<hash>.npy`, then reopens it with `mmap_mode="r"` (data-model.md GroundModel).
- [ ] T045 [US3] Implement `load_city_scene(data_dir)` in `src/bridgeview/scene.py`. It reads the pinned gzip GeoJSON through pyogrio and reprojects from EPSG:4326 to EPSG:26910, documenting both CRSs (Constitution IV). It maps fields per data-model.md (`Building.building_id`, `Building.footprint`, `Building.viewpoint_z`, `Building.top_z`, `Building.ground_z`), builds the GroundModel, and applies the `missing_height`, `viewpoint_outside_elevation_model` and `viewpoint_below_ground` reasons (data-model.md `Building.evaluable`). It sets data-model.md `Scene.dataset_version` by joining the pin ids with `+`, and `Scene.landmarks_version` from `landmarks.toml`.
- [ ] T046 [US3] Check that the elevation model has data, not nodata, over Alcatraz, Treasure Island and Yerba Buena Island. Record the result in research.md R2 and list any gaps in `docs/data-sources.md`.
- [ ] T047 [US3] Write `src/bridgeview/landmarks.toml`, with `landmarks_version = "1"` and the 13 reference points from research R5, each with a `source` (data-model.md `Landmark.id`, `Landmark.name`, `ReferencePoint.id`, `ReferencePoint.lat`, `ReferencePoint.lon`, `ReferencePoint.z`, `ReferencePoint.source`). Choose the four Alcatraz shore points from the elevation model and building footprints, using ground + 2 m from the T044 GroundModel. Add a loader in `src/bridgeview/scene.py` that reads it with `importlib.resources`.
- [ ] T048 [US3] Add the parallel driver to `compute_visibility` in `src/bridgeview/visibility.py`. It uses a `multiprocessing` pool (fork on Linux, spawn-safe elsewhere) over fixed-size, sorted batches of observers, with the memory-mapped ground cache shared between workers. Results are merged in `building_id` order, so the output doesn't depend on `workers`.
- [ ] T049 [US3] Wire `compute --city --out FILE [--data-dir] [--workers]` in `src/bridgeview/cli.py`. Call `verify_pins` first, and exit 1 before writing anything on failure (SC-006). Write to `FILE.tmp` and then rename.
- [ ] T050 [US3] Benchmark a random subset of 5,000 buildings and extrapolate to the full city. If the estimate exceeds 1 hour on 8 cores, add the raster pre-filter fallback from research R6 in `src/bridgeview/visibility.py`, keeping the exact check for the final decision. Record the timings in research.md R6.
- [ ] T051 [US3] Run quickstart §3 in full: the run time, the identical-rerun check, and 177,024 lines. Record the results in the PR description.

**Checkpoint**: All three stories work, and the results CSV is ready for the web-page feature.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T052 [P] Audit the public functions in `src/bridgeview/` for type annotations and docstrings that state inputs, outputs, units and CRS, so that `uv run mypy` passes in strict mode (Constitution V)
- [ ] T053 [P] Add a "Usage" section to `README.md` covering `download`, `compute --scene`, `compute --city` and the CSV contract link
- [ ] T054 Confirm coverage is at least 90% with `uv run pytest`, and add unit tests for any uncovered branches in `src/bridgeview/`
- [ ] T055 Run `uv run mutmut run` on `src/bridgeview/visibility.py`. Add tests that kill the surviving mutants, or list the accepted survivors with reasons in research.md (Constitution II).
- [ ] T056 The owner runs the quickstart §4 spot check of 20 random buildings and records the score against SC-003 (at least 18 of 20) in the PR description

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup, and blocks all user stories.
- **US1 (Phase 3)**: depends on Foundational only.
- **US2 (Phase 4)**: depends on Foundational only, and is independent of US1.
- **US3 (Phase 5)**: depends on US1 (engine and CSV) and US2 (pinned data).
- **Polish (Phase 6)**: depends on US3.

### Within Each Story

- Fixtures and tests come before implementation, and should fail first.
- In US1: T024 and T025 (scene and ground) → T026 → T027 (visibility) → T029 (CLI). T028 (results) can run alongside T024 to T027.
- In US2: T033 → T034 → T035 → T037, and T036 must finish before T037.
- In US3: T044 → T045 → T047, with T046 after T044. Then T048 → T049 → T050 → T051.

### Parallel Opportunities

- Setup: T003, T004 and T005.
- US1: all ten fixtures (T009 to T018) and the unit and property tests (T020 to T023) in parallel; then T024, T025 and T028 together.
- US1 and US2 can be developed in parallel once Phase 2 is done.
- US3 tests: T039, T040, T041, T042 and T043.

---

## Parallel Example: User Story 1

```bash
# Hand-worked fixtures (independent files):
Task: "Fixture three_boxes_blocked in tests/fixtures/scenes/three_boxes_blocked.toml"
Task: "Fixture grazing in tests/fixtures/scenes/grazing.toml"
Task: "Fixture ground_ridge in tests/fixtures/scenes/ground_ridge.toml"

# Then the independent modules:
Task: "Scene dataclasses and load_scene in src/bridgeview/scene.py"
Task: "GroundModel in src/bridgeview/ground.py"
Task: "CSV writer in src/bridgeview/results.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phases 1 and 2: setup and the CLI shell.
2. Phase 3: fixtures, then the engine and CSV.
3. **Stop and validate**: the owner reviews the hand calculations in each fixture. That review
   is the main correctness check.
4. Open a PR. CI runs all fixture and property tests, with no data download.

### Incremental Delivery (one PR per phase is recommended)

1. Setup + Foundational → PR
2. US1 → PR (MVP: a working, checkable engine)
3. US2 → PR (includes the first data release, which needs owner approval)
4. US3 → PR (the city results; quickstart §3 numbers in the description)
5. Polish → PR (mutmut, spot check)

---

## Notes

- Never commit `data/`; CI must never download city data.
- The owner should check the hand calculation in each fixture `.toml`. `/tests/` is in
  CODEOWNERS, so every fixture change needs the owner's review.
- Commit after each task or logical group, with one logical change per commit (constitution).
