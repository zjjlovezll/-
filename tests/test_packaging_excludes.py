"""The freeze list must stay honest: everything excluded from the build is unused by the product.

``packaging/Velch.spec`` excludes a long list of heavy packages.  Excluding something the code
actually imports produces a build that fails only when a user clicks the wrong button, so the
list is checked against ``src/`` here: no excluded top-level name may appear as an import.
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "velch"

# Packages whose absence is fine because nothing in ``src`` imports them by name.  ``h5py`` is
# deliberately absent from this set: ⑥ 对照屏 reads Simpack .mat through it when it is installed.
EXCLUDED_TOP_LEVEL = {
    "torch", "torchvision", "torchaudio", "sklearn", "numba", "llvmlite", "sympy", "plotly",
    "pyarrow", "cv2", "imageio", "seaborn", "statsmodels", "dask", "xarray", "bokeh", "pandas",
    "tables", "numexpr", "zmq", "tornado", "sphinx", "docutils", "PIL", "_pytest", "pytest",
    "IPython", "jupyter", "notebook", "PyQt5", "PyQt6", "PySide2", "PySide6",
}


def _imported_modules() -> set[str]:
    found: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return found


def test_the_product_never_imports_an_excluded_package():
    offenders = sorted(_imported_modules() & EXCLUDED_TOP_LEVEL)
    assert offenders == [], "spec excludes packages the product imports: " + ", ".join(offenders)


def test_the_spec_lists_the_heavyweights_it_claims_to():
    spec = (SRC.parent.parent / "packaging" / "Velch.spec").read_text(encoding="utf-8")
    for name in ("torch", "plotly", "PyQt5", "pandas"):
        assert f'"{name}"' in spec, f"{name} missing from the exclude list"


def test_matplotlib_is_collected_not_excluded():
    """The charts are part of the product; excluding matplotlib would ship a broken ④ 屏."""

    spec = (SRC.parent.parent / "packaging" / "Velch.spec").read_text(encoding="utf-8")
    assert "collect_data_files(\"matplotlib\"" in spec
    assert "\"matplotlib\"" not in spec.split("EXCLUDES = [")[1]
