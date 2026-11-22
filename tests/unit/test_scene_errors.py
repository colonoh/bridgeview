"""Bad input is reported as SceneError, so the CLI prints one 'error:' line (contracts/cli.md)."""

import gzip
import json
from pathlib import Path

import numpy as np
import pytest
import shapely

import bridgeview
from bridgeview.cli import main
from bridgeview.errors import SceneError
from bridgeview.scene import Building, load_city_scene, load_landmarks, load_scene
from tests.synthetic_city import X0, Y0, make_city, write_tile

HEAD = 'name = "s"\ncrs = "EPSG:26910"\n'
GROUND = "[ground]\nconstant_z = 0.0\n"
BOX = "[[buildings]]\nid = \"A\"\nfootprint = [[0,0],[1,0],[1,1]]\nviewpoint_z = 5\ntop_z = 5\n"
LANDMARK = '[[landmarks]]\nid = "lm"\n[[landmarks.points]]\nid = "p"\nx = 1\ny = 1\nz = 1\nsource = "t"\n'


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("not toml [", "cannot read scene"),
        (HEAD + BOX + LANDMARK, "missing 'ground'"),
        (HEAD + "[ground]\nresolution = 1\n" + BOX + LANDMARK, "missing 'origin_x'"),
        (
            HEAD + "[ground]\norigin_x=0\norigin_y=0\nresolution=0\nz=[[1,1],[1,1]]\n" + BOX + LANDMARK,
            "resolution must be positive",
        ),
        (HEAD + GROUND + BOX + BOX + LANDMARK, "duplicate building id"),
        (HEAD + 'landmarks = []\n' + GROUND + BOX, "no landmarks"),
        (HEAD + GROUND + BOX + LANDMARK.replace('"p"', '"p;q"'), "duplicated or contains"),
        (HEAD + GROUND + BOX + '[[landmarks]]\nid = "lm"\npoints = []\n', "no points"),
    ],
)
def test_bad_scene_files(tmp_path: Path, text: str, message: str) -> None:
    path = tmp_path / "s.toml"
    path.write_text(text)
    with pytest.raises(SceneError, match=message):
        load_scene(path)


def test_bad_landmarks_text() -> None:
    with pytest.raises(SceneError, match="landmarks.toml"):
        load_landmarks("not toml [")
    with pytest.raises(SceneError, match="landmarks_version"):
        load_landmarks("landmarks = []\n")


def test_empty_footprint_has_no_viewpoint() -> None:
    assert Building("e", shapely.Polygon(), 1.0, 1.0).viewpoint_xy is None


def test_city_needs_one_building_file(tmp_path: Path) -> None:
    data_dir, pins = make_city(tmp_path)
    text = pins.read_text().split("\n[[datasets]]", 1)[1]  # drop the building pin
    pins.write_text("[[datasets]]" + text)
    with pytest.raises(SceneError, match="exactly one|must pin one"):
        load_city_scene(data_dir, pins)


def test_city_missing_field(tmp_path: Path) -> None:
    data_dir, pins = make_city(tmp_path)
    path = data_dir / "raw" / "bldg.geojson.gz"
    fc = json.loads(gzip.decompress(path.read_bytes()))
    for f in fc["features"]:
        del f["properties"]["peak_1st_m"]
    path.write_bytes(gzip.compress(json.dumps(fc).encode()))
    with pytest.raises(SceneError, match="missing fields.*peak_1st_m"):
        load_city_scene(data_dir, pins)


def test_bad_tile_is_a_scene_error(tmp_path: Path) -> None:
    data_dir, pins = make_city(tmp_path)
    write_tile(data_dir / "raw" / "west.tif", X0, Y0 + 100, np.zeros((100, 100)), epsg=32610)
    with pytest.raises(SceneError, match="EPSG:26910"):
        load_city_scene(data_dir, pins)


def test_contract_functions_are_exported() -> None:
    for name in ("load_scene", "load_city_scene", "compute_visibility", "write_results_csv", "verify_pins"):
        assert callable(getattr(bridgeview, name)) and name in bridgeview.__all__


def test_cli_download_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    make_city(tmp_path)  # every file is already present and valid, so nothing is fetched
    monkeypatch.chdir(tmp_path)
    assert main(["download"]) == 0
    assert capsys.readouterr().out.splitlines() == ["skip bldg", "skip west", "skip east"]
