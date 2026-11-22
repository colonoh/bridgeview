"""Maintainer snapshot of the DataSF export (contracts/cli.md: snapshot-buildings)."""

import gzip
import hashlib
from pathlib import Path

import pytest

from bridgeview.errors import DownloadError
from bridgeview.pins import snapshot_buildings
from tests.unit.conftest import LocalServer

GEOJSON = b'{"type": "FeatureCollection", "features": []}' * 50


def test_snapshot_is_repeatable(http_server: LocalServer, tmp_path: Path) -> None:
    (http_server.root / "export.geojson").write_bytes(GEOJSON)
    url = f"{http_server.base_url}/export.geojson"
    a, b = tmp_path / "a.geojson.gz", tmp_path / "b.geojson.gz"
    size_a, sha_a = snapshot_buildings(a, url)
    size_b, sha_b = snapshot_buildings(b, url)
    assert a.read_bytes() == b.read_bytes()
    assert (size_a, sha_a) == (size_b, sha_b)
    assert sha_a == hashlib.sha256(a.read_bytes()).hexdigest()
    assert size_a == a.stat().st_size
    assert gzip.decompress(a.read_bytes()) == GEOJSON


def test_snapshot_http_error_leaves_nothing(http_server: LocalServer, tmp_path: Path) -> None:
    out = tmp_path / "snap.geojson.gz"
    with pytest.raises(DownloadError):
        snapshot_buildings(out, f"{http_server.base_url}/missing")
    assert list(tmp_path.iterdir()) == [http_server.root]


def test_cli_prints_size_and_sha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import bridgeview.pins
    from bridgeview.cli import main

    calls: list[Path] = []

    def fake(out: Path) -> tuple[int, str]:
        calls.append(out)
        return 123, "ab" * 32

    monkeypatch.setattr(bridgeview.pins, "snapshot_buildings", fake)
    assert main(["snapshot-buildings", "--out", str(tmp_path / "s.gz")]) == 0
    assert calls == [tmp_path / "s.gz"]
    assert capsys.readouterr().out == f"size 123\nsha256 {'ab' * 32}\n"
