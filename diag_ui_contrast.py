"""Measure WCAG contrast for the planned UI token pairs (no external deps)."""


def srgb_to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)


def ratio(a: str, b: str) -> float:
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


BG = "#0E1116"
SURF = "#151A21"
RAISED = "#1C232C"
PAIRS = [
    ("ink #E6EDF3", "#E6EDF3", BG),
    ("ink #E6EDF3 on surface", "#E6EDF3", SURF),
    ("muted #9BA9B8 on surface", "#9BA9B8", SURF),
    ("dim #7D8B9C on surface", "#7D8B9C", SURF),
    ("accent #4CC2FF on bg", "#4CC2FF", BG),
    ("accent #4CC2FF on raised", "#4CC2FF", RAISED),
    ("amber #F2B134 on bg", "#F2B134", BG),
    ("pass #46C46A on surface", "#46C46A", SURF),
    ("fail #FF6B5E on surface", "#FF6B5E", SURF),
    ("warn #E0A33A on surface", "#E0A33A", SURF),
    ("info #6FB2FF on surface", "#6FB2FF", SURF),
    ("fg on accent #4CC2FF", "#06121B", "#4CC2FF"),
    ("fg on pass #46C46A", "#04170A", "#46C46A"),
    ("fg on fail #FF6B5E", "#1A0605", "#FF6B5E"),
    ("border #2A3341 on bg", "#2A3341", BG),
]
for name, fg, bg in PAIRS:
    r = ratio(fg, bg)
    tag = "AA-text" if r >= 4.5 else ("AA-large/UI" if r >= 3.0 else "decorative")
    print(f"{name:34s} {r:5.2f}:1  {tag}")
