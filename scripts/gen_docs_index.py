"""Regenerate the "complete document list" block in ``docs/CHANGELOG_DOCS.md``.

``AGENTS.md`` makes that file the single entry point to the documentation, and
``tests/test_docs_index.py`` fails if any ``docs/*.md`` is missing from the block or if a stored
title no longer matches the file's own heading.  The block used to be produced by a throwaway
``.tmp/gen_docs_index.py`` that did not survive, so the list drifted and -- worse -- the file ended
up carrying *two* generated blocks, of which only the first was checked (the second was a stale
copy from an earlier round).  This script is that generator, kept where it can be re-run:

    python -X utf8 scripts/gen_docs_index.py            # rewrite the block
    python -X utf8 scripts/gen_docs_index.py --check    # exit 2 if it is out of date

It rewrites the block between the FIRST pair of markers and drops every later pair, so re-running it
cannot accumulate copies again.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
INDEX = DOCS / "CHANGELOG_DOCS.md"
BEGIN = "<!-- DOCS:ALL:BEGIN -->"
END = "<!-- DOCS:ALL:END -->"
HEADER = ("## 完整文档清单（由 `scripts/gen_docs_index.py` 生成，测试会检查是否过期）\n"
          "\n"
          "| 文件 | 首行标题 |\n"
          "|---|---|")


def title_of(path: Path) -> str:
    """The file's own first heading, so the list cannot say something the document does not."""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if stripped:
            return stripped[:80]
    return "(空文件)"


def rows() -> list[str]:
    entries = []
    for path in sorted(DOCS.glob("*.md")):
        if path.name == INDEX.name:
            continue
        title = title_of(path)
        if "|" in title:                          # the table separator would split the row
            title = title.replace("|", "/")
        entries.append(f"| [{path.name}]({path.name}) | {title} |")
    return entries


def rebuild(text: str) -> str:
    if BEGIN not in text or END not in text:
        raise SystemExit(f"{INDEX.name} 里缺少清单标记")
    head, rest = text.split(BEGIN, 1)
    _stale, tail = rest.split(END, 1)
    # Drop any later copy of the block: only the first one is the list.
    while BEGIN in tail and END in tail:
        before, after = tail.split(BEGIN, 1)
        _ignored, tail = after.split(END, 1)
        tail = before + tail
    block = f"{BEGIN}\n{HEADER}\n" + "\n".join(rows()) + f"\n{END}"
    return head + block + tail


def main(argv: list[str]) -> int:
    current = INDEX.read_text(encoding="utf-8")
    updated = rebuild(current)
    if "--check" in argv:
        if updated != current:
            print("文档清单已过期：运行 python -X utf8 scripts/gen_docs_index.py")
            return 2
        print(f"文档清单一致（{len(rows())} 篇）")
        return 0
    if updated == current:
        print(f"文档清单已是最新（{len(rows())} 篇）")
        return 0
    INDEX.write_text(updated, encoding="utf-8")
    print(f"已重写文档清单：{len(rows())} 篇")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
