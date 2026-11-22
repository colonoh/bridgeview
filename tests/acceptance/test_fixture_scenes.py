"""US1 acceptance: every hand-worked fixture scene matches its expected CSV.

The expected CSVs hold the hand-worked answers from each scene's header comment.
The comparison is byte-for-byte except the ``software_version`` column.
"""

import csv
import io
from pathlib import Path

import pytest

from bridgeview.cli import main
from tests.conftest import SCENES_DIR

SCENES = sorted(SCENES_DIR.glob("*.toml"))


def _without_software_version(text: str) -> list[list[str]]:
    rows = list(csv.reader(io.StringIO(text)))
    col = rows[0].index("software_version")
    return [r[:col] + r[col + 1 :] for r in rows]


def test_at_least_six_scenes() -> None:  # SC-001
    assert len(SCENES) >= 6


@pytest.mark.parametrize("scene", SCENES, ids=[s.stem for s in SCENES])
def test_scene_matches_hand_worked_answer(scene: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    assert main(["compute", "--scene", str(scene), "--out", str(out)]) == 0
    expected = scene.with_name(scene.stem + ".expected.csv").read_text(encoding="utf-8")
    actual = out.read_bytes().decode("utf-8")
    assert "\r" not in actual
    assert _without_software_version(actual) == _without_software_version(expected)
    # Byte-level check of everything else: same line count and same text per line.
    assert actual.count("\n") == expected.count("\n")
