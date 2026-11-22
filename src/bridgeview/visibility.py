"""Sight-line visibility engine (research R4 and R6; data-model.md: SightLine).

All coordinates are EPSG:26910 metres and all heights NAVD88 metres.

Curvature and refraction: a point at horizontal distance ``d`` from the observer
has its height lowered by ``c * d**2``, where ``c = (1 - K) / (2 * R)``. The sight
line is then straight in ``d``, from the viewpoint height to the target's lowered
height. An obstruction blocks when it rises more than ``MARGIN_M`` above the line,
so a line that only touches a surface is not blocked (FR-006).
"""

from __future__ import annotations

import gc
import math
import multiprocessing
import os
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import shapely
from numpy.typing import NDArray

from bridgeview.ground import GroundModel
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
#: Longest segment used when querying the footprint index (m).
QUERY_SEGMENT_M = 100.0
#: Most ground samples held in memory at once.
GROUND_CHUNK = 250_000

GROUND = "ground"

#: Codes in an outcome array; any other value is the blocking building's position
#: in the index (``_Index``).
CLEAR_CODE = -1
GROUND_CODE = -2

FloatArray = NDArray[np.float64]
Outcomes = NDArray[np.int32]


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
    """Spatial index over the evaluable footprints, and the arrays a batch needs.

    Workers read only these arrays, never the Building objects: touching a Python
    object changes its reference count, which would copy its page in each worker.
    """

    tree: shapely.STRtree
    building_index: NDArray[np.intp]  # tree position -> index in scene.buildings
    top_z: FloatArray  # tree position -> top_z (m)
    contains_keys: NDArray[np.int64]  # point index * n_tree + tree position, for footprints containing a point
    id_rank: NDArray[np.intp]  # tree position -> rank of building_id (tie-break)
    bounds: FloatArray  # tree position -> (min_x, min_y, max_x, max_y), m
    viewpoint: FloatArray  # tree position -> viewpoint (x, y, z), m
    points: FloatArray  # point index -> reference point (x, y, z), m


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
    bounds = shapely.bounds(np.asarray(geoms, dtype=object)).reshape(-1, 4)
    viewpoint = np.empty((len(idx), 3))
    for t, i in enumerate(idx):
        b = scene.buildings[i]
        xy = b.viewpoint_xy
        assert xy is not None and b.viewpoint_z is not None
        viewpoint[t] = (xy[0], xy[1], b.viewpoint_z)
    point_xyz = np.array([(p.x, p.y, p.z) for p in points], dtype=np.float64).reshape(-1, 3)
    return _Index(
        tree, np.array(idx, dtype=np.intp), tops, np.sort(keys), rank, bounds, viewpoint, point_xyz
    )


def _crossed_footprints(
    index: _Index,
    vx: FloatArray,
    vy: FloatArray,
    ux: FloatArray,
    uy: FloatArray,
    dist: FloatArray,
) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    """Unique (line, tree position) pairs where a line crosses a footprint.

    A long diagonal line has a huge bounding box, so querying the tree with it
    tests thousands of footprints. Each line is split into segments of at most
    QUERY_SEGMENT_M for the query instead, and the pairs are deduplicated.
    """
    n_seg = np.maximum(np.ceil(dist / QUERY_SEGMENT_M).astype(np.int64), 1)
    line = np.repeat(np.arange(len(dist)), n_seg)
    starts = np.cumsum(n_seg) - n_seg
    k = np.arange(int(n_seg.sum())) - np.repeat(starts, n_seg)
    step = dist[line] / n_seg[line]
    d0, d1 = k * step, (k + 1) * step
    x0, y0 = vx[line] + ux[line] * d0, vy[line] + uy[line] * d0
    x1, y1 = vx[line] + ux[line] * d1, vy[line] + uy[line] * d1
    segs = shapely.linestrings(np.stack([np.c_[x0, y0], np.c_[x1, y1]], axis=1))
    si, tj = index.tree.query(segs, predicate="intersects")
    n_tree = max(len(index.building_index), 1)
    keys = np.unique(line[si].astype(np.int64) * n_tree + tj)
    return (keys // n_tree).astype(np.intp), (keys % n_tree).astype(np.intp)


def _evaluate_batch(
    ground: GroundModel,
    index: _Index,
    observers: NDArray[np.intp],
    c: float,
) -> Outcomes:
    """Outcome of every line from ``observers`` (tree positions) to every point.

    Returns an int32 array of shape (observers, points): ``CLEAR_CODE``,
    ``GROUND_CODE``, or the tree position of the nearest blocking building.
    """
    n_pts = len(index.points)
    own = np.repeat(observers, n_pts)
    vx, vy, vz = index.viewpoint[own].T
    pk = np.tile(np.arange(n_pts), len(observers))
    px, py, pz = index.points[pk].T

    dx, dy = px - vx, py - vy
    dist = np.hypot(dx, dy)
    safe = np.where(dist > 0, dist, 1.0)
    ux, uy = dx / safe, dy / safe
    slope = np.where(dist > 0, ((pz - c * dist**2) - vz) / safe, 0.0)

    n_lines = len(vx)
    bld_d = np.full(n_lines, np.inf)
    bld_pos = np.full(n_lines, -1, dtype=np.intp)

    # --- Buildings: exact intersection of each line with each crossed footprint.
    lines = shapely.linestrings(np.stack([np.c_[vx, vy], np.c_[px, py]], axis=1))
    li, tj = _crossed_footprints(index, vx, vy, ux, uy, dist)
    # Skip the observer's own footprint (FR-005) and any footprint containing the
    # target point (spec Edge Cases: a landmark's own structure).
    keep = (tj != own[li]) & (dist[li] > 0)
    if len(index.contains_keys):
        n_tree = max(len(index.building_index), 1)
        keys = pk[li].astype(np.int64) * n_tree + tj.astype(np.int64)
        keep &= ~np.isin(keys, index.contains_keys)
    li, tj = li[keep], tj[keep]
    if len(li):
        # Cheap upper bound first: the footprint's bounding box, projected onto the
        # line, contains its true stretch. If even that can't rise above the line,
        # the exact intersection is not needed.
        bx0, by0, bx1, by1 = index.bounds[tj].T
        cx = np.stack([bx0, bx1, bx1, bx0], axis=1) - vx[li, None]
        cy = np.stack([by0, by0, by1, by1], axis=1) - vy[li, None]
        proj = cx * ux[li, None] + cy * uy[li, None]
        lo = np.clip(proj.min(axis=1), 0.0, dist[li])
        hi = np.clip(proj.max(axis=1), 0.0, dist[li])
        could = max_clearance(index.top_z[tj], vz[li], slope[li], c, lo, hi) > MARGIN_M
        li, tj = li[could], tj[could]
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
                bld_pos[lines_b[first]] = tpos_b[first]

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
        _ground_hits(ground, c, gnd_d, n_samples, start_line, stop, vx, vy, vz, ux, uy, slope)
        start_line = stop

    clear_line = np.isinf(bld_d) & np.isinf(gnd_d)
    out = np.where(clear_line, CLEAR_CODE, np.where(bld_d <= gnd_d, bld_pos, GROUND_CODE))
    return out.astype(np.int32).reshape(len(observers), n_pts)


def _ground_hits(
    ground: GroundModel,
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
    g = ground.sample(vx[line] + ux[line] * ds, vy[line] + uy[line] * ds)
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
_WORKER_STATE: tuple[GroundModel, _Index, float] | None = None


def _run_batch(span: tuple[int, int]) -> Outcomes:
    assert _WORKER_STATE is not None
    ground, index, c = _WORKER_STATE
    return _evaluate_batch(ground, index, np.arange(*span, dtype=np.intp), c)


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
    n_obs = len(index.building_index)
    spans = [(i, min(i + BATCH_SIZE, n_obs)) for i in range(0, n_obs, BATCH_SIZE)]
    n_workers = workers or os.cpu_count() or 1
    # One int32 per sight line: about 9 MB for the whole city.
    outcomes = np.empty((n_obs, len(points)), dtype=np.int32)

    def collect(span: tuple[int, int], out: Outcomes) -> None:
        outcomes[span[0] : span[1]] = out
        if progress is not None:
            progress(span[1], n_obs)

    use_pool = n_workers > 1 and len(spans) > 1
    if use_pool and "fork" in multiprocessing.get_all_start_methods():
        _WORKER_STATE = (scene.ground, index, c)
        # Keep the garbage collector in the workers from writing to inherited objects.
        gc.collect()
        gc.freeze()
        try:
            with multiprocessing.get_context("fork").Pool(n_workers) as pool:
                for span, out in zip(spans, pool.imap(_run_batch, spans, chunksize=4), strict=True):
                    collect(span, out)
        finally:
            gc.unfreeze()
            _WORKER_STATE = None
    else:
        for span in spans:
            ids = np.arange(*span, dtype=np.intp)
            collect(span, _evaluate_batch(scene.ground, index, ids, c))

    # Blocker labels are shared between results rather than rebuilt per sight line.
    labels: dict[int, str] = {GROUND_CODE: GROUND}
    position = {int(bi): t for t, bi in enumerate(index.building_index)}
    results: list[BuildingResult] = []
    for bi, b in enumerate(scene.buildings):
        if not b.evaluable:
            results.append(_not_evaluated(scene, b))
            continue
        xy = b.viewpoint_xy
        assert xy is not None
        per_landmark: list[VisibilityResult] = []
        codes = iter(outcomes[position[bi]].tolist())
        for lm in scene.landmarks:
            visible: list[str] = []
            blockers: list[tuple[str, str]] = []
            for p in lm.points:
                code = next(codes)
                if code == CLEAR_CODE:
                    visible.append(p.id)
                    continue
                if code not in labels:
                    blocker = scene.buildings[index.building_index[code]]
                    labels[code] = f"building:{blocker.building_id}"
                blockers.append((p.id, labels[code]))
            status = VISIBLE if visible else NOT_VISIBLE
            per_landmark.append(VisibilityResult(lm.id, status, tuple(visible), tuple(blockers)))
        results.append(
            BuildingResult(b.building_id, xy[0], xy[1], b.viewpoint_z, None, tuple(per_landmark))
        )
    results.sort(key=lambda r: r.building_id)
    return results
