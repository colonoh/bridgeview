"""Scene entities and loaders (data-model.md: Building, Landmark, ReferencePoint, Scene).

All geometry is in EPSG:26910 (NAD83 / UTM zone 10N, metres); heights are NAVD88
metres.
"""

from __future__ import annotations

import logging
import math
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import shapely
from shapely.geometry.base import BaseGeometry

from bridgeview.errors import SceneError
from bridgeview.ground import GroundModel

log = logging.getLogger(__name__)

#: The only CRS the engine computes in (research R3).
CRS = "EPSG:26910"

#: Closed set of not-evaluated reasons (data-model.md: Building).
INVALID_GEOMETRY = "invalid_geometry"
MISSING_HEIGHT = "missing_height"
VIEWPOINT_OUTSIDE_ELEVATION_MODEL = "viewpoint_outside_elevation_model"
VIEWPOINT_BELOW_GROUND = "viewpoint_below_ground"

#: Characters a reference point id must not contain (results CSV encoding).
_FORBIDDEN_ID_CHARS = frozenset(";=,")


@dataclass(frozen=True, eq=False)
class Building:
    """One footprint: both an observer and a potential obstruction.

    ``footprint`` is a shapely Polygon or MultiPolygon in EPSG:26910 metres.
    ``viewpoint_z`` (typical roof) and ``top_z`` (highest point) are NAVD88 m.
    ``ground_z`` is NAVD88 m, used only for the zero-height check.
    ``reason`` is None when the building is evaluable, else one of the
    not-evaluated reasons above.
    """

    building_id: str
    footprint: BaseGeometry
    viewpoint_z: float | None
    top_z: float | None
    ground_z: float | None = None
    reason: str | None = None

    @property
    def evaluable(self) -> bool:
        """True when the building is observed and acts as an obstruction."""
        return self.reason is None

    @property
    def viewpoint_xy(self) -> tuple[float, float] | None:
        """The footprint's geometric centroid (m), even when it lies outside the
        footprint; None for an empty footprint."""
        if self.footprint.is_empty:
            return None
        c = self.footprint.centroid
        return (float(c.x), float(c.y))


@dataclass(frozen=True)
class ReferencePoint:
    """A point on a landmark: EPSG:26910 ``x``, ``y`` (m) and NAVD88 ``z`` (m)."""

    id: str
    x: float
    y: float
    z: float
    source: str


@dataclass(frozen=True)
class Landmark:
    """A named target with one or more reference points, in file order."""

    id: str
    name: str
    points: tuple[ReferencePoint, ...]


@dataclass(frozen=True, eq=False)
class Scene:
    """Everything one computation run needs."""

    name: str
    buildings: tuple[Building, ...]
    ground: GroundModel
    landmarks: tuple[Landmark, ...]
    dataset_version: str
    landmarks_version: str
    curvature: bool = True


def _finite(value: float | None) -> bool:
    return value is not None and math.isfinite(value)


def assess_buildings(buildings: Sequence[Building], ground: GroundModel) -> tuple[Building, ...]:
    """Return copies of ``buildings`` with ``reason`` set and ``top_z`` repaired.

    Applies the not-evaluated rules from data-model.md (Building), in order:
    invalid geometry, missing height (including zero height), viewpoint outside
    the elevation model, viewpoint below ground. A ``top_z`` below ``viewpoint_z``
    is raised to ``viewpoint_z`` with a warning.
    """
    out: list[Building] = []
    for b in buildings:
        top_z = b.top_z
        reason: str | None = None
        if b.footprint.is_empty or not b.footprint.is_valid:
            reason = INVALID_GEOMETRY
        elif (
            not _finite(b.viewpoint_z)
            or not _finite(b.top_z)
            or (_finite(b.ground_z) and b.viewpoint_z <= b.ground_z)  # type: ignore[operator]
        ):
            reason = MISSING_HEIGHT
        else:
            assert b.viewpoint_z is not None and b.top_z is not None
            xy = b.viewpoint_xy
            assert xy is not None
            g = float(ground.sample(xy[0], xy[1]))
            if math.isnan(g):
                reason = VIEWPOINT_OUTSIDE_ELEVATION_MODEL
            elif b.viewpoint_z < g:
                reason = VIEWPOINT_BELOW_GROUND
            elif b.top_z < b.viewpoint_z:
                log.warning(
                    "building %s: top_z %.2f below viewpoint_z %.2f; raised",
                    b.building_id, b.top_z, b.viewpoint_z,
                )
                top_z = b.viewpoint_z
        out.append(
            Building(b.building_id, b.footprint, b.viewpoint_z, top_z, b.ground_z, reason)
        )
    return tuple(out)


def _req(table: dict[str, Any], key: str, where: str) -> Any:
    if key not in table:
        raise SceneError(f"{where}: missing '{key}'")
    return table[key]


def _opt_float(table: dict[str, Any], key: str) -> float | None:
    v = table.get(key)
    return None if v is None else float(v)


def _load_ground(table: dict[str, Any]) -> GroundModel:
    if "constant_z" in table:
        return GroundModel.constant(float(table["constant_z"]))
    try:
        return GroundModel.from_grid(
            float(_req(table, "origin_x", "ground")),
            float(_req(table, "origin_y", "ground")),
            float(_req(table, "resolution", "ground")),
            _req(table, "z", "ground"),
        )
    except ValueError as e:
        raise SceneError(f"ground: {e}") from e


def _load_landmarks(items: list[dict[str, Any]]) -> tuple[Landmark, ...]:
    landmarks: list[Landmark] = []
    seen: set[str] = set()
    for lm in items:
        lid = str(_req(lm, "id", "landmark"))
        points: list[ReferencePoint] = []
        for p in _req(lm, "points", f"landmark {lid}"):
            pid = str(_req(p, "id", f"landmark {lid} point"))
            if pid in seen or _FORBIDDEN_ID_CHARS & set(pid):
                raise SceneError(f"reference point id '{pid}' is duplicated or contains ; = ,")
            seen.add(pid)
            where = f"point {pid}"
            points.append(
                ReferencePoint(
                    pid,
                    float(_req(p, "x", where)),
                    float(_req(p, "y", where)),
                    float(_req(p, "z", where)),
                    str(_req(p, "source", where)),
                )
            )
        if not points:
            raise SceneError(f"landmark {lid}: no points")
        landmarks.append(Landmark(lid, str(lm.get("name", lid)), tuple(points)))
    if not landmarks:
        raise SceneError("scene has no landmarks")
    return tuple(landmarks)


def load_scene(path: Path) -> Scene:
    """Load a hand-worked fixture scene (contracts/scene-fixture.md).

    The file must declare ``crs = "EPSG:26910"``; footprints and reference points
    are read as EPSG:26910 metres, and no reprojection is done.

    Raises SceneError on any missing or invalid field.
    """
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise SceneError(f"cannot read scene {path}: {e}") from e
    crs = data.get("crs")
    if crs != CRS:
        raise SceneError(f"scene crs must be {CRS!r}, got {crs!r}")
    name = str(_req(data, "name", "scene"))
    ground = _load_ground(_req(data, "ground", "scene"))
    buildings: list[Building] = []
    ids: set[str] = set()
    for b in _req(data, "buildings", "scene"):
        bid = str(_req(b, "id", "building"))
        if bid in ids:
            raise SceneError(f"duplicate building id {bid!r}")
        ids.add(bid)
        footprint = shapely.Polygon(_req(b, "footprint", f"building {bid}"))
        buildings.append(
            Building(
                bid,
                footprint,
                _opt_float(b, "viewpoint_z"),
                _opt_float(b, "top_z"),
                _opt_float(b, "ground_z"),
            )
        )
    return Scene(
        name=name,
        buildings=assess_buildings(buildings, ground),
        ground=ground,
        landmarks=_load_landmarks(_req(data, "landmarks", "scene")),
        dataset_version=name,
        landmarks_version=str(data.get("landmarks_version", "fixture")),
        curvature=bool(data.get("curvature", True)),
    )


def load_landmarks(text: str | None = None) -> tuple[str, tuple[Landmark, ...]]:
    """Load landmark reference points; return ``(landmarks_version, landmarks)``.

    Reads the packaged ``landmarks.toml`` unless ``text`` is given. Points are
    given as WGS84 latitude/longitude (EPSG:4326) and converted here to
    EPSG:26910 metres; heights are NAVD88 metres and are not changed.

    Raises SceneError if the file is invalid or has no ``landmarks_version``.
    """
    from importlib.resources import files

    from pyproj import Transformer

    if text is None:
        text = files("bridgeview").joinpath("landmarks.toml").read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise SceneError(f"landmarks.toml: {e}") from e
    version = data.get("landmarks_version")
    if not isinstance(version, str) or not version:
        raise SceneError("landmarks.toml: missing 'landmarks_version'")
    to_utm = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    items = []
    for lm in _req(data, "landmarks", "landmarks.toml"):
        points = []
        for p in _req(lm, "points", f"landmark {lm.get('id')}"):
            where = f"point {p.get('id')}"
            x, y = to_utm.transform(float(_req(p, "lon", where)), float(_req(p, "lat", where)))
            points.append({**p, "x": x, "y": y})
        items.append({**lm, "points": points})
    return version, _load_landmarks(items)


#: DataSF field -> Building field (data-model.md: Building; research R1).
CITY_FIELDS = {
    "building_id": "sf16_bldgid",
    "viewpoint_z": "median_1st_m",
    "top_z": "peak_1st_m",
    "ground_z": "gnd_min_m",
}
#: Margin around buildings and landmarks when cropping the elevation model (m).
GROUND_BUFFER_M = 500.0


def load_city_scene(data_dir: Path, pins_path: Path | None = None) -> Scene:
    """Load the pinned San Francisco data as a Scene.

    Reads the building snapshot (``*.geojson.gz``, EPSG:4326) and reprojects the
    footprints to EPSG:26910. Builds the ground model from the pinned ``*.tif``
    tiles (EPSG:26910), cropped to the buildings and landmarks plus
    ``GROUND_BUFFER_M`` and cached under ``<data_dir>/cache``. Does not verify
    checksums; callers do that first (``bridgeview.pins.verify_pins``).

    Raises SceneError if the pins don't name exactly one building file and at
    least one tile, or if a required field is missing.
    """
    import geopandas as gpd
    import numpy as np
    import pandas as pd

    from bridgeview.pins import PINS_FILE, load_pins

    pins = load_pins(pins_path or PINS_FILE, allow_insecure=True)
    raw = Path(data_dir) / "raw"
    bfiles = [raw / p.filename for p in pins if p.filename.endswith(".geojson.gz")]
    tiles = [raw / p.filename for p in pins if p.filename.endswith(".tif")]
    if len(bfiles) != 1 or not tiles:
        raise SceneError("datasets.toml must pin one *.geojson.gz and at least one *.tif")

    gdf = gpd.read_file(f"/vsigzip/{bfiles[0]}", columns=list(CITY_FIELDS.values()))
    missing = [f for f in CITY_FIELDS.values() if f not in gdf.columns]
    if missing:
        raise SceneError(f"building data is missing fields: {missing}")
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        raise SceneError(f"building data must be EPSG:4326, got {gdf.crs}")
    gdf = gdf.to_crs(CRS)  # EPSG:4326 -> EPSG:26910

    version, landmarks = load_landmarks()
    xs = [p.x for lm in landmarks for p in lm.points]
    ys = [p.y for lm in landmarks for p in lm.points]
    bx0, by0, bx1, by1 = gdf.total_bounds
    extent = (
        min(bx0, *xs) - GROUND_BUFFER_M,
        min(by0, *ys) - GROUND_BUFFER_M,
        max(bx1, *xs) + GROUND_BUFFER_M,
        max(by1, *ys) + GROUND_BUFFER_M,
    )
    ground = GroundModel.from_tiles(tiles, extent, Path(data_dir) / "cache")

    def num(col: str) -> list[float]:
        vals = pd.to_numeric(gdf[CITY_FIELDS[col]], errors="coerce").to_numpy(dtype=float)
        return [float(v) for v in np.asarray(vals)]

    ids = gdf[CITY_FIELDS["building_id"]].astype(str).tolist()
    geoms = gdf.geometry.tolist()
    buildings = [
        Building(bid, geom if geom is not None else shapely.Polygon(), vz, top, gz)
        for bid, geom, vz, top, gz in zip(
            ids, geoms, num("viewpoint_z"), num("top_z"), num("ground_z"), strict=True
        )
    ]
    return Scene(
        name="city",
        buildings=assess_buildings(buildings, ground),
        ground=ground,
        landmarks=landmarks,
        dataset_version="+".join(p.id for p in pins),
        landmarks_version=version,
        curvature=True,
    )
