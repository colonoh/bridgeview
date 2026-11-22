"""Bare-ground elevation model (data-model.md: GroundModel).

Coordinates are EPSG:26910 metres; elevations are NAVD88 metres.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike, NDArray

#: Rows read from a tile at a time when building the mosaic.
_ROW_BLOCK = 1024


@dataclass(frozen=True, eq=False)
class GroundModel:
    """Bare-ground elevations on a regular grid of nodes, or a constant plane.

    Grid node ``z[i, j]`` is the elevation at ``(origin_x + j * resolution,
    origin_y - i * resolution)``: row 0 is the northernmost row. Between nodes the
    elevation is interpolated bilinearly. NaN in ``z`` marks nodata.

    For a constant plane, ``z`` is ``None`` and every location has ``constant_z``.
    """

    origin_x: float = 0.0
    origin_y: float = 0.0
    resolution: float = 1.0
    z: NDArray[np.floating] | None = field(default=None, repr=False)
    constant_z: float = 0.0

    @classmethod
    def constant(cls, z: float) -> GroundModel:
        """A flat ground plane at elevation ``z`` (NAVD88 m) everywhere."""
        return cls(constant_z=float(z))

    @classmethod
    def from_grid(
        cls, origin_x: float, origin_y: float, resolution: float, z: ArrayLike
    ) -> GroundModel:
        """A grid of node elevations (m); see the class docstring for the layout.

        Raises ValueError if the grid is not 2-D with at least 2x2 nodes or the
        resolution is not positive.
        """
        arr = np.asarray(z, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[0] < 2 or arr.shape[1] < 2:
            raise ValueError("ground grid must be 2-D with at least 2x2 nodes")
        if not resolution > 0:
            raise ValueError("ground grid resolution must be positive")
        return cls(float(origin_x), float(origin_y), float(resolution), arr)

    def sample(self, x: ArrayLike, y: ArrayLike) -> NDArray[np.float64]:
        """Ground elevation (NAVD88 m) at EPSG:26910 points ``x``, ``y`` (m).

        Inputs broadcast like numpy arrays. Returns NaN outside the grid, or where
        any of the four surrounding nodes is nodata.
        """
        xa = np.asarray(x, dtype=np.float64)
        ya = np.asarray(y, dtype=np.float64)
        if self.z is None:
            return np.full(np.broadcast(xa, ya).shape, self.constant_z)
        xa, ya = np.broadcast_arrays(xa, ya)
        rows, cols = self.z.shape
        fx = (xa - self.origin_x) / self.resolution
        fy = (self.origin_y - ya) / self.resolution
        inside = (fx >= 0) & (fy >= 0) & (fx <= cols - 1) & (fy <= rows - 1)
        j0 = np.clip(np.floor(np.where(inside, fx, 0)).astype(np.intp), 0, cols - 2)
        i0 = np.clip(np.floor(np.where(inside, fy, 0)).astype(np.intp), 0, rows - 2)
        tx = np.where(inside, fx, 0) - j0
        ty = np.where(inside, fy, 0) - i0
        z = self.z
        top = z[i0, j0] * (1 - tx) + z[i0, j0 + 1] * tx
        bottom = z[i0 + 1, j0] * (1 - tx) + z[i0 + 1, j0 + 1] * tx
        out = top * (1 - ty) + bottom * ty
        return np.where(inside, out, np.nan)

    @classmethod
    def from_tiles(
        cls,
        paths: Sequence[Path],
        extent: tuple[float, float, float, float],
        cache_dir: Path,
    ) -> GroundModel:
        """Mosaic GeoTIFF tiles into a grid covering ``extent``, cached on disk.

        ``extent`` is ``(min_x, min_y, max_x, max_y)`` in EPSG:26910 metres. Every
        tile must be EPSG:26910 with the same resolution; pixel centres become
        grid nodes, and nodata becomes NaN. The mosaic is written tile by tile into
        ``cache_dir/ground_<key>.npy`` and reopened memory-mapped, so it is never
        held in memory whole and worker processes can share it. The cache key
        covers the tile names, sizes and the extent.

        Raises ValueError on a CRS or resolution mismatch.
        """
        import rasterio
        from rasterio.windows import Window, from_bounds
        from rasterio.windows import bounds as window_bounds

        paths = [Path(p) for p in paths]
        key_src = json.dumps(
            [[p.name, p.stat().st_size] for p in sorted(paths)] + [list(extent)]
        )
        key = hashlib.sha256(key_src.encode()).hexdigest()[:16]
        cache_dir = Path(cache_dir)
        npy, meta_path = cache_dir / f"ground_{key}.npy", cache_dir / f"ground_{key}.json"
        if npy.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text())
            z = np.load(npy, mmap_mode="r")
            return cls(meta["origin_x"], meta["origin_y"], meta["resolution"], z)

        res: float | None = None
        for p in paths:
            with rasterio.open(p) as ds:
                if ds.crs is None or ds.crs.to_epsg() != 26910:
                    raise ValueError(f"{p.name}: CRS must be EPSG:26910, got {ds.crs}")
                if res is None:
                    res = float(ds.res[0])
                if ds.res[0] != res or ds.res[1] != res:
                    raise ValueError(f"{p.name}: resolution {ds.res} differs from {res}")
        assert res is not None
        # Clip the extent to the area the tiles cover; beyond it is nodata anyway.
        tb = []
        for p in paths:
            with rasterio.open(p) as ds:
                tb.append(ds.bounds)
        min_x = max(extent[0], min(b.left for b in tb))
        min_y = max(extent[1], min(b.bottom for b in tb))
        max_x = min(extent[2], max(b.right for b in tb))
        max_y = min(extent[3], max(b.top for b in tb))
        if min_x >= max_x or min_y >= max_y:
            raise ValueError("the tiles do not overlap the requested extent")
        # Snap the grid to whole pixels of the first tile so nodes are pixel centres.
        with rasterio.open(paths[0]) as ds:
            ref_left, ref_top = ds.bounds.left, ds.bounds.top
        col0 = np.floor((min_x - ref_left) / res)
        row0 = np.floor((ref_top - max_y) / res)
        left, top = ref_left + col0 * res, ref_top - row0 * res
        ncols = int(np.ceil((max_x - left) / res))
        nrows = int(np.ceil((top - min_y) / res))

        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = npy.with_name(npy.name + ".tmp.npy")
        z_out = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float32, shape=(nrows, ncols))
        z_out[:] = np.nan
        for p in paths:
            with rasterio.open(p) as ds:
                b = ds.bounds
                ix0, iy1 = max(left, b.left), min(top, b.top)
                ix1, iy0 = min(left + ncols * res, b.right), max(top - nrows * res, b.bottom)
                if ix0 >= ix1 or iy0 >= iy1:
                    continue
                win = from_bounds(ix0, iy0, ix1, iy1, transform=ds.transform)
                win = win.round_offsets().round_lengths()
                wl, _, _, wt = window_bounds(win, ds.transform)
                r0 = int(round((top - wt) / res))
                c = int(round((wl - left) / res))
                w = min(int(win.width), ncols - c)
                # Read in blocks of rows to bound memory use.
                for off in range(0, int(win.height), _ROW_BLOCK):
                    h = min(_ROW_BLOCK, int(win.height) - off, nrows - r0 - off)
                    if h <= 0:
                        break
                    block = Window(win.col_off, win.row_off + off, w, h)
                    data = ds.read(1, window=block).astype(np.float32)
                    if ds.nodata is not None:
                        data[data == ds.nodata] = np.nan
                    dest = z_out[r0 + off : r0 + off + h, c : c + w]
                    # Where tiles overlap, keep existing data and fill only the gaps.
                    np.copyto(dest, data, where=np.isnan(dest))
        z_out.flush()
        del z_out
        os.replace(tmp, npy)
        meta = {"origin_x": left + res / 2, "origin_y": top - res / 2, "resolution": res}
        meta_path.write_text(json.dumps(meta))
        return cls(meta["origin_x"], meta["origin_y"], res, np.load(npy, mmap_mode="r"))
