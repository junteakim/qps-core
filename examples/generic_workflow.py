from __future__ import annotations

import argparse
import json
from pathlib import Path

from qps_core import StageOutcome, WorkflowContext, WorkflowKernel, WorkflowStage


def normalize(context: WorkflowContext) -> StageOutcome:
    records = [
        {"name": str(item["name"]).strip(), "value": int(item["value"])}
        for item in context.payload["records"]
    ]
    context.values["records"] = records
    target = context.output_dir / "normalized_records.json"
    target.write_text(
        json.dumps({"records": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    context.register_artifact("normalized_records", target)
    return StageOutcome("PASS", "normalized_records")


def validate(context: WorkflowContext) -> StageOutcome:
    records = context.values["records"]
    names_are_unique = len({item["name"] for item in records}) == len(records)
    context.record_gate(
        "unique_names",
        names_are_unique,
        f"record_count={len(records)}",
    )
    return StageOutcome(
        "PASS" if names_are_unique else "HOLD",
        "unique_names",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("generic-output"))
    args = parser.parse_args()
    kernel = WorkflowKernel(
        "synthetic_record_review",
        (
            WorkflowStage("normalize", normalize),
            WorkflowStage("validate", validate),
        ),
    )
    result = kernel.run(
        {
            "records": [
                {"name": "alpha", "value": 10},
                {"name": "beta", "value": 20},
            ]
        },
        args.output,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
