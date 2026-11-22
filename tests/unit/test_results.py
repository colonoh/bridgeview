"""Results CSV writer (contracts/results-csv.md; data-model.md: VisibilityResult)."""

import csv
from pathlib import Path

from bridgeview.results import (
    NOT_EVALUATED,
    NOT_VISIBLE,
    VISIBLE,
    BuildingResult,
    RunMeta,
    VisibilityResult,
    header,
    write_results_csv,
)

META = RunMeta("ds-1", "lm-1", "9.9.9")


def _result(bid: str, **kw: object) -> BuildingResult:
    lm = kw.pop("lm", VisibilityResult("gg", VISIBLE, ("p1",)))
    return BuildingResult(bid, 550000.0, 4180000.0, 12.345, None, (lm,))  # type: ignore[arg-type]


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_header_order() -> None:
    assert header(["gg", "bb"]) == [
        "building_id", "lon", "lat", "viewpoint_z_m", "not_evaluated_reason",
        "gg_status", "gg_visible_points", "gg_blockers",
        "bb_status", "bb_visible_points", "bb_blockers",
        "dataset_version", "landmarks_version", "software_version",
    ]


def test_rows_sorted_formatted_and_encoded(tmp_path: Path) -> None:
    rows = [
        _result("b2", lm=VisibilityResult("gg", NOT_VISIBLE, (), (("p1", "building:b1"), ("p2", "ground")))),
        _result("b1", lm=VisibilityResult("gg", VISIBLE, ("p1", "p2"))),
        BuildingResult("b0", None, None, None, "invalid_geometry", (VisibilityResult("gg", NOT_EVALUATED),)),
    ]
    out = tmp_path / "r.csv"
    write_results_csv(rows, out, META, ["gg"])
    text = out.read_bytes()
    assert b"\r" not in text and text.endswith(b"\n")
    got = _read(out)
    assert [r["building_id"] for r in got] == ["b0", "b1", "b2"]
    b0, b1, b2 = got
    assert (b0["lon"], b0["viewpoint_z_m"], b0["not_evaluated_reason"]) == ("", "", "invalid_geometry")
    assert b0["gg_status"] == "not_evaluated" and b0["gg_visible_points"] == b0["gg_blockers"] == ""
    assert b1["gg_visible_points"] == "p1;p2" and b1["gg_blockers"] == ""
    assert b2["gg_blockers"] == "p1=building:b1;p2=ground"
    assert b1["viewpoint_z_m"] == "12.35"
    assert len(b1["lon"].split(".")[1]) == 7 and len(b1["lat"].split(".")[1]) == 7
    assert (b1["dataset_version"], b1["landmarks_version"], b1["software_version"]) == ("ds-1", "lm-1", "9.9.9")
    assert not (tmp_path / "r.csv.tmp").exists()


def test_negative_zero_is_not_written(tmp_path: Path) -> None:
    r = BuildingResult("a", 550000.0, 4180000.0, -0.001, None, (VisibilityResult("gg", VISIBLE, ("p",)),))
    out = tmp_path / "r.csv"
    write_results_csv([r], out, META, ["gg"])
    assert _read(out)[0]["viewpoint_z_m"] == "0.00"
