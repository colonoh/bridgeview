# Implementation Plan: Building Landmark Visibility

**Branch**: `001-building-visibility` | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-building-visibility/spec.md`

## Summary

For every San Francisco building, compute whether a straight sight line from its roof
reaches any reference point on the Golden Gate Bridge, Alcatraz or the Bay Bridge. Other
buildings and the bare ground can block the line, and the calculation allows for Earth
curvature and refraction. The building data is a pinned snapshot of DataSF's LiDAR-attributed
footprints. The ground is the pinned USGS 1 m bare-earth elevation model. Sight lines are
checked exactly against footprint polygons, and the ground is sampled every 1 m along each
line. The result is one deterministic CSV with a row per building, recording what blocked
each blocked point. Small hand-worked fixture scenes in TOML drive acceptance tests. See
[research.md](research.md).

## Technical Context

**Language/Version**: Python 3.14 (`.python-version`, `requires-python = ">=3.14"`)

**Primary Dependencies**: shapely 2.2, geopandas 1.2 with pyogrio, pyproj 3.8, numpy 2.5,
and **rasterio** (new, for the elevation GeoTIFFs; see research R8). The standard library's
`tomllib`, `hashlib`, `urllib`, `multiprocessing` and `csv` cover the rest.

**Storage**: Files only. Downloaded data goes in `data/raw/` and derived caches in
`data/cache/`, both gitignored. The pins are in `datasets.toml`, and the landmarks in
`src/bridgeview/landmarks.toml`.

**Testing**: pytest with pytest-cov at a 90% floor; Hypothesis for property tests; mutmut on
`visibility.py` before a release is tagged. Static type checking uses **mypy** (new dev
dependency).

**Target Platform**: A Linux or macOS developer laptop, plus GitHub Actions `ubuntu-latest`
for CI, which runs fixtures only.

**Project Type**: A Python library with a CLI (`bridgeview` console script), run as a batch
job.

**Performance Goals**: The city-wide run finishes in under 1 hour on 8 cores (SC-004). A
fixture scene runs in under 1 second.

**Constraints**: Reruns are byte-identical (FR-018). Peak memory stays under about 4 GB,
since the elevation cache is memory-mapped and shared between workers. CI downloads no city
data.

**Scale/Scope**: 177,023 buildings, 13 reference points, about 2.3M sight lines, and a 1 m
elevation grid of about 15 × 15 km.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | How the plan complies |
|---|---|---|
| I. Specification-driven | ✅ | Spec 001 is clarified. Every module traces to the spec's FRs, and tasks.md comes next. |
| II. Test-first, 90% coverage | ✅ | Hand-worked fixtures are written before the engine. Hypothesis properties: raising an obstruction never turns blocked into visible; removing a building never turns visible into blocked; raising the observer never turns visible into blocked when curvature is off. Coverage stays at the existing 90% gate. mutmut runs on `visibility.py` before a release is tagged. |
| III. Reproducible environments | ✅ | New dependencies are added with `uv add` and locked in `uv.lock`. The data is pinned by SHA-256 in `datasets.toml`. |
| IV. Explicit CRS and units | ✅ | All computation is in EPSG:26910 metres, heights in NAVD88 metres, and output in EPSG:4326. Every geometry loader states its source and target CRS, and fixtures declare `crs`. See research R3. |
| V. Typed, documented interfaces | ⚠ → ✅ | The public functions are typed and have docstrings with units. **Gap**: CI has no type check yet. The plan adds mypy (strict on `src/`) as a CI step, which closes pre-merge gate 3. |
| Data provenance | ✅ | `docs/data-sources.md` and `datasets.toml` record source, version, date and license, before first use. |
| New runtime dependency justified | ✅ | rasterio (research R8). |
| Computation separable from presentation | ✅ | The CSV is the only interface, and there is no web code in this feature. |

**Observer height**: the observer uses `median_1st_m`, as decided by the owner on 2026-11-22.
FR-001 has been updated to match. The 2010 vintage of the heights is a documented limitation
(research R1).

**Post-design re-check**: ✅ The design adds no new principle violations. The type-check gap
is planned as a task.

## Project Structure

### Documentation (this feature)

```text
specs/001-building-visibility/
├── plan.md              # This file
├── research.md          # Phase 0: data sources, CRS, algorithm, format decisions
├── data-model.md        # Phase 1: entities and rules
├── quickstart.md        # Phase 1: end-to-end validation steps
├── contracts/
│   ├── cli.md           # bridgeview download / compute / snapshot-buildings
│   ├── results-csv.md   # Output contract for the web page
│   └── scene-fixture.md # Hand-worked fixture format and required scenes
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
datasets.toml                    # DatasetPin entries (url, sha256, size, provenance)
docs/
└── data-sources.md              # Provenance and licenses (FR-012)
src/bridgeview/
├── __init__.py                  # Public API re-exports and __version__
├── cli.py                       # argparse entry point: download, compute, snapshot-buildings
├── pins.py                      # Reads datasets.toml, downloads, verifies sha256 (FR-009/010)
├── landmarks.toml               # Reference points with sources (FR-008)
├── scene.py                     # Building, Landmark, GroundModel, Scene; loads fixtures and the city
├── ground.py                    # GroundModel: tile mosaic, crop, .npy cache, bilinear sampling
├── visibility.py                # Sight-line maths, building and ground blocking, parallel driver
└── results.py                   # BuildingResult, deterministic CSV writer
tests/
├── test_smoke.py                # Existing
├── unit/                        # pins, ground sampling, curvature maths, CSV formatting
├── property/                    # Hypothesis monotonicity properties
├── acceptance/                  # One test per fixture scene: compute and compare with expected CSV
└── fixtures/
    └── scenes/                  # <name>.toml and <name>.expected.csv (scene-fixture.md)
.github/workflows/ci.yml         # Adds a `uv run mypy src` step
```

**Structure Decision**: A single package in the existing `src/bridgeview/` layout. The
modules follow the data flow: pins → scene and ground → visibility → results. The
constitution's simplicity rule rules out extra layers, so there are no service, repository or
plugin abstractions.

## Complexity Tracking

No constitution violations need justifying.
