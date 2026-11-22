"""GroundModel.from_tiles mosaic and cache (data-model.md: GroundModel)."""

import math
from pathlib import Path

import numpy as np
import pytest

from bridgeview.ground import GroundModel
from tests.synthetic_city import NODATA, X0, Y0, write_tile


def _tiles(tmp_path: Path) -> list[Path]:
    a, b = tmp_path / "a.tif", tmp_path / "b.tif"
    west = np.arange(100 * 100, dtype=float).reshape(100, 100) % 7
    west[0:10, 0:10] = NODATA
    write_tile(a, X0, Y0 + 100, west)
    write_tile(b, X0 + 100, Y0 + 100, np.full((100, 100), 3.0))
    return [a, b]


def test_mosaic_crop_nodata_and_cache(tmp_path: Path) -> None:
    tiles = _tiles(tmp_path)
    cache = tmp_path / "cache"
    extent = (X0 + 20, Y0 + 20, X0 + 180, Y0 + 95)
    g = GroundModel.from_tiles(tiles, extent, cache)
    assert g.resolution == 1.0
    # Nodes are pixel centres: the pixel whose top-left is (X0+20, Y0+95) has centre (X0+20.5, Y0+94.5).
    assert (g.origin_x, g.origin_y) == (X0 + 20.5, Y0 + 94.5)
    assert float(g.sample(X0 + 150.5, Y0 + 50.5)) == 3.0
    # A west pixel: row 49 from the top, column 30 -> value (49*100+30) % 7.
    assert float(g.sample(X0 + 30.5, Y0 + 50.5)) == (49 * 100 + 30) % 7
    assert g.z is not None and g.z.shape[1] == 160  # cropped, spanning both tiles
    [npy] = list(cache.glob("ground_*.npy"))
    stamp = npy.stat().st_mtime_ns
    again = GroundModel.from_tiles(tiles, extent, cache)
    assert npy.stat().st_mtime_ns == stamp  # reused, not rebuilt
    assert isinstance(again.z, np.memmap)

    full = GroundModel.from_tiles(tiles, (X0 - 50, Y0 - 50, X0 + 250, Y0 + 250), cache)
    assert full.z is not None and full.z.shape == (100, 200)  # clipped to the tiles
    assert math.isnan(float(full.sample(X0 + 5, Y0 + 95)))  # nodata -> NaN


def test_rejects_wrong_crs_and_mismatched_resolution(tmp_path: Path) -> None:
    bad = tmp_path / "bad.tif"
    write_tile(bad, X0, Y0 + 100, np.zeros((10, 10)), epsg=32610)
    with pytest.raises(ValueError, match="EPSG:26910"):
        GroundModel.from_tiles([bad], (X0, Y0, X0 + 10, Y0 + 100), tmp_path / "c")
    with pytest.raises(ValueError, match="do not overlap"):
        GroundModel.from_tiles(_tiles(tmp_path), (0, 0, 10, 10), tmp_path / "c")
