import csv, json
from pathlib import Path
import numpy as np
base = Path(r"validation\crh380a_m")
sp = json.loads(Path(r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\validation\CRH380A_M_2026-10-19\result_summary.json").read_text(encoding="utf-8"))
cr = sp["front_wheelset_x_crossings_of_duplicate_stations"]
with (base/"out_B_1p2s"/"history.csv").open(encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
t = np.array([float(r["time_s"]) for r in rows])
xr = np.array([float(r["axle1_right_normal_n"]) for r in rows])
xl = np.array([float(r["axle1_left_normal_n"]) for r in rows])
print(f"{'station_m':>9} {'SimpL':>10} {'SimpR':>10} {'VelchL':>8} {'VelchR':>9}  note")
for c in cr:
    s = c["station_model_length_unit"]
    tt = c["time_interpolated_s"]
    win = np.abs(t - tt) <= 0.0015
    sl = c["contact_z_at_bracketing_samples"]["front_left_contact_z"]
    sr = c["contact_z_at_bracketing_samples"]["front_right_contact_z"]
    print(f"{s:9.3f} {sl[0]:10.0f} {sr[0]:10.0f} {xl[win].mean():8.0f} {xr[win].max():9.0f}  "
          f"SimpR after {sr[1]:.0f} | Velch t={tt:.4f}")
