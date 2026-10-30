"""Environment guard for pytest's own temp root.

``tmp_path`` derives its base directory from ``tempfile.gettempdir()/pytest-of-<user>``.  On this
Windows machine that directory can end up in a state where *nothing* can touch it -- measured
2026-10-31: ``os.listdir`` and even ``icacls`` fail with ``[WinError 5] access denied``, and renaming
it fails the same way, so it cannot be cleared from inside the session.

When that happens pytest fails at fixture setup for **every** ``tmp_path`` test, whatever the code
under test does: ``tests/test_assets.py`` reported 5 errors with ``PermissionError`` on the temp base,
none of which was a defect in the module.  A red gate that says nothing about the code is worse than a
loud workaround, so this module points pytest at a workspace-local temp root instead.

``PYTEST_DEBUG_TEMPROOT`` is read once, when ``tmp_path_factory`` resolves its base, so it has to be
set before that.  Importing the root ``conftest.py`` happens earlier than any fixture, which is why
this lives here rather than in a fixture of its own.
"""
from __future__ import annotations

import os
import pathlib
import tempfile

_FALLBACK = pathlib.Path(__file__).resolve().parent.parent / "scratch" / "pytest_tmp"


def _temp_root_is_usable() -> bool:
    """One listing probe on the directory pytest would actually use.

    Probing the system temp root is not enough: it is listable here, and it is the
    ``pytest-of-<user>`` child inside it that denies access.  That child's name is pytest's own
    convention (``getpass.getuser()``), so it is reproduced rather than guessed.
    """
    import getpass

    base = pathlib.Path(tempfile.gettempdir())
    if not base.is_dir():
        return False
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001 - pytest falls back to "unknown" for the same reason
        user = "unknown"
    candidate = base / f"pytest-of-{user}"
    if candidate.exists():
        try:
            for _ in candidate.iterdir():
                break
        except OSError:
            return False
    return True


if not os.environ.get("PYTEST_DEBUG_TEMPROOT") and not _temp_root_is_usable():
    _FALLBACK.mkdir(parents=True, exist_ok=True)
    os.environ["PYTEST_DEBUG_TEMPROOT"] = str(_FALLBACK)
    print(f"\n[conftest] system temp root is unreadable; pytest temp root -> {_FALLBACK}")
