"""Hand-worked edges of the engine. Distances are along the x axis unless noted."""

import math

import numpy as np
import pytest
import shapely

from bridgeview import visibility
from bridgeview.ground import GroundModel
from bridgeview.results import NOT_EVALUATED
from bridgeview.scene import Building, Landmark, ReferencePoint, Scene, assess_buildings
from bridgeview.visibility import compute_visibility, max_clearance

X0, Y0 = 550000.0, 4180000.0


def _b(bid: str, x0: float, x1: float, vz: float, top: float | None = None,
       y0: float = -5, y1: float = 5) -> Building:
    return Building(bid, shapely.box(X0 + x0, Y0 + y0, X0 + x1, Y0 + y1), vz, vz if top is None else top)


def _run(buildings: list[Building], target: tuple[float, float], ground: GroundModel | None = None,
         curvature: bool = False) -> str | None:
    """Blocker seen by building A's viewpoint looking at target (x offset, z); None if clear."""
    ground = ground or GroundModel.constant(-100.0)
    pts = (ReferencePoint("t", X0 + target[0], Y0, target[1], "test"),)
    scene = Scene("s", assess_buildings(buildings, ground), ground, (Landmark("lm", "LM", pts),), "v", "v", curvature)
    result = {r.building_id: r for r in compute_visibility(scene, workers=1)}["A"]
    return dict(result.landmarks[0].blockers).get("t")


def test_peak_beyond_the_stretch_uses_its_far_end() -> None:
    # f peaks at d = 50, past the stretch [0, 20], so the far end d = 20 is highest.
    a = np.array([0.0])
    got = max_clearance(a, a, np.array([-0.1]), 1e-3, a, np.array([20.0]))
    assert got[0] == pytest.approx(-1e-3 * 400 + 0.1 * 20)


def test_margin_is_strict_for_buildings() -> None:
    # Level line at z = 0: a top of exactly 1 mm is a touch, and 2 mm blocks.
    a = _b("A", -5, 5, 0.0)
    assert _run([a, _b("B", 50, 60, 0.001)], (100, 0)) is None
    assert _run([a, _b("B", 50, 60, 0.002)], (100, 0)) == "building:B"


def test_nearest_of_several_blockers_is_reported() -> None:
    # Listed far-to-near, and the nearest has the last id.
    far, mid, near = _b("B", 80, 90, 20), _b("C", 50, 60, 20), _b("D", 20, 30, 20)
    assert _run([_b("A", -5, 5, 10), far, mid, near], (200, 10)) == "building:D"


def test_blocker_tie_is_broken_by_id() -> None:
    assert _run([_b("A", -5, 5, 10), _b("Z", 50, 60, 20), _b("C", 50, 60, 20)], (200, 10)) == "building:C"


def test_neighbour_within_a_metre_blocks() -> None:
    # A is 0.4 m wide, so its neighbour starts 0.2 m from A's viewpoint. The line rises 1 m per
    # metre from 10 m: at 0.2 m it is at 10.2 m, below the 10.5 m top, and at 1 m it is above it.
    assert _run([_b("A", -0.2, 0.2, 10), _b("B", 0.2, 5, 10.5)], (100, 110)) == "building:B"


def test_target_under_a_metre_away() -> None:
    # From z = 10 to z = 14 over 0.8 m, the line is at 11.5-12 m over a wall 0.3-0.4 m away.
    wall = _b("B", 0.3, 0.4, 11.0)
    assert _run([_b("A", -0.1, 0.1, 10), wall], (0.8, 14)) is None
    assert _run([_b("A", -0.1, 0.1, 10), _b("B", 0.3, 0.4, 12.0)], (0.8, 14)) == "building:B"


def test_target_at_the_viewpoint_is_visible() -> None:
    assert _run([_b("A", -5, 5, 10)], (0, 10)) is None


def _poly(bid: str, pts: list[tuple[float, float]], vz: float, top: float | None = None) -> Building:
    return Building(bid, shapely.Polygon([(X0 + x, Y0 + y) for x, y in pts]), vz, vz if top is None else top)


def test_target_in_the_bounding_box_but_outside_the_footprint_is_not_exempt() -> None:
    # A C shape open to the east; the target at x = 60 is in its notch, so it isn't inside the
    # footprint, and the wall from 50 to 54 m blocks the line to it.
    c = _poly("B", [(50, -5), (70, -5), (70, -3), (54, -3), (54, 3), (70, 3), (70, 5), (50, 5)], 20.0)
    assert _run([_b("A", -5, 5, 10), c], (60, 10)) == "building:B"


def test_footprint_that_ends_within_a_metre() -> None:
    # The line falls 1 m per metre from 10 m. At y = 0 the footprint spans 0.3-0.4 m, where the
    # line is at 9.7-9.6 m, above the 9.3 m top. Its bounding box reaches 0.9 m, where it isn't.
    b = _poly("B", [(0.3, -1), (0.4, -1), (0.4, 0.5), (0.9, 1), (0.3, 1)], 9.3)
    assert _run([_b("A", -0.1, 0.1, 10), b], (20, -10)) is None


def test_margin_is_strict_where_the_bounding_box_overstates_the_footprint() -> None:
    # The line falls from 0.5 m to -0.5 m over 64 m, so it is at exactly 0 m at 32 m, where the
    # footprint ends on y = 0: the 1 mm top is a touch there. The bounding box goes on to 40 m.
    shape = [(20.0, -5.0), (32.0, -5.0), (32.0, 1.0), (40.0, 5.0), (20.0, 5.0)]
    a = _b("A", -5, 5, 0.5)
    assert _run([a, _poly("B", shape, 0.001)], (64, -0.5)) is None
    assert _run([a, _poly("B", shape, 0.002)], (64, -0.5)) == "building:B"


def _ridge(at: float, height: float, length: int = 120) -> GroundModel:
    """1 m grid, ground -50 m except ``height`` at x offset ``at`` (a one-node ridge)."""
    row = [-50.0] * (length + 41)
    row[int(at) + 20] = height
    return GroundModel.from_grid(X0 - 20, Y0 + 20, 1.0, [row] * 41)


@pytest.mark.parametrize(
    ("at", "want"),
    [
        (1, None),       # within 2 m of the viewpoint: not sampled
        (2, "ground"),   # first sample
        (50, "ground"),
        (98, "ground"),  # last sample: 2 m from the target, at 100 m
        (99, None),      # within 2 m of the target: not sampled
    ],
)
def test_ground_is_sampled_from_2_m_to_2_m(at: float, want: str | None) -> None:
    assert _run([_b("A", -5, 5, 10)], (100, 10), _ridge(at, 11.0)) == want


def test_margin_is_strict_for_ground() -> None:
    a = _b("A", -5, 5, 0.0)
    assert _run([a], (100, 0), _ridge(50, 0.001)) is None
    assert _run([a], (100, 0), _ridge(50, 0.002)) == "ground"


def test_building_wins_a_tie_with_the_ground() -> None:
    # The ridge and the building's near wall are both 50 m away.
    assert _run([_b("A", -5, 5, 10), _b("B", 50, 60, 20)], (100, 10), _ridge(50, 11.0)) == "building:B"


@pytest.mark.parametrize(("ridge", "want"), [(-2.0, None), (-1.0, "ground")])
def test_ground_curvature(ridge: float, want: str | None) -> None:
    # 10 km at z = 0 to z = 0. At the middle the Earth's curve brings the line 1.71 m closer to
    # the ground (c * 5000**2, c = 0.87 / 2R), so a ridge at -1 m blocks and one at -2 m doesn't.
    row = [-50.0] * 10_041
    row[5_020] = ridge
    ground = GroundModel.from_grid(X0 - 20, Y0 + 20, 1.0, [row] * 41)
    assert _run([_b("A", -5, 5, 0.0)], (10_000, 0), ground, curvature=True) == want


def test_not_evaluated_results_keep_landmark_ids() -> None:
    ground = GroundModel.constant(0.0)
    pts = (ReferencePoint("t", X0 + 100, Y0, 5.0, "test"),)
    buildings = assess_buildings(
        [
            Building("empty", shapely.Polygon(), 5.0, 5.0),
            Building("noheight", shapely.box(X0, Y0, X0 + 1, Y0 + 1), None, 5.0),
            Building("nan", shapely.box(X0, Y0, X0 + 1, Y0 + 1), math.nan, 5.0),
            _b("A", -5, 5, 10),
        ],
        ground,
    )
    scene = Scene("s", buildings, ground, (Landmark("lm", "LM", pts),), "v", "v")
    by_id = {r.building_id: r for r in compute_visibility(scene, workers=1)}
    assert (by_id["empty"].viewpoint_x, by_id["empty"].viewpoint_y) == (None, None)
    assert by_id["noheight"].viewpoint_z is None and by_id["nan"].viewpoint_z is None
    for r in by_id.values():
        assert [v.landmark_id for v in r.landmarks] == ["lm"]
    assert by_id["empty"].landmarks[0].status == NOT_EVALUATED


# --- Driver: which pool is used, and progress ---------------------------------


class _FakeContext:
    def __init__(self, calls: list[tuple[str | None, int | None]], method: str | None) -> None:
        self.calls, self.method = calls, method

    def Pool(self, n: int | None) -> _FakeContext:  # noqa: N802
        self.calls.append((self.method, n))
        return self

    def __enter__(self) -> _FakeContext:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def imap(self, fn, items, chunksize=1):  # type: ignore[no-untyped-def]
        return map(fn, items)


def _many(n: int) -> Scene:
    ground = GroundModel.constant(0.0)
    buildings = [_b(f"b{i:03d}", 20 * i, 20 * i + 5, 10.0) for i in range(n)]
    pts = (ReferencePoint("t", X0 + 50, Y0 + 500, 50.0, "test"),)
    return Scene("s", assess_buildings(buildings, ground), ground, (Landmark("lm", "LM", pts),), "v", "v")


@pytest.mark.parametrize(
    ("n", "workers", "cpus", "methods", "want"),
    [
        (17, 2, 8, ["fork"], [("fork", 2)]),      # two batches of 16: a pool of the size asked for
        (33, None, 3, ["fork"], [("fork", 3)]),   # default: one worker per CPU
        (33, 1, 8, ["fork"], []),                 # one worker: serial
        (33, None, None, ["fork"], []),           # unknown CPU count: serial
        (16, 4, 8, ["fork"], []),                 # a single batch: serial
        (33, 4, 8, ["spawn"], []),                # fork unavailable: serial
    ],
)
def test_pool_choice(monkeypatch: pytest.MonkeyPatch, n: int, workers: int | None, cpus: int | None,
                     methods: list[str], want: list[tuple[str, int]]) -> None:
    calls: list[tuple[str | None, int | None]] = []
    mp = visibility.multiprocessing
    monkeypatch.setattr(mp, "get_context", lambda m: _FakeContext(calls, m))
    monkeypatch.setattr(mp, "get_all_start_methods", lambda: methods)
    monkeypatch.setattr(visibility.os, "cpu_count", lambda: cpus)
    seen: list[tuple[int, int]] = []
    results = compute_visibility(_many(n), workers=workers, progress=lambda d, t: seen.append((d, t)))
    assert calls == want
    assert len(results) == n
    assert seen[-1] == (n, n) and all(t == n for _, t in seen)
    assert visibility._WORKER_STATE is None
