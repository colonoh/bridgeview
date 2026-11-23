"""Bridgeview: which San Francisco buildings can see the Golden Gate Bridge,
Alcatraz and the Bay Bridge.

Geometry is computed in EPSG:26910 (metres) with NAVD88 heights (metres).
"""

from importlib.metadata import version

from bridgeview.ground import GroundModel
from bridgeview.pins import verify_pins
from bridgeview.results import BuildingResult, RunMeta, VisibilityResult, write_results_csv
from bridgeview.scene import (
    Building,
    Landmark,
    ReferencePoint,
    Scene,
    load_city_scene,
    load_scene,
)
from bridgeview.visibility import compute_visibility

__version__: str = version("bridgeview")

__all__ = [
    "Building",
    "BuildingResult",
    "GroundModel",
    "Landmark",
    "ReferencePoint",
    "RunMeta",
    "Scene",
    "VisibilityResult",
    "__version__",
    "compute_visibility",
    "load_city_scene",
    "load_scene",
    "verify_pins",
    "write_results_csv",
]
