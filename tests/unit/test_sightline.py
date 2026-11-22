"""Sight-line maths (data-model.md: SightLine; research R4, R6)."""

import numpy as np
import pytest

from bridgeview.visibility import EARTH_RADIUS_M, K, curvature_coefficient, max_clearance


def test_curvature_coefficient() -> None:
    assert curvature_coefficient(False) == 0.0
    c = curvature_coefficient(True)
    assert c == pytest.approx((1 - K) / (2 * EARTH_RADIUS_M))
    # Drop over 10 km is about 6.8 m.
    assert c * 10_000**2 == pytest.approx(6.83, abs=0.01)


def _arr(*v: float) -> np.ndarray:
    return np.array(v, dtype=np.float64)


def test_flat_line_clearance_is_at_nearest_end() -> None:
    # line rises 0.4 m/m from 10 m; a 30 m block from d = 35 to 45
    got = max_clearance(_arr(30), _arr(10), _arr(0.4), 0.0, _arr(35), _arr(45))
    assert got[0] == pytest.approx(30 - 24)


def test_falling_line_clearance_is_at_far_end() -> None:
    got = max_clearance(_arr(20), _arr(30), _arr(-0.5), 0.0, _arr(10), _arr(20))
    assert got[0] == pytest.approx(20 - (30 - 10))


def test_interior_peak_with_curvature() -> None:
    # f(d) = top - c d^2 - (zv + s d) peaks at d* = -s / (2c) when inside the stretch.
    c = 1e-3
    s = -0.1  # d* = 50
    got = max_clearance(_arr(0), _arr(0), _arr(s), c, _arr(0), _arr(100))
    assert got[0] == pytest.approx(-c * 50**2 + 0.1 * 50)
    # ...and when the peak is outside the stretch, the nearest end wins.
    got = max_clearance(_arr(0), _arr(0), _arr(s), c, _arr(60), _arr(100))
    assert got[0] == pytest.approx(-c * 60**2 + 0.1 * 60)
