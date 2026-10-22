"""Prove the creep-derivative tests fail when the defect is put back.

A regression test that also passes on the broken code is decoration.  This script
re-introduces each of the three defects one at a time, runs the test file, and asserts
that it fails -- restoring the file in a ``finally`` so a crash cannot leave the tree
modified.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "velch" / "jacobian.py"
TESTS = ["tests/test_jacobian_creep.py"]

DEFECTS = {
    "denominator": (
        "        d_scale_d_limit = (shape - ratio * dshape) / demand",
        "        d_scale_d_limit = (shape - ratio * dshape) / limit",
    ),
    "zero-demand": (
        "            return linear_x, linear_lateral, 1.0, 0.0, 0.0",
        "            return linear_x, linear_lateral, 0.0, 0.0, 0.0",
    ),
    "block-placement": (
        "longitudinal_v = np.zeros(self.n)\n"
        "                longitudinal_v[wheel + 3] += gain_x * slope_x * geometry.lever_z_m",
        "longitudinal_q = np.zeros(self.n)\n"
        "                longitudinal_q[wheel + 3] += gain_x * slope_x * geometry.lever_z_m",
    ),
}


def run(command: list[str]) -> int:
    return subprocess.run(command, cwd=ROOT, capture_output=True).returncode


def pytest_run() -> int:
    return run([sys.executable, "-X", "utf8", "-m", "pytest", *TESTS, "-q",
                "-p", "no:cacheprovider", "--basetemp", r"F:\velch_tmp\pytest"])


def drop_bytecode() -> None:
    """Delete the compiled module after a rewrite.

    The defects below change exactly one character each (``v`` <-> ``q``), so the file
    keeps its size, and CPython's mtime-in-second + size check can happily reuse a
    ``.pyc`` built from the *broken* source.  That happened once: the tree was correct
    and the next run still raised ``NameError: longitudinal_q``.
    """
    for cached in (SOURCE.parent / "__pycache__").glob("jacobian*.pyc"):
        cached.unlink(missing_ok=True)


def main() -> int:
    original = SOURCE.read_text(encoding="utf-8")
    failures = 0
    try:
        if pytest_run() != 0:
            print("baseline is already failing; fix that first")
            return 2
        for name, (fixed, broken) in DEFECTS.items():
            if fixed not in original:
                print(f"{name}: cannot find the fixed form, skipping (code moved?)")
                failures += 1
                continue
            SOURCE.write_text(original.replace(fixed, broken, 1), encoding="utf-8")
            drop_bytecode()
            try:
                code = pytest_run()
            finally:
                SOURCE.write_text(original, encoding="utf-8")
                drop_bytecode()
            caught = code != 0
            verdict = "FAIL (good)" if caught else "PASS (blind!)"
            print(f"{name:16s} reintroduced -> tests {verdict}")
            failures += 0 if caught else 1
    finally:
        SOURCE.write_text(original, encoding="utf-8")
        drop_bytecode()
    print("all three defects are caught" if failures == 0
          else f"{failures} defect(s) not caught")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
