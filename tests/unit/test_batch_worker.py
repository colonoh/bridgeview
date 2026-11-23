"""The worker entry point returns the same outcomes as a direct call."""

import numpy as np
import pytest

from bridgeview import visibility
from tests.unit.test_batch_outcomes import _scene


def test_run_batch_uses_worker_state(monkeypatch: pytest.MonkeyPatch) -> None:
    scene = _scene()
    index = visibility._build_index(scene, list(scene.landmarks[0].points))
    monkeypatch.setattr(visibility, "_WORKER_STATE", (scene.ground, index, 0.0))
    got = visibility._run_batch((0, 2))
    assert got.tolist() == visibility._evaluate_batch(scene.ground, index, np.array([0, 1]), 0.0).tolist()
