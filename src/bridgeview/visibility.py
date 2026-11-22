"""Sight-line visibility engine (research R4 and R6; data-model.md: SightLine).

All coordinates are EPSG:26910 metres and all heights NAVD88 metres.

Curvature and refraction: a point at horizontal distance ``d`` from the observer
has its height lowered by ``c * d**2``, where ``c = (1 - K) / (2 * R)``. The sight
line is then straight in ``d``, from the viewpoint height to the target's lowered
height. An obstruction blocks when it rises more than ``MARGIN_M`` above the line,
so a line that only touches a surface is not blocked (FR-006).
"""

from __future__ import annotations

import math
import multiprocessing
import os
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import shapely
from numpy.typing import NDArray

from bridgeview.results import (
    NOT_EVALUATED,
    NOT_VISIBLE,
    VISIBLE,
    BuildingResult,
    VisibilityResult,
)
from bridgeview.scene import Building, ReferencePoint, Scene

#: Standard refraction coefficient (dimensionless).
K = 0.13
#: Mean Earth radius (m).
EARTH_RADIUS_M = 6_371_000.0
#: An obstruction must exceed the sight line by more than this to block (m).
MARGIN_M = 0.001
#: Spacing of ground samples along a sight line (m).
GROUND_STEP_M = 1.0
#: Length at each end of a sight line where the ground is not sampled (m).
GROUND_END_SKIP_M = 2.0
#: Observers evaluated per vectorised batch.
BATCH_SIZE = 16
#: Most ground samples held in memory at once.
GROUND_CHUNK = 2_000_000

GROUND = "ground"

FloatArray = NDArray[np.float64]


def curvature_coefficient(enabled: bool) -> float:
    """``c`` in the drop ``c * d**2`` (1/m); 0 when curvature is disabled."""
    return (1.0 - K) / (2.0 * EARTH_RADIUS_M) if enabled else 0.0


def max_clearance(
    top: FloatArray, z_v: FloatArray, slope: FloatArray, c: float, d0: FloatArray, d1: FloatArray
) -> FloatArray:
    """Largest ``top - c*d**2 - (z_v + slope*d)`` over ``d`` in ``[d0, d1]`` (m).

    This is how far an obstruction of height ``top`` rises above the sight line
    anywhere along a stretch from ``d0`` to ``d1`` metres from the observer. The
    function curves downward (``c >= 0``), so its maximum is at an end of the
    stretch or at its peak ``d = -slope / (2c)`` when that lies inside.
    """

    def f(d: FloatArray) -> FloatArray:
        return top - c * d * d - (z_v + slope * d)

    best = np.maximum(f(d0), f(d1))
    if c > 0:
        peak = np.clip(-slope / (2.0 * c), d0, d1)
        best = np.maximum(best, f(peak))
    return best


@dataclass(frozen=True)
class _Index:
    """Spatial index over the evaluable footprints."""

    tree: shapely.STRtree
    building_index: NDArray[np.intp]  # tree position -> index in scene.buildings
    top_z: FloatArray  # tree position -> top_z (m)
    contains_keys: NDArray[np.int64]  # point index * n_tree + tree position, for footprints containing a point
    id_rank: NDArray[np.intp]  # tree position -> rank of building_id (tie-break)


def _build_index(scene: Scene, points: list[ReferencePoint]) -> _Index:
    idx = [i for i, b in enumerate(scene.buildings) if b.evaluable]
    geoms = [scene.buildings[i].footprint for i in idx]
    tree = shapely.STRtree(geoms)
    tops = np.array([scene.buildings[i].top_z for i in idx], dtype=np.float64)
    pts = shapely.points([(p.x, p.y) for p in points])
    pk, tj = tree.query(pts, predicate="intersects")
    keys = pk.astype(np.int64) * max(len(geoms), 1) + tj.astype(np.int64)
    ids = np.array([scene.buildings[i].building_id for i in idx], dtype=object)
    rank = np.empty(len(idx), dtype=np.intp)
    rank[np.argsort(ids, kind="stable")] = np.arange(len(idx))
    return _Index(tree, np.array(idx, dtype=np.intp), tops, np.sort(keys), rank)


def _evaluate_batch(
    scene: Scene,
    index: _Index,
    points: list[ReferencePoint],
    observers: list[int],
    c: float,
) -> dict[tuple[int, int], tuple[bool, str | None]]:
    """Outcome of every (observer, point) line: (clear, blocker or None)."""
    n_pts = len(points)
    tree_pos = {int(b): t for t, b in enumerate(index.building_index)}
    vx = np.empty(len(observers) * n_pts)
    vy = np.empty_like(vx)
    vz = np.empty_like(vx)
    own = np.empty(len(vx), dtype=np.intp)
    px = np.tile(np.array([p.x for p in points]), len(observers))
    py = np.tile(np.array([p.y for p in points]), len(observers))
    pz = np.tile(np.array([p.z for p in points]), len(observers))
    pk = np.tile(np.arange(n_pts), len(observers))
    for o, bi in enumerate(observers):
        b = scene.buildings[bi]
        xy = b.viewpoint_xy
        assert xy is not None and b.viewpoint_z is not None
        sl = slice(o * n_pts, (o + 1) * n_pts)
        vx[sl], vy[sl], vz[sl] = xy[0], xy[1], b.viewpoint_z
        own[sl] = tree_pos[bi]

    dx, dy = px - vx, py - vy
    dist = np.hypot(dx, dy)
    safe = np.where(dist > 0, dist, 1.0)
    ux, uy = dx / safe, dy / safe
    slope = np.where(dist > 0, ((pz - c * dist**2) - vz) / safe, 0.0)

    n_lines = len(vx)
    bld_d = np.full(n_lines, np.inf)
    bld_id = np.full(n_lines, -1, dtype=np.intp)

    # --- Buildings: exact intersection of each line with each crossed footprint.
    lines = shapely.linestrings(np.stack([np.c_[vx, vy], np.c_[px, py]], axis=1))
    li, tj = index.tree.query(lines, predicate="intersects")
    # Skip the observer's own footprint (FR-005) and any footprint containing the
    # target point (spec Edge Cases: a landmark's own structure).
    keep = (tj != own[li]) & (dist[li] > 0)
    if len(index.contains_keys):
        n_tree = max(len(index.building_index), 1)
        keys = pk[li].astype(np.int64) * n_tree + tj.astype(np.int64)
        keep &= ~np.isin(keys, index.contains_keys)
    li, tj = li[keep], tj[keep]
    if len(li):
        inter = shapely.intersection(lines[li], index.tree.geometries[tj])
        parts, part_pair = shapely.get_parts(inter, return_index=True)
        coords, coord_part = shapely.get_coordinates(parts, return_index=True)
        if len(coords):
            line_of_coord = li[part_pair[coord_part]]
            d = (coords[:, 0] - vx[line_of_coord]) * ux[line_of_coord] + (
                coords[:, 1] - vy[line_of_coord]
            ) * uy[line_of_coord]
            d0 = np.full(len(parts), np.inf)
            d1 = np.full(len(parts), -np.inf)
            np.minimum.at(d0, coord_part, d)
            np.maximum.at(d1, coord_part, d)
            ok = np.isfinite(d0)
            part_line = li[part_pair]
            lim = dist[part_line]
            d0 = np.clip(np.where(ok, d0, 0.0), 0.0, lim)
            d1 = np.clip(np.where(ok, d1, 0.0), 0.0, lim)
            clear = max_clearance(
                index.top_z[tj[part_pair]], vz[part_line], slope[part_line], c, d0, d1
            )
            blocked = ok & (clear > MARGIN_M)
            if blocked.any():
                # Nearest blocker per line; ties broken by building id (deterministic).
                bl = np.flatnonzero(blocked)
                lines_b, d_b = part_line[bl], d0[bl]
                tpos_b = tj[part_pair[bl]]
                order = np.lexsort((index.id_rank[tpos_b], d_b, lines_b))
                ls = lines_b[order]
                first = order[np.r_[True, ls[1:] != ls[:-1]]]
                bld_d[lines_b[first]] = d_b[first]
                bld_id[lines_b[first]] = index.building_index[tpos_b[first]]

    # --- Ground: sample every GROUND_STEP_M, skipping GROUND_END_SKIP_M at each end.
    # Only the stretch before the nearest building blocker can change the answer.
    gnd_d = np.full(n_lines, np.inf)
    reach = np.minimum(dist - GROUND_END_SKIP_M, bld_d)
    n_samples = np.maximum(
        np.floor((reach - GROUND_END_SKIP_M) / GROUND_STEP_M).astype(np.int64) + 1, 0
    )
    ends = np.cumsum(n_samples)
    start_line = 0
    while start_line < n_lines:
        # Chunk lines so that at most GROUND_CHUNK samples are held at once.
        base = ends[start_line - 1] if start_line else 0
        stop = int(np.searchsorted(ends, base + GROUND_CHUNK, side="right"))
        stop = max(stop, start_line + 1)
        _ground_hits(scene, c, gnd_d, n_samples, start_line, stop, vx, vy, vz, ux, uy, slope)
        start_line = stop

    out: dict[tuple[int, int], tuple[bool, str | None]] = {}
    for line in range(n_lines):
        key = (observers[line // n_pts], line % n_pts)
        if bld_d[line] == np.inf and gnd_d[line] == np.inf:
            out[key] = (True, None)
        elif bld_d[line] <= gnd_d[line]:
            out[key] = (False, f"building:{scene.buildings[int(bld_id[line])].building_id}")
        else:
            out[key] = (False, GROUND)
    return out


def _ground_hits(
    scene: Scene,
    c: float,
    gnd_d: FloatArray,
    n_samples: NDArray[np.int64],
    lo: int,
    hi: int,
    vx: FloatArray,
    vy: FloatArray,
    vz: FloatArray,
    ux: FloatArray,
    uy: FloatArray,
    slope: FloatArray,
) -> None:
    """Record in ``gnd_d`` the first ground-blocked distance for lines ``lo..hi-1``."""
    counts = n_samples[lo:hi]
    total = int(counts.sum())
    if not total:
        return
    line = np.repeat(np.arange(lo, hi), counts)
    starts = np.cumsum(counts) - counts
    ds = GROUND_END_SKIP_M + (np.arange(total) - np.repeat(starts, counts)) * GROUND_STEP_M
    g = scene.ground.sample(vx[line] + ux[line] * ds, vy[line] + uy[line] * ds)
    exceed = (g - c * ds * ds) - (vz[line] + slope[line] * ds)
    hit = exceed > MARGIN_M  # NaN (nodata, e.g. open water) compares False
    np.minimum.at(gnd_d, line[hit], ds[hit])


def _not_evaluated(scene: Scene, b: Building) -> BuildingResult:
    xy = b.viewpoint_xy
    return BuildingResult(
        b.building_id,
        None if xy is None else xy[0],
        None if xy is None else xy[1],
        b.viewpoint_z if b.viewpoint_z is not None and math.isfinite(b.viewpoint_z) else None,
        b.reason,
        tuple(VisibilityResult(lm.id, NOT_EVALUATED) for lm in scene.landmarks),
    )


#: Shared with forked worker processes (copy-on-write); set only during a run.
_WORKER_STATE: tuple[Scene, _Index, list[ReferencePoint], float] | None = None


def _run_batch(batch: list[int]) -> dict[tuple[int, int], tuple[bool, str | None]]:
    assert _WORKER_STATE is not None
    scene, index, points, c = _WORKER_STATE
    return _evaluate_batch(scene, index, points, batch, c)


def compute_visibility(
    scene: Scene,
    workers: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[BuildingResult]:
    """Visibility of every landmark from every building in ``scene``.

    Returns one BuildingResult per building, sorted by ``building_id``. A
    landmark is visible when at least one of its reference points has a clear
    sight line (FR-002).

    ``workers`` is the number of processes (default: CPU count). Workers are
    forked so they share the scene and the memory-mapped ground model; where
    ``fork`` is unavailable the run is serial. The result never depends on
    ``workers`` (FR-018). ``progress(done, total)`` is called after each batch
    of observers.
    """
    global _WORKER_STATE
    points = [p for lm in scene.landmarks for p in lm.points]
    c = curvature_coefficient(scene.curvature)
    index = _build_index(scene, points)
    evaluable = [i for i, b in enumerate(scene.buildings) if b.evaluable]
    batches = [evaluable[i : i + BATCH_SIZE] for i in range(0, len(evaluable), BATCH_SIZE)]
    n_workers = workers or os.cpu_count() or 1
    outcomes: dict[tuple[int, int], tuple[bool, str | None]] = {}
    done = 0

    def collect(out: dict[tuple[int, int], tuple[bool, str | None]], size: int) -> None:
        nonlocal done
        outcomes.update(out)
        done += size
        if progress is not None:
            progress(done, len(evaluable))

    use_pool = n_workers > 1 and len(batches) > 1
    if use_pool and "fork" in multiprocessing.get_all_start_methods():
        _WORKER_STATE = (scene, index, points, c)
        try:
            with multiprocessing.get_context("fork").Pool(n_workers) as pool:
                for batch, out in zip(batches, pool.imap(_run_batch, batches, chunksize=4), strict=True):
                    collect(out, len(batch))
        finally:
            _WORKER_STATE = None
    else:
        for batch in batches:
            collect(_evaluate_batch(scene, index, points, batch, c), len(batch))

    results: list[BuildingResult] = []
    for bi, b in enumerate(scene.buildings):
        if not b.evaluable:
            results.append(_not_evaluated(scene, b))
            continue
        xy = b.viewpoint_xy
        assert xy is not None
        per_landmark: list[VisibilityResult] = []
        k = 0
        for lm in scene.landmarks:
            visible: list[str] = []
            blockers: list[tuple[str, str]] = []
            for p in lm.points:
                clear, blocker = outcomes[(bi, k)]
                k += 1
                if clear:
                    visible.append(p.id)
                else:
                    assert blocker is not None
                    blockers.append((p.id, blocker))
            status = VISIBLE if visible else NOT_VISIBLE
            per_landmark.append(VisibilityResult(lm.id, status, tuple(visible), tuple(blockers)))
        results.append(
            BuildingResult(b.building_id, xy[0], xy[1], b.viewpoint_z, None, tuple(per_landmark))
        )
    results.sort(key=lambda r: r.building_id)
    return results
