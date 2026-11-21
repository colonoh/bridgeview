"""Temporary test used to confirm the main ruleset blocks failing PRs."""

from bridgeview import hello


def test_deliberately_failing() -> None:
    assert hello() == "this is wrong on purpose"
