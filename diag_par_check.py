import hashlib, json, sys, time
sys.path.insert(0,"src")
from pathlib import Path
from velch.parallel import run_vehicle_batch

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]

if __name__ == "__main__":
    root = Path(r"validation\crh380a_m")
    a = root/"out_par_j1"/"case_par0"/"history.csv"
    b = root/"out_par_j4"/"case_par0"/"history.csv"
    print("serial   sha:", sha(a))
    print("parallel sha:", sha(b))
    print("identical  :", sha(a) == sha(b))
    # 8-case scaling
    src = root/"case_bench_0.json"
    raw = json.loads(src.read_text(encoding="utf-8"))
    raw["run"]["duration_s"] = 0.02
    paths = []
    for i in range(8):
        p = root/f"case_s{i}.json"
        raw["case_id"] = f"s{i}"
        p.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
        paths.append(p)
    for jobs in (1, 8):
        t0 = time.perf_counter()
        rep = run_vehicle_batch(paths, root/f"out_s_j{jobs}", jobs=jobs, workers=1)
        wall = time.perf_counter() - t0
        ok = all(c["result_status"] == "numerically_checked" for c in rep["cases"])
        print("8 cases jobs=%-2d wall=%.2f s  summed=%.2f s  speedup=%.2fx  all_ok=%s" % (
            jobs, wall, rep["summed_case_wall_s"], rep["effective_speedup"], ok))
