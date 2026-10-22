"""Guards for the readability work: one number format, no clipped tables, one handler per job.

Each test here exists because a screen once got it wrong in a way that a human read as a fact:
a limit of 49 790 N printed as ``4.97`` (four orders of magnitude off), a hash column cut to
``ed42f7ff7``, and a spectrum that silently showed the previous run's numbers after two jobs
finished out of order.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from velch.ui import fmt

UI = Path(__file__).resolve().parent.parent / "src" / "velch" / "ui"


# -- one formatter ---------------------------------------------------------

@pytest.mark.parametrize(("value", "unit", "expected"), [
    (0.0, "", "0"),
    (0.0, "N", "0 N"),
    (3089.0, "N", "3089 N"),
    (49790.0, "N", "49.79 kN"),
    (3896.0, "N", "3896 N"),
    (0.4738, "", "0.4738"),
    (4.44e-5, "m", "44.4 µm"),
    (39.3725, "Hz", "39.37 Hz"),
    (1234567.0, "kg", "1.235 Mkg"),
    (0.05, "m/s", "0.05 m/s"),
])
def test_fmt_number_is_one_number_one_text(value: float, unit: str, expected: str) -> None:
    assert fmt.fmt_number(value, unit) == expected


def test_fmt_number_never_invents_a_prefixed_ratio() -> None:
    # A percentage is not a quantity with an SI prefix: "47.38 k%" would be a lie, so a large
    # percentage stays in exponent form instead of borrowing the k prefix.
    assert fmt.fmt_number(47380.0, "%") == "4.738e+04 %"
    assert fmt.fmt_number(47380.0) == "4.738e+04"
    # Inside the plain range it is just the number, prefix or not.
    assert fmt.fmt_number(4738.0, "%") == "4738 %"


def test_fmt_number_reports_missing_data_rather_than_zero() -> None:
    assert fmt.fmt_number(float("nan")) == "—"
    assert fmt.fmt_number(float("inf")) == "—"
    assert fmt.fmt_pair(float("nan"), 1.0) == "—"


def test_fmt_pair_shares_one_scale_so_the_comparison_cannot_be_misread() -> None:
    # The bug this pins: value 3896 N against limit 49 790 N used to render as "3896 / 4.97".
    # One scale for both sides: the value follows the limit into kN, not into a second unit.
    assert fmt.fmt_pair(3896.0, 49790.0, "N") == "3.896 / 49.79 kN"
    assert fmt.fmt_pair(0.06499, 0.8) == "0.06499 / 0.8"


def test_fmt_percent_reads_as_a_percentage() -> None:
    assert fmt.fmt_percent(0.4738) == "47.38 %"
    assert fmt.fmt_percent(0.0) == "0 %"


# -- no interface-level number formatting escapes --------------------------

def test_screens_do_not_carry_their_own_number_formats() -> None:
    """A four-significant-digit format outside :mod:`velch.ui.fmt` read one band three ways."""

    offenders: list[str] = []
    for path in sorted(UI.glob("screen_*.py")) + [UI / "widgets.py", UI / "store.py"]:
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or '"""' in stripped:
                continue
            for pattern in (":.4g}", ":.3g}", ":.4g "):
                if pattern in stripped and "fmt_number" not in stripped:
                    offenders.append(f"{path.name}:{number}: {stripped[:88]}")
    assert offenders == [], "format these through velch.ui.fmt:\n" + "\n".join(offenders)


# -- tables cannot silently clip their last column -------------------------

def test_list_panel_columns_accept_stretch_weights() -> None:
    source = (UI / "widgets.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    panel = next(node for node in ast.walk(tree)
                 if isinstance(node, ast.ClassDef) and node.name == "ListPanel")
    columns = next(node for node in panel.body
                   if isinstance(node, ast.FunctionDef) and node.name == "columns")
    names = {arg.arg for arg in columns.args.args} | {arg.arg for arg in columns.args.kwonlyargs}
    assert "stretch_weights" in names
    body = ast.get_source_segment(source, columns) or ""
    assert "minwidth" in body, "a column that cannot shrink is a column that clips"


def test_case_table_declares_few_columns_that_fit_beside_the_contract_card() -> None:
    """The table only carries what the card cannot: id, duration, DOF.

    The hash, the output step and the start mileage all moved into the contract card, where each
    one gets a full line instead of being clipped past the panel edge.
    """

    text = (UI / "screen_cases.py").read_text(encoding="utf-8")
    module = ast.parse(text)
    columns = next(node for node in module.body
                   if isinstance(node, ast.Assign)
                   and getattr(node.targets[0], "id", "") == "COLUMNS")
    widths = [element.elts[2].value for element in columns.value.elts]
    assert 3 <= len(widths) <= 4, "each extra column costs width the free-DOF number needs"
    assert sum(widths) <= 500, f"declared width {sum(widths)} px does not fit the panel"
    names = {element.elts[1].value for element in columns.value.elts}
    assert not any("哈希" in name for name in names), "the hash belongs to the contract card"
    assert "起始里程" in text, "dropping the column must not drop the value from the card"


# -- one handler per job ---------------------------------------------------

def test_every_job_keeps_its_own_callback() -> None:
    source = (UI / "app.py").read_text(encoding="utf-8")
    assert "_job_handlers[job_id] = done" in source
    assert "_job_handlers.pop(job_id" in source
    assert "_job_done" not in source, "a single slot let a finished job call another job's handler"


def test_zoom_scale_is_a_theme_decision_not_a_screen_constant() -> None:
    """⑦ used to hard-code fontsize=9, so Ctrl+= grew six screens and left one behind."""

    offenders = []
    for path in sorted(UI.glob("screen_*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "fontsize=" in stripped and "theme.FONT_SIZE" not in stripped:
                offenders.append(f"{path.name}:{number}: {stripped[:80]}")
            if "labelsize=" in stripped and "theme.FONT_SIZE" not in stripped:
                offenders.append(f"{path.name}:{number}: {stripped[:80]}")
    assert offenders == [], "screen type sizes must come from theme.FONT_SIZE:\n" + "\n".join(offenders)
