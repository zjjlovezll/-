"""Inverse layer: observations, identifiability, estimation.

This package depends on the forward solver, never the other way round, so that the
forward implementation can be replaced (finite differences -> adjoint -> GPU batches)
without touching the frozen-oracle regression surface.
"""

from .channels import (
    ChannelContractError,
    DetectedEvent,
    SensorChannel,
    SensorPlan,
    StrainCalibration,
    detect_peak_event,
    observed_from_measured,
    standard_turnout_plan,
    strain_channel_to_force,
)
from .estimator import (
    Estimate,
    EstimatorError,
    Iteration,
    finite_difference_jacobian,
    gauss_newton,
)
from .identifiability import (
    IdentifiabilityError,
    Sensitivity,
    Verdict,
    analyse,
    finite_difference_jacobian as sensitivity_jacobian,
    normalised_sensitivity,
)
from .observation import (
    Alignment,
    AlignmentStrategy,
    ChannelSpec,
    ObservationError,
    ObservationSet,
    align,
    make_spec,
)

__all__ = [
    "Alignment",
    "AlignmentStrategy",
    "ChannelContractError",
    "ChannelSpec",
    "DetectedEvent",
    "Estimate",
    "EstimatorError",
    "IdentifiabilityError",
    "Iteration",
    "ObservationError",
    "ObservationSet",
    "SensorChannel",
    "SensorPlan",
    "Sensitivity",
    "StrainCalibration",
    "Verdict",
    "align",
    "analyse",
    "detect_peak_event",
    "finite_difference_jacobian",
    "normalised_sensitivity",
    "sensitivity_jacobian",
    "gauss_newton",
    "make_spec",
    "observed_from_measured",
    "standard_turnout_plan",
    "strain_channel_to_force",
]
