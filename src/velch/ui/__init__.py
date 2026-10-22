"""Velch desktop UI: a six-screen workbench over saved run artifacts.

Entry point is ``python -X utf8 -m velch.ui`` (see :mod:`velch.ui.__main__`); the
``--selftest`` flag loads every screen headlessly and prints what it found, which is how
this package is smoke-tested on a machine without an interactive display.

Deliberately separate from the v0.3 workbench in :mod:`velch.gui`: that module stays
importable and unchanged so nothing that depends on it breaks.
"""

from __future__ import annotations

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """Run the desktop UI, or the headless self-test, depending on ``argv``."""

    from .app import main as _main
    return _main(argv)
