"""Round 316 patch: the audit and the gate page learn about window coverage.

Round 315 established that "the load is quiet" and "the window was driven" are two different
conditions.  Gate 9 now requires both.  The two readers that predate it -- the stationarity audit and
the gate page -- still only know the first, so they would still call a quiet 0.44 m of a 9 m window
quotable.  This patch adds the second condition to both, without touching the pre-registered force
test.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def patch(relative: str, pairs: list[tuple[str, str]]) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        count = text.count(old)
        assert count == 1, f"{relative}: anchor found {count} times: {old[:70]!r}"
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"patched {relative}")


COVERAGE_HELPER = '''def window_coverage(meta: dict) -> dict:
    """Did this run drive the window it claims?

    Recomputes from the archive's own record when the writer did not store coverage, so the audit can
    judge runs written before round 315: ``span`` is bounded by both the window length and how far the
    run travelled, ``spacing`` from the sample count, and one spacing of shortfall is allowed because
    no grid puts a sample exactly on both ends.
    """
    window = meta.get("stationarity_window_m")
    if window is None:
        return {"window_m": None, "covered": None, "span_m": None, "expected_span_m": None,
                "spacing_m": None, "samples": None}
    if meta.get("stationarity_covered") is not None:
        return {"window_m": [float(window[0]), float(window[1])],
                "covered": bool(meta["stationarity_covered"]),
                "span_m": meta.get("stationarity_span_m"),
                "expected_span_m": meta.get("stationarity_expected_span_m"),
                "spacing_m": meta.get("stationarity_spacing_m"),
                "samples": meta.get("stationarity_samples")}
    low, high = float(window[0]), float(window[1])
    duration = float(meta.get("duration_s") or 0.0)
    speed = float(meta.get("speed_kmh", float("nan"))) / 3.6
    samples = int(meta.get("stationarity_samples") or 0)
    span = min(high - low, duration * speed)
    spacing = None if samples < 2 else span / (samples - 1)
    expected = None if spacing is None else (high - low) - spacing
    covered = None if expected is None else bool(span >= expected - 1.0e-9)
    return {"window_m": [low, high], "covered": covered, "span_m": span,
            "expected_span_m": expected, "spacing_m": spacing, "samples": samples}


def is_stationary(max_std_kn: float) -> bool:
'''

STATIONARY_RUN = (
    "def _stationary_run(run_id: str | None) -> bool | None:\n"
    "    # Not just \"is the load quiet\": since round 315 an archive can be quiet over 4.4 % of the\n"
    "    # window it claims, so this returns the audit's ``quotable`` (quiet *and* driven) and falls\n"
    "    # back to ``stationary`` only for reports written before coverage existed.\n"
    "    if not run_id or not AUDIT.is_file():\n"
    "        return None\n"
    "    report = json.loads(AUDIT.read_text(encoding=\"utf-8\"))\n"
    "    for row in report.get(\"rows\", []):\n"
    "        if row[\"run_id\"] == run_id:\n"
    "            if \"quotable\" in row:\n"
    "                return bool(row[\"quotable\"])\n"
    "            return bool(row[\"stationary\"])\n"
    "    return None"
)

patch("scripts/s164_stationarity_audit.py", [
    (
        "def is_stationary(max_std_kn: float) -> bool:\n",
        COVERAGE_HELPER,
    ),
    (
        "    decay = None if modal_start <= 0.0 else modal_end / modal_start\n    return {\n",
        "    decay = None if modal_start <= 0.0 else modal_end / modal_start\n"
        "    coverage = window_coverage(meta)\n"
        "    stationary = is_stationary(peak)\n"
        "    return {\n",
    ),
    (
        '        "gates_all_true": bool(all(meta["gates"].values())) if isinstance(meta.get("gates"), dict) else None,\n'
        '        "stationary": is_stationary(peak),\n'
        "    }\n",
        '        "gates_all_true": bool(all(meta["gates"].values())) if isinstance(meta.get("gates"), dict) else None,\n'
        '        "stationary": stationary,\n'
        '        "window_m": coverage["window_m"],\n'
        '        "window_covered": coverage["covered"],\n'
        '        "window_span_m": coverage["span_m"],\n'
        '        "window_expected_span_m": coverage["expected_span_m"],\n'
        '        "window_spacing_m": coverage["spacing_m"],\n'
        '        "window_samples": coverage["samples"],\n'
        "        # Two conditions, kept separate on purpose: the force test is pre-registered and\n"
        "        # unchanged, and coverage is a different question.  A number is quotable only when both\n"
        "        # hold.\n"
        '        "quotable": bool(stationary and coverage["covered"] is not False),\n'
        "    }\n",
    ),
    (
        '    quarantined = [row["run_id"] for row in rows if not row["stationary"]]\n',
        '    quarantined = [row["run_id"] for row in rows if not row["stationary"]]\n'
        '    uncovered = [row["run_id"] for row in rows if row["window_covered"] is False]\n',
    ),
    (
        '                                   "modal_decay": row["modal_decay"], "stationary": row["stationary"]}\n',
        '                                   "modal_decay": row["modal_decay"],\n'
        '                                   "stationary": row["stationary"],\n'
        '                                   "window_covered": row["window_covered"],\n'
        '                                   "quotable": row["quotable"]}\n',
    ),
    (
        '            "quarantined": quarantined,\n',
        '            "quarantined": quarantined,\n'
        '            "window_declared": [row["run_id"] for row in rows if row["window_m"] is not None],\n'
        '            "uncovered_window": uncovered,\n'
        '            "not_quotable": [row["run_id"] for row in rows if not row["quotable"]],\n',
    ),
    (
        "    print(f\"{'run':>52} {'dur s':>7} {'maxStd kN':>10} {'worst rail':>14} {'modal decay':>12} {'ok':>4}\")\n",
        "    print(f\"{'run':>52} {'dur s':>7} {'maxStd kN':>10} {'window':>7} {'modal decay':>12} {'ok':>4}\")\n",
    ),
    (
        '        decay = "n/a" if row["modal_decay"] is None else f"{row[\'modal_decay\']:.3f}"\n'
        '        print(f"{row[\'run_id\'][:52]:>52} {row[\'duration_s\']:7.3f} {row[\'max_rail_std_kn\']:10.2f} "\n'
        '              f"{row[\'worst_rail\']:>14} {decay:>12} {\'yes\' if row[\'stationary\'] else \'NO\':>4}")\n',
        '        decay = "n/a" if row["modal_decay"] is None else f"{row[\'modal_decay\']:.3f}"\n'
        '        window = "-" if row["window_covered"] is None else ("yes" if row["window_covered"] else "NO")\n'
        '        print(f"{row[\'run_id\'][:52]:>52} {row[\'duration_s\']:7.3f} {row[\'max_rail_std_kn\']:10.2f} "\n'
        '              f"{window:>7} {decay:>12} {\'yes\' if row[\'quotable\'] else \'NO\':>4}")\n',
    ),
    (
        "    print(f\"gates true but not stationary: {v['all_gates_true_but_not_stationary']}\")\n",
        "    print(f\"gates true but not stationary: {v['all_gates_true_but_not_stationary']}\")\n"
        "    print(f\"declared a window: {len(v['window_declared'])}   never reached it: {v['uncovered_window']}\")\n"
        "    print(f\"not quotable: {len(v['not_quotable'])}\")\n",
    ),
])

patch("scripts/s156_gate_page.py", [
    (
        "def _stationary_run(run_id: str | None) -> bool | None:\n"
        "    if not run_id or not AUDIT.is_file():\n"
        "        return None\n"
        "    report = json.loads(AUDIT.read_text(encoding=\"utf-8\"))\n"
        "    for row in report.get(\"rows\", []):\n"
        "        if row[\"run_id\"] == run_id:\n"
        "            return bool(row[\"stationary\"])\n"
        "    return None\n",
        STATIONARY_RUN + "\n",
    ),
    (
        '        "not_stationary": [key for key, row in table.items() if row.get("stationary") is False],\n',
        '        "not_stationary": [key for key, row in table.items() if row.get("stationary") is False],\n'
        '        "not_quotable": [key for key, row in table.items()\n'
        '                         if row.get("stationary") is False or row.get("stationary_bump") is False],\n',
    ),
])

print("all patches applied")
