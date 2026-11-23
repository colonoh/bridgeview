"""Visibility results and the results CSV writer (contracts/results-csv.md).

Viewpoints are held in EPSG:26910 metres and written as EPSG:4326 longitude and
latitude; heights are NAVD88 metres.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from pyproj import Transformer

VISIBLE = "visible"
NOT_VISIBLE = "not_visible"
NOT_EVALUATED = "not_evaluated"

#: EPSG:26910 (UTM 10N, m) -> EPSG:4326 (lon, lat in degrees).
_TO_WGS84 = Transformer.from_crs("EPSG:26910", "EPSG:4326", always_xy=True)


@dataclass(frozen=True)
class VisibilityResult:
    """One building's outcome for one landmark (data-model.md: VisibilityResult).

    ``visible_points`` lists clear reference point ids, and ``blockers`` lists
    ``(point_id, blocker)`` pairs, where blocker is ``building:<id>`` or ``ground``.
    Both are in landmarks-file order.
    """

    landmark_id: str
    status: str
    visible_points: tuple[str, ...] = ()
    blockers: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class BuildingResult:
    """All landmark results for one building, plus its viewpoint.

    ``viewpoint_x``/``viewpoint_y`` are EPSG:26910 metres (None for an empty
    footprint); ``viewpoint_z`` is NAVD88 metres (None if missing).
    """

    building_id: str
    viewpoint_x: float | None
    viewpoint_y: float | None
    viewpoint_z: float | None
    not_evaluated_reason: str | None
    landmarks: tuple[VisibilityResult, ...]


@dataclass(frozen=True)
class RunMeta:
    """Run identity written into every row (FR-016)."""

    dataset_version: str
    landmarks_version: str
    software_version: str


def _fmt(value: float | None, decimals: int) -> str:
    if value is None:
        return ""
    text = f"{value:.{decimals}f}"
    if text.lstrip("-").strip("0.") == "":  # avoid "-0.00"
        text = text.lstrip("-")
    return text


def header(landmark_ids: Sequence[str]) -> list[str]:
    """The results CSV column names (contracts/results-csv.md): the building columns,
    three columns per landmark in ``landmark_ids`` order, then the run metadata."""
    cols = ["building_id", "lon", "lat", "viewpoint_z_m", "not_evaluated_reason"]
    for lid in landmark_ids:
        cols += [f"{lid}_status", f"{lid}_visible_points", f"{lid}_blockers"]
    return cols + ["dataset_version", "landmarks_version", "software_version"]


def _row(result: BuildingResult, meta: RunMeta) -> list[str]:
    lon = lat = None
    if result.viewpoint_x is not None and result.viewpoint_y is not None:
        lon, lat = _TO_WGS84.transform(result.viewpoint_x, result.viewpoint_y)
    row = [
        result.building_id,
        _fmt(lon, 7),
        _fmt(lat, 7),
        _fmt(result.viewpoint_z, 2),
        result.not_evaluated_reason or "",
    ]
    for lm in result.landmarks:
        row += [
            lm.status,
            ";".join(lm.visible_points),
            ";".join(f"{p}={b}" for p, b in lm.blockers),
        ]
    return row + [meta.dataset_version, meta.landmarks_version, meta.software_version]


def write_results_csv(
    results: Iterable[BuildingResult],
    path: Path,
    meta: RunMeta,
    landmark_ids: Sequence[str],
) -> None:
    """Write the results CSV to ``path`` (contracts/results-csv.md).

    Viewpoints are converted from EPSG:26910 metres to EPSG:4326 longitude and
    latitude; heights are NAVD88 metres. ``landmark_ids`` fixes the column order
    even when ``results`` is empty. Rows are sorted by ``building_id``. The file
    is written to ``<path>.tmp``
    and renamed into place, so a failed run leaves no partial file.
    """
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    ordered = sorted(results, key=lambda r: r.building_id)
    try:
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow(header(landmark_ids))
            for r in ordered:
                writer.writerow(_row(r, meta))
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
