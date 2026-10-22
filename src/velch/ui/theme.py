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
BORDER = "#2A3341"      # hairlines (decorative only, never text)   1.48:1 on BG
BORDER_STRONG = "#3A4657"  # hover/pressed wash for buttons, decorative by design (1.83:1)
#: Focus ring geometry.  A 2 px ring at ACCENT (8.71:1 on SURFACE) is the only
#: non-text cue that a keyboard user is here, so both number and colour are tokens.
FOCUS_THICKNESS = 2
#: Outline of a *control* (entry, combobox, table border). WCAG 1.4.11 wants 3:1 for the
#: boundary that tells you where the field is; BORDER at 1.48:1 does not (visual review
#: measured 1.37:1 against SURFACE and read it as "no field at all").
BORDER_CONTROL = "#6B7A8D"
#: Every second table row. Subtle by intent: it must group rows without competing with
#: the text, so it is a surface difference, not a text-contrast pair.
ROW_ALT = "#191F27"

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
#: The declared sizes are the 100 % scale.  ``set_scale()`` rewrites ``FONT_SIZE`` from this table,
#: so a HiDPI screen (or a projector) can be served without touching a single screen file.
# One notch up from the first design: the layout subtraction (four columns instead of
# six, horizontal scroll where columns still overflow, chip strip wrapped) bought the
# room, and 11 px body was the single most repeated complaint in the visual review.
BASE_FONT_SIZE = {
    "micro": 10,     # table meta, axis ticks (Chinese sentences never use this)
    "tiny": 11,      # dense tables
    "body": 12,      # default UI text
    "body_lg": 13,   # emphasised body
    "section": 15,   # card titles
    "title": 20,     # screen titles
    "display": 26,   # hero metric numerals
}
FONT_SIZE = dict(BASE_FONT_SIZE)
LINE_HEIGHT = {"micro": 15, "tiny": 17, "body": 19, "section": 23, "title": 27}
TREE_ROW_HEIGHT = 28

#: Current display scale.  ``1.0`` is the design size; the UI offers 0.9 … 1.6 so the same layout
#: stays usable on a 1280 px laptop panel and on a 4 K monitor without a second theme.
SCALE = 1.0
SCALE_MIN = 0.9
SCALE_MAX = 1.6
SCALE_STEP = 0.1


def set_scale(factor: float) -> float:
    """Rescale every typographic token; returns the scale actually applied.

    Only sizes are scaled, not paddings: growing the font inside the same 4 px grid keeps the
    layout honest (a control grows because its text did), while scaling padding too would make a
    1.6× UI spill outside an 1180 px window.
    """

    global SCALE, TREE_ROW_HEIGHT, LINE_HEIGHT
    factor = max(SCALE_MIN, min(SCALE_MAX, round(float(factor), 2)))
    SCALE = factor
    for key, base in BASE_FONT_SIZE.items():
        FONT_SIZE[key] = max(8, round(base * factor))
    for key in LINE_HEIGHT:
        LINE_HEIGHT[key] = max(12, round(LINE_HEIGHT[key] * factor))
    TREE_ROW_HEIGHT = max(26, round(28 * factor))
    return factor


def scale_from_environment() -> float:
    """``VELCH_UI_SCALE`` for a launcher, so a shortcut can pin the size its owner prefers."""

    import os

    raw = os.environ.get("VELCH_UI_SCALE", "").strip()
    if not raw:
        return SCALE
    try:
        return set_scale(float(raw))
    except ValueError:
        return SCALE

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
    ("BORDER_CONTROL", "SURFACE"): 3.99,   # non-text boundary of a control
    ("BORDER_CONTROL", "BG"): 4.32,
    ("INK", "ROW_ALT"): 14.05,             # text on a striped row
    ("INK_MUTED", "ROW_ALT"): 6.92,
}
MIN_TEXT_CONTRAST = 4.5
#: WCAG 1.4.11: the boundary of a control (not its text) must reach 3:1.
MIN_NON_TEXT_CONTRAST = 3.0


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


#: Pairs that describe a *boundary* rather than text: WCAG 1.4.11 asks 3:1 for these, and holding
#: them to the 4.5:1 text rule would reject a perfectly legible control outline.
NON_TEXT_PAIRS = frozenset({
    ("BORDER_CONTROL", "SURFACE"), ("BORDER_CONTROL", "BG"), ("BORDER_CONTROL", "RAISED"),
    # The focus ring and the semantic states are not text either: they carry state, so 1.4.11's
    # 3:1 applies.  Measured 6.26–9.43:1 on 2026-10-23 -- declared here so a palette change cannot
    # quietly drop them below the floor.
    ("ACCENT", "SURFACE"), ("ACCENT", "BG"), ("ACCENT", "RAISED"),
    ("WARN", "SURFACE"), ("FAIL", "SURFACE"), ("PASS", "SURFACE"),
})
#: Purely decorative separators.  WCAG 1.4.11 exempts these: a divider between cards carries no
#: state and no boundary, so 1.48:1 is a design choice rather than a defect.
DECORATIVE_PAIRS = frozenset({("BORDER", "BG")})


def contrast_violations() -> list[str]:
    """Token pairs that miss their WCAG threshold (text 4.5:1, control boundary 3:1)."""

    problems: list[str] = []
    for (fg_name, bg_name), documented in CONTRAST.items():
        measured = contrast_ratio(globals()[fg_name], globals()[bg_name])
        if abs(measured - documented) > 0.02:
            problems.append(f"{fg_name}/{bg_name} documented {documented:.2f} "
                            f"but measured {measured:.2f}")
        if (fg_name, bg_name) in DECORATIVE_PAIRS:
            continue
        if (fg_name, bg_name) in NON_TEXT_PAIRS:
            if measured < MIN_NON_TEXT_CONTRAST:
                problems.append(f"{fg_name}/{bg_name} only {measured:.2f}:1 "
                                f"(< 1.4.11 3:1 for a control boundary)")
            continue
        if measured < MIN_TEXT_CONTRAST:
            problems.append(f"{fg_name}/{bg_name} only {measured:.2f}:1 (< AA 4.5:1)")
    return problems
