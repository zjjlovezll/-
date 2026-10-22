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
    "marker_path",
    "data_root",
    "case_dir",
    "oracle_dir",
    "case_path",
    "explain",
]

#: ``.../Velch`` -- the directory that holds ``src``, ``tests`` and (by default) ``validation``.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

#: Written next to ``pyproject.toml`` when the corpus has been moved out of the repository.
MARKER_NAME = ".velch-data.json"


def repository_root() -> Path:
    """Directory holding ``src``/``tests``; the anchor for every relative default."""
    return REPOSITORY_ROOT


def marker_path() -> Path:
    return repository_root() / MARKER_NAME


def _root_from_marker() -> Path | None:
    marker = marker_path()
    if not marker.is_file():
        return None
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
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
        raise FileNotFoundError(f"case file not found: {path}")
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
        "repository_root": str(repository_root()),
        "data_root": str(root),
        "source": source,
        "case_dir": str(cases),
        "case_dir_exists": cases.is_dir(),
        "case_files": len(list(cases.glob("case_*.json"))) if cases.is_dir() else 0,
        "marker": str(marker_path()) if marker_path().is_file() else None,
    }
