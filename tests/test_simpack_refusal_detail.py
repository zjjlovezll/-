"""A refusal must carry its numbers, not only a sentence.

O008's whole point is that this model cannot supply both rails. A caller (or a script) needs
``detail.other_side_stations`` to decide "use --keep-profiles", and parsing Chinese prose to get it
is not a contract.
"""

from __future__ import annotations

import json

import pytest

from velch import cli, simpack_case
from velch.simpack_case import LATERAL_GAUGE_LIMIT_MM, SimpackCaseError

from test_simpack_crown import TEMPLATE, _gauge_catalog


@pytest.fixture()
def refused(tmp_path, monkeypatch):
    """The real one-sided import on the 74-86 m gauge catalog, refused as a gauge change."""

    monkeypatch.setattr(simpack_case, "_crown_lateral_delta",
                        lambda entry, template: 0.103 if entry.side == "right" else None)
    catalog = _gauge_catalog(tmp_path)
    with pytest.raises(SimpackCaseError) as caught:
        simpack_case.build_case(catalog_path=catalog, template_path=TEMPLATE,
                                out_path=tmp_path / "out.json", side="right", rail=None,
                                sample=None, x_start_m=80.0, duration_s=0.05,
                                keep_profiles=False, import_lateral=True,
                                allow_gauge_change=False)
    return caught.value, catalog


def test_the_gauge_refusal_carries_the_numbers(refused):
    error, _catalog = refused

    detail = error.detail
    assert detail["code"] == "lateral_gauge_change"
    assert detail["gauge_mm"] == pytest.approx(103.0, abs=0.05)
    assert detail["other_side_stations"] == 0
    assert detail["both_sides_possible"] is False
    assert detail["limit_mm"] == LATERAL_GAUGE_LIMIT_MM
    assert detail["ways_out"], "a refusal has to name a way out"


def test_the_cli_prints_that_detail_as_json(refused, capsys, tmp_path):
    _error, catalog = refused

    code = cli.main(["simpack-case", "--catalog", str(catalog), "--template", str(TEMPLATE),
                     "--out", str(tmp_path / "cli_out.json"), "--x-start", "80",
                     "--duration", "0.05", "--sample", "40", "--side", "right",
                     "--import-lateral"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["status"] == "failed"
    assert payload["detail"]["code"] == "lateral_gauge_change"


def test_other_failures_stay_plain(capsys):
    """A missing catalog must not pretend to have gauge numbers."""

    code = cli.main(["simpack-case", "--catalog", "no-such-catalog.json",
                     "--template", "no-such-template.json", "--out", "out.json",
                     "--x-start", "1"])

    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["status"] == "failed"
    assert "detail" not in payload
