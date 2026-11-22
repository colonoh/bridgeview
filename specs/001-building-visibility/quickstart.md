# Quickstart: Validating Building Landmark Visibility

These are the steps that show the feature works end to end. Each maps to a user story or
success criterion in [spec.md](spec.md).

## Prerequisites

- `uv`, with Python 3.14 picked up from `.python-version`.
- About 1.5 GB of free disk space for the city data, which only the city run needs.
- Network access to GitHub Releases and `prd-tnm.s3.amazonaws.com`.

```bash
uv sync
```

## 1. Hand-worked fixtures (US1, SC-001): no downloads needed

```bash
uv run pytest tests/acceptance -v
```

**Expected**: every fixture scene listed in
[contracts/scene-fixture.md](contracts/scene-fixture.md) passes. Each test runs
`compute --scene` and compares the result with `<name>.expected.csv` byte for byte.

To run one scene by hand and read the output:

```bash
uv run bridgeview compute --scene tests/fixtures/scenes/three_boxes_blocked.toml --out /tmp/out.csv
cat /tmp/out.csv
```

**Expected**: building `A` has `target_status=not_visible` and `target_blockers=t1=building:B`.

## 2. Reproducible data download (US2, SC-006)

```bash
uv run bridgeview download          # first run: "ok <id>" for every pin
uv run bridgeview download          # second run: "skip <id>" for every pin, with no network transfer
```

To check that tampering is caught:

```bash
printf 'x' >> data/raw/<any pinned file>
uv run bridgeview compute --city --out /tmp/city.csv
```

**Expected**: the exit code is 1, the message is
`error: checksum mismatch for <id>: …`, and `/tmp/city.csv` is not created.
Running `download` again replaces the file.

## 3. City-wide run (US3, SC-004, SC-005, SC-007)

```bash
time uv run bridgeview compute --city --out results-a.csv
uv run bridgeview compute --city --out results-b.csv --workers 2
cmp results-a.csv results-b.csv && echo identical
```

**Expected**:
- The first run finishes in under 1 hour on an 8-core laptop.
- `identical` is printed, so reruns give the same file even with a different worker count.
- The file has 177,024 lines: a header plus one row per building.

## 4. Spot check (SC-002, SC-003)

Pick 20 random rows:

```bash
uv run python -c "import csv,random; r=list(csv.DictReader(open('results-a.csv'))); random.seed(1); [print(x['building_id'],x['lat'],x['lon'],x['golden_gate_status'],x['golden_gate_blockers']) for x in random.sample(r,20)]"
```

For each row, open the latitude and longitude in a map or Street View and judge whether the
result is plausible, using any listed blocker id to find the blocking building.

**Expected**: at least 18 of the 20 results are judged correct, and each takes under 5
minutes to check.
