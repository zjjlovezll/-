"""Swap a window case onto a modal rail track and pad the state with the modal coordinates.

Stage 2 of the goal needs the rail modal count raised from 60 to >=300 so the contact-force spectrum
can be inspected above 400 Hz.  The loader already accepts ``track_dynamics = {"kind": "modal",
"modal_file": ...}`` and sizes the state as ``35 + mode_count`` (``vehicle.py``), so this script only
has to:

1. point ``track_dynamics`` at the modal exchange file,
2. keep the existing 35 vehicle coordinates and append ``mode_count`` zeros (and the same for v),
3. drop any ``equilibrate_vertical`` flag that assumed the previous track kind.

Every other block (contact law, rails, path, run settings) is copied untouched so the only variable
between the two runs is the modal basis.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE_DOF = 35


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--modal-file", default="track_modes_turnout_320.json")
    args = parser.parse_args()
    base = Path(__file__).resolve().parent

    raw = json.loads((base / args.source).read_text(encoding="utf-8"))
    modal = json.loads((base / args.modal_file).read_text(encoding="utf-8"))
    modes = modal["modes"]
    count = len(modes)

    raw["track_dynamics"] = {"kind": "modal", "modal_file": args.modal_file}
    state = raw.setdefault("initial_state", {})
    q = list(state.get("q") or [0.0] * BASE_DOF)
    v = list(state.get("v") or [0.0] * BASE_DOF)
    if len(q) < BASE_DOF or len(v) < BASE_DOF:
        raise SystemExit(f"source state is shorter than {BASE_DOF} coordinates")
    raw["initial_state"] = {"q": q[:BASE_DOF] + [0.0] * count,
                            "v": v[:BASE_DOF] + [0.0] * count}
    raw["case_id"] = f"{raw['case_id']}_modal{count}"
    raw["purpose_detail"] = (raw.get("purpose_detail", "") +
                             f" | modal rail track: {args.modal_file} ({count} modes, "
                             f"{modes[0]['frequency_hz']:.2f}-{modes[-1]['frequency_hz']:.2f} Hz)")
    (base / args.output).write_text(json.dumps(raw, indent=1), encoding="utf-8")
    print(f"wrote {args.output}: kind=modal, {count} modes "
          f"({modes[0]['frequency_hz']:.2f}-{modes[-1]['frequency_hz']:.2f} Hz), "
          f"state {BASE_DOF}+{count} = {BASE_DOF + count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
