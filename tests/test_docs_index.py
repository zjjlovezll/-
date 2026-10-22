"""The doc index must cover every document and every link must resolve.

``AGENTS.md`` calls ``CHANGELOG_DOCS.md`` the single entry point.  It named 42 of 74 files, and a
hand-maintained list drifts the moment someone adds a document -- which is exactly the "docs and
version disagree" failure the release objective is about.  The generated block is checked here, so
a new document that nobody indexed fails the gate instead of quietly disappearing.
"""
from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
INDEX = DOCS / "CHANGELOG_DOCS.md"
BEGIN = "<!-- DOCS:ALL:BEGIN -->"
END = "<!-- DOCS:ALL:END -->"


def _index_text() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_the_index_has_a_generated_block() -> None:
    text = _index_text()
    assert BEGIN in text and END in text, "文档清单块被删掉了"
    block = text.split(BEGIN, 1)[1].split(END, 1)[0]
    assert block.count("| [") >= 60, block.count("| [")


def test_every_document_is_named_in_the_index() -> None:
    text = _index_text()
    missing = [path.name for path in sorted(DOCS.glob("*.md"))
               if path.name != INDEX.name and path.name not in text]
    assert not missing, f"这些文档没有进索引：{missing}"


def test_every_link_in_the_index_resolves() -> None:
    text = _index_text()
    links = re.findall(r"\]\(([^)]+\.md)\)", text)
    assert links, "索引里一个文档链接都没有"
    broken = [link for link in links if not (DOCS / link).is_file()]
    assert not broken, f"索引里的链接指向不存在的文件：{broken}"


def test_the_generated_block_is_current() -> None:
    """Drift guard: compare the stored rows against what the files say today."""

    def title_of(path: Path) -> str:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
            if stripped:
                return stripped[:80]
        return "(空文件)"

    expected = {path.name: title_of(path) for path in DOCS.glob("*.md")
                if path.name != INDEX.name}
    block = _index_text().split(BEGIN, 1)[1].split(END, 1)[0]
    stored = dict(re.findall(r"\| \[([^\]]+)\]\([^)]+\) \| ([^|]+) \|", block))
    stale = {name: (stored.get(name), title) for name, title in expected.items()
             if stored.get(name) != title}
    assert not stale, f"标题变了但清单没重生成：{list(stale)[:5]}"


def test_the_current_version_has_release_notes_in_the_index() -> None:
    """Doc and version must agree: whatever __version__ says, its notes exist and are listed.

    Row order in the index table is the order things were written, not semver order, so sorting
    versions there is not a meaningful check -- matching the shipped version is.
    """

    from velch import __version__

    notes = DOCS / f"RELEASE_NOTES_{__version__}.md"
    assert notes.is_file(), f"{__version__} 没有发布说明"
    assert notes.name in _index_text(), f"{notes.name} 没进索引"
