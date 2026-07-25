from pathlib import Path

from qps_core.cli import DEFAULT_EXAMPLE, run_demo


def test_demo_runs_end_to_end(tmp_path: Path) -> None:
    result = run_demo(DEFAULT_EXAMPLE, tmp_path)

    assert result["formula_verifier"] == "PASS"
    assert result["shacl"] == "PASS"
    assert result["receipt_verifier"] == "PASS"
    assert result["workflow_status"] == "HOLD"
    assert (tmp_path / "review_workbook.xlsx").exists()
    assert (tmp_path / "final_snapshot.json").exists()
    assert (tmp_path / "engineering_demo.json").exists()
    assert (tmp_path / "normalized_request.json").exists()
    assert (tmp_path / "pipeline_receipt.json").exists()


def test_packaged_demo_resource_is_available() -> None:
    assert DEFAULT_EXAMPLE.is_file()
