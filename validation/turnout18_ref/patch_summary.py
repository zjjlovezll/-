import pathlib

p = pathlib.Path('src/velch/vehicle_solver.py')
s = p.read_text(encoding='utf-8')
pairs = [
    ('    max_depth = max_friction_excess = 0.0',
     '    max_depth = max_friction_excess = 0.0\n    max_hertz_depth = max_settlement = 0.0'),
    ('                max_depth = max(max_depth, response.geometry.penetration_m)',
     '                max_depth = max(max_depth, response.geometry.penetration_m)\n'
     '                max_hertz_depth = max(max_hertz_depth, response.hertz_penetration_m)\n'
     '                max_settlement = max(max_settlement, response.support_settlement_m)'),
    ('        "max_penetration_m": max_depth, "max_friction_excess_n": max_friction_excess,',
     '        "max_penetration_m": max_depth, "max_friction_excess_n": max_friction_excess,\n'
     '        "max_hertz_penetration_m": max_hertz_depth,\n'
     '        "max_support_settlement_m": max_settlement,'),
]
applied = 0
for old, new in pairs:
    if new.strip() and new.strip().splitlines()[-1].strip() in s:
        print('skip', old.strip()[:48])
        continue
    assert s.count(old) == 1, (old[:48], s.count(old))
    s = s.replace(old, new, 1)
    applied += 1
p.write_text(s, encoding='utf-8')
print('applied', applied)
