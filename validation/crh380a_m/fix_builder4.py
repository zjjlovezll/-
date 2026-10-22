"""Repair pass 4: the right rail template carries ``bodies`` and no ``stations`` -- select by that."""

from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("build_diverging_case.py")
text = path.read_text(encoding="utf-8")

start = text.index("    right_index = 0")
end = text.index('    rails[right_index]["stations"] = [entry[4] for entry in entries]')
replacement = ('    # The right rail is the template built from bodies (main / point / wing); the left one\n'
               '    # carries a plain station list.  Select by that, not by an offset that a body-only\n'
               '    # template does not have.\n'
               '    right_index = next((i for i, rail in enumerate(rails) if rail.get("bodies")), 0)\n')
text = text[:start] + replacement + text[end:]
path.write_text(text, encoding="utf-8")
print("repaired pass 4")
