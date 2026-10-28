"""The yaw-stability report must refuse to call a growing curve settled.

The measurement behind these tests: after the curving force is derived from the design line, the
net lateral force on R = 1100 m at 80 km/h still grows with time (+11 691.2 N at 0.34 s to
+29 544.4 N at 0.60 s).  A growing response has no steady state, so the analyser's criterion is a
ratio test and its parser must either read all four numbers or refuse -- a silently truncated read
would turn a missing run into a passing one.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "s45_yaw_stability.py"


def _module():
    spec = importlib.util.spec_from_file_location("s45_yaw_stability", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _log(path: pathlib.Path, *, fy: float, delay: str, pen: float = 91.39) -> pathlib.Path:
    path.write_text(
        f"  run {delay} s -> numerically_checked  frames 1701  gates 7/7 failing []\n"
        f"  max penetration {pen} um\n"
        f"  last frame: sum Fy {fy:+.1f} N  (fictitious demand 21842.4 N, "
        f"{100.0 * fy / 21842.4:+.1f}%)  left 255467 N / right 219648 N  transfer +35819 N\n",
        encoding="utf-8")
    return path


def test_the_percentage_is_read_without_a_space_before_the_sign(tmp_path):
    # The run prints "+55.4%" with no space; the first version of the pattern demanded one and
    # rejected every real log with "could not read the run summary".
    module = _module()
    parsed = module.parse(_log(tmp_path / "a.log", fy=12091.6, delay="0.34"))
    assert parsed["sum_fy_n"] == pytest.approx(12091.6)
    # share_of_demand is the share the run *printed* (one decimal place), not a second
    # calculation: 0.554 here against 0.5536 from the raw numbers is the rounding, and keeping the
    # printed value means the report cannot disagree with the log it cites.
    assert parsed["share_of_demand"] == pytest.approx(0.554)
    assert parsed["status"] == "numerically_checked"


def test_a_missing_summary_line_is_refused_rather_than_guessed(tmp_path):
    module = _module()
    broken = tmp_path / "b.log"
    broken.write_text("  run 0.34 s -> numerically_checked  frames 1701\n", encoding="utf-8")
    with pytest.raises(ValueError, match="could not read the run summary"):
        module.parse(broken)


def test_the_ratio_criterion_accepts_the_boundary_and_rejects_a_growing_curve(tmp_path, monkeypatch):
    module = _module()
    module.LOG_DIR = tmp_path
    # Exactly 1.2 is inside the criterion; 1.21 is not.
    _log(tmp_path / "k2_0.34.log", fy=10000.0, delay="0.34")
    _log(tmp_path / "k2_0.60.log", fy=12000.0, delay="0.60")
    _log(tmp_path / "k5_0.34.log", fy=10000.0, delay="0.34")
    _log(tmp_path / "k5_0.60.log", fy=12100.0, delay="0.60")
    _log(tmp_path / "kalker_0.34.log", fy=18952.7, delay="0.34")
    _log(tmp_path / "kalker_0.60.log", fy=41516.7, delay="0.60")
    monkeypatch.setattr(module, "OUT", tmp_path / "out")
    table = {row["name"]: row for row in module.rows() if "name" in row}
    assert table["k2"]["ratio"] == pytest.approx(1.2)
    assert table["k2"]["passes_the_ratio"] is True
    assert table["k5"]["passes_the_ratio"] is False
    # The measured Kalker pair grows by 2.19x, so it must not be reported as settling.
    assert table["kalker"]["ratio"] == pytest.approx(41516.7 / 18952.7, rel=1e-9)
    assert table["kalker"]["passes_the_ratio"] is False
    assert table["kalker"]["points_with_demand"] is True
