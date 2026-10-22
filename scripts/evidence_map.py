"""One page that says, per objective item, how to re-check it and what the last result was.

The point is not documentation for its own sake: after fifty rounds the evidence exists but is
scattered over fifty changelog entries, so "is this shippable?" can only be answered by reading all
of them.  This script **runs** the cheap checks and writes what they said, with the commit that last
touched each piece of evidence, so the page cannot drift from the repository without the test that
reads it failing.

    python -X utf8 scripts/evidence_map.py            # rewrite docs/EVIDENCE_MAP.md
    python -X utf8 scripts/evidence_map.py --check    # verify references resolve, write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src"
TARGET = ROOT / "docs" / "EVIDENCE_MAP.md"
REPORTS = ROOT / "reports"

#: objective item -> (what proves it, the command, the artefacts that hold the detail)
ITEMS: list[tuple[str, str, str, str, list[str]]] = [
    ("① 代码整理与稳定",
     "架构规则、`TODO/FIXME` 计数、文档索引与版本一致性都由测试守着",
     "python -X utf8 -m pytest tests/test_architecture_rules.py tests/test_docs_index.py -q",
     "全绿；索引覆盖 `docs/*.md` 每一篇；`__version__` 有对应发布说明",
     ["docs/ARCHITECTURE_2026-10-21.md", "docs/CHANGELOG_DOCS.md", "tests/test_docs_index.py"]),
    ("② 全仓 bug 清理",
     "缺陷账本归零：已修记 B 编号，仍开记 O 编号并写明理由",
     "python -X utf8 scripts/auto_accept.py --skip-run",
     "四步全 PASS（tests / doctor / contract / invariants）",
     ["docs/BUGS.md", "scripts/auto_accept.py"]),
    ("③ 界面美观与可读性",
     "截断由布局测试量出来，不是靠看图；对比度由主题测试算出来",
     "python -X utf8 -m pytest tests/test_ui_layout.py tests/test_ui_scale.py -q",
     "7 屏 × 100%/130% 无被裁控件；`contrast_violations() == []`",
     ["tests/test_ui_layout.py", "tests/test_ui_scale.py", "docs/UI_READABILITY_2026-10-22.md"]),
    ("④ 安装包",
     "onedir 双 exe（窗口版 + 控制台版），装完能双击运行，并在包内跑一次真实算例",
     "python -X utf8 packaging/build_installer.py && python -X utf8 packaging/smoke_test.py",
     "冒烟 6 步全 PASS：selftest / cli-run / missing-corpus / agent-contract / unicode-path / install-dir-untouched",
     ["docs/PACKAGING_2026-10-22.md", "packaging/smoke_test.py", "packaging/Velch.spec"]),
    ("⑤ 读取 Simpack 模型",
     "只读几何导入（catalog → case），导入后由静平衡决定能不能算",
     "python -X utf8 -m velch inspect-simpack-track <db>/substructure/<x>.spck --model-root <db> --output catalog.json",
     "`geometry_readable = true`、`missing_profile_references = 0`；派生算例 `seats: true` 后跑出 `numerically_checked`（加 `--with-run` 才跑这一段）",
     ["docs/SIMPACK_IMPORT_2026-10-22.md", "docs/SIMPACK_COMPARE_2026-10-23.md",
      "src/velch/simpack_case.py"]),
]

#: the promise every release note repeats, and the gate that now enforces it
INVARIANT_ITEM = ("物理数值不变",
                  "复算门：归档 2401 帧 + 一次 `--fast` 现跑，与 committed 参考值比较",
                  "python -X utf8 scripts/physics_invariants.py",
                  "VERDICT: UNCHANGED",
                  ["docs/PHYSICS_INVARIANTS.md", "docs/physics_invariants.json",
                   "scripts/physics_invariants.py"])


def _run(command: list[str], timeout: float = 900.0) -> tuple[int, str]:
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", cwd=str(ROOT), timeout=timeout,
                               env={**__import__("os").environ, "PYTHONPATH": str(SOURCE)})
    return completed.returncode, (completed.stdout + completed.stderr)


def _last_commit(path: str) -> str:
    completed = subprocess.run(["git", "log", "-1", "--format=%h %ad", "--date=short", "--", path],
                               capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))
    text = completed.stdout.strip()
    return text or "（未提交）"


def _counts() -> str:
    code, output = _run([sys.executable, "-X", "utf8", "-m", "pytest", "tests", "-q",
                         "--basetemp", str(Path(__import__("os").environ.get("TEMP", ".")) / "velch_ev")])
    match = re.search(r"(\d+) passed(?:, (\d+) skipped)?", output)
    if not match:
        return f"pytest 未跑通（exit {code}）"
    passed, skipped = match.group(1), match.group(2) or "0"
    return f"**{passed} passed, {skipped} skipped**"


def _gate() -> str:
    code, output = _run([sys.executable, "-X", "utf8", "scripts/auto_accept.py", "--skip-run"])
    verdict = "ACCEPT" if "verdict: ACCEPT" in output else "REJECT"
    steps = re.findall(r"(PASS|FAIL|SKIP)\s+(?:[\d.]+s?|-)\s+(\w[\w-]*)", output)
    listed = "、".join(f"{name} {state}" for state, name in steps) or "（无步骤输出）"
    return f"`{verdict}` — {listed}（exit {code}）"


def _invariants() -> str:
    code, output = _run([sys.executable, "-X", "utf8", "scripts/physics_invariants.py", "--no-run"])
    line = "UNCHANGED" if "UNCHANGED" in output else "DRIFT"
    peak = re.search(r"整程峰值 ([\d.]+) kN", output)
    return f"`{line}`" + (f"（整程峰值 {peak.group(1)} kN）" if peak else "") + f"，exit {code}"


def _smoke() -> str:
    files = sorted(REPORTS.glob("packaging_smoke_*.json"))
    if not files:
        return "尚无冒烟报告"
    payload = json.loads(files[-1].read_text(encoding="utf-8"))
    steps = payload.get("steps") or []
    failed = sum(1 for step in steps if not step.get("ok"))
    skipped = sum(1 for step in steps if step.get("skipped"))
    return (f"`{payload.get('verdict')}` · {len(steps)} 步 · 失败 {failed} · 跳过 {skipped}"
            f"（`{files[-1].name}`）")


def _pytest_of(command: str) -> str:
    """Run one item's own pytest command -- quoting the whole-suite count for four rows is a lie."""

    parts = command.split()
    if parts[:4] != ["python", "-X", "utf8", "-m"]:
        return "（命令无法直接运行）"
    code, output = _run([sys.executable, *parts[1:], "--basetemp",
                         str(Path(__import__("os").environ.get("TEMP", ".")) / "velch_ev_item")])
    match = re.search(r"(\d+) passed(?:, (\d+) skipped)?", output)
    if not match:
        return f"未跑通（exit {code}）"
    passed, skipped = match.group(1), match.group(2) or "0"
    failures = re.search(r"(\d+) failed", output)
    tail = f"，失败 {failures.group(1)}" if failures else ""
    return f"**{passed} passed, {skipped} skipped**{tail}（exit {code}）"


def _simpack(with_run: bool = False) -> str:
    """Import the model named by ``VELCH_SIMPACK_MODEL``; say so plainly when unset."""

    model = os.environ.get("VELCH_SIMPACK_MODEL", "").strip()
    root = os.environ.get("VELCH_SIMPACK_ROOT", "").strip()
    if not model or not root:
        return "未设置 `VELCH_SIMPACK_MODEL`/`VELCH_SIMPACK_ROOT`（本机未挂模型；细节见文档）"
    work = Path(__import__("tempfile").mkdtemp(prefix="velch_evidence_"))
    catalog = work / "catalog.json"
    code, _output = _run([sys.executable, "-X", "utf8", "-m", "velch", "inspect-simpack-track",
                          model, "--model-root", root, "--output", str(catalog)], timeout=600.0)
    if code != 0 or not catalog.is_file():
        return f"catalog 生成失败（exit {code}）"
    summary = (json.loads(catalog.read_text(encoding="utf-8")).get("summary") or {})
    line = (f"`geometry_readable = {summary.get('geometry_readable')}`、"
            f"`missing_profile_references = {summary.get('missing_profile_references')}`、"
            f"`profile_references = {summary.get('profile_references')}`")
    if not with_run:
        return line
    template = Path(os.environ.get("VELCH_EVIDENCE_TEMPLATE", "").strip())
    if not template.is_file():
        return line + "；`--with-run` 需要 `VELCH_EVIDENCE_TEMPLATE` 指向模板算例"
    case = work / "case_evidence.json"
    code, output = _run([sys.executable, "-X", "utf8", "-m", "velch", "simpack-case",
                         "--catalog", str(catalog), "--template", str(template),
                         "--out", str(case), "--x-start", "82", "--duration", "0.05",
                         "--sample", "400"], timeout=900.0)
    if code != 0 or not case.is_file():
        return line + f"；派生失败（exit {code}）"
    seating = (json.loads(output[output.index("{"):output.rindex("}") + 1])
               .get("seating") or {})
    if not seating.get("seats"):
        return line + f"；派生算例没坐上：{seating.get('reason', '')[:60]}"
    out = work / "run"
    code, _output = _run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle",
                          str(case), "--output", str(out), "--fast"], timeout=900.0)
    manifest = out / "manifest.json"
    if code != 0 or not manifest.is_file():
        return line + f"；现跑失败（exit {code}）"
    payload = json.loads(manifest.read_text(encoding="utf-8")).get("summary") or {}
    gates = payload.get("gates") or {}
    return (line + f"；`seats: true`（{len(seating.get('per_contact_kn') or {})} 个接触、"
            f"最大侵入 {seating.get('max_penetration_um')} µm）；现跑 "
            f"`{payload.get('result_status')}`、门 {sum(1 for v in gates.values() if v)}/"
            f"{len(gates)}、`nfev {payload.get('solver', {}).get('nfev')}`")


def build(with_run: bool = False) -> str:
    counts = _counts()
    gate = _gate()
    invariants = _invariants()
    smoke = _smoke()
    tags = subprocess.run(["git", "tag", "--list"], capture_output=True, text=True,
                          encoding="utf-8", cwd=str(ROOT)).stdout.split()
    head = subprocess.run(["git", "log", "-1", "--format=%h"], capture_output=True, text=True,
                          encoding="utf-8", cwd=str(ROOT)).stdout.strip()

    lines = [
        "# 证据地图：这一版凭什么可以说「可以发布」",
        "",
        "由 `scripts/evidence_map.py` 生成——里面的结果都是**跑出来的**，不是抄来的。"
        "`tests/test_evidence_map.py` 会检查这里引用的每个文件都还在、每条命令都能解析，"
        "所以这一页没法悄悄过期。",
        "",
        f"- 当前提交 **`{head}`**",
        f"- 标签 {len(tags)} 个：{'、'.join(f'`{t}`' for t in tags[-4:])} …",
        f"- 全仓测试 {counts}",
        "",
        "## 逐项证据",
        "",
        "| 目标分项 | 凭什么 | 复核命令 | 最近一次结果 |",
        "|---|---|---|---|",
    ]
    results = {"①": _pytest_of(ITEMS[0][2]), "②": gate, "③": _pytest_of(ITEMS[2][2]),
               "④": smoke, "⑤": _simpack(with_run)}
    for name, claim, command, expected, _artefacts in ITEMS:
        result = results.get(name[:1], "见下设文档")
        lines.append(f"| **{name}** | {claim} | `{command}` | {result}<br>期望：{expected} |")
    name, claim, command, expected, _ = INVARIANT_ITEM
    lines.append(f"| **{name}** | {claim} | `{command}` | {invariants}<br>期望：{expected} |")

    lines += ["", "## 证据文件与最后一次改动", "",
              "| 文件 | 内容 | 最后改动 |", "|---|---|---|"]
    for number, (_name, _claim, _command, _expected, artefacts) in enumerate(ITEMS, start=1):
        for artefact in artefacts:
            lines.append(f"| [`{artefact}`](../{artefact}) | 分项 {number} 的细节 | `{_last_commit(artefact)}` |")
    for artefact in INVARIANT_ITEM[4]:
        lines.append(f"| [`{artefact}`](../{artefact}) | 物理不变量 | `{_last_commit(artefact)}` |")

    lines += [
        "",
        "## 这道门怎么进提交",
        "",
        "`Velch/.githooks/pre-commit` → `scripts/auto_accept.py --skip-run`（约 44 s：测试 43 s + "
        "doctor + 契约 + 不变量）。启用一次即可：",
        "",
        "```powershell",
        "git config core.hooksPath .githooks",
        "```",
        "",
        "`python scripts/auto_accept.py`（不加 `--skip-run`）会再加一步端到端：派生算例 → 真跑 "
        "0.05 s → 读 manifest。安装包另有 `packaging/smoke_test.py` 六步，跑的是**冻结后的 exe**。",
        "",
        "## 不在这张表里的东西",
        "",
        "- 与实测数据的标定：没有同一道岔的实测与模型配对，`physics_validation_status` 仍是 "
        "`unvalidated_against_measurement_or_Simpack`。",
        "- 与 Simpack 的定量关系只到**逐点差异报告**（`docs/SIMPACK_COMPARE_2026-10-23.md`），"
        "不改任何默认值。",
        "- 包未签名；只读安装的 ACL 情形需按 `docs/PACKAGING_2026-10-22.md` 末尾人工验一遍（O009）。",
    ]
    return "\n".join(lines) + "\n"


def check() -> int:
    if not TARGET.is_file():
        print("EVIDENCE_MAP.md 不存在：先跑一次不带 --check 的")
        return 1
    text = TARGET.read_text(encoding="utf-8")
    problems: list[str] = []
    for target in re.findall(r"\]\(\.\./([^)]+)\)", text):
        if not (ROOT / target).exists():
            problems.append(f"引用不存在：{target}")
    for command in re.findall(r"`(python -X utf8 [^`]+)`", text):
        script = command.split()
        for token in script:
            if token.startswith("scripts/") or token.startswith("packaging/"):
                if not (ROOT / token).exists():
                    problems.append(f"命令里的脚本不存在：{token}")
    for name, *_rest in ITEMS:
        if name not in text:
            problems.append(f"缺少分项：{name}")
    if problems:
        print("EVIDENCE MAP: STALE")
        for problem in problems:
            print("  -", problem)
        return 2
    print("EVIDENCE MAP: OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="生成/校验证据地图")
    parser.add_argument("--check", action="store_true", help="只校验，不重写")
    parser.add_argument("--with-run", action="store_true",
                        help="⑤ 也跑一次导入后的算例（约 10 s，需要 VELCH_EVIDENCE_TEMPLATE）")
    arguments = parser.parse_args()
    if arguments.check:
        return check()
    TARGET.write_text(build(arguments.with_run), encoding="utf-8", newline="\n")
    print(f"已写入 {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
