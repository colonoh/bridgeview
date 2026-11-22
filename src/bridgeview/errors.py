"""Exception types that the CLI turns into ``error: ...`` messages with exit code 1."""


class BridgeviewError(Exception):
    """Base class for expected, user-facing failures (bad input, failed verification)."""


class SceneError(BridgeviewError):
    """A scene file or dataset could not be loaded or is invalid."""
