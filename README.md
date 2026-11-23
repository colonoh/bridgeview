# Bridgeview

This is an experiment in AI-directed software development.  The goal is to produce a web page which shows which buildings in San Francisco can see the:
- Golden gate bridge
- Alcatraz island
- San Francisco – Oakland Bay Bridge

## Usage

You need [uv](https://docs.astral.sh/uv/). `uv sync` installs the right Python and all dependencies.

Compute visibility for a small hand-worked scene, which needs no downloaded data:

```bash
uv run bridgeview compute --scene tests/fixtures/scenes/three_boxes_blocked.toml --out out.csv
```

Compute it for the whole city:

```bash
uv run bridgeview download                         # about 600 MB into data/raw/, checked against datasets.toml
uv run bridgeview compute --city --out city.csv    # uses every CPU; add --workers N to limit it
```

The city run re-checks every file first and refuses to start if one doesn't match. It takes about 1 h 23 min on 2 cores with 3.8 GB of memory, and the CPU time extrapolates to about 21 minutes on 8 cores (not measured). Keep at least 1 GB of memory free for the elevation cache in `data/cache/`.

The output has one row per building. Columns, status values and formats are in [contracts/results-csv.md](specs/001-building-visibility/contracts/results-csv.md), and all commands and exit codes are in [contracts/cli.md](specs/001-building-visibility/contracts/cli.md). The data sources and their licences are in [docs/data-sources.md](docs/data-sources.md).

Run the tests and the type checker with `uv run pytest` and `uv run mypy`.
