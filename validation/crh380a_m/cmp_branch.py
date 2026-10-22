import csv, json
from pathlib import Path
base = Path(r"validation\crh380a_m")
def rows(name):
    with (base/name/"history.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))
for name in ("out_B_1p2s", "out_B_1p2s_inverted"):
    r = rows(name)
    man = json.loads((base/name/"manifest.json").read_text(encoding="utf-8"))["summary"]
    print(f"--- {name} ---")
    for s in ("axle1_left","axle1_right"):
        v=[float(x[s+"_normal_n"]) for x in r]
        act=sum(1 for x in r if float(x[s+"_active"])>0.5)
        print(f"  {s}: min {min(v):.1f} max {max(v):.1f} mean {sum(v)/len(v):.1f} active {act}/{len(v)}")
    print(f"  max_penetration {man['max_penetration_m']*1e3:.4f} mm  nfev {man['solver']['nfev']}  status {man['result_status']}")
    print(f"  peaks right: {[round(v) for k,v in man['peak_normal_force_n'].items() if k.endswith('_right')]}")
    print(f"  energy change {man['energy_change_j']:.0f} J")
    c="axle1_right_normal_n"
    idx=sorted(range(len(r)), key=lambda i:-float(r[i][c]))[:4]
    print("  worst:", [(round(float(r[i]['time_s']),3), round(float(r[i]['axle1_x_m']),2), round(float(r[i][c])), round(float(r[i]['axle1_left_normal_n']))) for i in idx])
