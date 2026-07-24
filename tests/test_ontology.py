import pytest

from qps_core.models import CostLine
from qps_core.ontology import validate_snapshot
from qps_core.quotation import QuoteEngine


def snapshot() -> dict:
    return (
        QuoteEngine()
        .calculate(
            quote_id="DEMO-Q-003",
            currency="DEMO",
            lines=[CostLine("Material", "1", "100", "SYNTHETIC")],
        )
        .to_dict()
    )


def test_valid_snapshot_conforms_to_shacl() -> None:
    result = validate_snapshot(snapshot())
    assert result.conforms, result.report_text


def test_missing_currency_fails_shacl() -> None:
    payload = snapshot()
    del payload["currency"]
    result = validate_snapshot(payload)
    assert not result.conforms


@pytest.mark.parametrize("field_name", ["quantity", "unit_cost", "amount"])
def test_missing_cost_line_numbers_fail_shacl(field_name) -> None:
    payload = snapshot()
    del payload["lines"][0][field_name]
    result = validate_snapshot(payload)
    assert not result.conforms
