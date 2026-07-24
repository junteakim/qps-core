from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

MONEY_QUANTUM = Decimal("0.01")


def as_decimal(value: Decimal | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MaterialProperties:
    allowable_stress_mpa: Decimal | int | float | str
    joint_efficiency: Decimal | int | float | str
    source_reference: str

    def __post_init__(self) -> None:
        stress = as_decimal(self.allowable_stress_mpa)
        efficiency = as_decimal(self.joint_efficiency)
        if stress <= 0:
            raise ValueError("allowable_stress_mpa must be positive")
        if not Decimal(0) < efficiency <= Decimal(1):
            raise ValueError("joint_efficiency must be in the interval (0, 1]")
        if not self.source_reference.strip():
            raise ValueError("source_reference is required")
        object.__setattr__(self, "allowable_stress_mpa", stress)
        object.__setattr__(self, "joint_efficiency", efficiency)


@dataclass(frozen=True)
class VesselInput:
    tag: str
    design_pressure_mpa: Decimal | int | float | str
    inside_diameter_mm: Decimal | int | float | str
    corrosion_allowance_mm: Decimal | int | float | str
    mill_tolerance_fraction: Decimal | int | float | str
    material: MaterialProperties

    def __post_init__(self) -> None:
        pressure = as_decimal(self.design_pressure_mpa)
        diameter = as_decimal(self.inside_diameter_mm)
        corrosion = as_decimal(self.corrosion_allowance_mm)
        tolerance = as_decimal(self.mill_tolerance_fraction)
        if not self.tag.strip():
            raise ValueError("tag is required")
        if pressure <= 0 or diameter <= 0:
            raise ValueError("pressure and diameter must be positive")
        if corrosion < 0:
            raise ValueError("corrosion allowance cannot be negative")
        if not Decimal(0) <= tolerance < Decimal(1):
            raise ValueError("mill tolerance must be in the interval [0, 1)")
        object.__setattr__(self, "design_pressure_mpa", pressure)
        object.__setattr__(self, "inside_diameter_mm", diameter)
        object.__setattr__(self, "corrosion_allowance_mm", corrosion)
        object.__setattr__(self, "mill_tolerance_fraction", tolerance)


@dataclass(frozen=True)
class EllipticalHeadInput:
    vessel: VesselInput
    inside_depth_mm: Decimal | int | float | str

    def __post_init__(self) -> None:
        depth = as_decimal(self.inside_depth_mm)
        if depth <= 0:
            raise ValueError("inside_depth_mm must be positive")
        object.__setattr__(self, "inside_depth_mm", depth)


@dataclass(frozen=True)
class ThicknessResult:
    component: str
    pressure_thickness_mm: Decimal
    required_nominal_thickness_mm: Decimal
    formula_reference: str
    source_reference: str
    applicable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "pressure_thickness_mm": str(self.pressure_thickness_mm),
            "required_nominal_thickness_mm": str(self.required_nominal_thickness_mm),
            "formula_reference": self.formula_reference,
            "source_reference": self.source_reference,
            "applicable": self.applicable,
        }


@dataclass(frozen=True)
class CostLine:
    category: str
    quantity: Decimal | int | float | str
    unit_cost: Decimal | int | float | str
    provenance: str

    def __post_init__(self) -> None:
        quantity = as_decimal(self.quantity)
        unit_cost = as_decimal(self.unit_cost)
        if not self.category.strip():
            raise ValueError("category is required")
        if quantity < 0 or unit_cost < 0:
            raise ValueError("quantity and unit_cost cannot be negative")
        if not self.provenance.strip():
            raise ValueError("provenance is required")
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "unit_cost", unit_cost)

    @property
    def amount(self) -> Decimal:
        return money(self.quantity * self.unit_cost)

    def to_dict(self) -> dict[str, str]:
        return {
            "category": self.category,
            "quantity": str(self.quantity),
            "unit_cost": str(self.unit_cost),
            "amount": str(self.amount),
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class QuoteSnapshot:
    quote_id: str
    currency: str
    lines: tuple[CostLine, ...]
    overhead_percent: Decimal
    profit_percent: Decimal

    @property
    def base_cost(self) -> Decimal:
        return money(sum((line.amount for line in self.lines), Decimal(0)))

    @property
    def overhead_amount(self) -> Decimal:
        return money(self.base_cost * self.overhead_percent / Decimal(100))

    @property
    def subtotal(self) -> Decimal:
        return money(self.base_cost + self.overhead_amount)

    @property
    def profit_amount(self) -> Decimal:
        return money(self.subtotal * self.profit_percent / Decimal(100))

    @property
    def grand_total(self) -> Decimal:
        return money(self.subtotal + self.profit_amount)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "qps.public.quote_snapshot.v1",
            "synthetic_demo": True,
            "quote_id": self.quote_id,
            "currency": self.currency,
            "lines": [line.to_dict() for line in self.lines],
            "overhead_percent": str(self.overhead_percent),
            "profit_percent": str(self.profit_percent),
            "base_cost": str(self.base_cost),
            "overhead_amount": str(self.overhead_amount),
            "subtotal": str(self.subtotal),
            "profit_amount": str(self.profit_amount),
            "grand_total": str(self.grand_total),
        }
