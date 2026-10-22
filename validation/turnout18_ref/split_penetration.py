"""Split the reported approach into Hertz indentation and rail-support settlement.

Before S1-e the contact depth *was* the Hertzian indentation. With the support
compliance in series it is the total approach, so the two parts are now reported
separately and the case gate keeps its original meaning via the Hertz field.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path("src/velch")


def patch(path: pathlib.Path, pairs: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if new.strip() and new.strip() in text:
            print(f"skip (already applied): {old[:48]!r}")
            continue
        if old not in text:
            raise SystemExit(f"anchor not found in {path.name}: {old[:72]!r}")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("patched", path.name)


patch(ROOT / "contact.py", [
    (
        "    damping_dissipation_w: float = 0.0",
        "    damping_dissipation_w: float = 0.0\n"
        "    # S1-e: the reported depth is the total approach; these split it into the\n"
        "    # Hertzian indentation of the contact spring and the rail settling on its\n"
        "    # fasteners. Without a support compliance the settlement is zero and the\n"
        "    # Hertz part equals the depth, which is the pre-S1-e meaning.\n"
        "    hertz_penetration_m: float = 0.0\n"
        "    support_settlement_m: float = 0.0",
    ),
    (
        "            damping_dissipation_w=sum(item.damping_dissipation_w for item in active),",
        "            damping_dissipation_w=sum(item.damping_dissipation_w for item in active),\n"
        "            hertz_penetration_m=sum(item.hertz_penetration_m for item in active),\n"
        "            support_settlement_m=sum(item.support_settlement_m for item in active),",
    ),
    (
        "    elastic = series_normal_force(depth, stiffness, support_compliance_m_per_n)",
        "    elastic = series_normal_force(depth, stiffness, support_compliance_m_per_n)\n"
        "    if stiffness > 0.0:\n"
        "        hertz_penetration = (elastic / stiffness) ** (2.0 / 3.0)\n"
        "    else:\n"
        "        hertz_penetration = 0.0\n"
        "    settlement = (elastic * support_compliance_m_per_n\n"
        "                  if support_compliance_m_per_n else 0.0)",
    ),
    (
        "        damping_dissipation_w=max(0.0, (normal - elastic) * approach),",
        "        damping_dissipation_w=max(0.0, (normal - elastic) * approach),\n"
        "        hertz_penetration_m=hertz_penetration, support_settlement_m=settlement,",
    ),
])

patch(ROOT / "vehicle_solver.py", [
    (
        "    max_depth = max_friction_excess = 0.0",
        "    max_depth = max_friction_excess = 0.0\n"
        "    max_hertz_depth = max_settlement = 0.0",
    ),
    (
        "                max_depth = max(max_depth, response.geometry.penetration_m)",
        "                max_depth = max(max_depth, response.geometry.penetration_m)\n"
        "                max_hertz_depth = max(max_hertz_depth, response.hertz_penetration_m)\n"
        "                max_settlement = max(max_settlement, response.support_settlement_m)",
    ),
    (
        '        "max_penetration_m": max_depth, "max_friction_excess_n": max_friction_excess,',
        '        "max_penetration_m": max_depth, "max_friction_excess_n": max_friction_excess,\n'
        '        "max_hertz_penetration_m": max_hertz_depth,\n'
        '        "max_support_settlement_m": max_settlement,\n'
        '        "support_compliance": (None if case.support_compliance is None else {\n'
        '            "spacing_m": case.support_compliance.spacing_m,\n'
        '            "pad_stiffness_n_m": case.support_compliance.pad_stiffness_n_m,\n'
        '            "rail_ei_n_m2": case.support_compliance.rail_ei_n_m2,\n'
        '            "mean_compliance_m_per_n": case.support_compliance.mean_m_per_n}),',
    ),
])
