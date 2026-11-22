"""Bare-ground elevation model (data-model.md: GroundModel).

Coordinates are EPSG:26910 metres; elevations are NAVD88 metres.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import ArrayLike, NDArray


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
