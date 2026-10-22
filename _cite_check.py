"""Resolve (file, symbol) pairs to current ``path:line`` anchors.

Used while writing docs/ARCHITECTURE_2026-10-21.md so every citation can be
re-checked in one command:  python -X utf8 _cite_check.py

It prints ``relpath:line: <stripped source line>`` for each anchor, in the order
given, so a doc revision only has to re-read this output.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = "src/velch"

ANCHORS: list[tuple[str, str]] = [
    # contact.py -- the single largest module
    ("contact.py", r"^GEOMETRY_POLICIES"),
    ("contact.py", r"^CURVATURE_POLICIES"),
    ("contact.py", r"^NORMAL_POLICIES"),
    ("contact.py", r"^from \.support_compliance import"),
    ("contact.py", r"^class ContactParameters"),
    ("contact.py", r"^class ContactGeometry"),
    ("contact.py", r"^class ContactResponse"),
    ("contact.py", r"^def merge_contact_responses"),
    ("contact.py", r"^def deduplicate_contacts"),
    ("contact.py", r"^_RAIL_GRID_CACHE_SIZE"),
    ("contact.py", r"^_rail_grid_cache"),
    ("contact.py", r"^def find_patch_contact"),
    ("contact.py", r"^def find_strip_contact"),
    ("contact.py", r"^def find_graph_contact"),
    ("contact.py", r"^def find_graph_contacts"),
    ("contact.py", r"^def saturate_creep_force"),
    ("contact.py", r"^def evaluate_contact"),
    ("contact.py", r"only sditt_cubic_saturation"),
    ("contact.py", r"^def _build_rail_grid"),
    ("contact.py", r"^def _grid_slope"),
    ("contact.py", r"^def _contact_on_span"),
    # profiles / geometry / laws
    ("profiles.py", r"^class ProfileSeries"),
    ("profiles.py", r"^    def sample"),
    ("profiles.py", r"^def graph_from_points"),
    ("profiles.py", r"^def load_profile"),
    ("contact_geometry.py", r"^def swept_contact"),
    ("contact_geometry.py", r"^class SplineProfile"),
    ("contact_law.py", r"^def local_curvature"),
    ("contact_law.py", r"^def hertz_stiffness_n_m_1p5"),
    ("contact_law.py", r"^def hunt_crossley_coefficient"),
    ("support_compliance.py", r"^class SupportCompliance"),
    ("support_compliance.py", r"^def series_normal_force"),
    ("support_compliance.py", r"^def series_normal_force_slope"),
    ("contact_native.py", r"^def inspect_contact_native"),
    ("contact_native.py", r"^def run_contact_hertz_probe"),
    # track
    ("track_models.py", r"^class TrackKernel"),
    ("track_models.py", r"^class ModalTrack"),
    ("track_models.py", r"^class ModeShape"),
    ("track_models.py", r"^def load_modal_track"),
    ("track_models.py", r"^    def local_state"),
    ("track_models.py", r"eta, etadot = q\[35:\]"),
    ("track_models.py", r"modal.stiffness_n_m \* q\[35:\]"),
    ("track_models.py", r"modal block is shared"),
    ("track_models.py", r"^    def internal_force"),
    ("track_models.py", r"^    def contact_reaction"),
    ("track_models.py", r"^    def potential_j"),
    ("track_models.py", r"^    def support_reaction"),
    ("track_models.py", r"^    def dimension"),
    # vehicle contract
    ("vehicle.py", r"^class VehicleCase"),
    ("vehicle.py", r"^def load_vehicle_case"),
    ("vehicle.py", r"^class RailBody"),
    ("vehicle.py", r"^    def active_at"),
    ("vehicle.py", r"^class VehicleRail"),
    ("vehicle.py", r"^    def contact_bodies"),
    ("vehicle.py", r"^class VehicleParameters"),
    ("vehicle.py", r"^    def axle_offsets_m"),
    ("vehicle.py", r"total = 35"),
    # solver
    ("vehicle_solver.py", r"^class VehicleDynamics"),
    ("vehicle_solver.py", r"^class Connector"),
    ("vehicle_solver.py", r"^CONTACT_RESEARCH_INTERVAL"),
    ("vehicle_solver.py", r"^BODY_SWITCH_MARGIN_M"),
    ("vehicle_solver.py", r"^    def _build_connectors"),
    ("vehicle_solver.py", r"^    def evaluate"),
    ("vehicle_solver.py", r"^    def _attribute_bodies"),
    ("vehicle_solver.py", r"^    def _evaluate_patch"),
    ("vehicle_solver.py", r"^    def derivative_pure"),
    ("vehicle_solver.py", r"^def _static_vertical_equilibrium"),
    ("vehicle_solver.py", r"^def simulate_vehicle"),
    ("vehicle_solver.py", r"^def _rhs_sparsity"),
    ("vehicle_solver.py", r"^def _integrate_vehicle"),
    ("vehicle_solver.py", r"^def save_vehicle_result"),
    ("vehicle_solver.py", r'== "analytic"'),
    ("vehicle_solver.py", r'jac_sparsity'),
    ("vehicle_solver.py", r"history.csv"),
    ("vehicle_solver.py", r"^from \.solver import"),
    ("vehicle_solver.py", r"from \.jacobian import"),
    ("vehicle_solver.py", r"unvalidated_against_measurement_or_Simpack"),
    # model / solver / parallel / metrics / jacobian
    ("model.py", r"^class RunSettings"),
    ("model.py", r"^class Case"),
    ("model.py", r"^def load_case"),
    ("model.py", r"self.jacobian not in"),
    ("model.py", r'ContactParameters\(\*\*raw\["contact"\]\)'),
    ("solver.py", r"^class SimulationFailure"),
    ("solver.py", r"^def simulate"),
    ("solver.py", r"^def save_result"),
    ("parallel.py", r"^def run_vehicle_batch"),
    ("parallel.py", r"^def _solve_case"),
    ("metrics.py", r"^class Assessment"),
    ("metrics.py", r"^def assess_history"),
    ("metrics.py", r"^class AssessmentLimits"),
    ("jacobian.py", r"^class JacobianAssembler"),
    ("jacobian.py", r"^    def _track_blocks"),
    ("jacobian.py", r"^    def _normal_slopes"),
    ("jacobian.py", r"^    def full"),
    ("jacobian.py", r"frozen"),
    ("jacobian.py", r"from \.contact import hunt_crossley_coefficient"),
    # cli / case / gui / ui
    ("cli.py", r"^def main"),
    ("cli.py", r'add_parser\("assess"'),
    ("cli.py", r'add_parser\("run-vehicle-batch"'),
    ("case/spec.py", r"^class CaseSpec"),
    ("case/spec.py", r"^from \.\.vehicle import"),
    ("gui.py", r"^class VelchWorkbench"),
    ("gui.py", r"^def _run_worker"),
    ("gui.py", r"subprocess.Popen"),
    ("gui_support.py", r"^def plot_series"),
    ("ui/__init__.py", r"^def main"),
    ("ui/store.py", r"^def read_history"),
    ("ui/store.py", r"^def scan_runs"),
    ("ui/store.py", r"^def assess"),
    ("ui/store.py", r"^def spectrum"),
    ("ui/store.py", r"^def compare"),
    ("ui/store.py", r"^def simpack_reference"),
    ("ui/store.py", r"^from \.\.inverse\.bands"),
    # io / inverse
    ("io/history.py", r"^def read_history"),
    ("io/history.py", r"^def write_history"),
    ("io/history.py", r"^def classify"),
    ("io/__init__.py", r"^from \.history"),
    ("io/__init__.py", r"^from \.measured"),
    ("io/measured.py", r"^def load_observations"),
    ("io/measured.py", r"^def read_record"),
    ("inverse/channels.py", r"^def standard_turnout_plan"),
    ("inverse/channels.py", r"^def strain_channel_to_force"),
    ("inverse/channels.py", r"^def detect_peak_event"),
    ("inverse/observation.py", r"^def align"),
    ("inverse/estimator.py", r"^def gauss_newton"),
    ("inverse/estimator.py", r"^class Estimate"),
    ("inverse/identifiability.py", r"^def analyse"),
    ("inverse/sensors.py", r"^def wheelset_acceleration"),
    ("inverse/sensors.py", r"^def bending_strain_micro"),
    ("inverse/bands.py", r"^def band_metrics"),
]


def main(argv: list[str]) -> int:
    only = argv[1] if len(argv) > 1 else None
    missing: list[str] = []
    for name, pattern in ANCHORS:
        if only and only not in name:
            continue
        path = ROOT / SRC / name
        if not path.is_file():
            print(f"MISSING FILE  {path}")
            continue
        hits = [
            (index, line.rstrip())
            for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(pattern, line)
        ]
        if not hits:
            missing.append(f"{SRC}/{name}  /{pattern}/")
            continue
        for index, line in hits:
            print(f"{SRC}/{name}:{index}: {line.strip()[:110]}")
    if missing:
        print("\n--- patterns not found ---")
        for item in missing:
            print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
