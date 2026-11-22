"""A tiny synthetic 'city' in the pinned-data layout, for US3 tests.

Buildings use the DataSF field names (values as strings, as Socrata exports them)
in EPSG:4326. The ground is two adjacent 100 x 100 m GeoTIFF tiles in EPSG:26910
near (550000, 4180000), at 1 m resolution, with nodata = -999999.
"""

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

X0, Y0 = 550000.0, 4180000.0
NODATA = -999999.0
_TO_LL = Transformer.from_crs("EPSG:26910", "EPSG:4326", always_xy=True)


def _ring(x: float, y: float, w: float, h: float) -> list[list[float]]:
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    return [list(_TO_LL.transform(X0 + px, Y0 + py)) for px, py in pts]


def _feature(bid: str, ring: list[list[float]], median: str, peak: str, gnd: str) -> dict:  # type: ignore[type-arg]
    return {
        "type": "Feature",
        "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]},
        "properties": {"sf16_bldgid": bid, "median_1st_m": median, "peak_1st_m": peak, "gnd_min_m": gnd},
    }


#: (id, ring, median_1st_m, peak_1st_m, gnd_min_m) and the expected reason.
FEATURES = [
    ("b-normal", _ring(10, 10, 10, 10), "15.5", "20.0", "1.0"),        # evaluable
    ("b-raise", _ring(40, 10, 10, 10), "15.0", "12.0", "1.0"),         # top_z raised to 15
    ("b-zero", _ring(70, 10, 10, 10), "1.0", "9.0", "1.0"),            # missing_height
    ("b-below", _ring(120, 10, 10, 10), "4.0", "6.0", "1.0"),          # ground 5 > 4: below
    ("b-bowtie", [list(_TO_LL.transform(X0 + a, Y0 + b)) for a, b in
                  [(10, 50), (20, 60), (20, 50), (10, 60), (10, 50)]], "9", "9", "1"),  # invalid
    ("b-outside", _ring(300, 300, 10, 10), "9.0", "9.0", "1.0"),       # off the tiles
    ("b-nodata", _ring(60, 80, 4, 4), "9.0", "9.0", "1.0"),            # centroid on nodata
]
EXPECTED_REASONS = {
    "b-normal": None, "b-raise": None, "b-zero": "missing_height",
    "b-below": "viewpoint_below_ground", "b-bowtie": "invalid_geometry",
    "b-outside": "viewpoint_outside_elevation_model", "b-nodata": "viewpoint_outside_elevation_model",
}


def write_tile(path: Path, left: float, top: float, values: np.ndarray, epsg: int = 26910) -> None:
    with rasterio.open(
        path, "w", driver="GTiff", height=values.shape[0], width=values.shape[1], count=1,
        dtype="float32", crs=f"EPSG:{epsg}", transform=from_origin(left, top, 1.0, 1.0), nodata=NODATA,
    ) as ds:
        ds.write(values.astype(np.float32), 1)


def make_city(root: Path) -> tuple[Path, Path]:
    """Create ``root/data/raw/*`` and ``root/datasets.toml``; return (data_dir, pins_path)."""
    raw = root / "data" / "raw"
    raw.mkdir(parents=True)
    fc = {"type": "FeatureCollection", "features": [_feature(*f) for f in FEATURES]}
    (raw / "bldg.geojson.gz").write_bytes(gzip.compress(json.dumps(fc).encode(), mtime=0))
    west = np.ones((100, 100))  # ground 1 m
    east = np.full((100, 100), 5.0)  # ground 5 m
    west[15:25, 55:65] = NODATA  # a nodata patch (rows from the north edge)
    write_tile(raw / "west.tif", X0, Y0 + 100, west)
    write_tile(raw / "east.tif", X0 + 100, Y0 + 100, east)
    lines = []
    for name in ("bldg.geojson.gz", "west.tif", "east.tif"):
        data = (raw / name).read_bytes()
        lines.append(
            f'[[datasets]]\nid = "{name.split(".")[0]}"\nurl = "https://example.invalid/{name}"\n'
            f'sha256 = "{hashlib.sha256(data).hexdigest()}"\nsize = {len(data)}\nfilename = "{name}"\n'
            f'source = "synthetic"\nlicense = "test"\nretrieved = "2026-11-22"\n'
        )
    pins = root / "datasets.toml"
    pins.write_text("\n".join(lines))
    return root / "data", pins
