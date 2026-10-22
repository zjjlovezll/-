"""Derive a case with a different contact curvature estimator.

    python make_curv_case.py <case.json> <policy> <output.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

source, policy, target = sys.argv[1], sys.argv[2], sys.argv[3]
case = json.loads(Path(source).read_text(encoding="utf-8"))
case["case_id"] = f"{case['case_id']}_{policy}"
case["contact"]["curvature_policy"] = policy
case.setdefault("parameter_source", {})
Path(target).write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
print(f"wrote {target}: curvature_policy={policy}")
