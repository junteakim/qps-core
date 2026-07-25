from __future__ import annotations

import argparse
import json
from pathlib import Path

from qps_core import StageOutcome, WorkflowContext, WorkflowStage
from qps_core.production import (
    RoutedWorkflowKernel,
    WorkOrder,
    work_order_from_context,
)


def prepare_traveler(context: WorkflowContext) -> StageOutcome:
    order = work_order_from_context(context)
    traveler = {
        "work_order_id": order.identifier,
        "revision": order.revision,
        "quantity": order.quantity,
        "part": context.payload["part"],
    }
    target = context.output_dir / "traveler.json"
    target.write_text(
        json.dumps(traveler, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    context.register_artifact("traveler", target)
    return StageOutcome("PASS", "traveler")


def material_gate(context: WorkflowContext) -> StageOutcome:
    status = context.payload.get("material_status", "not_required")
    passed = status in {"ready", "not_required"}
    context.record_gate("material_ready", passed, f"material_status={status}")
    return StageOutcome("PASS" if passed else "HOLD", "material_ready")


def final_inspection(context: WorkflowContext) -> StageOutcome:
    context.record_gate("final_inspection", True, "synthetic inspection passed")
    return StageOutcome("PASS", "final_inspection")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("hmlv-output"))
    args = parser.parse_args()
    kernel = RoutedWorkflowKernel(
        "synthetic_job_shop",
        (
            WorkflowStage("prepare_traveler", prepare_traveler),
            WorkflowStage("material_gate", material_gate),
            WorkflowStage("final_inspection", final_inspection),
        ),
    )
    orders = (
        WorkOrder(
            "SYNTHETIC-WO-001",
            "C",
            1,
            ("prepare_traveler", "material_gate", "final_inspection"),
            {
                "part": "CUSTOM-ASSEMBLY-A",
                "material_status": "ready",
            },
        ),
        WorkOrder(
            "SYNTHETIC-WO-002",
            "A",
            2,
            ("prepare_traveler", "final_inspection"),
            {
                "part": "REPAIR-ASSEMBLY-B",
            },
        ),
        WorkOrder(
            "SYNTHETIC-WO-003",
            "B",
            1,
            ("prepare_traveler", "material_gate", "final_inspection"),
            {
                "part": "CUSTOM-ASSEMBLY-C",
                "material_status": "pending",
            },
        ),
    )
    result = kernel.run_batch("SYNTHETIC-BATCH-001", orders, args.output)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
