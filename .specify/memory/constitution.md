# Bridgeview Constitution

## Core Principles

### I. Specification-Driven Development

Every feature MUST begin as a written specification in `specs/` before any implementation
begins. The sequence MUST be: specify → clarify (where ambiguity exists) → plan → tasks →
implement. Code that has no traceable spec or task MUST NOT be merged.

Rationale: This project is an experiment in AI-directed development. Specifications are the
durable source of intent, and they keep generated code reviewable against stated requirements.

### II. Test-First with a Coverage Gate

Behavior changes MUST be accompanied by tests written before or alongside the implementation.
Test line coverage MUST remain at or above 90%, as enforced by `fail_under = 90` in
`pyproject.toml`. A change that drops coverage below this threshold MUST NOT be merged.

Geometric and visibility logic SHOULD be covered by property-based tests (Hypothesis). Mutation
testing (mutmut) MUST be run on core computation modules before a release is tagged.

Rationale: The product's central claim is that a building can or cannot see a landmark. Errors
in that logic are silent and would mislead users, so verification must be automated and strict.

### III. Reproducible Environments

All Python dependencies MUST be declared in `pyproject.toml` and locked in `uv.lock`. The
project MUST be run through `uv`. The interpreter version MUST match `.python-version`
(currently 3.14). Dependencies MUST NOT be installed through ad hoc `pip` commands that bypass
the lockfile.

Rationale: Geospatial libraries (geopandas, shapely, pyproj) have version-sensitive numerical
behavior. Locked, reproducible environments make results comparable across machines and runs.

### IV. Explicit Coordinate Reference Systems and Units

Every geometry MUST carry an explicit coordinate reference system (CRS). Distance and area
calculations MUST be performed in a projected CRS with a stated unit, never on raw
latitude/longitude degrees. Any function that converts between CRSs MUST document the source
and target CRS.

Rationale: Computing on unprojected degrees produces distortion that varies with latitude. For
San Francisco-scale visibility checks, that distortion can change the answer.

### V. Typed, Documented Public Interfaces

All public functions, methods, and classes in `src/bridgeview/` MUST have type annotations.
The package MUST ship with `py.typed`, and public interfaces MUST pass a static type check
before merge. Public functions MUST have a docstring that states inputs, outputs, and units.
Simplicity is preferred: abstractions MUST NOT be introduced until a second concrete use
exists.

Rationale: The project is developed largely through AI-generated code. Explicit types and
docstrings give both humans and tools a precise contract to check against.

## Technology Stack & Constraints

- **Language and runtime**: Python 3.14 or later, as declared in `pyproject.toml`
  (`requires-python = ">=3.14"`).
- **Package and environment manager**: `uv`. The build backend is `uv_build`.
- **Core libraries**: geopandas, shapely, pyproj, numpy. New runtime dependencies MUST be
  justified in the relevant specification or plan.
- **Testing and quality tools**: pytest, pytest-cov, hypothesis, mutmut.
- **Data handling**: Source geographic data MUST be recorded with its provenance (source, date,
  and license) in the specification or a `docs/` note before it is used.
- **Output target**: The end product is a web page. The computation layer MUST remain
  separable from presentation so that it can be tested without a browser.

## Development Workflow & Quality Gates

- **Spec Kit workflow**: Features follow the Spec Kit commands in `.claude/skills/speckit-*`.
  Each feature gets a sequentially numbered directory under `specs/`.
- **Pre-merge gates**: Before a change is merged, the following MUST pass:
  1. The test suite (`uv run pytest`) passes.
  2. Coverage is at or above 90%.
  3. The type check passes on public interfaces.
  4. The change is consistent with its spec, plan, and tasks.
  5. Continuous integration (CI) has passed on the change.
  6. The change has been explicitly approved by the project owner, `colonoh`. Approval from the
     `colonoh-bot` account does not satisfy this gate.
- **Review**: Every change to `main` MUST be reviewed for compliance with these principles.
  Nothing MUST merge to `main` without CI passing and explicit approval from the project owner,
  `colonoh`.
  Reviewers MUST check specification traceability, coverage, and CRS handling in geometry code.
- **Commits**: Commits MUST be small and describe one logical change. Commit messages MUST
  state what changed and why.
- **Complexity**: Any deviation from these principles MUST be recorded with a justification in
  the feature plan's complexity-tracking section.

## Governance

This constitution supersedes all other development practices in this repository. Where another
document conflicts with it, this constitution prevails until it is amended.

**Amendment procedure**: An amendment is proposed as a change to
`.specify/memory/constitution.md` with an updated Sync Impact Report. It MUST be approved by the
project owner before merge. Any dependent templates or Spec Kit commands affected by the
amendment MUST be updated in the same change.

**Versioning policy**: The constitution uses semantic versioning.
- **MAJOR**: A principle is removed or redefined in a backward-incompatible way, or a
  governance rule is removed.
- **MINOR**: A principle or section is added, or existing guidance is materially expanded.
- **PATCH**: Wording clarifications, typo fixes, or non-semantic refinements.

**Compliance review**: Each feature plan MUST include a Constitution Check that confirms
compliance with Principles I–V before implementation starts. Each pull request MUST be checked
against the pre-merge gates above. Violations MUST be resolved or explicitly justified.

**Runtime guidance**: Day-to-day development guidance for AI agents is provided by the Spec Kit
skills in `.claude/skills/`. Those skills MUST be consistent with this constitution.

**Version**: 1.1.0 | **Ratified**: 2026-11-21 | **Last Amended**: 2026-11-21
