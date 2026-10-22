"""Probe the parameter registry against a real case: coverage, editable count, one patch."""

from __future__ import annotations

import json
from pathlib import Path

from velch.ui.parameters import REGISTRY, apply_patch, coverage, editable, registry_by_path

CASE = Path("validation/crh380a_m/case_full12_cap05.json")


def main() -> None:
    case = json.loads(CASE.read_text(encoding="utf-8"))
    registry_by_path()  # duplicate check
    found = editable(case)
    named, missing = coverage(case)
    total = named + len(missing)
    print(f"registry entries      : {len(REGISTRY)}")
    print(f"resolved in this case : {len(found)}")
    print(f"numeric leaves covered: {named}/{total} ({100.0 * named / total:.1f} %)")
    print(f"groups                : {sorted({s.group for s, _ in found})}")
    print("\nsample (group / label / unit / value):")
    seen: set[str] = set()
    for spec, value in found:
        if spec.group in seen:
            continue
        seen.add(spec.group)
        print(f"  {spec.group:<6} {spec.label_zh:<12} [{spec.unit:<9}] {value}")
    print("\nuncovered leaves (first 14):")
    for name in missing[:14]:
        print(f"  {name}")

    patch = {
        "vehicle.travel_speed_m_s": 27.0,
        "contact.friction_coefficient": 0.32,
        "rail_templates[].support.k_z_n_m": 4.5e7,
    }
    patched = apply_patch(case, patch)
    for path, value in patch.items():
        spec = registry_by_path()[path]
        targets = []
        node = patched
        for token in path.replace("][", "].[").split("."):
            if token.endswith("[]"):
                node = node[token[:-2]][0]
                targets.append(node)
            else:
                node = node[token]
        print(f"patched {spec.label_zh}: {value} (first element {node if isinstance(node, dict) else node})")
    print(f"original untouched   : {case['vehicle']['travel_speed_m_s']} m/s")
    print(f"copied deeply        : {patched is not case}")


if __name__ == "__main__":
    main()
