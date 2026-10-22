"""Guard tests for the imported-surface drop: refuse, warn, or let the caller override.

The measurement itself is patched here on purpose.  A synthetic catalog cannot produce a realistic
"the switch blade sits 12 mm low" section without inventing a whole PRR, and what these tests are
about is the decision the builder makes once a number exists: refuse above the limit, warn between
3 mm and the limit, and record which of the two happened in the sidecar.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from velch import simpack_case
from velch.simpack_case import SimpackCaseError

# Reuse the synthetic catalog/template builders rather than duplicating them.  ``tests`` is not a
# package (no ``__init__.py``), so this imports the sibling module by its bare name.
from test_simpack_case import _catalog, _template


def _build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, delta: tuple[float, float] | None,
           **kwargs: object):
    monkeypatch.setattr(simpack_case, "_surface_delta_mm", lambda *a, **k: delta)
    return simpack_case.build_case(
        catalog_path=_catalog(tmp_path),
        template_path=_template(tmp_path),
        out_path=tmp_path / "case.json",
        side="right",
        x_start_m=0.0,
        **kwargs,
    )


def test_a_drop_beyond_the_limit_is_refused_with_the_numbers_it_measured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(SimpackCaseError) as excinfo:
        _build(tmp_path, monkeypatch, (11.91, 56.569))

    message = str(excinfo.value)
    assert "11.91" in message and "56.569" in message
    assert "8.0" in message, "the limit in force has to be visible in the refusal"
    assert "5.18" in message, "the measured boundary belongs in the message, not only in a doc"
    assert not (tmp_path / "case.json").exists()


def test_a_moderate_drop_builds_and_says_so_in_the_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _build(tmp_path, monkeypatch, (5.18, 80.004))

    sidecar = json.loads(Path(result.sidecar_path).read_text(encoding="utf-8"))
    delta = sidecar["surface_delta_mm"]
    assert delta["max_abs"] == pytest.approx(5.18, abs=1e-3)
    assert delta["at_m"] == pytest.approx(80.004, abs=1e-3)
    warning = sidecar["surface_drop_warning"]
    assert warning and "5.18" in warning
    assert sidecar["surface_drop_allowed"] is False


def test_a_small_drop_warns_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _build(tmp_path, monkeypatch, (0.4, 84.0))

    sidecar = json.loads(Path(result.sidecar_path).read_text(encoding="utf-8"))
    assert sidecar["surface_delta_mm"]["max_abs"] == pytest.approx(0.4, abs=1e-3)
    assert sidecar["surface_drop_warning"] is None


def test_allow_surface_drop_overrides_the_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _build(tmp_path, monkeypatch, (15.85, 56.642), allow_surface_drop=True)

    sidecar = json.loads(Path(result.sidecar_path).read_text(encoding="utf-8"))
    assert sidecar["surface_drop_allowed"] is True
    assert sidecar["surface_delta_mm"]["max_abs"] == pytest.approx(15.85, abs=1e-3)
    assert (tmp_path / "case.json").exists()


def test_an_unmeasurable_surface_is_not_a_clean_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """"No measurement" must not read as "no drop": the guard records None and lets the build go."""
    result = _build(tmp_path, monkeypatch, None)

    sidecar = json.loads(Path(result.sidecar_path).read_text(encoding="utf-8"))
    assert sidecar["surface_delta_mm"] is None
    assert sidecar["surface_drop_warning"] is None
