"""The ``bridgeview`` command line (contracts/cli.md).

Exit codes: 0 success, 1 bad input or verification failure, 2 usage error.
Errors are printed to stderr as a single line starting with ``error:``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from bridgeview.errors import BridgeviewError


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _UsageError(message)


def _build_parser() -> _Parser:
    parser = _Parser(prog="bridgeview", description="Building landmark visibility.")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    dl = sub.add_parser("download", help="fetch and verify the pinned city datasets")
    dl.add_argument("--data-dir", type=Path, default=Path("data"))

    comp = sub.add_parser("compute", help="compute visibility and write the results CSV")
    src = comp.add_mutually_exclusive_group(required=True)
    src.add_argument("--city", action="store_true", help="use the pinned city data")
    src.add_argument("--scene", type=Path, help="use a hand-worked fixture scene")
    comp.add_argument("--out", type=Path, required=True)
    comp.add_argument("--data-dir", type=Path, default=Path("data"))
    comp.add_argument("--workers", type=int, default=None)

    snap = sub.add_parser("snapshot-buildings", help="(maintainer) snapshot the DataSF export")
    snap.add_argument("--out", type=Path, required=True)
    return parser


def _compute(args: argparse.Namespace) -> int:
    from bridgeview import __version__
    from bridgeview.results import RunMeta, write_results_csv
    from bridgeview.scene import load_scene
    from bridgeview.visibility import compute_visibility

    if args.city:
        raise NotImplementedError("compute --city is not implemented yet")
    scene = load_scene(args.scene)
    results = compute_visibility(scene, workers=args.workers)
    meta = RunMeta(scene.dataset_version, scene.landmarks_version, __version__)
    write_results_csv(results, args.out, meta, [lm.id for lm in scene.landmarks])
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI with ``argv`` (defaults to ``sys.argv[1:]``); return the exit code."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except _UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except SystemExit as e:  # --help
        return int(e.code or 0)
    try:
        if args.command == "compute":
            return _compute(args)
        if args.command == "download":
            from bridgeview.pins import download_all

            download_all(args.data_dir)
            return 0
        if args.command == "snapshot-buildings":
            from bridgeview.pins import snapshot_buildings

            size, sha = snapshot_buildings(args.out)
            print(f"size {size}\nsha256 {sha}")
            return 0
        raise NotImplementedError(f"'{args.command}' is not implemented yet")  # pragma: no cover
    except BridgeviewError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except NotImplementedError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
