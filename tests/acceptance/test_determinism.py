"""Reruns are byte-identical whatever the worker count (FR-018, SC-005)."""

import random
from pathlib import Path

import shapely

from bridgeview.ground import GroundModel
from bridgeview.results import RunMeta, write_results_csv
from bridgeview.scene import Building, Landmark, ReferencePoint, Scene, assess_buildings
from bridgeview.visibility import compute_visibility

X0, Y0 = 550000.0, 4180000.0


def _scene() -> Scene:
    rng = random.Random(42)
    buildings = []
    for i in range(200):
        x, y = rng.uniform(0, 900), rng.uniform(0, 900)
        w, h = rng.uniform(5, 25), rng.uniform(5, 25)
        vz = rng.uniform(5, 60)
        buildings.append(Building(f"b{i:03d}", shapely.box(X0 + x, Y0 + y, X0 + x + w, Y0 + y + h),
                                  vz, vz + rng.uniform(0, 15)))
    ground = GroundModel.from_grid(X0 - 100, Y0 + 1100, 100.0,
                                   [[rng.uniform(0, 30) for _ in range(13)] for _ in range(13)])
    pts = tuple(ReferencePoint(f"p{k}", X0 + rng.uniform(-200, 1100), Y0 + rng.uniform(-200, 1100),
                               rng.uniform(20, 120), "test") for k in range(4))
    return Scene("det", assess_buildings(buildings, ground), ground, (Landmark("lm", "LM", pts),),
                 "det", "det", curvature=True)


def test_worker_count_does_not_change_output(tmp_path: Path) -> None:
    scene = _scene()
    meta = RunMeta("det", "det", "x")
    outs = []
    for workers in (1, 3):
        path = tmp_path / f"w{workers}.csv"
        write_results_csv(compute_visibility(scene, workers=workers), path, meta, ["lm"])
        outs.append(path.read_bytes())
    assert outs[0] == outs[1]
    assert outs[0].count(b"\n") == 201
