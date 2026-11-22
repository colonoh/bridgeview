# Contract: Command-Line Interface

The package installs a `bridgeview` console script, which runs as `uv run bridgeview …`.
Exit codes: `0` success, `1` bad input or verification failure, `2` usage error. Errors go to
stderr as one line beginning with `error:`.

## `bridgeview download [--data-dir DIR]`

Fetches every pin in `datasets.toml` into `DIR/raw/`. The default for `DIR` is `data/`.

- If a file already exists and its size and SHA-256 match, it is skipped and not downloaded
  again (US2 scenario 3).
- Otherwise the file is downloaded to `<filename>.part`, its size and SHA-256 are checked,
  and only then is it renamed into place. On a mismatch the `.part` file is deleted, and the
  command exits `1` with
  `error: checksum mismatch for <id>: expected <sha>, got <sha>` (FR-010).
- On success, prints one line per pin: `ok <id>` or `skip <id>`.

## `bridgeview compute (--city | --scene FILE) --out FILE [--data-dir DIR] [--workers N]`

Computes visibility and writes the results CSV ([results-csv.md](results-csv.md)).

- `--city`: uses the pinned data. It first re-checks every pinned file's SHA-256, and exits `1`
  without writing output if any check fails (SC-006). It builds the elevation cache on first
  use.
- `--scene FILE`: uses a fixture scene ([scene-fixture.md](scene-fixture.md)) and needs no
  downloaded data (FR-020).
- `--workers`: the number of worker processes. The default is the number of CPUs. The output
  is identical whatever value is used (FR-018).
- The output is written to `FILE.tmp` first, then renamed into place.

## `bridgeview snapshot-buildings --out FILE` (maintainer only)

Downloads a fresh GeoJSON export of DataSF `ynuv-fyni`, compresses it with gzip using a fixed
modification time so the result is repeatable, and prints its size and SHA-256. The maintainer
uploads the file as a GitHub Release asset and updates `datasets.toml` in a reviewed PR. This
command is never run in CI.

## Library interface

These are public functions in `bridgeview`. Each is typed and documented, with units
(Constitution V).

- `load_scene(path: Path) -> Scene`
- `load_city_scene(data_dir: Path) -> Scene`
- `compute_visibility(scene: Scene, workers: int | None = None) -> list[BuildingResult]`
- `write_results_csv(results: list[BuildingResult], path: Path, meta: RunMeta) -> None`
- `verify_pins(data_dir: Path) -> None`, which raises `ChecksumError`
