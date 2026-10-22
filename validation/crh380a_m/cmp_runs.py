"""Tabulate manifest summaries for every run directory under this folder."""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent

FIELDS = [
    ("result_status", 22, "s"),
    ("peak_normal_force_n", 11, ".0f"),
    ("max_penetration_m", 12, ".5f"),
    ("initial_mechanical_energy_j", 13, ".1f"),
    ("final_mechanical_energy_j", 13, ".1f"),
    ("energy_change_j", 13, ".1f"),
    ("active_output_samples", 7, "d"),
    ("edge_limited_active_output_samples", 9, "d"),
]


def main() -> None:
    rows = []
    for directory in sorted(BASE.glob("out_*")):
        manifest = directory / "manifest.json"
        if not manifest.exists():
            continue
        summary = json.loads(manifest.read_text(encoding="utf-8"))["summary"]
        rows.append((directory.name, summary))
    head = f"{'dir':30s}" + "".join(f"{name[:10]:>{w}s}" for name, w, _ in FIELDS)
    print(head)
    for name, summary in rows:
        line = f"{name:30s}"
        for field, width, fmt in FIELDS:
            value = summary.get(field)
            if value is None:
                line += f"{'-':>{width}s}"
            elif isinstance(value, (dict, list)):
                line += f"{json.dumps(value, ensure_ascii=False)[:width]:>{width}s}"
            elif fmt == "s":
                line += f"{str(value)[:width]:>{width}s}"
            elif fmt == ".5f":
                line += f"{float(value) * 1e3:>{width}.4f}"
            else:
                line += f"{value:>{width}{fmt}}"
        print(line)


if __name__ == "__main__":
    main()
