"""The corpus needs to be declared, not guessed from a module's source text.

The old rule scanned for ``case_dir(``/``VALIDATION_DIR`` in the file and skipped the whole module
when the corpus was absent.  That gets two things wrong: a module that reads a case *indirectly*
(through a helper in another module) was run and then failed with a confusing error, and a module
that merely mentions ``VALIDATION_DIR`` in a docstring was skipped although it never opens a file.
Both failures are silent, so the gate's meaning drifts away from its name.

Now the module says so: ``pytestmark = pytest.mark.corpus``.  The text scan stays as a **fallback
for modules that forgot the marker**, and ``tests/test_corpus_marker.py`` fails when a module the
scan would skip lacks it -- drift surfaces in CI instead of on a machine without the corpus.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from velch.data_root import case_dir, explain

#: Kept for the fallback: a module with no marker but reaching for a case file is still skipped.
CORPUS_HINTS = ("case_dir(", "case_path(", "VALIDATION_DIR", "oracle_dir(")
_SOURCE_CACHE: dict[Path, str] = {}
MARKER_INFO = (
    "validation corpus not present "
    "(looked in {case_dir}, source={source}); "
    "set VELCH_DATA_ROOT or add .velch-data.json -- see validation/INDEX.md"
)


def corpus_present() -> bool:
    """The single probe: one file that every corpus-dependent test ultimately needs."""

    return (case_dir() / "case_full12_cap05.json").is_file()


def declares_corpus(path: Path) -> bool:
    """Whether the module declares ``pytestmark = pytest.mark.corpus`` at module level."""

    text = _source(path)
    return "pytest.mark.corpus" in text


def mentions_corpus(path: Path) -> bool:
    """Fallback probe: the module's source reaches for a case file."""

    text = _source(path)
    return any(hint in text for hint in CORPUS_HINTS)


def needs_corpus(path: Path | None) -> bool:
    """Declared marker first; the text scan only fills the gaps."""

    if path is None:
        return False
    return declares_corpus(path) or mentions_corpus(path)


def _source(path: Path) -> str:
    if path not in _SOURCE_CACHE:
        try:
            _SOURCE_CACHE[path] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            _SOURCE_CACHE[path] = ""
    return _SOURCE_CACHE[path]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if corpus_present():
        return
    details = explain()
    marker = pytest.mark.skip(reason=MARKER_INFO.format(case_dir=details["case_dir"],
                                                        source=details["source"]))
    skipped = 0
    for item in items:
        path = getattr(item, "path", None) or getattr(item, "fspath", None)
        if needs_corpus(Path(str(path)) if path is not None else None):
            item.add_marker(marker)
            skipped += 1
    if skipped:
        print(f"\n[conftest] corpus absent: skipped {skipped}/{len(items)} tests that read cases")
