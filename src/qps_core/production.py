from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qps_core.kernel import (
    WorkflowContext,
    WorkflowKernel,
    WorkflowStage,
)

PRODUCTION_BATCH_SCHEMA = "qps.public.production_batch.v1"


@dataclass(frozen=True)
class WorkOrder:
    identifier: str
    revision: str
    quantity: int
    route: tuple[str, ...]
    payload: dict[str, Any]
    _fingerprint: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _required_text(self.identifier, "work order")
        _required_text(self.revision, "revision")
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int):
            raise TypeError("quantity must be an integer")
        if self.quantity < 1:
            raise ValueError("quantity must be at least 1")
        if not isinstance(self.route, tuple):
            raise TypeError("route must be a tuple")
        if not self.route:
            raise ValueError("work order requires at least one route stage")
        for stage_id in self.route:
            _required_text(stage_id, "route stage")
        if len(self.route) != len(set(self.route)):
            raise ValueError("route stage identifiers must be unique")
        if not isinstance(self.payload, dict):
            raise TypeError("payload must be a dictionary")
        fingerprint = _payload_fingerprint(self.payload)
        object.__setattr__(self, "payload", dict(self.payload))
        object.__setattr__(self, "_fingerprint", fingerprint)

    @property
    def payload_fingerprint(self) -> str:
        return self._fingerprint


@dataclass(frozen=True)
class WorkOrderResult:
    order: WorkOrder
    context: WorkflowContext
    planned_route: tuple[str, ...]
    output_reference: str

    @property
    def completed_route(self) -> tuple[str, ...]:
        return tuple(stage["id"] for stage in self.context.stage_records)

    @property
    def remaining_route(self) -> tuple[str, ...]:
        return self.planned_route[len(self.completed_route) :]

    @property
    def status(self) -> str:
        return self.context.status

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_order_id": self.order.identifier,
            "revision": self.order.revision,
            "quantity": self.order.quantity,
            "payload_fingerprint": self.order.payload_fingerprint,
            "status": self.status,
            "planned_route": list(self.planned_route),
            "completed_route": list(self.completed_route),
            "remaining_route": list(self.remaining_route),
            "output_reference": self.output_reference,
            "trace": self.context.to_dict(),
        }


@dataclass(frozen=True)
class ProductionBatchResult:
    batch_id: str
    kernel_id: str
    orders: tuple[WorkOrderResult, ...]

    @property
    def status(self) -> str:
        return (
            "PASS"
            if self.orders and all(order.status == "PASS" for order in self.orders)
            else "HOLD"
        )

    def to_dict(self) -> dict[str, Any]:
        passed = sum(order.status == "PASS" for order in self.orders)
        held = len(self.orders) - passed
        return {
            "schema": PRODUCTION_BATCH_SCHEMA,
            "batch_id": self.batch_id,
            "kernel_id": self.kernel_id,
            "status": self.status,
            "counts": {
                "total": len(self.orders),
                "pass": passed,
                "hold": held,
            },
            "orders": [order.to_dict() for order in self.orders],
        }


@dataclass(frozen=True)
class RoutedWorkflowKernel:
    identifier: str
    stages: tuple[WorkflowStage, ...]

    def __post_init__(self) -> None:
        _required_text(self.identifier, "routed workflow")
        if not self.stages:
            raise ValueError("routed workflow requires at least one stage")
        identifiers = [stage.identifier for stage in self.stages]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("stage identifiers must be unique")

    def run_order(
        self,
        order: WorkOrder,
        output_dir: str | Path,
        *,
        output_reference: str = ".",
    ) -> WorkOrderResult:
        route = self._resolve_route(order)
        if _payload_fingerprint(order.payload) != order.payload_fingerprint:
            raise ValueError("work order payload changed after creation")
        execution_payload = json.loads(
            json.dumps(order.payload, ensure_ascii=False, allow_nan=False)
        )
        _prepare_output_dir(Path(output_dir))
        context = WorkflowKernel(self.identifier, route).run(
            execution_payload,
            output_dir,
            initial_values={"work_order": order},
            stop_on_hold=True,
        )
        return WorkOrderResult(
            order=order,
            context=context,
            planned_route=order.route,
            output_reference=output_reference,
        )

    def run_batch(
        self,
        batch_id: str,
        orders: tuple[WorkOrder, ...],
        output_dir: str | Path,
    ) -> ProductionBatchResult:
        _required_text(batch_id, "batch")
        if not orders:
            raise ValueError("batch requires at least one work order")
        order_ids = [order.identifier for order in orders]
        if len(order_ids) != len(set(order_ids)):
            raise ValueError("work order identifiers must be unique")
        for order in orders:
            self._resolve_route(order)

        output = Path(output_dir)
        _prepare_output_dir(output)
        results = tuple(
            self.run_order(
                order,
                output / f"order-{index:04d}",
                output_reference=f"order-{index:04d}",
            )
            for index, order in enumerate(orders, start=1)
        )
        batch = ProductionBatchResult(
            batch_id=batch_id,
            kernel_id=self.identifier,
            orders=results,
        )
        (output / "production_batch.json").write_text(
            json.dumps(batch.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return batch

    def _resolve_route(self, order: WorkOrder) -> tuple[WorkflowStage, ...]:
        catalog = {stage.identifier: stage for stage in self.stages}
        unknown = [stage_id for stage_id in order.route if stage_id not in catalog]
        if unknown:
            raise ValueError(
                f"work order {order.identifier} has unknown route stages: {unknown}"
            )
        return tuple(catalog[stage_id] for stage_id in order.route)


def work_order_from_context(context: WorkflowContext) -> WorkOrder:
    order = context.values.get("work_order")
    if not isinstance(order, WorkOrder):
        raise TypeError("workflow context does not contain a WorkOrder")
    return order


def _required_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} identifier is required")
    if value != value.strip():
        raise ValueError(f"{name} identifier cannot contain outer whitespace")
    return value


def _payload_fingerprint(payload: dict[str, Any]) -> str:
    try:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as error:
        raise ValueError("work order payload must be JSON serializable") from error
    return hashlib.sha256(canonical).hexdigest()


def _prepare_output_dir(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise ValueError("output_dir must be a directory")
        if any(path.iterdir()):
            raise ValueError("output_dir must be empty")
    path.mkdir(parents=True, exist_ok=True)
