"""How does the contact move when the wheel moves, now that the stiffness is fitted?（B048 之后）

`case_A_plain` 的 20 mm 等效半径退役后，1 mm 横移卸载 45 %。这一轮要回答的是：那个 45 %
是“踏面本来就这么快离开”，还是“接触点没跟着车轮走”。

对每个横移量：把四个轮对的 `y` 移过去，重新座椅（垂向行），求值，读
- `N`：法向力
- `contact_in_wheel_mm`：接触点相对**车轮本地坐标**的位置（`lever_y − wheel.lateral_offset`）
  负值 = 偏向轮缘侧；0 = 正好在滚动圆（LMA 断面 `y=0`，`z = −0.429997`）
- `crown_offset_mm`：接触点相对**轨冠**的位置
判据：若 `contact_in_wheel` 随横移同向同量变化，说明接触跟着车走，那么“卸载快”是踏面几何
本身的性质（可接受）；若它几乎不动（20 mm 时代是 36 mm 只动 6 mm），说明接触被钉住，注册
才是问题。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch.data_root import case_dir
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import VehicleDynamics, _seat

EVEN_SHARE_N = 59_662.0
SPEED_M_S = 22.2222


def load(shifts_mm: list[float]) -> None:
    base = load_vehicle_case(case_dir() / "case_A_plain.json")
    rows = []
    for shift_mm in shifts_mm:
        case = base
        dynamics = VehicleDynamics(case)
        velocity = np.zeros(dynamics.dimension)
        for body in dynamics.topology.bodies:
            try:
                velocity[dynamics.topology.require(body.id, "spin")] = SPEED_M_S / 0.43
            except Exception:
                continue
        state = np.zeros(dynamics.dimension)
        for body in dynamics.topology.bodies:
            if body.id.startswith("wheelset"):
                state[dynamics.topology.require(body.id, "y")] = shift_mm * 1e-3
        try:
            seated, residual = _seat(case, dynamics, state, velocity)
        except Exception as exc:  # a shift this large leaves the car standing on one side
            rows.append({"shift_mm": shift_mm, "N": None, "refused": str(exc).split(":")[0]})
            print(f"shift {shift_mm:+6.2f} mm  REFUSED  {str(exc).splitlines()[0][:96]}")
            continue
        seated = np.array(seated, dtype=float)
        for body in dynamics.topology.bodies:
            if body.id.startswith("wheelset"):
                seated[dynamics.topology.require(body.id, "y")] = shift_mm * 1e-3
        dynamics.evaluate(0.0, seated, velocity)
        contacts = dynamics.body_contacts["axle1_left"]
        entry = next((c for c in contacts if c.geometry is not None), None)
        wheel = dynamics.wheels["L"]
        if entry is None:
            rows.append({"shift_mm": shift_mm, "N": 0.0, "contact_in_wheel_mm": float("nan"),
                         "crown_offset_mm": float("nan")})
            continue
        lever_y = float(entry.geometry.lever_y_m)
        rows.append({
            "shift_mm": shift_mm,
            "N": float(entry.normal_force_n),
            "contact_in_wheel_mm": (lever_y - wheel.lateral_offset_m) * 1e3,
            "crown_offset_mm": float("nan"),
            "residual": float(residual),
            "pen_um": float(entry.geometry.penetration_m) * 1e6,
        })
        print(f"shift {shift_mm:+6.2f} mm  N {rows[-1]['N']/1e3:8.3f} kN "
              f"({rows[-1]['N']/EVEN_SHARE_N:5.3f}x)  pen {rows[-1]['pen_um']:7.2f} um  "
              f"contact in wheel {rows[-1]['contact_in_wheel_mm']:+7.3f} mm")
    finite = [r for r in rows if r.get("N")]
    if len(finite) >= 2:
        dy = (finite[-1]["shift_mm"] - finite[0]["shift_mm"]) * 1e-3
        dN = finite[-1]["N"] - finite[0]["N"]
        follow = (finite[-1]["contact_in_wheel_mm"] - finite[0]["contact_in_wheel_mm"])
        print("\nN range {:.3f} .. {:.3f} kN over {:+.2f} mm".format(
            finite[0]["N"]/1e3, finite[-1]["N"]/1e3,
            finite[-1]["shift_mm"] - finite[0]["shift_mm"]))
        print("d N / d y = {:.1f} kN/mm   (20 mm era: 211.6, theory at 65.5 um: ~453)".format(
            abs(dN / dy) / 1e3))
        print("contact follows the wheel by {:.2f} mm per mm of shift "
              "(0 = pinned, 1 = follows exactly)".format(follow / (finite[-1]["shift_mm"] - finite[0]["shift_mm"])))
    out = Path(__file__).resolve().parents[2] / "scratch" / "s96"
    out.mkdir(parents=True, exist_ok=True)
    (out / "registration.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("\nwrote", out / "registration.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--shifts", type=float, nargs="+",
                        default=[-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0])
    args = parser.parse_args()
    load(args.shifts)
