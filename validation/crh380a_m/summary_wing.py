import json
import pathlib

names = [
    "out_patch_frog_base",
    "out_patch_frog_2mm",
    "out_patch_frog_4mm",
    "out_wing_frog_0p05s",
]
here = pathlib.Path(__file__).resolve().parent
print(f"{'case':26s} {'peakR':>9s} {'peakL':>8s} {'maxpen':>8s} {'actR':>5s} {'actL':>5s} {'E':>8s} {'status':>20s}")
for n in names:
    m = here / n / "manifest.json"
    if not m.exists():
        print(f"{n:26s} MISSING")
        continue
    s = json.loads(m.read_text(encoding="utf-8"))["summary"]
    print(
        f"{n:26s} "
        f"{s['peak_normal_force_n']['axle1_right']:9.0f} "
        f"{s['peak_normal_force_n']['axle1_left']:8.0f} "
        f"{s['max_penetration_m']*1000:8.4f} "
        f"{s['active_output_samples']['axle1_right']:5d} "
        f"{s['active_output_samples']['axle1_left']:5d} "
        f"{s['energy_change_j']:8.0f} "
        f"{s['result_status']:>20s}"
    )
