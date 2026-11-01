import pathlib

p = pathlib.Path("scripts/s99_run_archive.py")
src = p.read_text(encoding="utf-8")
original = src


def sub(old: str, new: str, count: int = 1) -> None:
    global src
    found = src.count(old)
    assert found == count, f"expected {count}, found {found}: {old[:60]!r}"
    src = src.replace(old, new, count)


sub(
    "        \"gates\": {str(k): bool(v) for k, v in gates.items()},\n"
    "        \"wall_s\": wall_s,\n"
    "        \"notes\": notes,\n"
    "    }\n",
    "        \"gates\": {str(k): bool(v) for k, v in gates.items()},\n"
    "        # Until round 314 the launch block lived only in the index row, so a reader who opened\n"
    "        # meta.json -- the file that describes a run -- could not see the state that run started\n"
    "        # from, and the two gates that read it.  Both travel with the run now.\n"
    "        \"result_status\": summary.get(\"result_status\"),\n"
    "        \"failed_gates\": list(summary.get(\"failed_gates\") or ()),\n"
    "        \"max_rail_force_std_kn\": summary.get(\"max_rail_force_std_kn\"),\n"
    "        \"stationary_force_std_limit_kn\": summary.get(\"stationary_force_std_limit_kn\"),\n"
    "        \"launch\": None if launch is None else {\n"
    "            \"modal_norm_m\": float(launch[\"modal_norm_m\"]),\n"
    "            \"modal_residual_n\": float(launch[\"modal_residual_n\"]),\n"
    "            \"modal_residual_share\": launch.get(\"modal_residual_share\"),\n"
    "            \"vertical_preload_residual_n\": launch[\"vertical_preload_residual_n\"],\n"
    "            \"spin_relative_max\": float(launch[\"spin_relative_max\"]),\n"
    "            \"balanced\": bool(launch[\"balanced\"]),\n"
    "        },\n"
    "        \"wall_s\": wall_s,\n"
    "        \"notes\": notes,\n"
    "    }\n",
)

anchor = "    gates = (getattr(result, \"summary\", {}) or {}).get(\"gates\") or {}\n"
assert src.count(anchor) >= 1
first = src.index(anchor)
src = (src[:first]
       + "    summary = getattr(result, \"summary\", {}) or {}\n"
       + anchor.replace("(getattr(result, \"summary\", {}) or {})", "summary")
       + src[first + len(anchor):])

import ast

ast.parse(src)
p.write_text(src, encoding="utf-8")
print("patched", len(src) - len(original), "chars")
for needle in ("\"result_status\": summary.get", "\"launch\": None if launch is None",
               "summary = getattr(result"):
    print(("OK  " if needle in src else "MISS"), needle)
