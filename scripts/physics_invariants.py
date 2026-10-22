"""Recompute the physics invariants from what is on disk, and refuse to ship if they moved.

Why this exists: "物理数值不变" is a promise in every release note, and until now the only thing
behind it was a sentence.  ``tests/test_oracle_frozen.py`` pins the static gate, but nothing compared
a *release* against the archived 1.2 s run, and nothing re-derived the eight contact peaks at all.

Two independent sources, checked against a committed reference:

1. **archive** -- ``out_full12_cap05/history.csv``, the frozen oracle: eight contact peaks, the
   deepest penetration, detach count, window rms / dominant frequency.  No simulation, pure reading.
2. **fresh** -- one ``--fast`` run of the 0.05 s frog case, which re-derives the static gate with
   the current code (4 s), plus its seven manifest gates.

Usage::

    python -X utf8 scripts/physics_invariants.py            # check against docs/physics_invariants.json
    python -X utf8 scripts/physics_invariants.py --write     # (re)create the reference, on purpose
    python -X utf8 scripts/physics_invariants.py --no-run    # archive only (fast, no subprocess)
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src"
REFERENCE = ROOT / "docs" / "physics_invariants.json"
#: A per-run artifact, so it lives with the other reports and stays out of git.
REPORT = ROOT / "reports" / "PHYSICS_INVARIANTS_LATEST.md"
ARCHIVE_RUN = "out_full12_cap05"
FAST_CASE = "case_frog_N_strip05.json"
WINDOW_M = (78.8, 82.2)

sys.path.insert(0, str(SOURCE))

from velch.data_root import case_dir  # noqa: E402  (after the path is set up)


def _columns(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _window_metrics(values: list[float], times: list[float]) -> dict[str, float]:
    """The station-window numbers exactly as ``bands_from_history.py`` defines them.

    That script is the source of the 9.13 kN / 57.14 Hz quoted in the docs, and it uses a plain
    mean-removed FFT (``2/N`` scaling) with no band-pass.  ``velch.inverse.bands.band_metrics``
    answers a different question -- 5-999 Hz filtered, settling transient trimmed, dominant reported
    as a third-octave centre -- and would put a second number in the reference for one quantity.
    """

    import numpy as np

    time = np.asarray(times, dtype=float)
    force = np.asarray(values, dtype=float) / 1e3
    step = float(np.median(np.diff(time)))
    grid = np.arange(time[0], time[-1], step)
    series = np.interp(grid, time, force)
    centred = series - series.mean()
    spectrum = np.abs(np.fft.rfft(centred)) * (2.0 / centred.size)
    frequencies = np.fft.rfftfreq(centred.size, step)

    def band(low: float, high: float) -> float:
        keep = (frequencies >= low) & (frequencies < high)
        return float(np.sqrt(np.sum(spectrum[keep] ** 2) / 2.0))

    return {
        "rms_kn": round(float(np.sqrt(np.mean(centred ** 2))), 3),
        "dominant_hz": round(float(frequencies[int(np.argmax(spectrum[1:]) + 1)]), 2),
        "band_30_60_kn": round(band(30.0, 60.0), 3),
        "band_150_250_kn": round(band(150.0, 250.0), 3),
        "band_250_400_kn": round(band(250.0, 400.0), 3),
    }


def _bands_unused(values: list[float], times: list[float]) -> dict[str, float]:
    count = len(values)
    mean = sum(values) / count
    sample = (times[-1] - times[0]) / (count - 1)
    window = [0.5 - 0.5 * math.cos(2.0 * math.pi * index / (count - 1)) for index in range(count)]
    centered = [(values[index] - mean) * window[index] for index in range(count)]
    real = [0.0] * count
    imag = [0.0] * count
    for index in range(count):
        angle = -2.0 * math.pi * index / count
        for k in range(count):
            real[index] += centered[k] * math.cos(angle * k)
            imag[index] += centered[k] * math.sin(angle * k)
    amplitudes = [math.hypot(real[k], imag[k]) for k in range(count // 2 + 1)]
    frequencies = [k / (count * sample) for k in range(count // 2 + 1)]
    dominant = frequencies[max(range(len(amplitudes)), key=lambda k: amplitudes[k])]
    power = sum(w * w for w in window) / count

    def band(lo: float, hi: float) -> float:
        total = 0.0
        for k in range(1, len(amplitudes) - 1):
            if lo <= frequencies[k] < hi:
                total += amplitudes[k] ** 2
        return math.sqrt(max(2.0 * total / (count ** 2 * power), 0.0))

    return {
        "rms_kn": round(math.sqrt(sum(v * v for v in centered) / (count * power)) / 1e3, 3),
        "dominant_hz": round(dominant, 2),
        "band_30_60_kn": round(band(30.0, 60.0) / 1e3, 3),
        "band_150_250_kn": round(band(150.0, 250.0) / 1e3, 3),
        "band_250_400_kn": round(band(250.0, 400.0) / 1e3, 3),
    }


def from_archive() -> dict[str, object]:
    run = case_dir() / ARCHIVE_RUN
    history = run / "history.csv"
    if not history.is_file():
        raise SystemExit(f"归档运行缺失：{history}")
    columns, rows = _columns(history)
    peaks: dict[str, float] = {}
    deepest = 0.0
    detached = 0
    for column in columns:
        if column.endswith("_normal_n") and column.startswith("axle"):
            peaks[column] = round(max(float(row[column]) for row in rows), 4)
        if column.endswith("_penetration_m"):
            deepest = max(deepest, max(float(row[column]) for row in rows))
        if column.endswith("_active"):
            detached += sum(1 for row in rows if float(row[column]) <= 0.0)
    times = [float(row["time_s"]) for row in rows]
    stations = [float(row["axle1_x_m"]) for row in rows]
    mask = [WINDOW_M[0] <= s <= WINDOW_M[1] for s in stations]
    lead = [float(row["axle1_right_normal_n"]) for row, keep in zip(rows, mask) if keep]
    lead_times = [time for time, keep in zip(times, mask) if keep]
    # ``result_status`` and ``gates`` live one level down, under ``summary``: reading the top level
    # silently produced a reference with ``None`` for both, which would have made the gate blind to
    # a failing solver.
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8")) if (
        run / "manifest.json").is_file() else {}
    summary = manifest.get("summary") or {}
    return {
        "source": str(history),
        "frames": len(rows),
        "contact_peaks_kn": {name: round(value / 1e3, 3) for name, value in sorted(peaks.items())},
        "max_penetration_um": round(deepest * 1e6, 3),
        "detached_samples": detached,
        # What the archived run itself sat at on its first frame.  The canonical 59 680.5769 N gate
        # belongs to the template case and is pinned by tests/test_oracle_frozen.py; this archive
        # starts at 13.5 m and seats at 59 680.3756 N, so demanding the canonical value here would
        # report drift on a run nobody touched.
        "static_first_frame_n": round(float(rows[0]["axle1_right_normal_n"]), 4),
        "lead_axle_right_peak_kn": round(peaks["axle1_right_normal_n"] / 1e3, 3),
        "overall_peak_kn": round(max(peaks.values()) / 1e3, 3),
        "overall_peak_contact": max(peaks, key=peaks.get),
        "window": list(WINDOW_M),
        "window_metrics": _window_metrics(lead, lead_times),
        "result_status": summary.get("result_status"),
        "gates": summary.get("gates"),
    }


def from_fresh_run(work: Path) -> dict[str, object]:
    cli = [sys.executable, "-X", "utf8", "-m", "velch"]
    case = case_dir() / FAST_CASE
    if not case.is_file():
        return {"skipped": f"语料缺失：{case}"}
    out = work / "invariants"
    command = cli + ["run-vehicle", str(case), "--output", str(out), "--fast"]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", cwd=str(ROOT),
                              env={**__import__("os").environ, "PYTHONPATH": str(SOURCE)})
    manifest = out / "manifest.json"
    if completed.returncode != 0 or not manifest.is_file():
        return {"ok": False, "exit": completed.returncode,
                "tail": (completed.stdout + completed.stderr).strip().splitlines()[-4:]}
    payload = (json.loads(manifest.read_text(encoding="utf-8")).get("summary") or {})
    history = (out / "history.csv")
    columns, rows = _columns(history)
    peaks: dict[str, float] = {}
    for column in columns:
        if column.endswith("_normal_n") and column.startswith("axle"):
            peaks[column] = round(max(float(row[column]) for row in rows) / 1e3, 3)
    static = round(float(rows[0]["axle1_right_normal_n"]) / 1e3, 6)
    return {
        "ok": True,
        "case": str(case),
        "result_status": payload.get("result_status"),
        "gates": payload.get("gates"),
        # The static gate is the seated state at t = 0.  The peak of the window is a different
        # quantity -- this case crosses the frog nose, so its peak is ~170 kN by design.
        "static_force_kn": static,
        "contact_peaks_kn": peaks,
        "max_penetration_um": round(max(max(float(row[c]) for row in rows)
                                        for c in columns if c.endswith("_penetration_m")) * 1e6, 3),
    }


TOLERANCES = {
    "contact_peaks_kn": 1.0,        # kN
    "max_penetration_um": 1.0,      # µm
    "overall_peak_kn": 1.0,
    "lead_axle_right_peak_kn": 1.0,
    "rms_kn": 0.2,
    "dominant_hz": 1.0,
    "band": 0.2,
}


def compare(reference: dict, observed: dict) -> list[str]:
    problems: list[str] = []

    def close(name: str, expected: float, got: float, tolerance: float) -> None:
        if abs(got - expected) > tolerance:
            problems.append(f"{name}: 参考 {expected} → 现在 {got}（容差 {tolerance}）")

    for name, expected in (reference.get("contact_peaks_kn") or {}).items():
        got = (observed.get("contact_peaks_kn") or {}).get(name)
        if got is None:
            problems.append(f"{name}: 现在没有这个接触通道")
        else:
            close(name, float(expected), float(got), TOLERANCES["contact_peaks_kn"])
    close("max_penetration_um", reference.get("max_penetration_um"),
          observed.get("max_penetration_um"), TOLERANCES["max_penetration_um"])
    close("overall_peak_kn", reference.get("overall_peak_kn"),
          observed.get("overall_peak_kn"), TOLERANCES["overall_peak_kn"])
    close("static_first_frame_n", reference.get("static_first_frame_n"),
          observed.get("static_first_frame_n"), 1.0)
    if reference.get("detached_samples") != observed.get("detached_samples"):
        problems.append(f"detached_samples: 参考 {reference.get('detached_samples')} → "
                        f"现在 {observed.get('detached_samples')}")
    for key, tolerance in (("rms_kn", TOLERANCES["rms_kn"]),
                           ("dominant_hz", TOLERANCES["dominant_hz"]),
                           ("band_30_60_kn", TOLERANCES["band"]),
                           ("band_150_250_kn", TOLERANCES["band"]),
                           ("band_250_400_kn", TOLERANCES["band"])):
        close(f"window.{key}", (reference.get("window_metrics") or {}).get(key),
              (observed.get("window_metrics") or {}).get(key), tolerance)
    return problems


def write_report(reference: dict, observed: dict, fresh: dict, problems: list[str]) -> None:
    lines = ["# 物理不变量复算（最近一次）", "",
             "由 `scripts/physics_invariants.py` 生成；参考值在 `docs/physics_invariants.json`。", "",
             "## 归档运行（`out_full12_cap05`，不重跑）", "",
             "| 量 | 参考 | 现在 |", "|---|---|---|"]
    for name, expected in (reference.get("contact_peaks_kn") or {}).items():
        got = (observed.get("contact_peaks_kn") or {}).get(name)
        lines.append(f"| {name} | {expected} kN | {got} kN |")
    for label, key in (("最大侵入", "max_penetration_um"), ("整程峰值", "overall_peak_kn"),
                       ("首帧静载 (N)", "static_first_frame_n")):
        lines.append(f"| {label} | {reference.get(key)} | {observed.get(key)} |")
    lines.append(f"| 脱空样本 | {reference.get('detached_samples')} | "
                 f"{observed.get('detached_samples')} |")
    for key in ("rms_kn", "dominant_hz", "band_30_60_kn", "band_150_250_kn", "band_250_400_kn"):
        lines.append(f"| 辙叉窗 {key} | {(reference.get('window_metrics') or {}).get(key)} | "
                     f"{(observed.get('window_metrics') or {}).get(key)} |")
    lines += ["", "## 现跑一次（`--fast`，0.05 s）", ""]
    if fresh.get("skipped"):
        lines.append(f"- 跳过：{fresh['skipped']}")
    elif not fresh.get("ok"):
        lines.append(f"- 失败：exit {fresh.get('exit')}，{fresh.get('tail')}")
    else:
        lines.append(f"- `result_status = {fresh.get('result_status')}`，七门：{fresh.get('gates')}")
        lines.append(f"- 首帧 axle1_right：{fresh.get('static_force_kn')} kN"
                     "（这个算例过辙叉，首帧不是静载门；59 680.5769 N 由 test_oracle_frozen 钉住）")
        lines.append(f"- 八接触峰值（kN）：{fresh.get('contact_peaks_kn')}")
        lines.append(f"- 最大侵入：{fresh.get('max_penetration_um')} µm")
    lines += ["", "## 结论", ""]
    lines.append("**物理不变量未移动。**" if not problems else f"**发现漂移：** {problems}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="物理不变量复算门")
    parser.add_argument("--write", action="store_true", help="重写参考值（只在有意变更物理时用）")
    parser.add_argument("--no-run", action="store_true", help="只读归档，不跑仿真")
    arguments = parser.parse_args()

    observed = from_archive()
    if arguments.write:
        REFERENCE.write_text(json.dumps(observed, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
        print(f"参考值已写入 {REFERENCE}（{len(observed['contact_peaks_kn'])} 个接触）")
        return 0

    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    problems = compare(reference, observed)
    fresh: dict[str, object] = {"skipped": "--no-run"}
    if not arguments.no_run:
        fresh = from_fresh_run(Path(tempfile.mkdtemp(prefix="velch_invariants_")))
        if fresh.get("ok"):
            if fresh.get("result_status") != "numerically_checked":
                problems.append(f"现跑 result_status = {fresh.get('result_status')}")
            gates = fresh.get("gates") or {}
            failing = [name for name, passed in gates.items() if not passed]
            if failing:
                problems.append(f"现跑未过的门：{failing}")
            finite = (fresh.get("contact_peaks_kn") or {})
            if len(finite) != 8:
                problems.append(f"现跑只报告了 {len(finite)} 个接触（应为 8）")
        elif not fresh.get("skipped"):
            problems.append(f"现跑失败：exit {fresh.get('exit')}")

    write_report(reference, observed, fresh, problems)
    print(f"归档：{len(observed['contact_peaks_kn'])} 个接触，"
          f"整程峰值 {observed['overall_peak_kn']} kN（{observed['overall_peak_contact']}）")
    if fresh.get("ok"):
        passed = sum(1 for v in (fresh.get("gates") or {}).values() if v)
        print(f"现跑：{fresh.get('result_status')}，七门 {passed}/7，"
              f"首帧 axle1_right {fresh.get('static_force_kn')} kN")
    if problems:
        print("VERDICT: DRIFT")
        for problem in problems:
            print("  -", problem)
        return 2
    print("VERDICT: UNCHANGED")
    print(f"报告：{REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
