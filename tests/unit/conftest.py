"""A local HTTP server fixture for download tests (no internet access needed)."""

import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest


@dataclass
class LocalServer:
    """Serves ``root`` over HTTP; ``requests`` records each requested path."""

    root: Path
    base_url: str
    requests: list[str] = field(default_factory=list)


@pytest.fixture
def http_server(tmp_path: Path) -> Iterator[LocalServer]:
    root = tmp_path / "www"
    root.mkdir()
    requests: list[str] = []

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            super().do_GET()

        def log_message(self, format: str, *args: Any) -> None:  # keep test output quiet
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield LocalServer(root, f"http://127.0.0.1:{server.server_port}", requests)
    finally:
        server.shutdown()
        server.server_close()
