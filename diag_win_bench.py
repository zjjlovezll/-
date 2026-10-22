import json, pathlib, subprocess, sys, time, csv, math

src = json.load(open(r"validation/crh380a_m/case_bench_0.json", encoding="utf-8"))
out = pathlib.Path("validation/crh380a_m")
specs = []
for xs in (60.0, 80.0):
    specs.append((f"global_x{xs:g}", xs, None))
    for half in (0.002, 0.005):
        specs.append((f"w{int(half*1000)}_x{xs:g}", xs, half))

rows = []
for tag, xs, half in specs:
    c = json.loads(json.dumps(src))
    c["case_id"] = f"crh380a_m_win_{tag}"
    c["run"]["x_start_m"] = xs
    if half is not None:
        c["run"]["contact_search_half_width_m"] = half
    p = out / f"case_win_{tag}.json"
    p.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    odir = out / f"out_win_{tag}"
    t0 = time.perf_counter()
    r = subprocess.run([sys.executable, "-m", "velch", "run-vehicle", str(p), "--output", str(odir)],
                       capture_output=True, text=True)
    wall = time.perf_counter() - t0
    if r.returncode != 0:
        print(tag, "FAILED", r.stderr[-400:]); continue
    m = json.load(open(odir / "manifest.json", encoding="utf-8"))
    s = m["summary"]
    rows.append((tag, wall, s.get("result_status"), s.get("max_penetration_m")))
    print("%-14s wall %6.2f s  status %-20s maxpen %.6f mm" % (tag, wall, s.get("result_status"), s.get("max_penetration_m",0)*1e3))

# compare forces column-wise
import numpy as np
def load(tag):
    with open(out / f"out_win_{tag}" / "history.csv", newline="", encoding="utf-8") as f:
        rd = csv.reader(f); hdr = next(rd)
        data = np.array([[float(v) for v in row] for row in rd])
    return hdr, data
for xs in (60.0, 80.0):
    hg, dg = load(f"global_x{xs:g}")
    for half in (0.002, 0.005):
        tag = f"w{int(half*1000)}_x{xs:g}"
        hh, dh = load(tag)
        ncol = [i for i,c in enumerate(hg) if c.endswith("_normal_n")]
        fr = np.abs(dh[:, ncol] - dg[:, ncol])
        print("x=%-5g %-6s vs global: max|dF| %8.2f N   mean|dF| %7.2f N   peakF glob %9.1f  win %9.1f  rows %d/%d"
              % (xs, tag, fr.max(), fr.mean(), dg[:, ncol].max(), dh[:, ncol].max(), dh.shape[0], dg.shape[0]))
