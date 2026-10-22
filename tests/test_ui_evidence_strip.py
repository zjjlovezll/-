"""Evidence-strip tests: newest report wins, a broken file is skipped, and nothing is invented."""
from __future__ import annotations

import json
from pathlib import Path

from velch.ui.evidence import latest_invariants, latest_smoke, summary_text


def _smoke(folder: Path, name: str, verdict: str, *, failed: int = 0, skipped: int = 0,
           steps: int = 8, mtime: float = 0.0) -> Path:
    payload = {
        "verdict": verdict,
        "finished": "2026-10-23T03:00:02+08:00",
        "steps": [{"name": f"s{index}", "ok": index >= failed, "skipped": index < skipped}
                  for index in range(steps)],
    }
    path = folder / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    if mtime:
        import os

        os.utime(path, (mtime, mtime))
    return path


def _invariants(folder: Path, *, verdict: str = "VERDICT: UNCHANGED", when: str = "生成：2026-10-23") -> Path:
    path = folder / "PHYSICS_INVARIANTS_LATEST.md"
    path.write_text(f"# 物理不变量\n\n{when}\n\n**{verdict}**\n", encoding="utf-8")
    return path


def test_the_newest_report_wins(tmp_path) -> None:
    _smoke(tmp_path, "packaging_smoke_old.json", "REJECT", failed=2, mtime=1_000.0)
    _smoke(tmp_path, "packaging_smoke_new.json", "ACCEPT", mtime=2_000.0)

    facts = latest_smoke(tmp_path)

    assert facts is not None
    assert facts.name == "packaging_smoke_new.json"
    assert facts.verdict == "ACCEPT"
    assert facts.ok is True


def test_a_broken_report_is_skipped_not_fatal(tmp_path) -> None:
    (tmp_path / "packaging_smoke_broken.json").write_text("{not json", encoding="utf-8")
    _smoke(tmp_path, "packaging_smoke_good.json", "ACCEPT", mtime=1_000.0)

    facts = latest_smoke(tmp_path)

    assert facts is not None and facts.verdict == "ACCEPT"


def test_a_failed_step_makes_the_report_not_ok(tmp_path) -> None:
    _smoke(tmp_path, "packaging_smoke_x.json", "ACCEPT", failed=1)

    facts = latest_smoke(tmp_path)

    assert facts is not None and facts.failed == 1 and facts.ok is False


def test_missing_reports_are_none_not_zeroed(tmp_path) -> None:
    assert latest_smoke(tmp_path) is None
    assert latest_invariants(tmp_path) is None


def test_invariants_verdict_and_tone(tmp_path) -> None:
    _invariants(tmp_path, verdict="VERDICT: UNCHANGED")
    ok = latest_invariants(tmp_path)
    assert ok is not None and ok.ok is True

    _invariants(tmp_path, verdict="VERDICT: DRIFT in axle2_right (12 %)")
    drifted = latest_invariants(tmp_path)
    assert drifted is not None and drifted.ok is False

    text, tone = summary_text(None, drifted)
    assert tone == "fail"
    assert "发现漂移" in text


def test_the_strip_says_what_is_missing(tmp_path) -> None:
    text, tone = summary_text(None, None)

    assert tone == "warn"
    assert "未找到" in text


def test_the_strip_names_skipped_steps(tmp_path) -> None:
    _smoke(tmp_path, "packaging_smoke_s.json", "ACCEPT", skipped=1)
    text, tone = summary_text(latest_smoke(tmp_path), None)

    assert tone == "warn", "不变量没找到时不能报 pass"
    assert "跳过 1" in text


def test_a_green_pair_reads_as_pass(tmp_path) -> None:
    _smoke(tmp_path, "packaging_smoke_ok.json", "ACCEPT")
    _invariants(tmp_path)

    text, tone = summary_text(latest_smoke(tmp_path), latest_invariants(tmp_path))

    assert tone == "pass"
    assert "冒烟 ACCEPT" in text and "不变量 未移动" in text
