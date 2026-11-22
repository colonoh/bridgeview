"""compute --city end to end on a synthetic city, and refusal on bad data (SC-006)."""

import csv
from pathlib import Path

import pytest

from bridgeview.cli import main
from tests.synthetic_city import EXPECTED_REASONS, make_city


def test_city_run_writes_all_buildings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir, _ = make_city(tmp_path)
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "city.csv"
    assert main(["compute", "--city", "--out", str(out), "--workers", "1"]) == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert sorted(r["building_id"] for r in rows) == sorted(EXPECTED_REASONS)
    assert {r["building_id"]: r["not_evaluated_reason"] or None for r in rows} == EXPECTED_REASONS
    assert {"golden_gate_status", "alcatraz_status", "bay_bridge_status"} <= set(rows[0])
    assert rows[0]["dataset_version"] == "bldg+west+east"


def test_tampered_pin_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir, _ = make_city(tmp_path)
    with (data_dir / "raw" / "east.tif").open("ab") as fh:
        fh.write(b"x")
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "city.csv"
    assert main(["compute", "--city", "--out", str(out)]) == 1
    assert capsys.readouterr().err.startswith("error: size mismatch for east")
    assert not out.exists() and not (tmp_path / "city.csv.tmp").exists()
