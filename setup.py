"""Build hook: ship the turnout library inside the wheel.

The library (``vehicles/``) sits at the repository root and is what every delivered case points at through
``lib:``.  Setuptools cannot treat it as package data because it is not inside ``src/velch``, so a plain wheel
carried 0 of its 295 section files (round 288 measured 104 entries, 463 KB, no ``vehicles/``) and an installed
copy failed on the first ``lib:`` reference.

Rather than duplicating 8.6 MB into the source tree, the copy happens **at build time**, straight into the
build directory:

    build/lib*/velch/_internal/vehicles/...     <- what lands in the wheel

and ``vehicle_db._root()`` prefers ``<package>/_internal/vehicles`` when it exists.  Consequences:

* a source checkout is unchanged -- ``_internal`` is not there, so the resolver keeps walking up to the repo;
* ``pip install -e .`` is unchanged -- ``build_py`` does not run for editable installs;
* a built wheel is self-contained, which is what ``scripts/s144_delivery_check.py`` gate ``D-WHEEL`` asks.

No network, no bytecode, no code generation: one ``copy_tree`` of the library directory.
"""
from __future__ import annotations

import pathlib
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = pathlib.Path(__file__).resolve().parent
LIBRARY = ROOT / "vehicles"
INSIDE = pathlib.Path("velch") / "_internal" / "vehicles"


class build_py(_build_py):
    """Copy ``vehicles/`` into ``velch/_internal/vehicles`` inside the build tree."""

    def run(self) -> None:  # noqa: D102 - setuptools hook
        super().run()
        if not LIBRARY.is_dir():
            raise SystemExit(f"build_py: the turnout library is missing at {LIBRARY}; a wheel without it "
                             "cannot resolve any 'lib:' reference")
        target = pathlib.Path(self.build_lib) / INSIDE
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(LIBRARY, target)
        files = sum(1 for _ in target.rglob("*") if _.is_file())
        print(f"build_py: bundled {files} library files into {INSIDE}")


setup(cmdclass={"build_py": build_py})
