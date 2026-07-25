from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
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
    QuoteSnapshot,
    VesselInput,
    as_decimal,
)
from qps_core.ontology import validate_snapshot
from qps_core.quotation import QuoteEngine

RECEIPT_SCHEMA = "qps.public.pipeline_receipt.v1"
REQUEST_SCHEMAS = {
    "qps.public.demo_input.v1",
    "qps.public.workflow_input.v1",
}
PUBLIC_BOUNDARY = {
    "customer_rules_included": False,
    "embedded_production_rates": False,
    "licensed_codebook_content_included": False,
    "private_benchmarks_included": False,
    "signoff_authentication_included": False,
}


class WorkflowInputError(ValueError):
    pass


@dataclass(frozen=True)
class CallerSignoff:
    reviewer: str
    signoff_reference: str

    def __post_init__(self) -> None:
        if not self.reviewer.strip():
            raise ValueError("reviewer is required")
        if not self.signoff_reference.strip():
            raise ValueError("signoff_reference is required")

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "status": "PRESENT",
            "approved": True,
            "trust_model": "caller_asserted",
            "reviewer": self.reviewer,
            "signoff_reference": self.signoff_reference,
        }


@dataclass(frozen=True)
class PublicWorkflowRequest:
    schema: str
    synthetic_demo: bool
    quote_id: str
    currency: str
    overhead_percent: Decimal
    profit_percent: Decimal
    vessel: VesselInput
    head: EllipticalHeadInput
    lines: tuple[CostLine, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PublicWorkflowRequest:
        _require_exact_keys(
            payload,
            {
                "schema",
                "synthetic_demo",
                "quote_id",
                "currency",
                "overhead_percent",
                "profit_percent",
                "vessel",
                "head",
                "cost_lines",
            },
            "request",
        )
        if payload["schema"] not in REQUEST_SCHEMAS:
            raise WorkflowInputError("unsupported request schema")
        if not isinstance(payload["synthetic_demo"], bool):
            raise WorkflowInputError("synthetic_demo must be a boolean")

        vessel_payload = _require_mapping(payload["vessel"], "vessel")
        _require_exact_keys(
            vessel_payload,
            {
                "tag",
                "design_pressure_mpa",
                "inside_diameter_mm",
                "corrosion_allowance_mm",
                "mill_tolerance_fraction",
                "material",
            },
            "vessel",
        )
        material_payload = _require_mapping(
            vessel_payload["material"],
            "vessel.material",
        )
        _require_exact_keys(
            material_payload,
            {
                "allowable_stress_mpa",
                "joint_efficiency",
                "source_reference",
            },
            "vessel.material",
        )
        material = MaterialProperties(**material_payload)
        vessel_values = dict(vessel_payload)
        vessel_values["material"] = material
        vessel = VesselInput(**vessel_values)

        head_payload = _require_mapping(payload["head"], "head")
        _require_exact_keys(head_payload, {"inside_depth_mm"}, "head")
        head = EllipticalHeadInput(
            vessel=vessel,
            inside_depth_mm=head_payload["inside_depth_mm"],
        )

        raw_lines = payload["cost_lines"]
        if not isinstance(raw_lines, list) or not raw_lines:
            raise WorkflowInputError("cost_lines must be a non-empty list")
        lines: list[CostLine] = []
        for index, raw_line in enumerate(raw_lines):
            line = _require_mapping(raw_line, f"cost_lines[{index}]")
            _require_exact_keys(
                line,
                {"category", "quantity", "unit_cost", "provenance"},
                f"cost_lines[{index}]",
            )
            lines.append(CostLine(**line))

        overhead = as_decimal(payload["overhead_percent"])
        profit = as_decimal(payload["profit_percent"])
        if overhead < 0 or profit < 0:
            raise WorkflowInputError(
                "overhead_percent and profit_percent cannot be negative"
            )
        return cls(
            schema=str(payload["schema"]),
            synthetic_demo=payload["synthetic_demo"],
            quote_id=str(payload["quote_id"]),
            currency=str(payload["currency"]),
            overhead_percent=overhead,
            profit_percent=profit,
            vessel=vessel,
            head=head,
            lines=tuple(lines),
        )

    def to_dict(self) -> dict[str, Any]:
        material = self.vessel.material
        return {
            "schema": self.schema,
            "synthetic_demo": self.synthetic_demo,
            "quote_id": self.quote_id,
            "currency": self.currency,
            "overhead_percent": str(self.overhead_percent),
            "profit_percent": str(self.profit_percent),
            "vessel": {
                "tag": self.vessel.tag,
                "design_pressure_mpa": str(self.vessel.design_pressure_mpa),
                "inside_diameter_mm": str(self.vessel.inside_diameter_mm),
                "corrosion_allowance_mm": str(self.vessel.corrosion_allowance_mm),
                "mill_tolerance_fraction": str(self.vessel.mill_tolerance_fraction),
                "material": {
                    "allowable_stress_mpa": str(material.allowable_stress_mpa),
                    "joint_efficiency": str(material.joint_efficiency),
                    "source_reference": material.source_reference,
                },
            },
            "head": {
                "inside_depth_mm": str(self.head.inside_depth_mm),
            },
            "cost_lines": [
                {
                    "category": line.category,
                    "quantity": str(line.quantity),
                    "unit_cost": str(line.unit_cost),
                    "provenance": line.provenance,
                }
                for line in self.lines
            ],
        }


def run_public_workflow(
    payload: dict[str, Any],
    output_dir: str | Path,
    *,
    signoff: CallerSignoff | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    request = PublicWorkflowRequest.from_dict(payload)

    normalized_path = _write_json(
        output / "normalized_request.json",
        request.to_dict(),
    )
    shell = calculate_shell_thickness(request.vessel)
    head = calculate_elliptical_head_2_to_1_thickness(request.head)
    engineering_path = _write_json(
        output / "engineering_demo.json",
        {
            "schema": "qps.public.engineering_demo.v1",
            "synthetic_demo": request.synthetic_demo,
            "tag": request.vessel.tag,
            "shell": shell.to_dict(),
            "elliptical_head": head.to_dict(),
        },
    )
    snapshot = _calculate_snapshot(request)
    snapshot_path = write_snapshot(
        snapshot,
        output / "final_snapshot.json",
    )
    workbook_path = build_review_workbook(
        snapshot,
        output / "review_workbook.xlsx",
    )

    formula_issues = verify_formula_workbook(workbook_path)
    ontology_result = validate_snapshot(snapshot.to_dict())
    gates = [
        _gate(
            "formula_contract",
            not formula_issues,
            f"issues={len(formula_issues)}",
        ),
        _gate(
            "ontology_shacl",
            ontology_result.conforms,
            "conforms" if ontology_result.conforms else "does_not_conform",
        ),
        _gate(
            "caller_signoff",
            signoff is not None,
            (signoff.signoff_reference if signoff is not None else "signoff_absent"),
        ),
    ]
    workflow_complete = all(gate["status"] == "PASS" for gate in gates)
    artifacts = [
        _artifact("engineering", engineering_path, output),
        _artifact("normalized_request", normalized_path, output),
        _artifact("quote_snapshot", snapshot_path, output),
        _artifact("review_workbook", workbook_path, output),
    ]
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "synthetic_demo": request.synthetic_demo,
        "request_fingerprint": _payload_hash(request.to_dict()),
        "workflow": [
            _stage("normalize", "normalized_request"),
            _stage("engineering", "engineering"),
            _stage("quotation", "quote_snapshot"),
            _stage("formula_first_review", "review_workbook"),
            _stage(
                "validation",
                "formula_contract,ontology_shacl",
                passed=not formula_issues and ontology_result.conforms,
            ),
            _stage(
                "approval",
                "caller_signoff",
                passed=signoff is not None,
            ),
        ],
        "artifacts": artifacts,
        "gates": gates,
        "signoff": (
            signoff.to_dict()
            if signoff is not None
            else {"status": "ABSENT", "approved": False}
        ),
        "decision": {
            "status": "CALLER_SIGNED_OFF" if workflow_complete else "HOLD",
            "workflow_complete": workflow_complete,
            "reason": (
                "all gates passed"
                if workflow_complete
                else "required gates remain on hold"
            ),
        },
        "public_boundary": PUBLIC_BOUNDARY,
    }
    receipt_path = _write_json(output / "pipeline_receipt.json", receipt)
    receipt_issues = verify_pipeline_receipt(receipt_path)
    if receipt_issues:
        raise RuntimeError(f"pipeline receipt verification failed: {receipt_issues}")

    return {
        "synthetic_demo": request.synthetic_demo,
        "workbook": str(workbook_path),
        "snapshot": str(snapshot_path),
        "engineering": str(engineering_path),
        "normalized_request": str(normalized_path),
        "pipeline_receipt": str(receipt_path),
        "formula_verifier": "PASS" if not formula_issues else "FAIL",
        "shacl": "PASS" if ontology_result.conforms else "FAIL",
        "receipt_verifier": "PASS",
        "workflow_status": receipt["decision"]["status"],
        "workflow_complete": workflow_complete,
        "approval_trust_model": "caller_asserted",
        "signoff_authentication_included": False,
    }


def verify_pipeline_receipt(path: str | Path) -> list[str]:
    receipt_path = Path(path)
    root = receipt_path.parent.resolve()
    issues: list[str] = []
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"cannot read pipeline receipt: {error}"]
    if set(receipt) != {
        "artifacts",
        "decision",
        "gates",
        "public_boundary",
        "request_fingerprint",
        "schema",
        "signoff",
        "synthetic_demo",
        "workflow",
    }:
        issues.append("pipeline receipt top-level contract changed")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        issues.append("unsupported pipeline receipt schema")
    fingerprint = str(receipt.get("request_fingerprint", ""))
    if len(fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in fingerprint
    ):
        issues.append("invalid request fingerprint")

    artifact_targets: dict[str, Path] = {}
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        issues.append("pipeline receipt must declare artifacts")
    else:
        artifact_ids = [
            str(artifact.get("id", ""))
            for artifact in artifacts
            if isinstance(artifact, dict)
        ]
        if len(artifact_ids) != len(set(artifact_ids)):
            issues.append("artifact identifiers must be unique")
        if set(artifact_ids) != {
            "engineering",
            "normalized_request",
            "quote_snapshot",
            "review_workbook",
        }:
            issues.append("pipeline receipt artifact set changed")
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                issues.append("artifact entry must be an object")
                continue
            relative = Path(str(artifact.get("path", "")))
            if not relative.parts or relative.is_absolute() or ".." in relative.parts:
                issues.append(f"unsafe artifact path: {relative}")
                continue
            target = (root / relative).resolve()
            if not target.is_relative_to(root):
                issues.append(f"artifact escapes receipt directory: {relative}")
                continue
            if not target.is_file():
                issues.append(f"missing artifact: {relative}")
                continue
            artifact_id = str(artifact.get("id", ""))
            artifact_targets[artifact_id] = target
            expected_hash = str(artifact.get("sha256", ""))
            if _file_hash(target) != expected_hash:
                issues.append(f"artifact hash mismatch: {relative}")
    normalized_target = artifact_targets.get("normalized_request")
    if normalized_target is not None:
        try:
            normalized_payload = json.loads(
                normalized_target.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            issues.append(f"cannot read normalized request: {error}")
        else:
            if not isinstance(normalized_payload, dict):
                issues.append("normalized request must be an object")
            elif _payload_hash(normalized_payload) != fingerprint:
                issues.append("request fingerprint mismatch")

    gates = receipt.get("gates")
    if not isinstance(gates, list) or not gates:
        issues.append("pipeline receipt must declare gates")
        expected_workflow_complete = False
    else:
        gate_ids = [str(gate.get("id", "")) for gate in gates if isinstance(gate, dict)]
        if len(gate_ids) != len(set(gate_ids)):
            issues.append("gate identifiers must be unique")
        if set(gate_ids) != {
            "caller_signoff",
            "formula_contract",
            "ontology_shacl",
        }:
            issues.append("pipeline receipt gate set changed")
        expected_workflow_complete = all(
            isinstance(gate, dict) and gate.get("status") == "PASS" for gate in gates
        )
        caller_gate_passed = any(
            isinstance(gate, dict)
            and gate.get("id") == "caller_signoff"
            and gate.get("status") == "PASS"
            for gate in gates
        )
        signoff = receipt.get("signoff")
        signoff_present = (
            isinstance(signoff, dict)
            and signoff.get("status") == "PRESENT"
            and signoff.get("approved") is True
            and signoff.get("trust_model") == "caller_asserted"
            and bool(str(signoff.get("reviewer", "")).strip())
            and bool(str(signoff.get("signoff_reference", "")).strip())
        )
        if caller_gate_passed is not signoff_present:
            issues.append("caller signoff does not match its gate")
    decision = receipt.get("decision")
    if not isinstance(decision, dict):
        issues.append("pipeline receipt must declare a decision")
    else:
        if set(decision) != {"reason", "status", "workflow_complete"}:
            issues.append("pipeline receipt decision contract changed")
        if decision.get("workflow_complete") is not expected_workflow_complete:
            issues.append("workflow_complete does not match gate statuses")
        expected_status = "CALLER_SIGNED_OFF" if expected_workflow_complete else "HOLD"
        if decision.get("status") != expected_status:
            issues.append("decision status does not match gate statuses")

    boundary = receipt.get("public_boundary")
    if boundary != PUBLIC_BOUNDARY:
        issues.append("public boundary contract changed")
    return issues


def _calculate_snapshot(request: PublicWorkflowRequest) -> QuoteSnapshot:
    return QuoteEngine().calculate(
        quote_id=request.quote_id,
        currency=request.currency,
        lines=request.lines,
        synthetic_demo=request.synthetic_demo,
        overhead_percent=request.overhead_percent,
        profit_percent=request.profit_percent,
    )


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowInputError(f"{name} must be an object")
    return value


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    name: str,
) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        raise WorkflowInputError(
            f"{name} contract mismatch: missing={missing}, unknown={unknown}"
        )


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(identifier: str, path: Path, root: Path) -> dict[str, str]:
    return {
        "id": identifier,
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "sha256": _file_hash(path),
    }


def _gate(identifier: str, passed: bool, evidence: str) -> dict[str, str]:
    return {
        "id": identifier,
        "status": "PASS" if passed else "HOLD",
        "evidence": evidence,
    }


def _stage(
    identifier: str,
    output_reference: str,
    *,
    passed: bool = True,
) -> dict[str, str]:
    return {
        "id": identifier,
        "status": "PASS" if passed else "HOLD",
        "output_reference": output_reference,
    }
