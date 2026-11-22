"""CLI usage and error handling (contracts/cli.md)."""

from pathlib import Path

import pytest

from bridgeview.cli import main


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    assert "compute" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["frobnicate"],
        ["compute", "--out", "x.csv"],  # neither --city nor --scene
        ["compute", "--scene", "s.toml"],  # missing --out
        ["compute", "--city", "--scene", "s.toml", "--out", "x.csv"],  # both
    ],
)
def test_usage_errors_exit_2(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert err.count("\n") == 1


def test_bad_scene_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scene = tmp_path / "bad.toml"
    scene.write_text('name = "bad"\ncrs = "EPSG:4326"\n')
    out = tmp_path / "out.csv"
    assert main(["compute", "--scene", str(scene), "--out", str(out)]) == 1
    assert capsys.readouterr().err.startswith("error: scene crs must be")
    assert not out.exists()


def test_download_without_pins_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["download"]) == 1
    assert capsys.readouterr().err.startswith("error: ")


def test_compute_city_not_implemented_yet(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["compute", "--city", "--out", "x.csv"]) == 1
    assert "not implemented" in capsys.readouterr().err
