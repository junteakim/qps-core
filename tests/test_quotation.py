from decimal import Decimal

from qps_core.models import CostLine
from qps_core.quotation import QuoteEngine


def test_quote_engine_has_no_embedded_rates() -> None:
    snapshot = QuoteEngine().calculate(
        quote_id="DEMO-Q-001",
        currency="DEMO",
        lines=[
            CostLine("Material", "2", "1200", "SYNTHETIC"),
            CostLine("Labor", "80", "75", "SYNTHETIC"),
            CostLine("Inspection", "1", "900", "SYNTHETIC"),
        ],
        overhead_percent="10",
        profit_percent="8",
    )

    assert snapshot.base_cost == Decimal("9300.00")
    assert snapshot.overhead_amount == Decimal("930.00")
    assert snapshot.subtotal == Decimal("10230.00")
    assert snapshot.profit_amount == Decimal("818.40")
    assert snapshot.grand_total == Decimal("11048.40")
