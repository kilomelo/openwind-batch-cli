"""Command-line interface for owbatch."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from owbatch import __version__
from owbatch.models import InspectRequest, RunRequest
from owbatch.runner import inspect_inputs, run_batch


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level argparse parser."""

    parser = argparse.ArgumentParser(
        prog="owbatch",
        description="Batch CLI for OpenWind frequency-domain research workflows.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect template and cases inputs before execution.",
    )
    inspect_parser.add_argument(
        "--template-dir",
        required=True,
        type=Path,
        help="Directory containing bore_template.csv, holes_template.csv, and fingering_template.csv.",
    )
    inspect_parser.add_argument(
        "--cases",
        required=True,
        type=Path,
        help="Path to cases.csv.",
    )
    inspect_parser.set_defaults(handler=_handle_inspect)

    run_parser = subparsers.add_parser(
        "run",
        help="Execute a batch run and write CSV outputs.",
    )
    run_parser.add_argument(
        "--template-dir",
        required=True,
        type=Path,
        help="Directory containing bore_template.csv, holes_template.csv, and fingering_template.csv.",
    )
    run_parser.add_argument(
        "--cases",
        required=True,
        type=Path,
        help="Path to cases.csv.",
    )
    run_parser.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Directory for impedance.csv, features.csv, and analysis.csv.",
    )
    run_parser.set_defaults(handler=_handle_run)

    return parser


def _handle_inspect(args: argparse.Namespace) -> int:
    request = InspectRequest(
        template_dir=args.template_dir,
        cases_path=args.cases,
    )
    print(inspect_inputs(request))
    return 0


def _handle_run(args: argparse.Namespace) -> int:
    request = RunRequest(
        template_dir=args.template_dir,
        cases_path=args.cases,
        out_dir=args.out_dir,
    )
    print(run_batch(request))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    handler = args.handler
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
