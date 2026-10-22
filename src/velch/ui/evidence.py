"""把"这版跑过什么"变成一句话，挂在界面状态栏上。

两样东西是发布前的证据：`reports/packaging_smoke_*.json`（装完之后能不能跑）与
`reports/PHYSICS_INVARIANTS_LATEST.md`（物理数值有没有漂）。它们本来是磁盘上的文件，
需要人记得去翻——所以这里只做一件事：**找到最新的一份，缩成一句话，标上时间**。

读不到就返回 ``None``，界面显示"未找到"，不要假装跑过。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SMOKE_GLOB = "packaging_smoke_*.json"
INVARIANTS_NAME = "PHYSICS_INVARIANTS_LATEST.md"


@dataclass(frozen=True)
class SmokeFacts:
    name: str
    verdict: str
    steps: int
    failed: int
    skipped: int
    when: str

    @property
    def ok(self) -> bool:
        return self.verdict.upper() == "ACCEPT" and self.failed == 0


@dataclass(frozen=True)
class InvariantFacts:
    name: str
    verdict: str
    when: str

    @property
    def ok(self) -> bool:
        text = self.verdict.upper()
        return "UNCHANGED" in text or "未移动" in self.verdict


def _reports_dir() -> Path:
    from ..data_root import repository_root

    return repository_root() / "reports"


def latest_smoke(reports: Path | None = None) -> SmokeFacts | None:
    """最新一份冒烟报告。坏文件跳过，不要因为解析不了就让整条证据消失。"""

    folder = reports or _reports_dir()
    candidates = sorted(folder.glob(SMOKE_GLOB), key=lambda path: path.stat().st_mtime,
                        reverse=True)
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        steps = payload.get("steps") or []
        if not isinstance(steps, list):
            continue
        failed = sum(1 for step in steps if isinstance(step, dict) and not step.get("ok", False))
        skipped = sum(1 for step in steps if isinstance(step, dict) and step.get("skipped"))
        return SmokeFacts(
            name=path.name,
            verdict=str(payload.get("verdict", "?")),
            steps=len(steps),
            failed=failed,
            skipped=skipped,
            when=str(payload.get("finished", "")),
        )
    return None


def latest_invariants(reports: Path | None = None) -> InvariantFacts | None:
    """最新一份物理不变量报告；结论取第一行含 ``VERDICT`` 或"未移动"的行。"""

    folder = reports or _reports_dir()
    path = folder / INVARIANTS_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    verdict = ""
    when = ""
    for line in text.splitlines():
        stripped = line.strip().strip("*` ")
        if not when and "生成" in stripped and ":" in stripped:
            when = stripped
        if not verdict and ("VERDICT" in stripped.upper() or "未移动" in stripped):
            verdict = stripped
        if verdict and when:
            break
    if not verdict:
        return None
    return InvariantFacts(name=path.name, verdict=verdict, when=when)


def summary_text(smoke: SmokeFacts | None, invariants: InvariantFacts | None) -> tuple[str, str]:
    """返回 ``(文案, 语气)``，语气取 ``pass``/``warn``/``fail`` 之一。"""

    if smoke is None and invariants is None:
        return "证据：未找到冒烟与不变量报告（跑 scripts/auto_accept.py 或 packaging/smoke_test.py）", "warn"

    parts: list[str] = []
    tone = "pass"
    if smoke is None:
        parts.append("冒烟：未找到")
        tone = "warn"
    else:
        label = f"冒烟 {smoke.verdict} · {smoke.steps} 步"
        if smoke.failed:
            label += f" · 失败 {smoke.failed}"
        if smoke.skipped:
            label += f" · 跳过 {smoke.skipped}"
        parts.append(label)
        if not smoke.ok:
            tone = "fail"

    if invariants is None:
        parts.append("不变量：未找到")
        tone = "warn" if tone == "pass" else tone
    else:
        short = "未移动" if invariants.ok else "发现漂移"
        parts.append(f"不变量 {short}")
        if not invariants.ok:
            tone = "fail"

    return "证据：" + " ｜ ".join(parts), tone
