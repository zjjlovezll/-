"""Where the bulky, non-shipped data lives.

The package is 1.6 MB; the validation corpus beside it is 1.4 GB (207 run directories, 354
case files, ~190 measurement scripts).  Mixing the two in one tree is what makes the repository
feel unmaintainable, but the corpus cannot simply be deleted either: tests compare against two
frozen oracles, the UI lists the cases, and the gates read them by value.

So the *location* of that corpus is a single decision made here, in one place, and every caller
asks this module instead of walking up from ``__file__``:

* ``VELCH_DATA_ROOT``  -- environment override, highest priority;
* ``<repo>/validation`` -- the layout as imported (still the default, so nothing moves silently);
* a marker file ``<repo>/.velch-data.json`` with ``{"data_root": "F:/velch_data/validation"}``
  -- written by whoever moves the corpus, and read here so a moved tree keeps working for every
  process (tests, UI, agent, gates) without setting an environment variable each time.

Resolving in that order means "move the data" is a configuration change, not a code change.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = [
    "REPOSITORY_ROOT",
    "MARKER_NAME",
    "repository_root",
    "frozen_install_root",
    "user_marker_path",
    "marker_candidates",
    "marker_path",
    "data_root",
    "case_dir",
    "oracle_dir",
    "case_path",
    "explain",
    "hint",
]

#: ``.../Velch`` -- the directory that holds ``src``, ``tests`` and (by default) ``validation``.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

#: Written next to ``pyproject.toml`` when the corpus has been moved out of the repository.
MARKER_NAME = ".velch-data.json"


def is_frozen() -> bool:
    """True inside a packaged build, where the anchor is the exe directory."""

    import sys
    return bool(getattr(sys, "frozen", False))


def frozen_install_root() -> Path:
    """The folder the product is installed into (the exe's own folder).

    Inside a PyInstaller onedir bundle ``__file__`` points into ``_internal``, so
    ``parents[2]`` is not the install folder -- using it would look for the corpus in
    ``_internal/validation``, a path nobody would ever create.
    """

    import sys
    return Path(sys.executable).resolve().parent


def repository_root() -> Path:
    """Directory holding ``src``/``tests`` (or the install folder when packaged)."""

    return frozen_install_root() if is_frozen() else REPOSITORY_ROOT


def user_marker_path() -> Path:
    """Per-user marker: the only writable place when the install folder is read-only."""

    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "Velch" / MARKER_NAME
    return Path.home() / ".velch" / MARKER_NAME


def marker_candidates() -> list[Path]:
    """Every place a marker may live, in the order it is honoured."""

    places = [user_marker_path(), repository_root() / MARKER_NAME]
    if is_frozen():
        # A side-by-side development marker should still work when running from source.
        places.append(REPOSITORY_ROOT / MARKER_NAME)
    # In a frozen build ``repository_root()`` is already the folder the package was built from, so
    # the third entry can repeat the second. Show each place once: a hint that lists the same path
    # twice reads like a defect in the message.
    unique: list[Path] = []
    for place in places:
        if place not in unique:
            unique.append(place)
    return unique


def marker_path() -> Path:
    """The marker next to the package/install folder (the one a developer writes)."""

    return repository_root() / MARKER_NAME


def active_marker() -> Path | None:
    """The marker actually in force, if any (per-user first, then the install folder)."""

    for place in marker_candidates():
        if place.is_file():
            return place
    return None


def _root_from_marker() -> Path | None:
    marker = active_marker()
    if marker is None:
        return None
    try:
        # ``utf-8-sig`` rather than ``utf-8``: PowerShell 5.1 writes a BOM when asked for
        # "utf8", and a BOM makes ``json.loads`` reject an otherwise valid marker file.
        payload = json.loads(marker.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    value = payload.get("data_root") if isinstance(payload, dict) else None
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = marker.parent / candidate
    return candidate.resolve()


def data_root() -> Path:
    """Directory that holds ``crh380a_m`` and the other validation sets."""
    override = os.environ.get("VELCH_DATA_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    marker = _root_from_marker()
    if marker is not None:
        return marker
    return repository_root() / "validation"


def hint() -> str:
    """A sentence a person can act on when the corpus is missing.

    A packaged product cannot ship 1.4 GB of cases, so "the folder is missing" is a normal first
    run, not a defect; the message must say where the program looked and what to do next.
    """

    seen = ", ".join(str(place) for place in marker_candidates())
    where = user_marker_path()
    return (
        "未找到算例语料（validation/crh380a_m）。程序按顺序查找：\n"
        f"  1. 环境变量 VELCH_DATA_ROOT（当前：{os.environ.get('VELCH_DATA_ROOT') or '未设置'}）\n"
        f"  2. 标记文件，依次尝试：{seen}\n"
        f"  3. 安装目录下的 validation/：{repository_root() / 'validation'}\n"
        "解决办法：把语料所在目录写进标记文件，例如\n"
        f'  {where}  内容  {{"data_root": "F:/velch_data"}}\n'
        "（该目录下应有 validation\\crh380a_m\\case_*.json）。"
    )


def case_dir() -> Path:
    """The CRH380A_M case set: ``case_*.json`` plus the profile files they reference."""
    return data_root() / "crh380a_m"


def oracle_dir() -> Path:
    """The two frozen oracles kept under version control (see ``validation/INDEX.md``)."""
    return case_dir()


def case_path(name: str) -> Path:
    """Absolute path of one case file.  Raises ``FileNotFoundError`` rather than guessing."""
    path = case_dir() / name
    if not path.is_file():
        raise FileNotFoundError(f"case file not found: {path}\n{hint()}")
    return path


def explain() -> dict[str, object]:
    """What this module decided, and why -- for ``velch doctor`` and error messages."""
    override = os.environ.get("VELCH_DATA_ROOT")
    marker = _root_from_marker()
    if override:
        source = "environment VELCH_DATA_ROOT"
    elif marker is not None:
        source = f"marker {marker_path().name}"
    else:
        source = "repository default"
    root = data_root()
    cases = case_dir()
    return {
        "frozen": is_frozen(),
        "repository_root": str(repository_root()),
        "data_root": str(root),
        "source": source,
        "case_dir": str(cases),
        "case_dir_exists": cases.is_dir(),
        "case_files": len(list(cases.glob("case_*.json"))) if cases.is_dir() else 0,
        "marker": str(active_marker()) if active_marker() else None,
        "marker_candidates": [str(place) for place in marker_candidates()],
        "hint": None if cases.is_dir() else hint(),
    }
