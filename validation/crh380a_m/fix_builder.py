"""One-off repair of build_diverging_case.py: restore ASCII-only strings and add the two missing lines.

PowerShell's Set-Content mangled the UTF-8 Chinese in one docstring, so the file is rewritten here in
Python (UTF-8 in, UTF-8 out) with plain-ASCII text, which removes the mojibake for good.
"""

from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("build_diverging_case.py")
text = path.read_text(encoding="utf-8")

if "import numpy as np" not in text:
    text = text.replace("import json\nfrom pathlib import Path",
                        "import json\nfrom pathlib import Path\n\nimport numpy as np", 1)

if "    known = []" not in text:
    text = text.replace("    entries = []", "    entries = []\n    known = []", 1)

lines = text.splitlines()
for index, line in enumerate(lines):
    if "rail shape from SDITT" in line:
        lines[index] = ('        "diverging route of turnout 18: rail shape from SDITT 07(009) parts, '
                        'placement from the drawing design radius "')
text = "\n".join(lines) + "\n"

path.write_text(text, encoding="utf-8")
print("repaired:", path.name)
for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
    if "numpy" in line or "known = []" in line or "diverging route of turnout 18" in line:
        print(f"  {index}: {line}")
