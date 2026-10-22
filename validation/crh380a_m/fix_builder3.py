"""Repair pass 3: never strip a template down to neither ``stations`` nor ``bodies``."""

from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("build_diverging_case.py")
text = path.read_text(encoding="utf-8")
old = ('    other = [i for i in range(len(rails)) if i != right_index]\n'
       '    for index in other:\n'
       '        rails[index].pop("bodies", None)')
new = ('    other = [i for i in range(len(rails)) if i != right_index]\n'
       '    for index in other:\n'
       '        if rails[index].get("stations"):\n'
       '            rails[index].pop("bodies", None)')
if old in text:
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("repaired pass 3")
