"""The type scale is a contract: every token scales, nothing is left at the old size.

Readability work fails quietly.  A widget built before the scale changed keeps its old font, so a
UI that says "130 %" can still draw half of itself at 100 %.  These tests pin the parts that are
checkable without a display: the token table, its bounds, the derived line/row heights, and the
environment hook a launcher uses.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from velch.ui import app as app_module
from velch.ui import theme

SOURCE = Path(__file__).resolve().parent.parent / "src" / "velch"


@pytest.fixture(autouse=True)
def _restore_scale():
    """Every test starts and ends at the design size."""

    theme.set_scale(1.0)
    yield
    theme.set_scale(1.0)


def test_design_size_reproduces_the_declared_table() -> None:
    theme.set_scale(1.0)

    assert theme.FONT_SIZE == theme.BASE_FONT_SIZE
    assert theme.TREE_ROW_HEIGHT == 28
    # The ladder itself: 12 px body is the floor the visual review asked for, so a later "compact"
    # edit cannot quietly walk it back to 11.
    assert theme.BASE_FONT_SIZE["body"] >= 12
    assert theme.BASE_FONT_SIZE["micro"] >= 10
    assert theme.BASE_FONT_SIZE["title"] >= 20


def test_scale_grows_every_token_monotonically() -> None:
    previous = None
    for factor in (0.9, 1.0, 1.1, 1.3, 1.6):
        theme.set_scale(factor)
        sizes = dict(theme.FONT_SIZE)
        assert sizes["body"] >= sizes["tiny"] >= sizes["micro"], sizes
        assert sizes["display"] > sizes["title"] > sizes["section"] > sizes["body_lg"], sizes
        if previous is not None:
            assert all(sizes[key] >= previous[key] for key in sizes), (factor, previous, sizes)
        previous = sizes


def test_scale_is_clamped_to_the_supported_range() -> None:
    assert theme.set_scale(5.0) == theme.SCALE_MAX
    assert theme.set_scale(0.1) == theme.SCALE_MIN
    assert theme.set_scale(0.1) >= 0.9  # readable at the bottom of the range


def test_line_and_row_heights_follow_the_type() -> None:
    theme.set_scale(1.0)
    base_row = theme.TREE_ROW_HEIGHT
    base_line = theme.LINE_HEIGHT["body"]
    theme.set_scale(1.4)

    assert theme.TREE_ROW_HEIGHT > base_row
    assert theme.LINE_HEIGHT["body"] > base_line
    # A row shorter than its own font would clip the glyphs it exists to show.
    assert theme.TREE_ROW_HEIGHT >= theme.FONT_SIZE["body"] + 8


def test_environment_variable_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VELCH_UI_SCALE", "1.3")
    assert theme.scale_from_environment() == pytest.approx(1.3)
    assert theme.FONT_SIZE["body"] > theme.BASE_FONT_SIZE["body"]


def test_bad_environment_value_keeps_the_current_scale(monkeypatch: pytest.MonkeyPatch) -> None:
    theme.set_scale(1.2)
    monkeypatch.setenv("VELCH_UI_SCALE", "大字")
    assert theme.scale_from_environment() == pytest.approx(1.2)


def test_colours_are_untouched_so_contrast_still_holds() -> None:
    theme.set_scale(1.6)
    assert theme.contrast_violations() == []


def test_every_zoom_key_is_documented() -> None:
    """The help screen is the only place a user can discover the keys, so they must be there."""

    documented = " ".join(f"{keys} {what}" for keys, what in app_module.SHORTCUTS)
    assert "Ctrl+=" in documented
    assert "Ctrl+-" in documented
    assert "Ctrl+0" in documented


def test_focus_ring_is_a_token_and_clears_the_floor() -> None:
    """O007: the focus ring is the only keyboard cue, so it is measured, not eyeballed.

    ``BORDER`` (1.48:1) and ``BORDER_STRONG`` (1.83:1) stay below 3:1 on purpose — they are a
    hairline divider and a hover wash, not control boundaries.  The boundary a user has to *see* is
    ``BORDER_CONTROL`` (3.61–4.32:1) and the ring is ``ACCENT`` (7.89–9.43:1).
    """
    assert theme.FOCUS_THICKNESS >= 2, "a 1 px focus ring disappears at 130 % zoom"
    for background in ("SURFACE", "BG", "RAISED"):
        measured = theme.contrast_ratio(theme.ACCENT, getattr(theme, background))
        assert measured >= 3.0, f"focus ring on {background} only {measured:.2f}:1"
    assert theme.contrast_violations() == []
    source = (SOURCE / "ui" / "app.py").read_text(encoding="utf-8")
    assert "theme.FOCUS_THICKNESS" in source, "the ring thickness must come from the token"
