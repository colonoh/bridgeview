"""Pinned downloads and verification (FR-009, FR-010, SC-006; data-model.md: DatasetPin)."""

import hashlib
from pathlib import Path

import pytest

from bridgeview.cli import main
from bridgeview.errors import ChecksumError, PinsError
from bridgeview.pins import download_all, load_pins, verify_pins
from tests.unit.conftest import LocalServer

PAYLOAD = b"building data " * 100


def _pin_toml(url: str, /, **override: object) -> str:
    fields: dict[str, object] = {
        "id": "sample",
        "url": url,
        "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        "size": len(PAYLOAD),
        "filename": "sample.bin",
        "source": "test fixture",
        "license": "public domain",
        "retrieved": "2026-11-22",
    }
    fields.update(override)
    body = "\n".join(
        f"{k} = {v}" if isinstance(v, int) else f'{k} = "{v}"'
        for k, v in fields.items()
        if v is not None
    )
    return f"[[datasets]]\n{body}\n"


@pytest.fixture
def served(http_server: LocalServer, tmp_path: Path) -> tuple[LocalServer, Path]:
    (http_server.root / "sample.bin").write_bytes(PAYLOAD)
    pins = tmp_path / "datasets.toml"
    pins.write_text(_pin_toml(f"{http_server.base_url}/sample.bin"))
    return http_server, pins


def test_download_then_skip(served: tuple[LocalServer, Path], tmp_path: Path) -> None:
    server, pins = served
    lines: list[str] = []
    data = tmp_path / "data"
    download_all(data, pins, allow_insecure=True, report=lines.append)
    assert lines == ["ok sample"]
    assert (data / "raw" / "sample.bin").read_bytes() == PAYLOAD
    assert len(server.requests) == 1

    download_all(data, pins, allow_insecure=True, report=lines.append)
    assert lines == ["ok sample", "skip sample"]
    assert len(server.requests) == 1  # no second request
    verify_pins(data, pins)


@pytest.mark.parametrize(
    "override, message",
    [
        ({"size": len(PAYLOAD) + 1}, "size mismatch for sample"),
        ({"sha256": "0" * 64}, "checksum mismatch for sample"),
    ],
)
def test_mismatch_leaves_no_file(
    http_server: LocalServer, tmp_path: Path, override: dict[str, object], message: str
) -> None:
    (http_server.root / "sample.bin").write_bytes(PAYLOAD)
    pins = tmp_path / "datasets.toml"
    pins.write_text(_pin_toml(f"{http_server.base_url}/sample.bin", **override))
    data = tmp_path / "data"
    with pytest.raises(ChecksumError, match=message):
        download_all(data, pins, allow_insecure=True, report=lambda _: None)
    assert list((data / "raw").iterdir()) == []


def test_verify_detects_tampering(served: tuple[LocalServer, Path], tmp_path: Path) -> None:
    _, pins = served
    data = tmp_path / "data"
    download_all(data, pins, allow_insecure=True, report=lambda _: None)
    with (data / "raw" / "sample.bin").open("ab") as fh:
        fh.write(b"x")
    with pytest.raises(ChecksumError):
        verify_pins(data, pins)


def test_verify_reports_missing_file(served: tuple[LocalServer, Path], tmp_path: Path) -> None:
    _, pins = served
    with pytest.raises(ChecksumError, match="run 'bridgeview download'"):
        verify_pins(tmp_path / "empty", pins)


def test_http_error_is_reported(http_server: LocalServer, tmp_path: Path) -> None:
    pins = tmp_path / "datasets.toml"
    pins.write_text(_pin_toml(f"{http_server.base_url}/missing.bin"))
    with pytest.raises(Exception, match="download failed"):
        download_all(tmp_path / "data", pins, allow_insecure=True, report=lambda _: None)
    assert list((tmp_path / "data" / "raw").iterdir()) == []


@pytest.mark.parametrize(
    "override, message",
    [
        ({"sha256": "abc"}, "sha256 must be 64"),
        ({"url": "http://example.com/x"}, "url must use https"),
        ({"license": None}, "'license' must be a non-empty string"),
        ({"retrieved": ""}, "'retrieved' must be a non-empty string"),
        ({"size": 0}, "size must be a positive integer"),
        ({"filename": "../escape.bin"}, "filename must not contain a directory"),
    ],
)
def test_malformed_pins_rejected(tmp_path: Path, override: dict[str, object], message: str) -> None:
    pins = tmp_path / "datasets.toml"
    pins.write_text(_pin_toml("https://example.com/sample.bin", **override))
    with pytest.raises(PinsError, match=message):
        load_pins(pins)


def test_missing_and_duplicate_pins(tmp_path: Path) -> None:
    with pytest.raises(PinsError, match="cannot read"):
        load_pins(tmp_path / "nope.toml")
    empty = tmp_path / "empty.toml"
    empty.write_text("")
    with pytest.raises(PinsError, match="no \\[\\[datasets\\]\\]"):
        load_pins(empty)
    dup = tmp_path / "dup.toml"
    dup.write_text(_pin_toml("https://example.com/a") * 2)
    with pytest.raises(PinsError, match="duplicate id"):
        load_pins(dup)


def test_cli_download_requires_https(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "datasets.toml").write_text(_pin_toml("http://127.0.0.1:9/sample.bin"))
    assert main(["download", "--data-dir", str(tmp_path / "data")]) == 1
    assert capsys.readouterr().err.startswith("error: ")
