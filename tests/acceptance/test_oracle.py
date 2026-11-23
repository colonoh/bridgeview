"""The engine agrees with a slow, independent implementation on random scenes.

The oracle shares no code with the engine beyond the scene entities and constants: one line at a
time, one building at a time, and a fine sampling of the line inside each footprint in place of a
closed-form clearance. Footprints are rotated and lines run in all directions, unlike the
hand-worked fixtures, whose lines run along the x axis.
"""

import math
import random

import numpy as np
import pytest
import shapely

from bridgeview.ground import GroundModel
from bridgeview.results import VISIBLE
from bridgeview.scene import Building, Landmark, ReferencePoint, Scene, assess_buildings
from bridgeview.visibility import compute_visibility

X0, Y0 = 550000.0, 4180000.0
C = (1 - 0.13) / (2 * 6_371_000.0)


def _random_scene(seed: int) -> Scene:
    rng = random.Random(seed)
    size = 700.0
    n = 15
    ground = GroundModel.from_grid(
        X0 - 100, Y0 + size + 100, 50.0,
        [[rng.uniform(0, 12) + (45 if rng.random() < 0.15 else 0) for _ in range(n + 4)] for _ in range(n + 4)],
    )
    buildings = []
    for i in range(45):
        cx, cy = X0 + rng.uniform(0, size), Y0 + rng.uniform(0, size)
        w, h, a = rng.uniform(8, 40), rng.uniform(8, 40), rng.uniform(0, 180)
        base = shapely.box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        rot = shapely.affinity.rotate(base, a)
        if i % 5 == 0:  # an L shape, so a line can cross it in two separate pieces
            rot = rot.difference(shapely.affinity.rotate(
                shapely.box(cx - w / 4, cy - h / 2, cx + w / 4, cy + h / 6), a, origin=(cx, cy)))
        vz = rng.uniform(22, 48)
        buildings.append(Building(f"b{rng.randrange(10**6):06d}", rot, vz, vz + rng.choice([0, 0, 6, 25])))
    pts = []
    for k in range(5):
        x, y = X0 + rng.uniform(-60, size + 60), Y0 + rng.uniform(-60, size + 60)
        if k == 0:  # inside a footprint
            c = buildings[3].footprint.representative_point()
            x, y = c.x, c.y
        pts.append(ReferencePoint(f"p{k}", x, y, rng.uniform(15, 80), "test"))
    return Scene("r", assess_buildings(buildings, ground), ground,
                 (Landmark("a", "A", tuple(pts[:2])), Landmark("b", "B", tuple(pts[2:]))),
                 "v", "v", curvature=bool(seed % 2))


def _oracle(scene: Scene, b: Building, p: ReferencePoint) -> str | None:
    """The blocker label, or None when the line is clear."""
    c = C if scene.curvature else 0.0
    assert b.viewpoint_xy is not None and b.viewpoint_z is not None
    vx, vy = b.viewpoint_xy
    dist = math.dist((vx, vy), (p.x, p.y))
    line = shapely.LineString([(vx, vy), (p.x, p.y)])

    def height(d: float) -> float:  # of the line, measured from the curved datum
        return b.viewpoint_z + (p.z - c * dist**2 - b.viewpoint_z) * d / dist  # type: ignore[operator]

    hits: list[tuple[float, str]] = []
    for o in scene.buildings:
        if o is b or not o.evaluable or o.footprint.intersects(shapely.Point(p.x, p.y)):
            continue
        for part in getattr(line.intersection(o.footprint), "geoms", [line.intersection(o.footprint)]):
            if part.is_empty:
                continue
            ends = [math.dist((vx, vy), q[:2]) for q in part.coords]
            ds = np.linspace(min(ends), max(ends), 4001)
            if any(o.top_z - c * d * d - height(d) > 0.001 for d in ds):
                hits.append((min(ends), f"building:{o.building_id}"))
    near = min(hits, default=None)
    d = 2.0
    while d <= dist - 2.0 and (near is None or d < near[0]):
        x, y = vx + (p.x - vx) * d / dist, vy + (p.y - vy) * d / dist
        if float(scene.ground.sample(x, y)) - c * d * d - height(d) > 0.001:
            return "ground"
        d += 1.0
    return None if near is None else near[1]


@pytest.mark.parametrize("seed", range(8))
def test_engine_matches_oracle(seed: int) -> None:
    scene = _random_scene(seed)
    by_id = {b.building_id: b for b in scene.buildings}
    points = {p.id: p for lm in scene.landmarks for p in lm.points}
    for r in compute_visibility(scene, workers=1):
        b = by_id[r.building_id]
        if not b.evaluable:
            continue
        for lm in r.landmarks:
            blockers = dict(lm.blockers)
            for pid in [p.id for x in scene.landmarks if x.id == lm.landmark_id for p in x.points]:
                want = _oracle(scene, b, points[pid])
                assert (pid in lm.visible_points) == (want is None), (b.building_id, pid, want)
                assert blockers.get(pid) == want
            assert (lm.status == VISIBLE) == bool(lm.visible_points)
