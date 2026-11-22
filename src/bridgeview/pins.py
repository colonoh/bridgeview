"""Pinned datasets: download and verify (FR-009, FR-010; data-model.md: DatasetPin).

``datasets.toml`` lists each file with its URL, size, SHA-256 and provenance.
Files are downloaded to ``<data_dir>/raw/<filename>``. A download goes to a
``.part`` file first and is renamed into place only after its size and SHA-256
match, so later steps never see a bad file.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from bridgeview.errors import ChecksumError, DownloadError, PinsError

#: Default location of the pin file, relative to the working directory.
PINS_FILE = Path("datasets.toml")
#: DataSF Building Footprints (ynuv-fyni) GeoJSON export (research R1).
DATASF_BUILDINGS_EXPORT_URL = (
    "https://data.sfgov.org/api/geospatial/ynuv-fyni?method=export&format=GeoJSON"
)

_CHUNK = 1 << 20
_SHA256 = re.compile(r"[0-9a-f]{64}")
_PROVENANCE = ("source", "license", "retrieved")


@dataclass(frozen=True)
class DatasetPin:
    """One pinned file (data-model.md: DatasetPin). ``size`` is in bytes."""

    id: str
    url: str
    sha256: str
    size: int
    filename: str
    source: str
    license: str
    retrieved: str


def _user_agent() -> str:
    from bridgeview import __version__

    return f"bridgeview/{__version__}"


def load_pins(pins_path: Path = PINS_FILE, *, allow_insecure: bool = False) -> list[DatasetPin]:
    """Read and validate the pin file.

    Every ``url`` must be HTTPS. ``allow_insecure`` also permits ``http://``, for
    tests against a local server only; the CLI never sets it.

    Raises PinsError if the file is missing or any entry is invalid.
    """
    try:
        data = tomllib.loads(Path(pins_path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PinsError(f"cannot read {pins_path}: {exc}") from exc
    entries = data.get("datasets")
    if not isinstance(entries, list) or not entries:
        raise PinsError(f"{pins_path}: no [[datasets]] entries")
    pins: list[DatasetPin] = []
    seen: set[str] = set()
    for i, e in enumerate(entries):
        where = f"{pins_path}: dataset {e.get('id', i)!r}"
        for key in ("id", "url", "sha256", "filename", *_PROVENANCE):
            if not isinstance(e.get(key), str) or not e[key].strip():
                raise PinsError(f"{where}: '{key}' must be a non-empty string")
        if e["id"] in seen:
            raise PinsError(f"{where}: duplicate id")
        seen.add(e["id"])
        schemes = ("https://", "http://") if allow_insecure else ("https://",)
        if not e["url"].startswith(schemes):
            raise PinsError(f"{where}: url must use https")
        if not _SHA256.fullmatch(e["sha256"]):
            raise PinsError(f"{where}: sha256 must be 64 lowercase hex characters")
        size = e.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise PinsError(f"{where}: size must be a positive integer")
        if Path(e["filename"]).name != e["filename"]:
            raise PinsError(f"{where}: filename must not contain a directory")
        pins.append(
            DatasetPin(e["id"], e["url"], e["sha256"], size, e["filename"],
                       e["source"], e["license"], e["retrieved"])
        )
    return pins


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def check_file(pin: DatasetPin, path: Path) -> None:
    """Raise ChecksumError unless ``path`` exists and matches ``pin``'s size and SHA-256."""
    if not path.is_file():
        raise ChecksumError(f"missing {path} for {pin.id}; run 'bridgeview download'")
    size = path.stat().st_size
    if size != pin.size:
        raise ChecksumError(f"size mismatch for {pin.id}: expected {pin.size} bytes, got {size}")
    got = _sha256_of(path)
    if got != pin.sha256:
        raise ChecksumError(f"checksum mismatch for {pin.id}: expected {pin.sha256}, got {got}")


def _fetch(url: str, sink: BinaryIO, limit: int | None = None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            written = 0
            while chunk := resp.read(_CHUNK):
                written += len(chunk)
                if limit is not None and written > limit:
                    return  # too big; the size check reports it
                sink.write(chunk)
    except (urllib.error.URLError, OSError) as e:
        raise DownloadError(f"download failed for {url}: {e}") from e


def download_all(
    data_dir: Path,
    pins_path: Path = PINS_FILE,
    *,
    allow_insecure: bool = False,
    report: Callable[[str], None] = print,
) -> None:
    """Fetch every pinned file into ``<data_dir>/raw/`` and verify it.

    Files that already match are skipped (``skip <id>``); others are downloaded
    and reported as ``ok <id>``. On a size or checksum mismatch the partial file
    is deleted and ChecksumError is raised.
    """
    raw = Path(data_dir) / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for pin in load_pins(pins_path, allow_insecure=allow_insecure):
        final = raw / pin.filename
        try:
            check_file(pin, final)
            report(f"skip {pin.id}")
            continue
        except ChecksumError:
            pass
        part = final.with_name(final.name + ".part")
        try:
            with part.open("wb") as fh:
                _fetch(pin.url, fh, limit=pin.size)
            check_file(pin, part)
            os.replace(part, final)
        finally:
            part.unlink(missing_ok=True)
        report(f"ok {pin.id}")


def verify_pins(data_dir: Path, pins_path: Path = PINS_FILE) -> list[DatasetPin]:
    """Check every pinned file under ``<data_dir>/raw/``; return the pins.

    Raises ChecksumError on the first missing or mismatched file (SC-006).
    """
    # Only local files are checked here, so the URL scheme is irrelevant.
    pins = load_pins(pins_path, allow_insecure=True)
    for pin in pins:
        check_file(pin, Path(data_dir) / "raw" / pin.filename)
    return pins


def snapshot_buildings(out: Path, url: str = DATASF_BUILDINGS_EXPORT_URL) -> tuple[int, str]:
    """(Maintainer) Save the DataSF export at ``url`` as a repeatable gzip file.

    The gzip header has no file name and a zero timestamp, so the same input
    always gives the same bytes. Returns ``(size in bytes, sha256 hex)``.
    The file is written to ``<out>.tmp`` first; on failure nothing is left.
    """
    out = Path(out)
    tmp = out.with_name(out.name + ".tmp")
    try:
        with tmp.open("wb") as raw_fh, gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_fh, mtime=0
        ) as gz:
            _fetch(url, gz)  # type: ignore[arg-type]
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    return out.stat().st_size, _sha256_of(out)


__all__ = [
    "DATASF_BUILDINGS_EXPORT_URL",
    "PINS_FILE",
    "DatasetPin",
    "check_file",
    "download_all",
    "load_pins",
    "snapshot_buildings",
    "verify_pins",
]
