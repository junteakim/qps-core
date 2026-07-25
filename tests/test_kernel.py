import json
from pathlib import Path

import pytest

from qps_core.kernel import (
    StageOutcome,
    WorkflowContext,
    WorkflowKernel,
    WorkflowStage,
)


def test_kernel_runs_domain_neutral_stages_and_records_evidence(
    tmp_path: Path,
) -> None:
    def normalize(context: WorkflowContext) -> StageOutcome:
        context.values["total"] = sum(context.payload["values"])
        target = context.output_dir / "normalized.json"
        target.write_text(
            json.dumps({"total": context.values["total"]}) + "\n",
            encoding="utf-8",
        )
        context.register_artifact("normalized", target)
        return StageOutcome("PASS", "normalized")

    def validate(context: WorkflowContext) -> StageOutcome:
        passed = context.values["total"] == 6
        context.record_gate("total_check", passed, "expected_total=6")
        return StageOutcome("PASS" if passed else "HOLD", "total_check")

    kernel = WorkflowKernel(
        "synthetic_aggregation",
        (
            WorkflowStage("normalize", normalize),
            WorkflowStage("validate", validate),
        ),
    )

    result = kernel.run({"values": [1, 2, 3]}, tmp_path)

    assert result.status == "PASS"
    assert result.to_dict() == {
        "workflow_id": "synthetic_aggregation",
        "status": "PASS",
        "stages": [
            {
                "id": "normalize",
                "status": "PASS",
                "output_reference": "normalized",
            },
            {
                "id": "validate",
                "status": "PASS",
                "output_reference": "total_check",
            },
        ],
        "gates": [
            {
                "id": "total_check",
                "status": "PASS",
                "evidence": "expected_total=6",
            }
        ],
        "artifacts": [{"id": "normalized", "path": "normalized.json"}],
    }


def test_kernel_reports_hold_without_hiding_later_stages(tmp_path: Path) -> None:
    def hold(context: WorkflowContext) -> StageOutcome:
        context.record_gate("review", False, "review_absent")
        return StageOutcome("HOLD", "review")

    def summarize(context: WorkflowContext) -> StageOutcome:
        context.values["summarized"] = True
        return StageOutcome("PASS", "memory")

    result = WorkflowKernel(
        "review_flow",
        (
            WorkflowStage("review", hold),
            WorkflowStage("summarize", summarize),
        ),
    ).run({}, tmp_path)

    assert result.status == "HOLD"
    assert result.values["summarized"] is True
    assert [stage["status"] for stage in result.stage_records] == ["HOLD", "PASS"]


def test_kernel_can_stop_after_hold_for_fail_closed_routing(
    tmp_path: Path,
) -> None:
    executed: list[str] = []

    def hold(context: WorkflowContext) -> StageOutcome:
        executed.append("hold")
        return StageOutcome("HOLD", "review")

    def downstream(context: WorkflowContext) -> StageOutcome:
        executed.append("downstream")
        return StageOutcome("PASS", "memory")

    result = WorkflowKernel(
        "fail_closed_route",
        (
            WorkflowStage("hold", hold),
            WorkflowStage("downstream", downstream),
        ),
    ).run({}, tmp_path, stop_on_hold=True)

    assert result.status == "HOLD"
    assert executed == ["hold"]
    assert [stage["id"] for stage in result.stage_records] == ["hold"]


def test_kernel_rejects_duplicate_stage_identifiers() -> None:
    def stage(context: WorkflowContext) -> StageOutcome:
        return StageOutcome("PASS", "memory")

    with pytest.raises(ValueError, match="stage identifiers must be unique"):
        WorkflowKernel(
            "duplicate_flow",
            (
                WorkflowStage("same", stage),
                WorkflowStage("same", stage),
            ),
        )


def test_context_rejects_duplicate_gate_and_artifact_identifiers(
    tmp_path: Path,
) -> None:
    context = WorkflowContext("test", {}, tmp_path)
    target = tmp_path / "artifact.json"
    target.write_text("{}\n", encoding="utf-8")
    context.register_artifact("result", target)
    context.record_gate("review", True, "present")

    with pytest.raises(ValueError, match="duplicate artifact"):
        context.register_artifact("result", target)
    with pytest.raises(ValueError, match="duplicate gate"):
        context.record_gate("review", True, "present")


def test_context_rejects_artifacts_outside_output_directory(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    context = WorkflowContext("test", {}, output)

    with pytest.raises(ValueError, match="inside output_dir"):
        context.register_artifact("outside", outside)

    link = output / "linked.json"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="inside output_dir"):
        context.register_artifact("linked", link)


def test_kernel_propagates_stage_failures(tmp_path: Path) -> None:
    def fail(context: WorkflowContext) -> StageOutcome:
        raise RuntimeError("stage failed")

    kernel = WorkflowKernel(
        "failing_flow",
        (WorkflowStage("fail", fail),),
    )

    with pytest.raises(RuntimeError, match="stage failed"):
        kernel.run({}, tmp_path)
