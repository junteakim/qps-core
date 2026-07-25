from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

StageStatus = Literal["PASS", "HOLD"]


@dataclass(frozen=True)
class StageOutcome:
    status: StageStatus
    output_reference: str

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "HOLD"}:
            raise ValueError("stage status must be PASS or HOLD")
        if not self.output_reference.strip():
            raise ValueError("output_reference is required")


@dataclass
class WorkflowContext:
    workflow_id: str
    payload: dict[str, Any]
    output_dir: Path
    values: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Path] = field(default_factory=dict)
    gates: list[dict[str, str]] = field(default_factory=list)
    stage_records: list[dict[str, str]] = field(default_factory=list)

    def register_artifact(self, identifier: str, path: str | Path) -> Path:
        artifact_id = _validated_identifier(identifier, "artifact")
        if artifact_id in self.artifacts:
            raise ValueError(f"duplicate artifact identifier: {artifact_id}")
        target = Path(path).resolve()
        root = self.output_dir.resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"artifact must stay inside output_dir: {target}")
        if not target.is_file():
            raise ValueError(f"artifact does not exist: {target}")
        self.artifacts[artifact_id] = target
        return target

    def record_gate(
        self,
        identifier: str,
        passed: bool,
        evidence: str,
    ) -> None:
        gate_id = _validated_identifier(identifier, "gate")
        if any(gate["id"] == gate_id for gate in self.gates):
            raise ValueError(f"duplicate gate identifier: {gate_id}")
        if not evidence.strip():
            raise ValueError("gate evidence is required")
        self.gates.append(
            {
                "id": gate_id,
                "status": "PASS" if passed else "HOLD",
                "evidence": evidence,
            }
        )

    @property
    def status(self) -> StageStatus:
        statuses = [
            *(stage["status"] for stage in self.stage_records),
            *(gate["status"] for gate in self.gates),
        ]
        return (
            "PASS" if statuses and all(item == "PASS" for item in statuses) else "HOLD"
        )

    def to_dict(self) -> dict[str, Any]:
        root = self.output_dir.resolve()
        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "stages": [dict(stage) for stage in self.stage_records],
            "gates": [dict(gate) for gate in self.gates],
            "artifacts": [
                {
                    "id": identifier,
                    "path": path.relative_to(root).as_posix(),
                }
                for identifier, path in self.artifacts.items()
            ],
        }


StageHandler = Callable[[WorkflowContext], StageOutcome]


@dataclass(frozen=True)
class WorkflowStage:
    identifier: str
    handler: StageHandler

    def __post_init__(self) -> None:
        _validated_identifier(self.identifier, "stage")
        if not callable(self.handler):
            raise TypeError("stage handler must be callable")


@dataclass(frozen=True)
class WorkflowKernel:
    workflow_id: str
    stages: tuple[WorkflowStage, ...]

    def __post_init__(self) -> None:
        _validated_identifier(self.workflow_id, "workflow")
        if not self.stages:
            raise ValueError("workflow requires at least one stage")
        identifiers = [stage.identifier for stage in self.stages]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("stage identifiers must be unique")

    def run(
        self,
        payload: dict[str, Any],
        output_dir: str | Path,
        *,
        initial_values: dict[str, Any] | None = None,
        stop_on_hold: bool = False,
    ) -> WorkflowContext:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        context = WorkflowContext(
            workflow_id=self.workflow_id,
            payload=dict(payload),
            output_dir=output.resolve(),
            values=dict(initial_values or {}),
        )
        for stage in self.stages:
            outcome = stage.handler(context)
            if not isinstance(outcome, StageOutcome):
                raise TypeError(f"stage {stage.identifier} must return StageOutcome")
            context.stage_records.append(
                {
                    "id": stage.identifier,
                    "status": outcome.status,
                    "output_reference": outcome.output_reference,
                }
            )
            if stop_on_hold and context.status == "HOLD":
                break
        return context


def _validated_identifier(value: str, kind: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{kind} identifier is required")
    if value != value.strip():
        raise ValueError(f"{kind} identifier cannot contain outer whitespace")
    return value
