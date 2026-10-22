import json
import pathlib

names = [
    "out_patch_frog_base",
    "out_patch_frog_2mm",
    "out_patch_frog_4mm",
    "out_patch_switch_base",
    "out_patch_switch_2mm",
]
here = pathlib.Path(__file__).resolve().parent
print(f"{'case':26s} {'peakR':>10s} {'maxpen':>9s} {'actR':>5s} {'status':>20s}")
for n in names:
    m = here / n / "manifest.json"
    if not m.exists():
        print(f"{n:26s} {'MISSING':>10s}")
        continue
    s = json.loads(m.read_text(encoding="utf-8"))["summary"]
    print(
        f"{n:26s} {s['peak_normal_force_n']['axle1_right']:10.0f} "
        f"{s['max_penetration_m']*1000:9.4f} {s['active_output_samples']['axle1_right']:5d} "
        f"{s['result_status']:>20s}"
    )
