import re, pathlib
p = pathlib.Path("src/velch/vehicle_solver.py")
s = p.read_text(encoding="utf-8")
if "CONTACT_RESEARCH_INTERVAL" in s and "CONTACT_RESEARCH_INTERVAL: int = " not in s:
    s = s.replace(
        "        self._contact_seed: dict[int, float] = {}",
        "        self._contact_seed: dict[int, float] = {}\n"
        "        # Evaluation age per rail patch, used to schedule the exhaustive re-check.\n"
        "        self._contact_age: dict[int, int] = {}\n"
        "        self.CONTACT_RESEARCH_INTERVAL: int = 40", 1)
    p.write_text(s, encoding="utf-8")
    print("patched counter init")
else:
    print("already present")
