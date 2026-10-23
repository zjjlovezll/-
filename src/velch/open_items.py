"""Open items, in one machine-readable place.

`docs/BUGS.md` is the ledger the reader trusts; this module is the version the *program* can read.
Two copies would drift, so `tests/test_open_items.py` checks both directions: every id here must
appear in `BUGS.md`, and every `O###` row there must appear here.

`status` is the honest part:

* ``open``      -- a real gap. Somebody has to do something.
* ``by_design`` -- not a defect. The software deliberately refuses to do it, and the reason matters.
* ``closed``    -- kept only so the ids in old notes still resolve.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["open", "by_design", "closed"]

LEDGER = "docs/BUGS.md"


@dataclass(frozen=True)
class OpenItem:
    """One known gap, in the words a user of the software can act on."""

    id: str
    title: str
    why: str
    status: Status
    since: str = ""

    @property
    def blocking_release(self) -> bool:
        """``True`` when a careful reader should know before quoting a number."""
        return self.status == "open" and self.id == "O008"


ITEMS: tuple[OpenItem, ...] = (
    OpenItem(
        id="O001",
        title="语料探测靠读源码文本，间接读语料的模块会硬失败",
        why="`tests/conftest.py` 看模块源码里有没有 `case_dir(` 之类的字样来决定是否 skip。"
            "一个通过别的模块间接读语料的测试会被判成\"不读语料\"，于是在没有语料的机器上硬失败。"
            "方向是 fail loud（宁可红也别假绿），代价是这类新测试要显式带 `pytest.mark.corpus`。",
        status="open",
        since="0.4.7",
    ),
    OpenItem(
        id="O003",
        title="⑥ 对照屏的 CSV 列靠猜",
        why="已修（0.4.22）：面板上常驻一行写明选了哪两列、是自动还是手动、还有几个候选；"
            "列名全不认识时明说「列名无法识别」，不再静默取第一列。",
        status="closed",
        since="0.4.7",
    ),
    OpenItem(
        id="O005",
        title="Simpack 侧的物理量不做自动映射",
        why="轴重、E*、R*、蠕滑系数、模态参数一律只作对照，必须由人显式写进模板算例。"
            "这是设计约束：自动映射会静默改动物理标定，而标定是这套结果的立足点。",
        status="by_design",
        since="0.4.2",
    ),
    OpenItem(
        id="O008",
        title="Simpack 模型的横向布置还不能双侧导入",
        why="这个模型的右轨有 236 站、233 个不同断面，左轨只有 2 站（0 与 150 m）。"
            "只导入一侧冠部就等于改轨距（实测 +103 mm），所以闸门拒绝并给出机器可读的 `detail`。"
            "要么换一个两条轨都有断面表的模型，要么继续用 `--keep-profiles`。",
        status="open",
        since="0.4.8",
    ),
    OpenItem(
        id="O002",
        title="评价屏不传静态轴重，界面与 CLI 可能给出两套 H 判定",
        why="已修（0.4.7）：输入框的正数会作为 `--static-axle-load-n` 传下去，留空就不加参数。",
        status="closed",
        since="0.4.7",
    ),
    OpenItem(
        id="O004",
        title="⑦ 屏加载运行目录时吞掉 I/O 失败",
        why="已修（0.4.7）：读不到时在状态栏报 `读不到运行目录：<类型>: <消息>（<路径>）`。",
        status="closed",
        since="0.4.7",
    ),
    OpenItem(
        id="O006",
        title="⑦ 三维屏没有接触斑着色",
        why="已实现（0.4.10，第 46 轮）：按记录的法向力着色、圆环用 `sqrt(2Rδ)` 的真实半径、"
            "另加 20 mm 指示杆。",
        status="closed",
        since="0.4.10",
    ),
    OpenItem(
        id="O007",
        title="界面控件边界对比度不足 3:1",
        why="撤销（0.4.7）：原条目量的 `BORDER`(1.48) 与 `BORDER_STRONG`(1.83) 是装饰细线；"
            "真正的控件边界 `BORDER_CONTROL` 是 3.99:1。",
        status="closed",
        since="0.4.7",
    ),
    OpenItem(
        id="O009",
        title="真·只读安装（ACL 拒绝写）未自动测",
        why="已自动化（0.4.15，第 53 轮）：`--readonly-acl` 会复制安装目录、删掉 `.agent`、"
            "`icacls /deny` 后断言自检 FAIL 而仿真仍可跑。",
        status="closed",
        since="0.4.15",
    ),
)


def open_items() -> tuple[OpenItem, ...]:
    """The gaps that still need somebody: ``open`` and ``by_design``."""
    return tuple(item for item in ITEMS if item.status != "closed")


def by_id(item_id: str) -> OpenItem:
    for item in ITEMS:
        if item.id == item_id.upper():
            return item
    raise KeyError(item_id)


def counts() -> dict[str, int]:
    result = {"open": 0, "by_design": 0, "closed": 0}
    for item in ITEMS:
        result[item.status] += 1
    return result


def summary_text() -> tuple[str, str]:
    """``(text, tone)`` for a one-line label: two gaps plus one deliberate limitation."""
    tally = counts()
    text = f"已知未修 {tally['open']} 项（其中 {tally['by_design']} 项是设计约束）"
    return text, ("warn" if tally["open"] else "pass")
