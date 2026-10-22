"""Clone a case JSON and override the contact-search policy.

The policy knobs are optional in the case schema, so every previously generated
case keeps its old behaviour when these are left alone. This script only writes
the fields it is asked to change.

Usage:
    python -X utf8 make_policy_case.py <base.json> <out.json> \
        [--half-width-mm 5] [--seed-scope rail|body] [--dedupe-mm 4] \
        [--hysteresis on|off] [--title TEXT]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("out")
    parser.add_argument("--half-width-mm", type=float, default=None)
    parser.add_argument("--seed-scope", choices=("rail", "body", "rail_hold"), default=None)
    parser.add_argument("--dedupe-mm", type=float, default=None)
    parser.add_argument("--hysteresis", choices=("on", "off"), default=None)
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    base = Path(args.base)
    raw = json.loads(base.read_text(encoding="utf-8"))
    run = raw.setdefault("run", {})
    if args.half_width_mm is not None:
        run["contact_search_half_width_m"] = args.half_width_mm / 1000.0
    if args.seed_scope is not None:
        run["contact_seed_scope"] = args.seed_scope
    if args.hysteresis is not None:
        run["body_hysteresis"] = args.hysteresis == "on"
    if args.dedupe_mm is not None:
        raw.setdefault("contact", {})["duplicate_patch_window_m"] = args.dedupe_mm / 1000.0
    if args.title:
        raw["case_id"] = args.title

    out = Path(args.out)
    out.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    policy = {
        "run.contact_search_half_width_m": run.get("contact_search_half_width_m"),
        "run.contact_seed_scope": run.get("contact_seed_scope", "body"),
        "run.body_hysteresis": run.get("body_hysteresis", False),
        "contact.duplicate_patch_window_m": raw.get("contact", {}).get("duplicate_patch_window_m", 0.0),
    }
    print(json.dumps({"out": str(out), "policy": policy}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
