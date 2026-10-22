import json, os, sys, time
sys.path.insert(0,"src")
from pathlib import Path
from velch.parallel import run_vehicle_batch

if __name__ == "__main__":
    src = Path(r"validation\crh380a_m\case_bench_0.json")
    raw = json.loads(src.read_text(encoding="utf-8"))
    raw["run"]["duration_s"] = 0.02
    paths = []
    for i in range(4):
        p = Path(r"validation\crh380a_m") / f"case_par{i}.json"
        raw["case_id"] = f"par{i}"
        p.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
        paths.append(p)
    print("logical cpu count:", os.cpu_count())
    for jobs in (1, 4):
        t0 = time.perf_counter()
        rep = run_vehicle_batch(paths, Path(r"validation\crh380a_m") / f"out_par_j{jobs}",
                                jobs=jobs, workers=1)
        wall = time.perf_counter() - t0
        print("jobs=%d  wall=%.2f s  summed=%.2f s  reported_speedup=%.2fx" % (
            jobs, wall, rep["summed_case_wall_s"], rep["effective_speedup"]))
        for c in rep["cases"]:
            print("   ", Path(c["case"]).name, c["result_status"], c.get("nfev"), "%.2f s" % c["wall_s"])
