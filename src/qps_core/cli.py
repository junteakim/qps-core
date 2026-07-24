from __future__ import annotations

import argparse
import json
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

from qps_core.asme import (
    calculate_elliptical_head_2_to_1_thickness,
    calculate_shell_thickness,
)
from qps_core.excel import (
    build_review_workbook,
    verify_formula_workbook,
    write_snapshot,
)
from qps_core.models import (
    CostLine,
    EllipticalHeadInput,
    MaterialProperties,
    VesselInput,
)
from qps_core.ontology import validate_snapshot
from qps_core.quotation import QuoteEngine

DEFAULT_EXAMPLE = resources.files("qps_core").joinpath("resources/demo_vessel.json")


def _load_demo(path: Path | Traversable) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_demo(
    input_path: Path | Traversable,
    output_dir: Path,
) -> dict[str, Any]:
    payload = _load_demo(input_path)
    material_payload = payload["vessel"]["material"]
    material = MaterialProperties(**material_payload)
    vessel_payload = dict(payload["vessel"])
    vessel_payload["material"] = material
    vessel = VesselInput(**vessel_payload)
    shell = calculate_shell_thickness(vessel)
    head = calculate_elliptical_head_2_to_1_thickness(
        EllipticalHeadInput(
            vessel=vessel,
            inside_depth_mm=payload["head"]["inside_depth_mm"],
        )
    )

    lines = [CostLine(**line) for line in payload["cost_lines"]]
    snapshot = QuoteEngine().calculate(
        quote_id=payload["quote_id"],
        currency=payload["currency"],
        lines=lines,
        overhead_percent=payload["overhead_percent"],
        profit_percent=payload["profit_percent"],
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = build_review_workbook(
        snapshot,
        output_dir / "review_workbook.xlsx",
    )
    snapshot_path = write_snapshot(
        snapshot,
        output_dir / "final_snapshot.json",
    )
    engineering_path = output_dir / "engineering_demo.json"
    engineering_path.write_text(
        json.dumps(
            {
                "schema": "qps.public.engineering_demo.v1",
                "synthetic_demo": True,
                "tag": vessel.tag,
                "shell": shell.to_dict(),
                "elliptical_head": head.to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    formula_issues = verify_formula_workbook(workbook_path)
    ontology_result = validate_snapshot(snapshot.to_dict())
    if formula_issues:
        raise RuntimeError(f"formula verification failed: {formula_issues}")
    if not ontology_result.conforms:
        raise RuntimeError(f"ontology validation failed: {ontology_result.report_text}")
    return {
        "synthetic_demo": True,
        "workbook": str(workbook_path),
        "snapshot": str(snapshot_path),
        "engineering": str(engineering_path),
        "formula_verifier": "PASS",
        "shacl": "PASS",
    }


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        print(
            json.dumps(
                run_demo(args.input, args.output),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
