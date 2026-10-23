"""把发布序列写成一张表：每个 tag → 哪一次提交 → 有没有发布说明 → 那一版解决了什么。

数据全部来自 git 与 `docs/RELEASE_NOTES_*.md`，不手写：手写的索引一定会落后于标签。
用法：
    python -X utf8 scripts/release_series.py            # 写 docs/RELEASE_SERIES.md
    python -X utf8 scripts/release_series.py --check    # 只比对，不同就退 2（给测试与闸门用）
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "RELEASE_SERIES.md"
NOTES = REPO / "docs"

HEADER = """# Velch 发布序列

这张表**由脚本生成**（`python -X utf8 scripts/release_series.py`）。数据来自 git 标签与
`docs/RELEASE_NOTES_<版本>.md`，所以它不会落后于标签；`tests/test_release_series.py` 会比对
生成结果与文件内容，漂移就红。

一版一句话：这一版解决的是**哪个具体问题**，以及证据落在哪里（发布说明 / 冒烟报告 / 测试数）。

| 版本 | 打标签时间 | 提交 | 一句话 | 发布说明 |
| --- | --- | --- | --- | --- |
"""


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.lstrip("v").split("."))


def _one_liner(version: str) -> str:
    """发布说明的第一句实质性描述（跳过标题与"发布日"那一行）。"""
    path = NOTES / f"RELEASE_NOTES_{version}.md"
    if not path.is_file():
        return "—（没有发布说明）"
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip().lstrip("-*").strip()
        if not text or text.startswith("#") or text.startswith("发布日") or text.startswith("|"):
            continue
        text = re.sub(r"[`*]", "", text)
        cut = re.split(r"[。；]", text)[0]
        return cut[:78] + ("…" if len(cut) > 78 else "")
    return "—"


def rows() -> list[tuple[str, str, str, str, str]]:
    tags = [tag.strip() for tag in _git("tag", "--list", "v*").splitlines() if tag.strip()]
    table = []
    for tag in sorted(tags, key=_version_key):
        version = tag.lstrip("v")
        when = _git("log", "-1", "--format=%ad", "--date=format:%Y-%m-%d", tag).strip()
        commit = _git("log", "-1", "--format=%h", tag).strip()
        has_note = (NOTES / f"RELEASE_NOTES_{version}.md").is_file()
        note = f"[{version}](RELEASE_NOTES_{version}.md)" if has_note else "—"
        table.append((version, when, commit, _one_liner(version), note))
    return table


def render() -> str:
    lines = [HEADER.rstrip()]
    for version, when, commit, summary, note in rows():
        lines.append(f"| {version} | {when} | `{commit}` | {summary} | {note} |")
    lines.append("")
    notes = sorted(p.name for p in NOTES.glob("RELEASE_NOTES_*.md"))
    missing = [name for name in notes
               if not any(f"({name})" in line for line in lines)]
    lines.append(f"共 {len(notes)} 份发布说明、{len(rows())} 个标签。")
    if missing:
        lines.append("")
        lines.append("未出现在上表的发布说明：" + "、".join(f"`{name}`" for name in missing))
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 docs/RELEASE_SERIES.md")
    parser.add_argument("--check", action="store_true", help="只比对，不写文件")
    args = parser.parse_args(argv)

    text = render()
    if args.check:
        current = DOC.read_text(encoding="utf-8") if DOC.is_file() else ""
        if current != text:
            print("docs/RELEASE_SERIES.md 与标签不一致：重新生成")
            return 2
        print(f"发布序列一致（{len(rows())} 个标签）")
        return 0

    DOC.write_text(text, encoding="utf-8", newline="\n")
    print(f"已写入 {DOC}（{len(rows())} 个标签）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
