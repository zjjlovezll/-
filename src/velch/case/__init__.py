"""Case contracts that separate "what the user writes" from "what the solver runs"."""

from .spec import CaseSpec, ParameterSpec, SpecError

__all__ = ["CaseSpec", "ParameterSpec", "SpecError"]
