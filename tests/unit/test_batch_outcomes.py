"""Batch outcomes are compact arrays, so a city-wide run stays small in memory (SC-004)."""

from dataclasses import replace

import numpy as np
import pytest
import shapely

from bridgeview import visibility
from bridgeview.ground import GroundModel
from bridgeview.scene import Building, Landmark, ReferencePoint, Scene, assess_buildings

X0, Y0 = 550000.0, 4180000.0


def _box(bid: str, x: float, top: float) -> Building:
    return Building(bid, shapely.box(X0 + x, Y0, X0 + x + 10, Y0 + 10), top, top)


def _scene() -> Scene:
    # A (10 m) looks east past B (30 m) to a low point behind it; the high point is above B.
    buildings = [_box("A", 0, 10.0), _box("B", 50, 30.0)]
    ground = GroundModel.constant(0.0)
    pts = (
        ReferencePoint("low", X0 + 205, Y0 + 5, 12.0, "test"),
        ReferencePoint("high", X0 + 205, Y0 + 5, 500.0, "test"),
        ReferencePoint("buried", X0 - 195, Y0 + 5, -100.0, "test"),
    )
    return Scene("s", assess_buildings(buildings, ground), ground, (Landmark("lm", "LM", pts),),
                 "v", "v", curvature=False)


def test_batch_outcomes_are_a_compact_int_array() -> None:
    scene = _scene()
    points = list(scene.landmarks[0].points)
    index = visibility._build_index(scene, points)
    out = visibility._evaluate_batch(scene.ground, index, np.array([0, 1]), 0.0)
    assert out.dtype == np.int32
    assert out.shape == (2, 3)
    assert out[0].tolist() == [1, visibility.CLEAR_CODE, visibility.GROUND_CODE]  # 1 = building B
    # B looks back over A (index 0), which blocks the line before the ground does.
    assert out[1].tolist() == [visibility.CLEAR_CODE, visibility.CLEAR_CODE, 0]


@pytest.mark.parametrize("chunk", [1, 7, 2_000_000])
def test_ground_chunk_size_does_not_change_outcomes(chunk: int, monkeypatch: pytest.MonkeyPatch) -> None:
    scene = replace(_scene(), curvature=True)
    expected = visibility.compute_visibility(scene, workers=1)
    monkeypatch.setattr(visibility, "GROUND_CHUNK", chunk)
    assert visibility.compute_visibility(scene, workers=1) == expected
