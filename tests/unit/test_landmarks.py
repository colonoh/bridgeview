"""Packaged landmarks.toml (data-model.md: Landmark, ReferencePoint)."""

import pytest
from pyproj import Transformer

from bridgeview.errors import SceneError
from bridgeview.scene import load_landmarks


def test_packaged_landmarks() -> None:
    version, landmarks = load_landmarks()
    assert version == "1"
    assert [lm.id for lm in landmarks] == ["golden_gate", "alcatraz", "bay_bridge"]
    points = [p for lm in landmarks for p in lm.points]
    assert len(points) == 13
    ids = [p.id for p in points]
    assert len(set(ids)) == 13
    assert not any(c in pid for pid in ids for c in ";=,")
    assert all(p.source.strip() for p in points)


def test_lat_lon_converted_to_utm() -> None:
    _, landmarks = load_landmarks()
    tower = landmarks[0].points[0]
    assert tower.id == "ggb_south_tower"
    lon, lat = Transformer.from_crs("EPSG:26910", "EPSG:4326", always_xy=True).transform(tower.x, tower.y)
    assert lat == pytest.approx(37.81401, abs=1e-7)  # about 1 cm
    assert lon == pytest.approx(-122.47789, abs=1e-7)
    assert tower.z == 227.4


def test_version_required() -> None:
    with pytest.raises(SceneError, match="landmarks_version"):
        load_landmarks('[[landmarks]]\nid = "x"\n')
