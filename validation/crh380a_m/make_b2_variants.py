# -*- coding: utf-8 -*-
"""Build refine_peak variants of the frog case (B2 verification)."""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
BASE = HERE / "case_frog_N_strip05.json"


def variant(name: str, **run_overrides) -> pathlib.Path:
    data = json.loads(BASE.read_text(encoding="utf-8"))
    data["id"] = name
    data["run"].update(run_overrides)
    path = HERE / f"case_{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(variant("b2_refine_5e4", output_step_s=5e-4, refine_peak=True))
    print(variant("b2_plain_5e4", output_step_s=5e-4, refine_peak=False))
