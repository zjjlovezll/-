# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: one onedir tree, two executables.

``velch-cli.exe`` console  -- CLI, MCP server, agent tools, and the children the UI starts
``Velch.exe``     windowed -- the seven-screen workbench

The console exe is deliberately not called ``velch.exe``: Windows file names are
case-insensitive, so ``Velch.exe`` and ``velch.exe`` collide inside one COLLECT and only one of
them survives -- which is exactly the "where did the windowed exe go" bug this fixes.

They share one COLLECT so the package is shipped as a single folder (250-400 MB) instead of two.
Data files that PyInstaller cannot infer are listed in ``DATAS``: the Tk theme assets come from
the interpreter, but matplotlib's font/style data and the matplotlib backend data are collected
explicitly, and the small ``docs``/``examples`` payloads make the folder self-explaining.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # type: ignore[name-defined]  # injected by PyInstaller
SRC = ROOT / "src"

datas = []
datas += collect_data_files("matplotlib", include_py_files=False)
# ``vehicles`` carries the vehicle library (five CRH380A variants) and the flexible-wheelset
# modal set ``vehicles/modes/CRH3C_wheelset_fe.json``.  ``velch.vehicle_db.vehicle_dir()`` looks
# for it next to the frozen executable, so a build without this entry starts up fine and then
# reports an empty library -- which reads as "the models are gone", not as "they were not packed".
for extra in ("examples", "docs", "vehicles", "portable"):
    folder = ROOT / extra
    if folder.is_dir():
        datas.append((str(folder), extra))
for name in ("README.md", "LICENSE"):
    path = ROOT / name
    if path.is_file():
        datas.append((str(path), "."))

# Every screen module is imported by name from a table (``app._build_screen``), so PyInstaller's
# static analysis cannot see them: a build without this list starts, then shows seven screens that
# all report "No module named 'velch.ui.screen_cases'".  Collecting the whole package is the honest
# fix for a package whose entry points are dynamic.
hiddenimports = collect_submodules("velch") + [
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.ttk",
    "matplotlib.backends.backend_tkagg",
    "mpl_toolkits.mplot3d",
    "velch.ui.app",
    "velch.ui.__main__",
    "velch.agent.__main__",
    "velch.agent.worker",
]

# Qt backends would add ~150 MB for a backend we never select: the UI draws Tk canvases and the
# headless renderer is Agg.  Excluding them also stops the analysis crawling through PyQt5.
#
# The rest of the list exists because this build runs on a workstation Python (Anaconda) where
# anything imported anywhere drags its whole neighbourhood in: an analysis that reached ``torch``
# and ``plotly`` was already past 5 minutes and would have shipped gigabytes the product never
# calls.  Excluding is safe here precisely because the product imports none of these by name --
# ``tests/test_packaging_excludes.py`` keeps that true by scanning ``src/``.
EXCLUDES = [
    "pytest", "PyInstaller", "setuptools", "pip", "wheel",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "shiboken2", "shiboken6",
    "matplotlib.backends.backend_qt5agg", "matplotlib.backends.backend_qtagg",
    "IPython", "jupyter", "notebook",
    "torch", "torchvision", "torchaudio", "sklearn", "numba", "llvmlite", "sympy",
    # h5py is deliberately NOT here: ⑥ 对照屏 reads Simpack .mat files through it when present.
    "plotly", "pyarrow", "cv2", "imageio", "seaborn", "statsmodels", "pandas",
    "dask", "xarray", "bokeh", "tables", "numexpr", "zmq", "tornado",
    # ``distutils``/``lib2to3`` must not be excluded: PyInstaller's own pre-safe-import hooks
    # alias ``distutils`` and the analysis dies with ValueError: already imported as ExcludedModule.
    # PIL must not be excluded either: matplotlib imports it for image formats, and a build without
    # it fails the ⑦ 三维 screen at runtime with "No module named 'PIL'".
    "sphinx", "docutils", "_pytest",
]

blockcipher = None

console_analysis = Analysis(
    [str(ROOT / "packaging" / "entry_console.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
console_pyz = PYZ(console_analysis.pure, console_analysis.zipped_data, cipher=blockcipher)  # noqa: F821
console_exe = EXE(
    console_pyz,
    console_analysis.scripts,
    [],
    exclude_binaries=True,
    name="velch-cli",
    debug=False,
    strip=False,
    upx=False,
    console=True,
    version=str(ROOT / "packaging" / "version_info.txt"),
)

window_analysis = Analysis(
    [str(ROOT / "packaging" / "entry_window.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
window_pyz = PYZ(window_analysis.pure, window_analysis.zipped_data, cipher=blockcipher)  # noqa: F821
window_exe = EXE(
    window_pyz,
    window_analysis.scripts,
    [],
    exclude_binaries=True,
    name="Velch",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    version=str(ROOT / "packaging" / "version_info.txt"),
    icon=str(ROOT / "packaging" / "velch.ico") if (ROOT / "packaging" / "velch.ico").is_file() else None,
)

collect = COLLECT(
    console_exe,
    console_analysis.binaries,
    console_analysis.zipfiles,
    console_analysis.datas,
    window_exe,
    window_analysis.binaries,
    window_analysis.zipfiles,
    window_analysis.datas,
    strip=False,
    upx=False,
    name="Velch",
)
