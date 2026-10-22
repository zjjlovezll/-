"""Cache key for the hoisted rail grid must identify the *surface*, not the interval.

The cached-grid experiment produced 1447.7 kN. The key was
``(surface_key, lower_s_m, upper_s_m)``: those two numbers are the *interval endpoints*
of the interpolated sample, so they are constant for every call between two stations,
while the blended surface inside that interval keeps changing. The cache therefore
served the surface built at the first call of the interval for its whole length -- up to
380 mm at the frog, where the crown migrates several mm per station. Stale geometry,
full force.

Fix: fold three ordinates of the interpolated profile into the key. A linear blend
between two sections changes those ordinates, so two different surfaces cannot collide,
and identical surfaces still hit the cache.
"""

from __future__ import annotations

from pathlib import Path

PATH = Path(r"F:\ai道岔状态反演辨识\Velch\src\velch\contact.py")
text = PATH.read_text(encoding="utf-8")

PATTERNS = (
    '((surface_key, rail_sample.lower_s_m, rail_sample.upper_s_m)',
)
NEW_TAIL = ('((surface_key, rail_sample.lower_s_m, rail_sample.upper_s_m,\n'
            '                 float(rail_z[0]), float(rail_z[rail_z.size // 2]),\n'
            '                 float(rail_z[-1]))')

count = text.count(PATTERNS[0])
assert count == 2, f"expected two cache-key sites, found {count}"
text = text.replace(PATTERNS[0], NEW_TAIL)
PATH.write_text(text, encoding="utf-8")
print(f"patched {count} cache-key sites in contact.py")
