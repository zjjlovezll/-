"""Skip only the tests that actually need the corpus; keep the rest meaningful without it.

Before this the hook marked *every* item skipped when the 1.4 GB corpus was absent — including
``test_architecture_rules``, the label grammar and the geometry maths, none of which open a case
file.  A gate that reports "skipped" for the layering rules is a gate that cannot fail, which is
worse than a gate that cannot run.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from velch.data_root import case_dir, explain

#: A module needs the corpus if its source reaches for a case file at all.
CORPUS_HINTS = ("case_dir(", "case_path(", "VALIDATION_DIR", "oracle_dir(")
_source_cache: dict[Path, bool] = {}


def corpus_present() -> bool:
    """The single probe: one file that every corpus-dependent test ultimately needs."""

    return (case_dir() / "case_full12_cap05.json").is_file()


def needs_corpus(path: Path | None) -> bool:
    """Whether a test module's source references the external corpus."""

    if path is None:
        return True
    if path not in _source_cache:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            _source_cache[path] = True
        else:
            _source_cache[path] = any(hint in text for hint in CORPUS_HINTS)
    return _source_cache[path]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if corpus_present():
        return
    details = explain()
    reason = (
        "validation corpus not present "
        f"(looked in {details['case_dir']}, source={details['source']}); "
        "set VELCH_DATA_ROOT or add .velch-data.json -- see validation/INDEX.md"
    )
    marker = pytest.mark.skip(reason=reason)
    skipped = 0
    for item in items:
        path = getattr(item, "path", None) or getattr(item, "fspath", None)
        module_path = Path(str(path)) if path is not None else None
        if needs_corpus(module_path):
            item.add_marker(marker)
            skipped += 1
    if skipped:
        print(f"\n[conftest] corpus absent: skipped {skipped}/{len(items)} tests that read cases")
