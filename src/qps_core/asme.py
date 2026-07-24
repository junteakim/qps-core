from __future__ import annotations

from decimal import ROUND_UP, Decimal

from qps_core.models import EllipticalHeadInput, ThicknessResult, VesselInput

THICKNESS_QUANTUM = Decimal("0.001")


class ApplicabilityError(ValueError):
    pass


def _round_thickness(value: Decimal) -> Decimal:
    return value.quantize(THICKNESS_QUANTUM, rounding=ROUND_UP)


def _nominal_from_pressure_thickness(
    pressure_thickness: Decimal,
    corrosion_allowance: Decimal,
    mill_tolerance_fraction: Decimal,
) -> Decimal:
    return _round_thickness(
        (pressure_thickness + corrosion_allowance)
        / (Decimal(1) - mill_tolerance_fraction)
    )


def calculate_shell_thickness(vessel: VesselInput) -> ThicknessResult:
    pressure = vessel.design_pressure_mpa
    radius = vessel.inside_diameter_mm / Decimal(2)
    stress = vessel.material.allowable_stress_mpa
    efficiency = vessel.material.joint_efficiency
    limit = Decimal("0.385") * stress * efficiency
    if pressure > limit:
        raise ApplicabilityError(
            "design pressure exceeds the shell formula applicability limit"
        )
    denominator = stress * efficiency - Decimal("0.6") * pressure
    if denominator <= 0:
        raise ApplicabilityError("shell formula denominator is not positive")
    pressure_thickness = pressure * radius / denominator
    if pressure_thickness > Decimal("0.5") * radius:
        raise ApplicabilityError(
            "calculated shell thickness exceeds the geometric applicability limit"
        )
    return ThicknessResult(
        component="cylindrical_shell",
        pressure_thickness_mm=_round_thickness(pressure_thickness),
        required_nominal_thickness_mm=_nominal_from_pressure_thickness(
            pressure_thickness,
            vessel.corrosion_allowance_mm,
            vessel.mill_tolerance_fraction,
        ),
        formula_reference="ASME VIII-1 UG-27(c)(1), user verification required",
        source_reference=vessel.material.source_reference,
    )


def calculate_elliptical_head_2_to_1_thickness(
    head: EllipticalHeadInput,
) -> ThicknessResult:
    vessel = head.vessel
    pressure = vessel.design_pressure_mpa
    diameter = vessel.inside_diameter_mm
    if head.inside_depth_mm * Decimal(4) != diameter:
        raise ApplicabilityError(
            "inside depth must equal one quarter of inside diameter for a 2:1 head"
        )
    stress = vessel.material.allowable_stress_mpa
    efficiency = vessel.material.joint_efficiency
    denominator = Decimal(2) * stress * efficiency - Decimal("0.2") * pressure
    if denominator <= 0:
        raise ApplicabilityError("head formula denominator is not positive")
    pressure_thickness = pressure * diameter / denominator
    return ThicknessResult(
        component="elliptical_head_2_to_1",
        pressure_thickness_mm=_round_thickness(pressure_thickness),
        required_nominal_thickness_mm=_nominal_from_pressure_thickness(
            pressure_thickness,
            vessel.corrosion_allowance_mm,
            vessel.mill_tolerance_fraction,
        ),
        formula_reference="ASME VIII-1 UG-32(d), user verification required",
        source_reference=vessel.material.source_reference,
    )


def calculate_shell_mawp(
    vessel: VesselInput,
    nominal_thickness_mm: Decimal | float | str,
) -> Decimal:
    nominal = Decimal(str(nominal_thickness_mm))
    net = (
        nominal * (Decimal(1) - vessel.mill_tolerance_fraction)
        - vessel.corrosion_allowance_mm
    )
    if net <= 0:
        raise ValueError("net shell thickness must be positive")
    radius = vessel.inside_diameter_mm / Decimal(2)
    stress = vessel.material.allowable_stress_mpa
    efficiency = vessel.material.joint_efficiency
    mawp = stress * efficiency * net / (radius + Decimal("0.6") * net)
    return mawp.quantize(Decimal("0.001"), rounding=ROUND_UP)
