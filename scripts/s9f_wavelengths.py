import json, sys, pathlib
import numpy as np
sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")
sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\scripts")
import s9f_shortwave as s9f
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle
from velch.io.history import read_history

out = {}
for wavelength in (0.025, 0.100):
    s9f.WORK = pathlib.Path(rf"F:\velch_tmp\s9f\w{int(wavelength*1000)}")
    s9f.WORK.mkdir(parents=True, exist_ok=True)
    s9f.WAVELENGTH_M = wavelength
    tre = s9f.build_corrugation()
    case_path = s9f.build_case(tre, False)
    loaded = load_vehicle_case(case_path)
    result = simulate_vehicle(loaded)
    directory = s9f.WORK / "out_rigid"
    directory.mkdir(parents=True, exist_ok=True)
    save_vehicle_result(loaded, result, directory)
    h = read_history(directory / "history.csv")
    t = np.asarray(h.data[h.ordering.index("time_s")], float)
    rate = 1.0 / float(np.mean(np.diff(t)))
    v = np.asarray(h.data[h.ordering.index("axle1_box_left_z_acc_m_per_s2")], float)
    w = np.hanning(len(v))
    amp = np.abs(np.fft.rfft((v - v.mean()) * w)) * (2.0 / w.sum())
    f = np.fft.rfftfreq(len(v), d=1.0 / rate)
    target = s9f.SPEED_M_S / wavelength
    keep = (f > 0.9 * target) & (f < 1.1 * target)
    index = int(np.argmax(np.where(keep, amp, 0.0)))
    entry = {"wavelength_m": wavelength, "target_hz": target, "peak_hz": float(f[index]),
             "peak_m_s2": float(amp[index]), "gain": float(amp[index] / s9f.DEPTH_M),
             "coordinates": int(result.positions.shape[1]),
             "status": result.summary.get("result_status")}
    out[f"{wavelength:.3f}"] = entry
    print(json.dumps(entry, indent=2))
( pathlib.Path(r"F:\velch_tmp\s9f\wavelengths.json") ).write_text(json.dumps(out, indent=2), encoding="utf-8")
