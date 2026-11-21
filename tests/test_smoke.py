"""Smoke test so CI has something to collect until real specs land."""

from bridgeview import hello


def test_package_imports_and_runs() -> None:
    assert hello() == "Hello from bridgeview!"
