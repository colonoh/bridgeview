"""Remaining GroundModel.from_tiles branches: resolution, partial overlap."""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from bridgeview.ground import GroundModel
from tests.synthetic_city import X0, Y0, write_tile


def test_rejects_mismatched_resolution(tmp_path: Path) -> None:
    a, b = tmp_path / "a.tif", tmp_path / "b.tif"
    write_tile(a, X0, Y0 + 10, np.zeros((10, 10)))
    with rasterio.open(b, "w", driver="GTiff", height=5, width=5, count=1, dtype="float32",
                       crs="EPSG:26910", transform=from_origin(X0 + 10, Y0 + 10, 2.0, 2.0)) as ds:
        ds.write(np.zeros((5, 5), dtype=np.float32), 1)
    with pytest.raises(ValueError, match="resolution"):
        GroundModel.from_tiles([a, b], (X0, Y0, X0 + 20, Y0 + 10), tmp_path / "c")


def test_tile_outside_the_extent_is_skipped(tmp_path: Path) -> None:
    a, b = tmp_path / "a.tif", tmp_path / "b.tif"
    write_tile(a, X0, Y0 + 10, np.full((10, 10), 4.0))
    write_tile(b, X0 + 10, Y0 + 10, np.full((10, 10), 9.0))
    g = GroundModel.from_tiles([a, b], (X0, Y0, X0 + 8, Y0 + 10), tmp_path / "c")
    assert g.z is not None and g.z.shape == (10, 8)
    assert np.asarray(g.z).tolist() == np.full((10, 8), 4.0).tolist()
