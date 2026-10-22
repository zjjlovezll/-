"""First-run self-check: does this copy of Velch have what it needs to do its job?

A packaged build ships without the 1.4 GB case corpus, so "it does not work" is usually one of five
things: no corpus, no matplotlib, no Tk, a Simpack path that no longer exists, or a directory the
process cannot write to. This module checks those five and says which one it is -- in Chinese,
because the person reading it is the one who just double-clicked the exe.

Design notes:

* ``collect()`` returns plain records and never raises; ``report()`` formats them; ``main()`` decides
  the exit code. That split is what makes the checks testable without a display or a corpus.
* Every failed check carries a ``fix``: a path, an environment variable, or a command. A check that
  only says "failed" is a check that moves the problem to the reader.
* Nothing here reads the 1.4 GB corpus beyond counting files, and nothing imports the solver.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

FAIL = "fail"
WARN = "warn"
PASS = "pass"


@dataclass(frozen=True)
class Check:
    """One line of the self-check."""

    name: str
    status: str
    detail: str
    fix: str = ""

    @property
    def ok(self) -> bool:
        return self.status != FAIL


def _module_missing(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is None
    except (ImportError, AttributeError, ValueError):
        return True


def _docs_roots() -> list[Path]:
    """Every folder that could hold ``docs/``: the checkout, and the build's two levels.

    PyInstaller 6 puts ``datas`` under ``_internal``, so a frozen build's notes live at
    ``<install>/_internal/docs`` while the exe sits at ``<install>``. ``parents[2]`` happened to
    work for one layout and not the other, so ask all of them instead of guessing.
    """

    file = Path(__file__).resolve()
    roots: list[Path] = [parent for parent in file.parents[:3]]
    try:
        from velch.data_root import frozen_install_root, is_frozen

        if is_frozen():
            roots.insert(0, frozen_install_root())
            roots.insert(1, frozen_install_root() / "_internal")
    except Exception:  # noqa: BLE001 - a missing helper must not break the check
        pass
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def _version_check() -> Check:
    from velch import __version__

    notes = next((root / "docs" / f"RELEASE_NOTES_{__version__}.md"
                  for root in _docs_roots()
                  if (root / "docs" / f"RELEASE_NOTES_{__version__}.md").is_file()), None)
    if notes is not None:
        return Check("版本与发布说明", PASS, f"{__version__}，发布说明在位")
    if os.environ.get("VELCH_ALLOW_UNVERSIONED_DOCS"):
        return Check("版本与发布说明", WARN, f"{__version__}，缺少发布说明（已按环境变量放行）")
    return Check("版本与发布说明", WARN, f"{__version__}，缺少 RELEASE_NOTES_{__version__}.md",
                 "发布前补 docs/RELEASE_NOTES_<version>.md，或用 VELCH_ALLOW_UNVERSIONED_DOCS=1 放行")


def _corpus_check() -> Check:
    from velch import data_root as root_module

    try:
        case_dir = root_module.case_dir()
    except Exception as error:  # noqa: BLE001 - the whole point is to report, not raise
        return Check("算例语料", FAIL, f"{type(error).__name__}: {error}", root_module.hint())
    try:
        count = sum(1 for _ in case_dir.glob("case_*.json"))
    except OSError as error:
        return Check("算例语料", FAIL, f"{case_dir} 读不到：{error.strerror}", root_module.hint())
    if count:
        return Check("算例语料", PASS, f"{count} 个算例，位于 {case_dir}")
    if os.environ.get("VELCH_DATA_ROOT", "").strip():
        # An explicitly set variable that lands on an empty directory is a mistake, not a fresh
        # install: the user asked for that corpus and it is not there.
        return Check("算例语料", FAIL,
                     f"VELCH_DATA_ROOT 指向 {case_dir}，但那里没有 case_*.json", root_module.hint())
    return Check("算例语料", WARN, f"{case_dir} 里没有 case_*.json", root_module.hint())


def _ui_check() -> list[Check]:
    checks = [Check("Tk 界面库", PASS if not _module_missing("tkinter") else FAIL,
                    "tkinter 可用" if not _module_missing("tkinter") else "找不到 tkinter",
                    "安装 Python 时勾选 tcl/tk；官方安装包默认包含")]
    if _module_missing("matplotlib"):
        checks.append(Check("绘图库 matplotlib", WARN, "没有安装：④⑥⑦ 屏会降级为文字提示",
                            "pip install .[ui]  （或 pip install matplotlib>=3.6）"))
    else:
        three_d = _module_missing("mpl_toolkits.mplot3d")
        checks.append(Check("绘图库 matplotlib", PASS,
                            "可用" if not three_d else "可用，但缺 mpl_toolkits.mplot3d（⑦ 屏不可用）"))
        if not three_d and _module_missing("PIL"):
            checks.append(Check("图像库 Pillow", WARN, "没有安装：PNG 导出与三维贴图可能失败",
                                "pip install pillow"))
    return checks


def _simpack_check() -> Check:
    model = os.environ.get("VELCH_SIMPACK_MODEL", "").strip()
    root = os.environ.get("VELCH_SIMPACK_ROOT", "").strip()
    if not model and not root:
        return Check("Simpack 模型", WARN, "未设置 VELCH_SIMPACK_MODEL / VELCH_SIMPACK_ROOT",
                     "要读 Simpack 模型时再设置；只跑 Velch 自带算例可以不管这一项")
    missing = [f"{name}={value}" for name, value in
               (("VELCH_SIMPACK_MODEL", model), ("VELCH_SIMPACK_ROOT", root))
               if value and not Path(value).exists()]
    if missing:
        return Check("Simpack 模型", FAIL, "路径不存在：" + "；".join(missing),
                     "检查工程目录是否被移动或改名")
    return Check("Simpack 模型", PASS, f"模型在位：{Path(model).name if model else root}")


def _write_check() -> Check:
    from velch.agent import core as agent_core

    # ``agent_home()`` creates its own subdirectories, so on a read-only install it raises before
    # returning a path at all -- the failure has to be caught here, or the whole self-check dies on
    # the very machine it was written to explain.
    try:
        home = agent_core.agent_home()
    except OSError as error:
        return Check("可写目录", FAIL, f"读不到也建不了程序状态目录：{error}",
                     "把 VELCH_AGENT_HOME 指到可写目录（例如 %LOCALAPPDATA%\\Velch\\agent）")
    try:
        home.mkdir(parents=True, exist_ok=True)
        probe = home / ".selfcheck"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as error:
        return Check("可写目录", FAIL, f"{home} 不可写：{error.strerror}",
                     "把 VELCH_AGENT_HOME 指到可写目录")
    return Check("可写目录", PASS, f"{home} 可写")


def collect() -> list[Check]:
    """Run every check; never raises."""

    checks: list[Check] = [_version_check(), _corpus_check()]
    checks.extend(_ui_check())
    checks.append(_simpack_check())
    checks.append(_write_check())
    return checks


def report(checks: Iterable[Check]) -> str:
    rows = list(checks)
    width = max((len(row.name) for row in rows), default=0)
    marks = {PASS: "PASS", WARN: "WARN", FAIL: "FAIL"}
    lines = ["Velch 自检（这台机器上这份程序能不能干活）", ""]
    for row in rows:
        lines.append(f"[{marks[row.status]}] {row.name.ljust(width)}  {row.detail}")
        if row.fix and row.status != PASS:
            lines.append(f"{' ' * 8}{row.name.ljust(width)}  → {row.fix}")
    failed = sum(1 for row in rows if row.status == FAIL)
    warned = sum(1 for row in rows if row.status == WARN)
    lines.append("")
    if failed:
        lines.append(f"结论：{failed} 项必须修，{warned} 项可选。")
    elif warned:
        lines.append(f"结论：可以启动，{warned} 项可选未满足（上面标了怎么补）。")
    else:
        lines.append("结论：全部通过。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    checks = collect()
    print(report(checks))
    if "--json" in arguments:
        import json

        print(json.dumps({"checks": [row.__dict__ for row in checks]}, ensure_ascii=False))
    return 0 if all(row.ok for row in checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
