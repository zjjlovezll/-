"""The corpus marker must be declared, not guessed -- and the guess must not outlive the marker.

``tests/conftest.py`` skips whole modules when the 1.4 GB corpus is absent.  It reads a declared
``pytestmark = pytest.mark.corpus`` first and only falls back to scanning the source text.  This
file keeps the two halves honest: every module the scan would skip must carry the marker, and the
fallback must still work for a module that forgot it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import CORPUS_HINTS, declares_corpus, mentions_corpus, needs_corpus

pytestmark = pytest.mark.corpus

TESTS = Path(__file__).resolve().parent


def _modules():
    return sorted(path for path in TESTS.glob("test_*.py") if path.name != Path(__file__).name)


def test_every_module_that_reads_cases_declares_the_marker() -> None:
    """A module the text scan would skip must say so explicitly, or the gate drifts."""

    missing = [path.name for path in _modules()
               if mentions_corpus(path) and not declares_corpus(path)]
    assert not missing, f"add pytestmark = pytest.mark.corpus to: {missing}"


def test_the_marker_is_registered_so_it_does_not_warn() -> None:
    config = (TESTS.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert '"corpus:' in config or "'corpus:" in config, "the corpus marker must be registered"


def test_a_module_without_the_marker_still_gets_skipped_by_the_fallback(tmp_path) -> None:
    """The fallback exists for the forgotten marker; it must actually fire."""

    legacy = tmp_path / "test_legacy.py"
    legacy.write_text("from velch.data_root import case_dir\nCASE = case_dir()\n", encoding="utf-8")
    assert mentions_corpus(legacy)
    assert not declares_corpus(legacy)
    assert needs_corpus(legacy)


def test_a_module_with_neither_signal_is_not_skipped(tmp_path) -> None:
    plain = tmp_path / "test_plain.py"
    plain.write_text("def test_maths():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    assert not needs_corpus(plain), "layering rules and maths must keep running without a corpus"


def test_the_hint_list_still_matches_the_probe_it_claims() -> None:
    """``CORPUS_HINTS`` is what the fallback looks for; keep it aligned with the real API."""

    assert "case_dir(" in CORPUS_HINTS and "VALIDATION_DIR" in CORPUS_HINTS
