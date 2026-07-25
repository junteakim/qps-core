import json
from pathlib import Path

import pytest

from qps_core.cli import DEFAULT_EXAMPLE
from qps_core.workflow import (
    CallerSignoff,
    WorkflowInputError,
    run_public_workflow,
    verify_pipeline_receipt,
)


def demo_payload() -> dict:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def test_workflow_holds_until_caller_signoff(tmp_path: Path) -> None:
    result = run_public_workflow(demo_payload(), tmp_path)
    receipt_path = Path(result["pipeline_receipt"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert result["workflow_status"] == "HOLD"
    assert result["workflow_complete"] is False
    assert result["receipt_verifier"] == "PASS"
    assert receipt["signoff"] == {"status": "ABSENT", "approved": False}
    assert (
        next(gate for gate in receipt["gates"] if gate["id"] == "caller_signoff")[
            "status"
        ]
        == "HOLD"
    )
    assert all(
        not Path(artifact["path"]).is_absolute() for artifact in receipt["artifacts"]
    )
    assert all(value is False for value in receipt["public_boundary"].values())
    assert verify_pipeline_receipt(receipt_path) == []


def test_workflow_approves_only_with_explicit_signoff(tmp_path: Path) -> None:
    result = run_public_workflow(
        demo_payload(),
        tmp_path,
        signoff=CallerSignoff(
            reviewer="SYNTHETIC_REVIEWER",
            signoff_reference="SYNTHETIC_SIGNOFF_001",
        ),
    )
    receipt = json.loads(Path(result["pipeline_receipt"]).read_text(encoding="utf-8"))

    assert result["workflow_status"] == "CALLER_SIGNED_OFF"
    assert result["workflow_complete"] is True
    assert result["approval_trust_model"] == "caller_asserted"
    assert result["signoff_authentication_included"] is False
    assert all(gate["status"] == "PASS" for gate in receipt["gates"])
    assert receipt["signoff"]["trust_model"] == "caller_asserted"


def test_workflow_preserves_non_synthetic_input_label(tmp_path: Path) -> None:
    payload = demo_payload()
    payload["synthetic_demo"] = False
    result = run_public_workflow(payload, tmp_path)
    snapshot = json.loads(Path(result["snapshot"]).read_text(encoding="utf-8"))
    receipt = json.loads(Path(result["pipeline_receipt"]).read_text(encoding="utf-8"))

    assert snapshot["synthetic_demo"] is False
    assert receipt["synthetic_demo"] is False


def test_receipt_verifier_detects_artifact_tampering(tmp_path: Path) -> None:
    result = run_public_workflow(demo_payload(), tmp_path)
    Path(result["snapshot"]).write_text("{}\n", encoding="utf-8")

    assert any(
        "artifact hash mismatch" in issue
        for issue in verify_pipeline_receipt(result["pipeline_receipt"])
    )


def test_receipt_verifier_detects_fingerprint_tampering(tmp_path: Path) -> None:
    result = run_public_workflow(demo_payload(), tmp_path)
    receipt_path = Path(result["pipeline_receipt"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["request_fingerprint"] = "0" * 64
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    assert "request fingerprint mismatch" in verify_pipeline_receipt(receipt_path)


def test_workflow_rejects_unknown_input_fields(tmp_path: Path) -> None:
    payload = demo_payload()
    payload["private_rate_table"] = "not_allowed"

    with pytest.raises(WorkflowInputError, match="unknown"):
        run_public_workflow(payload, tmp_path)


def test_workflow_rejects_non_finite_numbers(tmp_path: Path) -> None:
    payload = demo_payload()
    payload["cost_lines"][0]["quantity"] = "NaN"

    with pytest.raises(ValueError, match="finite"):
        run_public_workflow(payload, tmp_path)
