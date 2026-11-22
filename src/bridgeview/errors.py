"""Exception types that the CLI turns into ``error: ...`` messages with exit code 1."""


class BridgeviewError(Exception):
    """Base class for expected, user-facing failures (bad input, failed verification)."""


class SceneError(BridgeviewError):
    """A scene file or dataset could not be loaded or is invalid."""


class PinsError(BridgeviewError):
    """``datasets.toml`` is missing or malformed."""


class ChecksumError(BridgeviewError):
    """A pinned file is missing or does not match its recorded size or SHA-256."""


class DownloadError(BridgeviewError):
    """A download failed (network or HTTP error)."""
