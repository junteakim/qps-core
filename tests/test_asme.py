from decimal import Decimal

import pytest

from qps_core.asme import (
    ApplicabilityError,
    calculate_elliptical_head_2_to_1_thickness,
    calculate_shell_mawp,
    calculate_shell_thickness,
)
from qps_core.models import EllipticalHeadInput, MaterialProperties, VesselInput


def vessel() -> VesselInput:
    return VesselInput(
        tag="DEMO-V-001",
        design_pressure_mpa="1.6",
        inside_diameter_mm="1200",
        corrosion_allowance_mm="3",
        mill_tolerance_fraction="0.125",
        material=MaterialProperties(
            allowable_stress_mpa="138",
            joint_efficiency="0.85",
            source_reference="SYNTHETIC",
        ),
    )


def test_shell_and_head_calculations_require_explicit_material_basis() -> None:
    shell = calculate_shell_thickness(vessel())
    head = calculate_elliptical_head_2_to_1_thickness(
        EllipticalHeadInput(vessel(), "300")
    )

    assert shell.pressure_thickness_mm == Decimal("8.252")
    assert shell.required_nominal_thickness_mm == Decimal("12.860")
    assert head.pressure_thickness_mm == Decimal("8.196")
    assert head.required_nominal_thickness_mm == Decimal("12.795")


def test_shell_mawp_uses_net_thickness() -> None:
    assert calculate_shell_mawp(vessel(), "14") == Decimal("1.792")


def test_shell_formula_fails_outside_pressure_limit() -> None:
    invalid = VesselInput(
        tag="DEMO-HIGH-P",
        design_pressure_mpa="50",
        inside_diameter_mm="1200",
        corrosion_allowance_mm="0",
        mill_tolerance_fraction="0",
        material=MaterialProperties(
            allowable_stress_mpa="100",
            joint_efficiency="1",
            source_reference="SYNTHETIC",
        ),
    )
    with pytest.raises(ApplicabilityError):
        calculate_shell_thickness(invalid)


def test_elliptical_head_formula_rejects_non_2_to_1_geometry() -> None:
    with pytest.raises(ApplicabilityError):
        calculate_elliptical_head_2_to_1_thickness(EllipticalHeadInput(vessel(), "250"))
