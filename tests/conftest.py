"""Shared pytest fixtures."""

from pathlib import Path

import pytest

SCENES_DIR = Path(__file__).parent / "fixtures" / "scenes"


@pytest.fixture
def scenes_dir() -> Path:
    """Directory holding the hand-worked fixture scenes."""
    return SCENES_DIR
