"""Auditable adapter for the upstream CONTACT module-3 Python interface.

This module never substitutes the Velch Hertz law when CONTACT is absent.
The probe returns forces in CONTACT's local convention and deliberately does
not map them into Velch wheel/rail generalized forces before calibration.
"""
from __future__ import annotations

import hashlib
import importlib
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ContactNativeUnavailable(RuntimeError):
    """The official CONTACT interface or native binary is unavailable."""


def inspect_contact_native(root: str | Path) -> dict[str, Any]:
    """Read-only prerequisite check for the official CONTACT checkout."""
    base = Path(root).expanduser().resolve()
    interface = base / "python_intfc" / "__init__.py"
    binary = base / "bin" / ("contact_addon_win64.dll" if os.name == "nt" else "contact_addon_linux64.so")
    info: dict[str, Any] = {
        "schema_version": "velch-contact-native-status-v1",
        "root": str(base),
        "interface_path": str(interface),
        "interface_present": interface.is_file(),
        "binary_path": str(binary),
        "binary_present": binary.is_file(),
        "ready_to_attempt_native_load": interface.is_file() and binary.is_file(),
        "physics_validation_status": "not_evaluated_by_preflight",
    }
    if interface.is_file():
        info["interface_sha256"] = hashlib.sha256(interface.read_bytes()).hexdigest()
    if binary.is_file():
        info["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    return info


def _load_contact(root: Path) -> Any:
    status = inspect_contact_native(root)
    if not status["ready_to_attempt_native_load"]:
        missing = []
        if not status["interface_present"]:
            missing.append(status["interface_path"])
        if not status["binary_present"]:
            missing.append(status["binary_path"])
        raise ContactNativeUnavailable("official CONTACT files missing: " + "; ".join(missing))
    existing = sys.modules.get("python_intfc")
    if existing is not None:
        loaded = Path(existing.__file__).resolve().parent.parent
        if loaded != root:
            raise ContactNativeUnavailable(f"another CONTACT interface is already loaded: {loaded}")
        return existing
    sys.path.insert(0, str(root))
    try:
        return importlib.import_module("python_intfc")
    except (ImportError, OSError, SystemExit) as exc:
        raise ContactNativeUnavailable(f"official CONTACT library could not load: {exc}") from exc
    finally:
        if sys.path[0] == str(root):
            sys.path.pop(0)


@dataclass(frozen=True)
class HertzProbe:
    """One controlled module-3 comparison case in SI units.

    gap_curvature = 1/(2R) for a circular local gap. CONTACT's module-3
    Hertz input is in 1/mm, while the public Velch input is in 1/m.
    """

    effective_gap_curvature_x_per_m: float
    effective_gap_curvature_y_per_m: float
    penetration_m: float
    speed_m_s: float
    young_modulus_pa: float
    poisson_ratio: float
    friction_coefficient: float
    creepage_x: float
    creepage_y: float
    spin_per_m: float = 0.0

    def __post_init__(self) -> None:
        positive = (self.effective_gap_curvature_x_per_m,
                    self.effective_gap_curvature_y_per_m,
                    self.penetration_m, self.speed_m_s, self.young_modulus_pa)
        if any(not math.isfinite(x) or x <= 0 for x in positive):
            raise ValueError("curvature, penetration, speed and Young modulus must be positive SI values")
        if not math.isfinite(self.poisson_ratio) or not 0 <= self.poisson_ratio < 0.5:
            raise ValueError("Poisson ratio must be in [0, 0.5)")
        if not math.isfinite(self.friction_coefficient) or not 0 <= self.friction_coefficient <= 1:
            raise ValueError("friction coefficient must be in [0, 1]")
        if any(not math.isfinite(x) for x in (self.creepage_x, self.creepage_y, self.spin_per_m)):
            raise ValueError("creepages and spin must be finite")


def run_contact_hertz_probe(root: str | Path, probe: HertzProbe,
                            grid_n: int = 32) -> dict[str, Any]:
    """Run the upstream CONTACT module-3 solver once; no approximation fallback."""
    if not isinstance(grid_n, int) or not 16 <= grid_n <= 256:
        raise ValueError("CONTACT grid_n must be an integer in [16, 256]")
    base = Path(root).expanduser().resolve()
    cntc = _load_contact(base)
    started = time.perf_counter()
    magic, version, error = cntc.initlibrary(" ", " ", " ", 0)
    if error:
        raise RuntimeError(f"CONTACT initlibrary failed: {error}")
    initialized = False
    try:
        _, error = cntc.initialize(1, 3, idebug=0)
        if error:
            raise RuntimeError(f"CONTACT module-3 initialize failed: {error}")
        initialized = True
        flags = [magic["if_units"], magic["if_wrtinp"], magic["ic_matfil"],
                 magic["ic_output"], magic["ic_flow"], magic["ic_norm"],
                 magic["ic_tang"], magic["ic_pvtime"]]
        values = [magic["un_cntc"], 0, 0, 0, 0, 0, 3, 2]
        cntc.setflags(1, 1, flags, values)
        # a1, b1 are half-gap curvatures in 1/mm in upstream CONTACT.
        cntc.sethertzcontact(1, 1, -1, [grid_n, grid_n,
                                      probe.effective_gap_curvature_x_per_m / 1000,
                                      probe.effective_gap_curvature_y_per_m / 1000, 1.2])
        shear_n_mm2 = probe.young_modulus_pa / (2 * (1 + probe.poisson_ratio)) / 1e6
        cntc.setmaterialparameters(1, 1, 0, [probe.poisson_ratio, probe.poisson_ratio,
                                               shear_n_mm2, shear_n_mm2])
        cntc.setfrictionmethod(1, 1, 0, [probe.friction_coefficient,
                                         probe.friction_coefficient])
        cntc.setsolverflags(1, 1, 0, [80, 200, 5, 1], [1e-6])
        cntc.setreferencevelocity(1, 1, probe.speed_m_s * 1000)
        cntc.setpenetration(1, 1, probe.penetration_m * 1000)
        cntc.setcreepages(1, 1, probe.creepage_x, probe.creepage_y,
                         probe.spin_per_m / 1000)
        calculate_started = time.perf_counter()
        error = cntc.calculate(1, 1, 0)
        calculate_time_s = time.perf_counter() - calculate_started
        if error:
            raise RuntimeError(f"CONTACT calculation failed: {error}")
        fn, tx, ty, mz = cntc.getcontactforces(1, 1)
        area, adhesion, slip, plastic = cntc.getcontactpatchareas(1, 1)
        return {
            "schema_version": "velch-contact-module3-probe-v1",
            "engine": "official_CONTACT_module_3",
            "contact_version": version,
            "contact_binary_sha256": inspect_contact_native(base)["binary_sha256"],
            "grid_n": grid_n,
            "solver_relative_tolerance": 1e-6,
            "force_convention": "raw_CONTACT_local; not mapped to Velch body signs",
            "normal_force_n": fn, "tangent_x_n": tx, "tangent_y_n": ty,
            "spin_moment_nm": mz * 1e-3,
            "patch_area_m2": area * 1e-6,
            "adhesion_area_m2": adhesion * 1e-6,
            "slip_area_m2": slip * 1e-6,
            "plastic_area_m2": plastic * 1e-6,
            "calculate_time_s": calculate_time_s,
            "wall_time_s": time.perf_counter() - started,
            "physics_validation_status": "unvalidated_against_benchmark",
        }
    finally:
        if initialized:
            cntc.finalize(1)
        cntc.finalizelast()


def assess_spherical_hertz_probe(probe: HertzProbe, results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare a symmetric elastic gap with the independent Hertz sphere law.

    This checks module 3's local contact result only. It does not validate
    wheel/rail profile search, body-coordinate signs, or vehicle integration.
    """
    if not math.isclose(probe.effective_gap_curvature_x_per_m,
                        probe.effective_gap_curvature_y_per_m, rel_tol=1e-12):
        raise ValueError("analytical sphere benchmark requires equal x/y gap curvatures")
    if not results:
        raise ValueError("analytical sphere benchmark requires native results")
    radius_m = 1 / (2 * probe.effective_gap_curvature_x_per_m)
    reduced_modulus_pa = probe.young_modulus_pa / (2 * (1 - probe.poisson_ratio ** 2))
    expected_force_n = (4 / 3) * reduced_modulus_pa * math.sqrt(radius_m) * probe.penetration_m ** 1.5
    force_errors = [abs(float(r["normal_force_n"]) / expected_force_n - 1) for r in results]
    friction_ratios = []
    for result in results:
        fn = float(result["normal_force_n"])
        tx = float(result["tangent_x_n"])
        ty = float(result["tangent_y_n"])
        area = float(result["patch_area_m2"])
        if not all(map(math.isfinite, (fn, tx, ty, area))):
            raise ValueError("CONTACT returned non-finite force or area")
        if fn <= 0 or area <= 0:
            raise ValueError("CONTACT returned non-positive normal force or patch area")
        friction_ratios.append(math.hypot(tx, ty) / fn)
    return {
        "reference": "elastic Hertz sphere-plane, equal isotropic solids",
        "effective_radius_m": radius_m,
        "reduced_modulus_pa": reduced_modulus_pa,
        "expected_normal_force_n": expected_force_n,
        "normal_force_relative_error_by_grid": force_errors,
        "finest_grid_normal_force_relative_error": force_errors[-1],
        "tangential_force_to_normal_force_by_grid": friction_ratios,
        "finest_grid_within_1_percent_of_analytic": force_errors[-1] <= 0.01,
        "coulomb_bound_satisfied_all_grids": all(x <= probe.friction_coefficient + 1e-6 for x in friction_ratios),
        "scope": "local module-3 force only; turnout geometry and vehicle force mapping untested",
    }
