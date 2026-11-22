"""Smoke test: the package imports and reports its version."""

import bridgeview


def test_package_has_version() -> None:
    assert isinstance(bridgeview.__version__, str)
    assert bridgeview.__version__
