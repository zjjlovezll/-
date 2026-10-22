# -*- coding: utf-8 -*-
"""A2: is the contact stiffness C separable from a geometric offset epsilon?

Force obeys N ~ C * delta^1.5, and a geometry offset shifts delta by epsilon.
A static force alone therefore cannot tell (C high, eps small) from (C low, eps
large).  This probe builds three runs and compares their *dynamics*, i.e. whether
a spectral observable breaks the degeneracy.

  base   : C from effective_radius_m = 0.02, eps = 0
  eps    : same C, rail shifted down by 0.1 mm  (static force rises ~4x)
  epsC   : rail shifted down 0.1 mm, C scaled so the static force matches base
"""
import json
import math
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
BASE = HERE / "case_frog_N_strip05.json"
ROOT = HERE.parents[1]  # Velch/

R0 = 0.02
EPS = -1.0e-4  # rail down 0.1 mm


def build(name: str, radius: float, eps: float) -> pathlib.Path:
    data = json.loads(BASE.read_text(encoding="utf-8"))
    data["case_id"] = name
    data["contact"]["stiffness_policy"] = "fixed_effective_radius"
    data["contact"]["effective_radius_m"] = radius
    for wheel in data["wheels"]:
        spec = wheel.get("profile")
        if isinstance(spec, dict):
            spec["z_offset_m"] = float(spec.get("z_offset_m", 0.0)) + eps
    path = HERE / f"case_{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run(case: pathlib.Path, out: pathlib.Path) -> dict:
    if out.exists():
        for child in sorted(out.rglob("*"), reverse=True):
            child.unlink() if child.is_file() else child.rmdir()
        out.rmdir()
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(case), "--output", str(out)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise SystemExit(f"run failed for {case.name}: {proc.stderr[-800:]}")
    return json.loads((out / "manifest.json").read_text(encoding="utf-8"))["summary"]


def series(out: pathlib.Path, column: str):
    import numpy as np
    rows = (out / "history.csv").read_text(encoding="utf-8").splitlines()
    header = rows[0].split(",")
    index = header.index(column)
    values = [float(row.split(",")[index]) for row in rows[1:] if row.strip()]
    return np.asarray(values, dtype=float)


def describe(summary: dict, out: pathlib.Path) -> dict:
    import numpy as np
    force = series(out, "axle2_right_normal_n")
    time = series(out, "time_s")
    step = float(time[1] - time[0])
    centred = force - force.mean()
    spectrum = np.abs(np.fft.rfft(centred))
    freq = np.fft.rfftfreq(force.size, step)
    return {
        "static_n": float(force[0]),
        "peak_n": float(force.max()),
        "mean_n": float(force.mean()),
        "rms_n": float(centred.std()),
        "dominant_hz": float(freq[int(np.argmax(spectrum[1:])) + 1]),
        "pen_um": summary["max_penetration_m"] * 1e6,
        "nfev": summary["solver"]["nfev"],
    }


def main() -> int:
    import numpy as np

    plans = [("a2_base", R0, 0.0), ("a2_eps", R0, EPS)]
    results = {}
    for name, radius, eps in plans:
        case = build(name, radius, eps)
        out = HERE / f"out_{name}"
        results[name] = describe(run(case, out), out)
        print(f"{name:9s} static={results[name]['static_n']/1e3:8.3f} kN")

    # scale C so the static force matches the base run: N ~ C*delta^1.5, C ~ r^-0.5
    ratio = results["a2_eps"]["static_n"] / results["a2_base"]["static_n"]
    radius = R0 * ratio ** 2.0
    print(f"static ratio {ratio:.3f} -> effective_radius_m {radius:.4f} m")
    case = build("a2_epsC", radius, EPS)
    out = HERE / "out_a2_epsC"
    results["a2_epsC"] = describe(run(case, out), out)

    print()
    print(f"{'variant':10s} {'static kN':>10s} {'mean kN':>10s} {'peak kN':>10s} "
          f"{'rms kN':>8s} {'dominant Hz':>12s} {'pen um':>8s} {'nfev':>7s}")
    for name in ("a2_base", "a2_eps", "a2_epsC"):
        r = results[name]
        print(f"{name:10s} {r['static_n']/1e3:10.3f} {r['mean_n']/1e3:10.3f} "
              f"{r['peak_n']/1e3:10.3f} {r['rms_n']/1e3:8.3f} {r['dominant_hz']:12.2f} "
              f"{r['pen_um']:8.3f} {r['nfev']:7d}")

    base, eps_c = results["a2_base"], results["a2_epsC"]
    print()
    print(f"static match: {abs(eps_c['static_n']-base['static_n'])/base['static_n']*100:.3f} %")
    print(f"peak   change: {(eps_c['peak_n']-base['peak_n'])/base['peak_n']*100:+.3f} %")
    print(f"rms    change: {(eps_c['rms_n']-base['rms_n'])/base['rms_n']*100:+.3f} %")
    print(f"dominant: {base['dominant_hz']:.2f} -> {eps_c['dominant_hz']:.2f} Hz")
    print(f"pen    : {base['pen_um']:.3f} -> {eps_c['pen_um']:.3f} um")

    payload = {"variants": results, "radius_for_match_m": radius, "epsilon_m": EPS}
    (HERE / "a2_degeneracy.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
