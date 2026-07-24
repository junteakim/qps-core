from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from qps_core.models import CostLine, QuoteSnapshot, as_decimal


class QuoteEngine:
    def calculate(
        self,
        *,
        quote_id: str,
        currency: str,
        lines: Iterable[CostLine],
        overhead_percent: Decimal | float | str = Decimal(0),
        profit_percent: Decimal | float | str = Decimal(0),
    ) -> QuoteSnapshot:
        if not quote_id.strip():
            raise ValueError("quote_id is required")
        if not currency.strip():
            raise ValueError("currency is required")
        prepared = tuple(lines)
        if not prepared:
            raise ValueError("at least one cost line is required")
        overhead = as_decimal(overhead_percent)
        profit = as_decimal(profit_percent)
        if overhead < 0 or profit < 0:
            raise ValueError("overhead and profit percentages cannot be negative")
        return QuoteSnapshot(
            quote_id=quote_id,
            currency=currency,
            lines=prepared,
            overhead_percent=overhead,
            profit_percent=profit,
        )
