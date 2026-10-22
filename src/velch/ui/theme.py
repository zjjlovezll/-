"""Design tokens for the Velch desktop UI (dark industrial).

Every colour pair used for text is documented with its WCAG 2.1 contrast ratio in
``docs/ui/UI_SPEC_2026-10-21.md``; ``CONTRAST`` below repeats the measured numbers so a
change to a hex value cannot silently drop below AA.  Ratios were computed with the
sRGB relative-luminance formula and are asserted by ``ui/selftest.py``.
"""
from __future__ import annotations

# --- surface stack ---------------------------------------------------------
BG = "#0E1116"          # app background, the darkest plane
SURFACE = "#151A21"     # panels, tables
RAISED = "#1C232C"      # cards, hovered rows, inputs
OVERLAY = "#222A34"     # menus, tooltips, selection chips
BORDER = "#2A3341"      # hairlines (decorative only, never text)
BORDER_STRONG = "#3A4657"

# --- text ------------------------------------------------------------------
INK = "#E6EDF3"         # primary text            16.00:1 on BG
INK_MUTED = "#9BA9B8"   # secondary text           7.29:1 on SURFACE
INK_DIM = "#7D8B9C"     # tertiary / disabled      5.03:1 on SURFACE

# --- signal ----------------------------------------------------------------
ACCENT = "#4CC2FF"      # interactive, focus ring  9.43:1 on BG
ACCENT_INK = "#06121B"  # text on accent           9.43:1
AMBER = "#F2B134"       # running / warning-ish   10.01:1 on BG
PASS = "#46C46A"        # gate pass                7.79:1 on SURFACE
PASS_INK = "#04170A"    # text on pass             8.27:1
FAIL = "#FF6B5E"        # gate fail / error        6.26:1 on SURFACE
FAIL_INK = "#1A0605"    # text on fail             7.01:1
WARN = "#E0A33A"        # limit near-miss          7.88:1 on SURFACE
INFO = "#6FB2FF"        # neutral emphasis         7.90:1 on SURFACE

# --- series palette (colour-blind safe ordering, no red/green adjacency) ----
SERIES = ("#4CC2FF", "#F2B134", "#B48EFF", "#46C46A", "#FF8FA3",
          "#7DE2D1", "#FFC978", "#8CB8FF")

# --- typography ------------------------------------------------------------
FONT_UI = "Microsoft YaHei UI"
FONT_MONO = "Consolas"
FONT_SIZE = {
    "micro": 9,      # table meta, axis ticks
    "tiny": 10,      # dense tables
    "body": 11,      # default UI text
    "body_lg": 12,   # emphasised body
    "section": 14,   # card titles
    "title": 18,     # screen titles
    "display": 24,   # hero metric numerals
}
LINE_HEIGHT = {"micro": 14, "tiny": 16, "body": 18, "section": 22, "title": 26}
TREE_ROW_HEIGHT = 26

# --- spacing (4 px base scale) --------------------------------------------
SPACE = {"1": 4, "2": 8, "3": 12, "4": 16, "6": 24, "8": 32, "12": 48}
GAP = 8          # inside a control
PAD = 16         # panel padding
PAD_LG = 24      # screen padding
RADIUS = 6
TOUCH_MIN = 28   # px; Tk has no 44 px rule, 28 px keeps dense tables usable

# --- measured contrast (WCAG 2.1, sRGB) -----------------------------------
CONTRAST = {
    ("INK", "BG"): 16.00,
    ("INK", "SURFACE"): 14.79,
    ("INK_MUTED", "SURFACE"): 7.29,
    ("INK_DIM", "SURFACE"): 5.03,
    ("ACCENT", "BG"): 9.43,
    ("ACCENT", "RAISED"): 7.89,
    ("AMBER", "BG"): 10.01,
    ("PASS", "SURFACE"): 7.79,
    ("FAIL", "SURFACE"): 6.26,
    ("WARN", "SURFACE"): 7.88,
    ("INFO", "SURFACE"): 7.90,
    ("ACCENT_INK", "ACCENT"): 9.43,
    ("BORDER", "BG"): 1.48,   # decorative hairline, never used for text
}
MIN_TEXT_CONTRAST = 4.5


def luminance(hex_color: str) -> float:
    """WCAG relative luminance of a ``#rrggbb`` colour."""

    body = hex_color.lstrip("#")
    channels = []
    for index in (0, 2, 4):
        value = int(body[index:index + 2], 16) / 255.0
        channels.append(value / 12.92 if value <= 0.04045
                        else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG 2.1 contrast ratio between two ``#rrggbb`` colours."""

    a, b = luminance(foreground), luminance(background)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


def contrast_violations() -> list[str]:
    """Token pairs that fall below AA for normal text (border excluded by design)."""

    problems: list[str] = []
    for (fg_name, bg_name), documented in CONTRAST.items():
        if documented < 3.0:      # documented decorative hairline
            continue
        measured = contrast_ratio(globals()[fg_name], globals()[bg_name])
        if abs(measured - documented) > 0.02:
            problems.append(f"{fg_name}/{bg_name} documented {documented:.2f} "
                            f"but measured {measured:.2f}")
        if measured < MIN_TEXT_CONTRAST:
            problems.append(f"{fg_name}/{bg_name} only {measured:.2f}:1 (< AA 4.5:1)")
    return problems
