from __future__ import annotations

import argparse
import json
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

from qps_core.workflow import CallerSignoff, run_public_workflow

DEFAULT_EXAMPLE = resources.files("qps_core").joinpath("resources/demo_vessel.json")


def _load_demo(path: Path | Traversable) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_demo(
    input_path: Path | Traversable,
    output_dir: Path,
    *,
    signoff: CallerSignoff | None = None,
) -> dict[str, Any]:
    payload = _load_demo(input_path)
    return run_public_workflow(payload, output_dir, signoff=signoff)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qps-core")
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo", help="run the synthetic demo")
    demo.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_EXAMPLE,
    )
    demo.add_argument(
        "--output",
        type=Path,
        default=Path("demo-output"),
    )
    demo.add_argument(
        "--signoff-by",
        dest="reviewer",
        help="record a caller-asserted signoff for this generated run",
    )
    demo.add_argument(
        "--signoff-reference",
        default="CLI_DEMO_SIGNOFF",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        signoff = (
            CallerSignoff(
                reviewer=args.reviewer,
                signoff_reference=args.signoff_reference,
            )
            if args.reviewer
            else None
        )
        print(
            json.dumps(
                run_demo(args.input, args.output, signoff=signoff),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
