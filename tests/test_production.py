import json
from pathlib import Path
from typing import Any

import pytest

from qps_core import StageOutcome, WorkflowContext, WorkflowStage
from qps_core.production import (
    PRODUCTION_BATCH_SCHEMA,
    RoutedWorkflowKernel,
    WorkOrder,
    work_order_from_context,
)


def test_batch_runs_different_routes_with_order_traceability(
    tmp_path: Path,
) -> None:
    def prepare(context: WorkflowContext) -> StageOutcome:
        order = work_order_from_context(context)
        target = context.output_dir / "traveler.json"
        target.write_text(
            json.dumps(
                {
                    "work_order_id": order.identifier,
                    "revision": order.revision,
                    "quantity": order.quantity,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        context.register_artifact("traveler", target)
        return StageOutcome("PASS", "traveler")

    def inspect(context: WorkflowContext) -> StageOutcome:
        context.record_gate("inspection", True, "synthetic inspection passed")
        return StageOutcome("PASS", "inspection")

    def special_process(context: WorkflowContext) -> StageOutcome:
        context.record_gate("special_process", True, "synthetic process passed")
        return StageOutcome("PASS", "special_process")

    kernel = RoutedWorkflowKernel(
        "synthetic_job_shop",
        (
            WorkflowStage("prepare", prepare),
            WorkflowStage("special_process", special_process),
            WorkflowStage("inspect", inspect),
        ),
    )
    orders = (
        WorkOrder(
            "WO-100",
            "C",
            1,
            ("prepare", "special_process", "inspect"),
            {"part": "ALPHA"},
        ),
        WorkOrder(
            "WO-101",
            "A",
            3,
            ("prepare", "inspect"),
            {"part": "BETA"},
        ),
    )

    result = kernel.run_batch("BATCH-001", orders, tmp_path)
    manifest = json.loads(
        (tmp_path / "production_batch.json").read_text(encoding="utf-8")
    )

    assert result.status == "PASS"
    assert [order.completed_route for order in result.orders] == [
        ("prepare", "special_process", "inspect"),
        ("prepare", "inspect"),
    ]
    assert manifest["schema"] == PRODUCTION_BATCH_SCHEMA
    assert manifest["counts"] == {"total": 2, "pass": 2, "hold": 0}
    assert manifest["orders"][0]["revision"] == "C"
    assert manifest["orders"][1]["quantity"] == 3
    assert len(manifest["orders"][0]["payload_fingerprint"]) == 64
    assert (tmp_path / "order-0001" / "traveler.json").is_file()
    assert (tmp_path / "order-0002" / "traveler.json").is_file()


def test_held_order_stops_its_route_but_not_later_orders(tmp_path: Path) -> None:
    released: list[str] = []

    def material_gate(context: WorkflowContext) -> StageOutcome:
        ready = context.payload["material_status"] == "ready"
        context.record_gate("material_ready", ready, context.payload["material_status"])
        return StageOutcome("PASS" if ready else "HOLD", "material_ready")

    def release(context: WorkflowContext) -> StageOutcome:
        released.append(work_order_from_context(context).identifier)
        return StageOutcome("PASS", "release")

    kernel = RoutedWorkflowKernel(
        "hold_isolation",
        (
            WorkflowStage("material_gate", material_gate),
            WorkflowStage("release", release),
        ),
    )
    orders = (
        WorkOrder(
            "WO-HOLD",
            "A",
            1,
            ("material_gate", "release"),
            {"material_status": "pending"},
        ),
        WorkOrder(
            "WO-PASS",
            "B",
            1,
            ("material_gate", "release"),
            {"material_status": "ready"},
        ),
    )

    result = kernel.run_batch("BATCH-HOLD", orders, tmp_path)

    assert result.status == "HOLD"
    assert result.orders[0].completed_route == ("material_gate",)
    assert result.orders[0].remaining_route == ("release",)
    assert result.orders[1].completed_route == ("material_gate", "release")
    assert released == ["WO-PASS"]
    assert result.to_dict()["counts"] == {"total": 2, "pass": 1, "hold": 1}


def test_batch_rejects_unknown_route_before_creating_output(
    tmp_path: Path,
) -> None:
    def prepare(context: WorkflowContext) -> StageOutcome:
        return StageOutcome("PASS", "memory")

    kernel = RoutedWorkflowKernel(
        "route_validation",
        (WorkflowStage("prepare", prepare),),
    )
    output = tmp_path / "output"
    order = WorkOrder("WO-404", "A", 1, ("missing",), {})

    with pytest.raises(ValueError, match="unknown route stages"):
        kernel.run_batch("BATCH-404", (order,), output)

    assert not output.exists()


def test_batch_uses_safe_directories_instead_of_work_order_ids(
    tmp_path: Path,
) -> None:
    def prepare(context: WorkflowContext) -> StageOutcome:
        return StageOutcome("PASS", "memory")

    kernel = RoutedWorkflowKernel(
        "safe_output",
        (WorkflowStage("prepare", prepare),),
    )
    order = WorkOrder("../../external-order", "A", 1, ("prepare",), {})

    result = kernel.run_batch("BATCH-SAFE", (order,), tmp_path / "output")

    assert result.orders[0].output_reference == "order-0001"
    assert (tmp_path / "output" / "order-0001").is_dir()
    assert not (tmp_path / "external-order").exists()


@pytest.mark.parametrize("quantity", [0, -1, True, 1.5])
def test_work_order_rejects_invalid_quantity(quantity: Any) -> None:
    error = TypeError if isinstance(quantity, (bool, float)) else ValueError
    with pytest.raises(error):
        WorkOrder("WO-INVALID", "A", quantity, ("prepare",), {})


def test_work_order_requires_json_serializable_payload() -> None:
    with pytest.raises(ValueError, match="JSON serializable"):
        WorkOrder("WO-JSON", "A", 1, ("prepare",), {"value": object()})


def test_order_run_rejects_payload_changes_after_creation(
    tmp_path: Path,
) -> None:
    def prepare(context: WorkflowContext) -> StageOutcome:
        return StageOutcome("PASS", "memory")

    kernel = RoutedWorkflowKernel(
        "payload_lock",
        (WorkflowStage("prepare", prepare),),
    )
    order = WorkOrder("WO-LOCK", "A", 1, ("prepare",), {"part": "A"})
    order.payload["part"] = "B"

    with pytest.raises(ValueError, match="payload changed"):
        kernel.run_order(order, tmp_path / "output")


def test_batch_rejects_nonempty_output_to_avoid_stale_traces(
    tmp_path: Path,
) -> None:
    def prepare(context: WorkflowContext) -> StageOutcome:
        return StageOutcome("PASS", "memory")

    output = tmp_path / "output"
    output.mkdir()
    (output / "old-result.json").write_text("{}\n", encoding="utf-8")
    kernel = RoutedWorkflowKernel(
        "fresh_output",
        (WorkflowStage("prepare", prepare),),
    )
    order = WorkOrder("WO-FRESH", "A", 1, ("prepare",), {})

    with pytest.raises(ValueError, match="output_dir must be empty"):
        kernel.run_batch("BATCH-FRESH", (order,), output)
