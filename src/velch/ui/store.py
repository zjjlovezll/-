"""Read-only data access for the Velch desktop UI.

Nothing in this module touches Tkinter, and nothing here writes a result: the UI only
reads run artifacts (``manifest.json`` / ``history.csv`` / ``case_snapshot.json``),
parses case JSON, and calls the public analysis API (``velch.metrics``,
``velch.inverse.bands``, ``velch.inverse.channels``).  Solver launches go through the
CLI as a subprocess, never through an in-process import.

Keeping this layer Tk-free is what lets ``--selftest`` load every screen headlessly
and report real row counts on a machine with no display.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from ..data_root import case_dir as _case_dir
from ..inverse.bands import (DEFAULT_BAND_HZ, BandError, BandMetrics, band_metrics,
                             third_octave_centres, third_octave_levels)
from ..metrics import Assessment, AssessmentError, assess_history

# ---------------------------------------------------------------------------
# locations
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
#: Resolved through :mod:`velch.data_root` so a moved validation corpus needs no edit here.
VALIDATION_DIR = _case_dir()
SIMPACK_MAT = (REPO_ROOT.parent / "simpack-mcp-2021x" / "results"
               / "case_a47bc7d9e48f40b08628147bfab5c3f4" / "model.output" / "350.mat")
SIMPACK_SRC = REPO_ROOT.parent / "simpack-mcp-2021x" / "src"

#: Simpack result subtree reused verbatim from
#: ``validation/crh380a_m/cmp_final_vs_simpack.py`` so both sides describe the same
#: physical quantities (front wheelset station, right-rail normal force, penetration).
SIMPACK_GROUP = "timeInt/RS_result/SRS_S_R/SRS_S_WS_F/SRS_RWP_R"
SIMPACK_Z_GROUP = "timeInt/bodyPosTrans/SS_F__S_WS_F__B_WS/z"
SIMPACK_STATION_OFFSET_M = 17.5

#: The manifest gates, in the order the solver writes them, with the numeric companion the
#: manifest records for each so a failure can be read, not just seen.  Nine since round 315: the
#: screen read only these seven and therefore showed a run whose ``launch_balance`` failed as
#: ``7/7`` -- the one gate that catches a launch with the wrong spin was invisible.  Unknown keys
#: are still rendered by name, so the next gate does not have to be added here to be seen.
GATE_LABELS: tuple[tuple[str, str], ...] = (
    ("solver_completed", "求解器收敛完成"),
    ("finite_states_and_forces", "状态与力全部有限"),
    ("vertical_preload_residual", "垂向预载残差"),
    ("penetration_within_case_limit", "侵入量在算例限值内"),
    ("friction_bound", "摩擦力在摩擦界内"),
    ("no_edge_limited_active_contact", "无边缘限幅有效接触"),
    ("translational_action_reaction", "平动作用-反力平衡"),
    ("launch_balance", "起点平衡（转速 + 预载）"),
    ("stationarity", "读数窗口平稳"),
)

GATE_DETAIL_FIELDS: dict[str, str] = {
    "vertical_preload_residual": "vertical_preload_max_residual_n",
    "penetration_within_case_limit": "max_penetration_m",
    "friction_bound": "max_friction_excess_n",
    "no_edge_limited_active_contact": "edge_limited_active_output_samples",
    "translational_action_reaction": "max_translation_balance_error_n",
    "launch_balance": "spin_relative_max",
    "stationarity": "max_rail_force_std_kn",
}

GATE_UNITS: dict[str, str] = {
    "vertical_preload_max_residual_n": "N",
    "max_penetration_m": "m",
    "max_friction_excess_n": "N",
    "edge_limited_active_output_samples": "个采样",
    "max_translation_balance_error_n": "N",
    "spin_relative_max": "-",
    "max_rail_force_std_kn": "kN",
}


class StoreError(RuntimeError):
    """Raised when a requested artifact cannot be read."""


# ---------------------------------------------------------------------------
# channel vocabulary
# ---------------------------------------------------------------------------

#: ``(suffix, unit, group)`` ordered most-specific first; the first match wins.  Length matters:
#: ``_m_per_s`` has to be tested before ``_m`` or every velocity would be labelled a position.
#: The acceleration suffixes go first for the same reason: ``axle1_z_acc_m_per_s2`` ends in neither
#: ``_m_per_s`` nor ``_m``, and without these two rules every acceleration channel would fall back to
#: its raw identifier -- which is what happened when B026 started emitting them.
_UNIT_RULES: tuple[tuple[str, str, str], ...] = (
    ("_acc_m_per_s2", "m/s²", "加速度"),
    ("_acc_rad_per_s2", "rad/s²", "角加速度"),
    ("_m_per_s", "m/s", "速度"),
    ("_rad_per_s", "rad/s", "角速度"),
    ("_normal_n", "N", "接触力"),
    ("_fx_n", "N", "接触力"),
    ("_fy_n", "N", "接触力"),
    ("_fz_n", "N", "接触力"),
    ("_nm", "N·m", "力矩"),
    ("_penetration_m", "m", "侵入深度"),
    ("_active", "—", "接触状态"),
    ("_rad", "rad", "转角"),
    ("_m", "m", "位移"),
    ("_s", "s", "时间"),
)

#: Body/owner words.  ``第1轴`` reads better than ``1 轴`` and keeps the number attached.
_OWNER = {
    "time": "时间",
    "carbody": "车体",
    "bogie1": "前转向架",
    "bogie2": "后转向架",
    "bogie": "转向架",
}
for _index in range(1, 9):
    _OWNER[f"axle{_index}"] = f"第{_index}轴"

#: Side words for the four wheel-rail contacts of one wheelset.
_SIDE = {"left": "左轨", "right": "右轨"}

#: Quantity words, keyed by the token that follows the owner (and optional side).
_QUANTITY = {
    "normal": "法向力",
    "fx": "纵向蠕滑力",
    "fy": "横向蠕滑力",
    "fz": "垂向轮轨力",
    "penetration": "侵入深度",
    "active": "接触状态",
    "x": "里程",
    "y": "横移",
    "z": "沉浮",
    "roll": "侧滚角",
    "pitch": "点头角",
    "yaw": "摇头角",
    "spin": "自转角",
    "mode": "模态位移",
}

#: Rail/sleeper channels of a flexible track, e.g. ``rail2_z_m``.
_TRACK_OWNER = {"rail": "钢轨", "sleeper": "轨枕"}

#: Quantity carried *by the unit suffix* rather than by a token of its own: in
#: ``axle1_left_active`` the word ``active`` is the suffix, so stripping it would otherwise lose
#: the one thing the channel means.
_SUFFIX_QUANTITY = {
    "_normal_n": "normal",
    "_fx_n": "fx",
    "_fy_n": "fy",
    "_fz_n": "fz",
    "_penetration_m": "penetration",
    "_active": "active",
}


def _split_suffix(column: str) -> tuple[str, str, str]:
    """``(base, unit, group)`` for a history column, by the documented suffix."""

    for suffix, unit, group in _UNIT_RULES:
        if column.endswith(suffix):
            return column[: -len(suffix)], unit, group
    return column, "—", "其他"


def _split_suffix_full(column: str) -> tuple[str, str, str, str]:
    """``(base, unit, group, suffix)`` — the suffix itself is sometimes the quantity word.

    ``axle1_left_active`` has no token left once ``_active`` is stripped, so the quantity has to
    come back out of the suffix; without this the label falls back to the raw identifier.
    """

    for suffix, unit, group in _UNIT_RULES:
        if column.endswith(suffix):
            return column[: -len(suffix)], unit, group, suffix
    return column, "—", "其他", ""


def channel_unit(column: str) -> str:
    """Unit of a history column, inferred from its documented suffix."""

    return _split_suffix(column)[1]


def channel_group(column: str) -> str:
    """Unit group shown as the y-axis band on the time-history screen."""

    return _split_suffix(column)[2]


def channel_label(column: str) -> str:
    """Chinese label for a history column.

    The label is built from the documented channel grammar rather than guessed:

        ``axle2_right_normal_n``   -> ``第2轴右轨 法向力 [N]``
        ``axle1_y_m_per_s``        -> ``第1轴 横移速度 [m/s]``
        ``carbody_yaw_rad``        -> ``车体 摇头角 [rad]``
        ``track_mode12_m``         -> ``钢轨 模态位移 12 [m]``

    An unrecognised column falls back to the raw name with its unit, never to a guess: a wrong
    Chinese word is worse than an untranslated identifier, because it reads like a definition.
    """

    base, unit, _group, suffix = _split_suffix_full(column)
    tokens = base.split("_")
    if not tokens:
        return column
    velocity = unit in {"m/s", "rad/s"}
    acceleration = unit in {"m/s²", "rad/s²"}
    # ``侧滚角`` already carries the 角, so the suffix word is 加速度 and not 角加速度
    suffix_word = "速度" if velocity else ("加速度" if acceleration else "")

    head = tokens[0]
    remainder = tokens[1:]
    if head == "time" and not remainder:
        return f"时间 [{unit}]"
    if head == "track" and remainder and remainder[0].startswith("mode"):
        digits = remainder[0][len("mode"):]
        return f"钢轨 模态位移 {digits} [{unit}]" if digits else f"钢轨 模态位移 [{unit}]"

    owner = _OWNER.get(head)
    track_kind = _TRACK_OWNER.get(head.rstrip("0123456789"))
    if owner is None and track_kind and remainder:
        index = head[len(head.rstrip("0123456789")):]
        quantity = _QUANTITY.get(remainder[0], "")
        spoken = f"{track_kind}{index} {quantity}{suffix_word}".strip()
        return f"{spoken} [{unit}]" if quantity else f"{column} [{unit}]"
    if owner is None:
        return f"{column} [{unit}]"

    side = ""
    if remainder[:1] and remainder[0] == "box":
        # ``axle1_box_left`` is the axle-box body, not the rail: the box rides the axle, and left and
        # right are two separate 48.2 kg bodies.  The side word has to say 轴箱 too, otherwise
        # ``第1轴左轨`` would claim it is a rail channel.
        remainder = remainder[1:]
        if remainder[:1] and remainder[0] in _SIDE:
            side = {"left": "左轴箱", "right": "右轴箱"}[remainder[0]]
            remainder = remainder[1:]
        else:
            side = "轴箱"
    elif remainder[:1] and remainder[0] in _SIDE:
        side = _SIDE[remainder[0]]
        remainder = remainder[1:]
    # Flexible-track channels name the structural part after the side: ``axle1_left_rail_z_m``
    # is the rail's vertical displacement under wheel 1's left contact, not the wheel's motion.
    part = ""
    quantity = ""
    if remainder and remainder[0] in _TRACK_OWNER:
        part = _TRACK_OWNER[remainder[0]]
        remainder = remainder[1:]
        direction = remainder[0] if remainder else ""
        quantity = {"y": "横向位移", "z": "垂向位移"}.get(direction, "")
    else:
        quantity_token = remainder[0] if remainder else _SUFFIX_QUANTITY.get(suffix, "")
        quantity = _QUANTITY.get(quantity_token, "")
        # ``x`` is mileage for a position (``axle1_x_m`` runs along the track) but the acceleration
        # along it is longitudinal motion, and 里程加速度 would be nonsense.
        if acceleration and quantity_token == "x":
            quantity = "纵向"
    if not quantity:
        return f"{column} [{unit}]"
    spoken = f"{owner}{side} {part}{quantity}{suffix_word}".strip()
    return f"{spoken} [{unit}]"


def channel_short_label(column: str) -> str:
    """``channel_label`` without the trailing unit, for tight tables."""

    label = channel_label(column)
    return label.rsplit(" [", 1)[0] if " [" in label else label


def group_channels(columns: Iterable[str]) -> dict[str, list[str]]:
    """Buckets history columns by unit group, preserving file order inside a bucket."""

    buckets: dict[str, list[str]] = {}
    for column in columns:
        buckets.setdefault(channel_group(column), []).append(column)
    return buckets


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CaseInfo:
    """One ``case_*.json`` on the case screen."""

    path: Path
    case_id: str
    schema: str = ""
    purpose: str = ""
    duration_s: float | None = None
    dof: int = 0
    x_start_m: float | None = None
    output_step_s: float | None = None
    size_bytes: int = 0
    sha256: str = ""
    problem: str = ""

    @property
    def kind(self) -> str:
        return "vehicle" if self.schema == "velch-vehicle-v2" else (
            "wheelset" if self.schema == "velch-case-v1" else "unknown")

    @property
    def kind_label(self) -> str:
        return {"vehicle": "整车 v2", "wheelset": "轮对 v1"}.get(self.kind, "未知")

    @property
    def duration_label(self) -> str:
        return f"{self.duration_s:.3f} s" if self.duration_s is not None else "—"

    @property
    def sha_short(self) -> str:
        return self.sha256[:12] if self.sha256 else "—"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def case_info(path: Path, *, hashing: bool = True) -> CaseInfo:
    """Parse one case file into the row the case screen shows."""

    try:
        raw = path.read_bytes()
    except OSError as exc:  # pragma: no cover - unreadable file
        return CaseInfo(path=path, case_id=path.stem, problem=f"无法读取: {exc}")
    sha = hashlib.sha256(raw).hexdigest() if hashing else ""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return CaseInfo(path=path, case_id=path.stem, size_bytes=len(raw), sha256=sha,
                        problem=f"JSON 解析失败: {exc}")
    if not isinstance(data, dict):
        return CaseInfo(path=path, case_id=path.stem, size_bytes=len(raw), sha256=sha,
                        problem="顶层不是 JSON 对象")
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    state = data.get("initial_state") if isinstance(data.get("initial_state"), dict) else {}
    q = state.get("q") if isinstance(state.get("q"), list) else []
    duration = run.get("duration_s")
    x_start = run.get("x_start_m")
    step = run.get("output_step_s")
    return CaseInfo(
        path=path,
        case_id=str(data.get("case_id") or path.stem),
        schema=str(data.get("schema_version") or ""),
        purpose=str(data.get("purpose") or ""),
        duration_s=float(duration) if isinstance(duration, (int, float)) else None,
        dof=len(q),
        x_start_m=float(x_start) if isinstance(x_start, (int, float)) else None,
        output_step_s=float(step) if isinstance(step, (int, float)) else None,
        size_bytes=len(raw),
        sha256=sha,
    )


def scan_cases(directory: Path | None = None, pattern: str = "case_*.json",
               *, hashing: bool = True) -> list[CaseInfo]:
    """All case files under ``directory`` (default: the CRH380A_M validation set)."""

    root = directory or VALIDATION_DIR
    if not root.is_dir():
        return []
    infos = [case_info(path, hashing=hashing)
             for path in sorted(root.glob(pattern)) if path.is_file()]
    infos.sort(key=lambda info: (info.problem != "", info.purpose, info.case_id))
    return infos


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------

@dataclass
class RunInfo:
    """One ``out_*`` run directory on the results screens."""

    path: Path
    case_id: str = ""
    case_purpose: str = ""
    result_status: str = ""
    physics_status: str = ""
    total_dof: int = 0
    vehicle_dof: int = 0
    peak_normal_force_n: dict[str, float] = field(default_factory=dict)
    max_penetration_m: float | None = None
    energy_change_j: float | None = None
    gates: dict[str, bool] = field(default_factory=dict)
    case_sha256: str = ""
    method: str = ""
    nfev: int | None = None
    columns: int = 0
    samples: int | None = None
    mtime: float = 0.0
    problem: str = ""

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def history(self) -> Path:
        return self.path / "history.csv"

    @property
    def manifest(self) -> Path:
        return self.path / "manifest.json"

    @property
    def snapshot(self) -> Path:
        return self.path / "case_snapshot.json"

    @property
    def gates_passed(self) -> int:
        return sum(1 for value in self.gates.values() if value)

    @property
    def gates_total(self) -> int:
        return len(self.gates)

    @property
    def status_label(self) -> str:
        return {"numerically_checked": "数值检查通过",
                "numerical_gate_failed": "数值门失败"}.get(self.result_status,
                                                           self.result_status or "—")

    @property
    def peak_force_n(self) -> float | None:
        """Largest contact normal force in newtons (the manifest stores N, not kN).

        Named ``peak_force_n`` on purpose: the old ``peak_force_kn`` returned newtons, and the one
        call site happened to divide by 1000 itself.  Any new caller trusting the name would have
        reported 170610 kN.
        """

        values = [v for v in self.peak_normal_force_n.values() if isinstance(v, float)]
        return max(values, default=None)


def _header_columns(history: Path) -> tuple[list[str], str]:
    try:
        with history.open("r", newline="", encoding="utf-8-sig") as stream:
            return next(csv.reader(stream)), ""
    except StopIteration:  # pragma: no cover - empty file
        return [], "history.csv 为空"
    except OSError as exc:  # pragma: no cover - unreadable
        return [], f"history.csv 读取失败: {exc}"


def run_info(path: Path, *, read_header: bool = True) -> RunInfo:
    """Build the results-screen row for one run directory."""

    info = RunInfo(path=path)
    try:
        info.mtime = path.stat().st_mtime
    except OSError:  # pragma: no cover
        pass
    manifest = path / "manifest.json"
    if not manifest.is_file():
        info.problem = "缺少 manifest.json"
        return info
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        info.problem = f"manifest.json 解析失败: {exc}"
        return info
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    solver = summary.get("solver") if isinstance(summary.get("solver"), dict) else {}
    gates = summary.get("gates") if isinstance(summary.get("gates"), dict) else {}
    peaks = summary.get("peak_normal_force_n")
    info.case_id = str(summary.get("case_id") or "")
    info.case_purpose = str(summary.get("case_purpose") or "")
    info.result_status = str(summary.get("result_status") or "")
    info.physics_status = str(summary.get("physics_validation_status") or "")
    info.total_dof = int(summary.get("total_dof") or 0)
    info.vehicle_dof = int(summary.get("vehicle_dof") or 0)
    info.peak_normal_force_n = ({str(k): float(v) for k, v in peaks.items()}
                                if isinstance(peaks, dict) else {})
    penetration = summary.get("max_penetration_m")
    info.max_penetration_m = float(penetration) if isinstance(penetration, (int, float)) else None
    energy = summary.get("energy_change_j")
    info.energy_change_j = float(energy) if isinstance(energy, (int, float)) else None
    info.gates = {str(k): bool(v) for k, v in gates.items()}
    info.case_sha256 = str(data.get("case_sha256") or "")
    info.method = str(solver.get("method") or "")
    nfev = solver.get("nfev")
    info.nfev = int(nfev) if isinstance(nfev, (int, float)) else None
    if read_header:
        columns, problem = _header_columns(path / "history.csv")
        info.columns = len(columns)
        if problem:
            info.problem = problem
    return info


def scan_runs(directory: Path | None = None, pattern: str = "out_*",
              *, read_header: bool = True, limit: int | None = None) -> list[RunInfo]:
    """All run directories, newest first, each with its manifest summary."""

    root = directory or VALIDATION_DIR
    if not root.is_dir():
        return []
    paths = [path for path in root.glob(pattern) if path.is_dir()]
    infos = [run_info(path, read_header=read_header) for path in paths]
    infos.sort(key=lambda info: (-info.mtime, info.name))
    return infos[:limit] if limit else infos


# ---------------------------------------------------------------------------
# history.csv access
# ---------------------------------------------------------------------------

def history_columns(path: Path) -> list[str]:
    columns, problem = _header_columns(path)
    if problem:
        raise StoreError(problem)
    return columns


#: Solver names as a person reads them.  The name itself stays in the label, the words explain it.
_METHOD_WORDS = {
    "DOP853": "显式 8 阶 DOP853",
    "Radau": "隐式 Radau",
    "BDF": "隐式 BDF",
}


def run_label(run: RunInfo) -> str:
    """One run in words: ``名称 · 帧数 · 通道 · 方法 · 门 7/7``.

    The directory name stays first and untranslated — it is the identifier a person types to
    reopen the run, and two runs can only be told apart by it.  The words after it are what
    makes the row readable without opening the docs.
    """

    parts = [run.name]
    if run.samples:
        parts.append(f"{run.samples} 帧")
    if run.columns:
        parts.append(f"{run.columns} 通道")
    if run.method:
        parts.append(_METHOD_WORDS.get(run.method, run.method))
    if run.gates:
        parts.append(f"门 {run.gates_passed}/{len(run.gates)}")
    if run.problem:
        parts.append(f"（{run.problem}）")
    elif len(parts) == 1:
        # A run directory with no readable manifest still has to say *something* in words, or
        # the dropdown reads as a pile of identifiers.
        parts.append("（无 history 表头）" if not run.history.is_file() else "（未解析通道）")
    return " · ".join(parts)


@dataclass
class Series:
    """A loaded history slab: the time base plus the requested channel arrays."""

    path: Path
    time_s: np.ndarray
    values: dict[str, np.ndarray]
    rows: int
    rate_hz: float

    @property
    def span_s(self) -> float:
        return float(self.time_s[-1] - self.time_s[0]) if self.time_s.size else 0.0


def read_history(path: Path, columns: Sequence[str] | None = None) -> Series:
    """Load ``history.csv`` once and keep the requested columns as float arrays."""

    if path.is_dir():
        path = path / "history.csv"
    if not path.is_file():
        raise StoreError(f"找不到 history.csv: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise StoreError(f"history.csv 为空: {path}") from exc
        index = {name: position for position, name in enumerate(header)}
        wanted = [name for name in (columns or header) if name in index]
        if not wanted:
            raise StoreError("请求的通道不在 history.csv 中")
        if "time_s" in index and "time_s" not in wanted:
            wanted.insert(0, "time_s")
        buckets: dict[str, list[float]] = {name: [] for name in wanted}
        slots = [(name, index[name]) for name in wanted]
        rows = 0
        for row in reader:
            if not row:
                continue
            rows += 1
            for name, position in slots:
                try:
                    value = float(row[position])
                except (IndexError, ValueError):
                    value = math.nan
                buckets[name].append(value if math.isfinite(value) else math.nan)
    arrays = {name: np.asarray(values, dtype=float) for name, values in buckets.items()}
    time_s = arrays.get("time_s")
    if time_s is None:
        time_s = np.arange(rows, dtype=float)
    rate = sample_rate(time_s)
    return Series(path=path, time_s=time_s, values=arrays, rows=rows, rate_hz=rate)


def sample_rate(time_s: np.ndarray) -> float:
    """Sampling rate from the median time step (0.0 when undeterminable)."""

    if time_s.size < 3:
        return 0.0
    steps = np.diff(time_s)
    steps = steps[np.isfinite(steps) & (steps > 0.0)]
    if steps.size == 0:
        return 0.0
    return float(1.0 / np.median(steps))


def decimate(xs: np.ndarray, ys: np.ndarray, max_points: int = 2000) -> tuple[np.ndarray, np.ndarray]:
    """Min/max envelope decimation that keeps every extremum of the drawn window.

    A plain stride would hide a 1-sample force spike, which on this data is exactly the
    event the screen exists to show, so each bucket contributes its first, last, min and
    max samples in original order.
    """

    if xs.size <= max_points or max_points < 8:
        return xs, ys
    buckets = max(1, max_points // 4)
    edges = np.linspace(0, xs.size, buckets + 1).astype(int)
    keep: list[int] = []
    for start, stop in zip(edges[:-1], edges[1:]):
        if stop <= start:
            continue
        block = ys[start:stop]
        finite = np.isfinite(block)
        if not finite.any():
            keep.append(start)
            continue
        local = np.flatnonzero(finite)
        picks = {0, local.size - 1,
                 int(local[np.argmin(block[finite])]), int(local[np.argmax(block[finite])])}
        keep.extend(start + pick for pick in sorted(picks))
    index = np.unique(np.asarray(keep, dtype=int))
    return xs[index], ys[index]


def clip_series(xs: np.ndarray, ys: np.ndarray, x0: float, x1: float
                ) -> tuple[np.ndarray, np.ndarray]:
    """Restrict a series to ``[x0, x1]`` (used by the zoom/pan interaction)."""

    if xs.size == 0:
        return xs, ys
    mask = (xs >= x0) & (xs <= x1)
    if not mask.any():
        return xs[:0], ys[:0]
    return xs[mask], ys[mask]


# ---------------------------------------------------------------------------
# spectrum
# ---------------------------------------------------------------------------

@dataclass
class SpectrumResult:
    column: str
    rate_hz: float
    low_hz: float
    high_hz: float
    levels: dict[float, float]
    metrics: BandMetrics
    note: str = ""

    @property
    def dominant_hz(self) -> float | None:
        return self.metrics.dominant_band_hz

    def band_table(self) -> list[tuple[float, float]]:
        return sorted(self.levels.items())


def spectrum(series: Series, column: str, low_hz: float = DEFAULT_BAND_HZ[0],
             high_hz: float = DEFAULT_BAND_HZ[1]) -> SpectrumResult:
    """1/3-octave levels and campaign-style metrics for one channel.

    Delegates to :mod:`velch.inverse.bands`; the UI adds no analysis of its own beyond
    dropping non-finite samples before the filter sees them.
    """

    if column not in series.values:
        raise StoreError(f"通道未加载: {column}")
    data = series.values[column]
    finite = data[np.isfinite(data)]
    if finite.size < 8:
        raise BandError("有效样本不足, 无法做 1/3 倍频程分解")
    rate = series.rate_hz
    if rate <= 0.0:
        raise BandError("无法从 time_s 推断采样率")
    clipped_high = min(high_hz, 0.49 * rate)
    levels = third_octave_levels(finite, rate, third_octave_centres(low_hz, clipped_high))
    metrics = band_metrics(finite, rate, low_hz, clipped_high)
    note = ""
    if clipped_high < high_hz:
        note = (f"采样率 {rate:.0f} Hz，上限频带自动收到 {clipped_high:.0f} Hz"
                "（Nyquist 之下）")
    return SpectrumResult(column=column, rate_hz=rate, low_hz=low_hz,
                          high_hz=clipped_high, levels=levels, metrics=metrics, note=note)


# ---------------------------------------------------------------------------
# assessment
# ---------------------------------------------------------------------------

@dataclass
class AssessmentView:
    assessment: Assessment
    verdict: dict[str, Any]

    @property
    def samples(self) -> int:
        return self.assessment.samples

    @property
    def passed(self) -> bool:
        return bool(self.verdict.get("pass"))

    def bars(self) -> list[tuple[str, float, float, bool, str, str]]:
        """``(label, value, limit, pass, caption, unit)`` for the three limit bars.

        The unit travels with the bar so the reading can take an SI prefix instead of printing
        ``4.979e+04``: "49.79 kN" is a number an engineer can check against a code, and a clipped
        "4.97" is a number that lies by four orders of magnitude.
        """

        limits = self.verdict.get("checks", {})
        out: list[tuple[str, float, float, bool, str]] = []
        names = {
            "derailment_coefficient": ("脱轨系数 Q/P", "限值 0.80 (GB/T 5599 客车)", ""),
            "wheel_load_reduction": ("轮重减载率 ΔP/P̄", "限值 0.60", ""),
            "axle_lateral_force_n": ("轮轴横向力 H", "限值 10 + P0/3 kN", "N"),
        }
        for key, (label, caption, unit) in names.items():
            check = limits.get(key) or {}
            value = float(check.get("value") or 0.0)
            limit = float(check.get("limit") or 0.0)
            out.append((label, value, limit, bool(check.get("pass")), caption, unit))
        return out


def assess(target: Path, static_axle_load_n: float | None = None) -> AssessmentView:
    """Run the same public function ``velch assess`` calls (``metrics.assess_history``)."""

    assessment = assess_history(target, static_axle_load_n=static_axle_load_n)
    return AssessmentView(assessment=assessment,
                          verdict=assessment.verdict(assessment.static_axle_load_n))


# ---------------------------------------------------------------------------
# Simpack / measured reference for the compare screen
# ---------------------------------------------------------------------------

def simpack_available() -> tuple[bool, str]:
    """Whether the Simpack reference can be read here, with the reason when it cannot."""

    if not SIMPACK_MAT.is_file():
        return False, f"找不到 Simpack 结果: {SIMPACK_MAT}"
    try:
        import h5py  # noqa: F401  (presence check only)
    except ImportError:
        return False, "缺少 h5py，无法读取 Simpack .mat（改用实测 CSV 对照）"
    return True, ""


@dataclass
class ReferenceSeries:
    """One side of the compare screen: station-aligned channels on a common axis."""

    label: str
    station_m: np.ndarray
    force_n: np.ndarray
    penetration_m: np.ndarray | None = None
    wheel_z_m: np.ndarray | None = None
    source: str = ""

    def resample(self, grid: np.ndarray) -> dict[str, np.ndarray]:
        out = {"force_n": np.interp(grid, self.station_m, self.force_n)}
        if self.penetration_m is not None:
            out["penetration_m"] = np.interp(grid, self.station_m, self.penetration_m)
        if self.wheel_z_m is not None:
            out["wheel_z_m"] = np.interp(grid, self.station_m, self.wheel_z_m)
        return out


def simpack_reference() -> ReferenceSeries:
    """Simpack front-wheelset right-rail channels, mapped exactly as the validation scripts do."""

    ok, reason = simpack_available()
    if not ok:
        raise StoreError(reason)
    import h5py

    with h5py.File(SIMPACK_MAT, "r") as handle:
        base = handle[SIMPACK_GROUP]

        def values(node: Any) -> np.ndarray:
            return np.asarray(node["values"]).ravel().astype(float)

        pair = base["SRS_RWP_R_Pair"]
        patch = base["SRS_RWP_R_1"]
        advanced = base["SRS_RWP_R_1_Adv"]
        station = values(pair["ch_008"]) + SIMPACK_STATION_OFFSET_M
        force = values(patch["ch_010"])
        penetration = values(advanced["ch_025"])
        wheel_z = values(handle[SIMPACK_Z_GROUP])
    return ReferenceSeries(label="Simpack 350.mat", station_m=station, force_n=force,
                           penetration_m=penetration, wheel_z_m=wheel_z,
                           source=f"{SIMPACK_MAT} :: {SIMPACK_GROUP}")


def velch_reference(run: Path) -> ReferenceSeries:
    """Velch front-wheelset right-rail channels from one saved run."""

    series = read_history(run, ["time_s", "axle1_x_m", "axle1_right_normal_n",
                                "axle1_right_penetration_m", "axle1_z_m"])
    return ReferenceSeries(
        label=f"Velch {Path(run).name}",
        station_m=series.values["axle1_x_m"],
        force_n=series.values["axle1_right_normal_n"],
        penetration_m=series.values.get("axle1_right_penetration_m"),
        wheel_z_m=series.values.get("axle1_z_m"),
        source=str(Path(run) / "history.csv"),
    )


def measured_reference(path: Path, station_column: str, force_column: str,
                       scale: float = 1.0) -> ReferenceSeries:
    """A measured CSV: any two numeric columns, with an explicit unit scale."""

    series = read_history(path, [station_column, force_column])
    station = series.values[station_column]
    force = series.values[force_column] * scale
    return ReferenceSeries(label=path.name, station_m=station, force_n=force,
                           source=f"{path} :: {station_column} / {force_column}")


@dataclass
class CompareResult:
    grid_m: np.ndarray
    ours: dict[str, np.ndarray]
    theirs: dict[str, np.ndarray]
    stats: dict[str, dict[str, float]]
    caveat: str = ""

    def summary_rows(self) -> list[tuple[str, float, float, float]]:
        """``(metric, ours, reference, delta)`` for the comparison table."""

        rows: list[tuple[str, float, float, float]] = []
        for key, values in self.stats.items():
            rows.append((key, values["ours"], values["reference"],
                         values["ours"] - values["reference"]))
        return rows


def compare(ours: ReferenceSeries, theirs: ReferenceSeries,
            window: tuple[float, float] | None = None,
            points: int = 200) -> CompareResult:
    """Overlay two sides on one station axis and report peak/RMS differences.

    The station axis is the overlap of both records (plus an optional window); nothing is
    shifted or scaled, so a peak difference is a real difference in the two records.
    """

    low = max(float(ours.station_m.min()), float(theirs.station_m.min()))
    high = min(float(ours.station_m.max()), float(theirs.station_m.max()))
    if window is not None:
        low = max(low, window[0])
        high = min(high, window[1])
    if not math.isfinite(low) or not math.isfinite(high) or high <= low:
        raise StoreError("两段记录没有共同里程区间，无法叠加")
    grid = np.linspace(low, high, max(16, points))
    a = ours.resample(grid)
    b = theirs.resample(grid)
    stats = {
        "峰值 force_n": {"ours": float(np.max(np.abs(a["force_n"]))),
                         "reference": float(np.max(np.abs(b["force_n"])))},
        "RMS force_n": {"ours": float(np.sqrt(np.mean(a["force_n"] ** 2))),
                        "reference": float(np.sqrt(np.mean(b["force_n"] ** 2)))},
    }
    if "wheel_z_m" in a and "wheel_z_m" in b:
        za = (a["wheel_z_m"] - np.mean(a["wheel_z_m"])) * 1e3
        zb = (b["wheel_z_m"] - np.mean(b["wheel_z_m"])) * 1e3
        stats["峰值 wheel_z_mm"] = {"ours": float(np.max(np.abs(za))),
                                    "reference": float(np.max(np.abs(zb)))}
        stats["RMS wheel_z_mm"] = {"ours": float(np.sqrt(np.mean(za ** 2))),
                                   "reference": float(np.sqrt(np.mean(zb ** 2)))}
    caveat = ("非同一道岔时只作口径对照：两侧共用同一里程轴、同一通道定义与同一滤波口径，"
              "力与位移的差异可以读，但不构成同工况验证。")
    return CompareResult(grid_m=grid, ours=a, theirs=b, stats=stats, caveat=caveat)


__all__ = [
    "GATE_LABELS", "GATE_DETAIL_FIELDS", "GATE_UNITS", "VALIDATION_DIR", "REPO_ROOT",
    "CaseInfo", "RunInfo", "Series", "SpectrumResult", "AssessmentView", "ReferenceSeries",
    "CompareResult", "StoreError", "assess", "case_info", "channel_group", "channel_label",
    "channel_unit", "clip_series", "compare", "decimate", "file_sha256", "group_channels",
    "history_columns", "measured_reference", "read_history", "run_info", "sample_rate",
    "scan_cases", "scan_runs", "simpack_available", "simpack_reference", "spectrum",
    "third_octave_centres", "velch_reference",
]
