"""City loader on a synthetic city (data-model.md: Building fields; research R1)."""

import logging
from pathlib import Path

import pytest

from bridgeview.scene import load_city_scene
from tests.synthetic_city import EXPECTED_REASONS, X0, Y0, make_city


def test_field_mapping_and_reasons(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    data_dir, pins = make_city(tmp_path)
    with caplog.at_level(logging.WARNING):
        scene = load_city_scene(data_dir, pins)
    by_id = {b.building_id: b for b in scene.buildings}
    assert {k: b.reason for k, b in by_id.items()} == EXPECTED_REASONS

    normal = by_id["b-normal"]
    # median_1st_m -> viewpoint_z, peak_1st_m -> top_z, gnd_min_m -> ground_z
    assert (normal.viewpoint_z, normal.top_z, normal.ground_z) == (15.5, 20.0, 1.0)
    # Reprojected EPSG:4326 -> EPSG:26910: the centroid is back at (15, 15).
    vx, vy = normal.viewpoint_xy  # type: ignore[misc]
    assert vx == pytest.approx(X0 + 15, abs=0.01) and vy == pytest.approx(Y0 + 15, abs=0.01)

    assert by_id["b-raise"].top_z == 15.0  # raised to viewpoint_z
    assert "b-raise" in caplog.text

    assert scene.dataset_version == "bldg+west+east"
    assert scene.landmarks_version == "1"
    assert [lm.id for lm in scene.landmarks] == ["golden_gate", "alcatraz", "bay_bridge"]
    # The mosaic spans both tiles and is cached for reuse.
    assert float(scene.ground.sample(X0 + 50, Y0 + 50)) == 1.0
    assert float(scene.ground.sample(X0 + 150, Y0 + 50)) == 5.0
    assert list((data_dir / "cache").glob("ground_*.npy"))
