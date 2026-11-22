"""GroundModel sampling (data-model.md: GroundModel)."""

import math

import numpy as np
import pytest

from bridgeview.ground import GroundModel


def test_constant_plane() -> None:
    g = GroundModel.constant(7.5)
    assert g.sample(1e6, -3.0) == 7.5
    assert g.sample(np.zeros(3), np.zeros(3)).tolist() == [7.5] * 3


def test_bilinear_on_grid() -> None:
    # nodes: x = 100, 110 ; y = 200 (row 0), 190 (row 1)
    g = GroundModel.from_grid(100.0, 200.0, 10.0, [[0.0, 10.0], [20.0, 30.0]])
    assert g.sample(100, 200) == 0.0
    assert g.sample(110, 190) == 30.0
    assert g.sample(105, 200) == pytest.approx(5.0)
    assert g.sample(105, 195) == pytest.approx(15.0)


def test_outside_and_nodata_are_nan() -> None:
    # 3x3 nodes at x = 0, 10, 20 and y = 20, 10, 0; only the top-right node is nodata.
    g = GroundModel.from_grid(
        0.0, 20.0, 10.0, [[0.0, 0.0, math.nan], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    )
    assert math.isnan(float(g.sample(-0.1, 5)))
    assert math.isnan(float(g.sample(5, 20.1)))
    assert math.isnan(float(g.sample(15, 15)))  # cell whose corner is the nodata node
    assert float(g.sample(5, 5)) == 0.0  # cells away from it are unaffected
    assert float(g.sample(15, 5)) == 0.0


def test_rejects_bad_grids() -> None:
    with pytest.raises(ValueError):
        GroundModel.from_grid(0, 0, 1, [[1.0, 2.0]])
    with pytest.raises(ValueError):
        GroundModel.from_grid(0, 0, 0, [[1.0, 2.0], [3.0, 4.0]])
