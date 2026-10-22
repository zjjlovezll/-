# 界面可读性：字号缩放与不截断

配套代码：`src/velch/ui/theme.py`（`set_scale`）、`src/velch/ui/app.py`（`zoom` / `--scale`）、
`src/velch/ui/widgets.py`（列宽）、`src/velch/ui/screen.py`（`wrap_with`）。
测试：`tests/test_ui_scale.py`（8 项）。

## 为什么需要它

设计字号是按 1360×860、100 % 缩放定的：正文 11 px、表格 10 px、注释 9 px。这在普通笔记本屏上勉强，
在 4K 屏或投影上就是"看不清"；而把界面固定成一套像素，用户只能改系统缩放，代价是整个窗口跟着虚。

所以字号变成**参数**，而不是散落在各屏的常数：

| 令牌 | 100 % | 130 % | 用途 |
|---|---|---|---|
| `micro` | 9 | 12 | 表头备注、轴刻度、脚注 |
| `tiny` | 10 | 13 | 密集表格 |
| `body` | 11 | 14 | 默认正文 |
| `body_lg` | 12 | 16 | 强调正文 |
| `section` | 14 | 18 | 卡片标题 |
| `title` | 18 | 23 | 屏标题 |
| `display` | 24 | 31 | 大数字 |

行高与表格行高同步缩放（`LINE_HEIGHT`、`TREE_ROW_HEIGHT`），否则字大了但行不变，字形会被上下切掉。

## 怎么用

- 窗口里：**Ctrl+=** 放大、**Ctrl+-** 缩小、**Ctrl+0** 还原（步长 0.1，范围 0.9–1.6）。
- 启动时：`python -X utf8 -m velch.ui --scale 1.3`；
- 或者给启动脚本设环境变量：`set VELCH_UI_SCALE=1.3`（桌面快捷方式里一次设定，长期生效）。
- 缩放后状态栏会显示当前比例，并可再按 Ctrl+0 回来。

**为什么缩放要重建窗口**：Tk 在创建控件时就把字体烤进去了，改令牌只影响之后创建的控件。若只改令牌
不重建，界面会声称 130 % 而一半控件仍是 100 % —— 这比不缩放更糟。所以 `zoom()` 销毁整棵控件树、
重建样式与布局，再切回原屏。

## 截断：字号放大的真正难点

字号变大后最先坏的不是字，是**为字留的空间**。这一轮修掉四处必然截断的地方：

1. **表格列宽**（`widgets.ListPanel.columns`）：列宽按声明值 × 缩放，否则表头比列宽、最后一列被切；
2. **固定左栏**（③④⑤⑥⑦ 的 `minsize` / `width`）：320–420 px 的侧栏按缩放放大，否则中文标签被压成
   每行三四个字；
3. **换行宽度**（`screen.py` 的 `wrap_with`）：`wraplength` 不再写死 280/560/760，而是跟随容器宽度
   （`<Configure>` 事件），窗口拉伸或字号变化都会重算；
4. **并排按钮**（① 算例屏）：三个按钮改成等宽网格而非向左堆叠 —— 130 % 下三个按钮加间距超过侧栏宽度，
   最后一个会被切掉半个字符，等于消失。

## 验证方式

`.tmp/shot_ui_scale.py <屏> <运行目录|-> <缩放> <输出.png>` 无头截图，把同一屏在 100 % / 125 % / 130 %
各截一张对比。**这一步不可省**：字号类问题在测试里看不出来（控件都在、文字都对），只有看图能发现
"这一行伸到面板外面了"。

`tests/test_ui_scale.py` 钉住可自动化的部分：令牌单调、上下限、行高不低于字号、环境变量、
颜色未动且对比度仍达 AA、快捷键在帮助里可见。

## 不再重复的坑

- `@staticmethod` 里读 `self.x_ticks` → `NameError`，而 Tk 回调异常只打到 stderr、**图照样画出来**；
  改字体格式化的这类"绘图副产物"必须靠截图核对。
- 给某轴换了全局 `FuncFormatter` 会覆盖 `set_xticks` 的显式标签：频谱横轴会从 `6.2079 … 793.7 Hz`
  变成 log10 位置 `0.7924 … 2.9`。显式刻度优先，格式化只负责其余轴。

## 二轮：按视觉验收 HOLD 的逐条处置（2026-10-22 晚）

一轮解决的是"字号能缩放"，视觉验收仍判 HOLD，理由是**有四处在 1280×820 上会读错数或找不到**。二轮的处置：

| 验收条目 | 处置 | 证据 |
|---|---|---|
| ② 四个按钮 `mapped=0 h=13`，"启动单次运行"不可见 | 左卡从 `pack` 改 `grid`，只有算例列表 `rowconfigure(weight=1)`；按钮改两行等宽 grid | `ui_run_v2.png` 两行按钮全部可见 |
| ⑤ 限值条 `3896 / 4.979e+04` 被裁成 `3896 / 4.97`（差 10⁴） | `LimitBar` 改 `width=1` + 由布局给宽度；数值走 `fmt.fmt_pair` 与限值同量级（`3.896 / 49.79 kN`）；补 80% WARN 刻度与"超限"字样 | `ui_assess_v2.png` 三条限值可读，ΔP/P 显示 79% 不再是 96% |
| ① 哈希列被切、列宽合计超容器 | 六列改四列，哈希/输出步长移入右侧契约卡（各有整行）；`ListPanel` 加横向滚动条、`minwidth`、`stretch_weights`；进入即默认选中首行（不再十个"—"） | `ui_cases_v2.png` |
| ③ 单序列无图例、三曲线说不出是哪一轴哪一轨 | 图例条件从 `len(series) > 1` 改为"任一序列有标签" | `ui_timeseries_v2.png` 三张子图各有图例 |
| ④ 同一频带在轴/表/卡片是 39.3725 / 39.4 / 39 Hz | 新增 `velch/ui/fmt.py`，四个调用点全部改走 `fmt_number` | `test_ui_readability.py` 断言全屏无 `:.4g` 直写 |
| ⑦ 唯一不跟缩放的屏（`fontsize=9/labelsize=8`） | 字号改 `theme.FONT_SIZE`；轴标题压在几何上 → 三根轴标题改为画布外一行"坐标：里程 x / 横向 y / 高程 z"；`set_box_aspect(zoom=1.45)` 填满画布；刻度 4 档 | `ui_model3d_v2.png` |
| ⑥ 两个下拉无 label、两种空态文案 | 加"站点列 / 力列"标签；两个 `empty_hint` 统一成一句 | `r_cmp` 截图 |
| 侧栏 `wraplength=170` 在 130% 出孤字行 | 改为跟随侧栏宽度的 `<Configure>` 重算 | 130% 截图 |
| **状态缺陷**：`_job_done` 单槽 → 两个作业互相覆盖回调 | 改为 `_job_handlers[job_id]`，队列带 id，`submit` 每次自增 | `test_every_job_keeps_its_own_callback` |
| **闸门虚假绿**：`conftest` 对全部用例加 skip | 只 skip 源码里引用 `case_dir(` / `case_path(` / `VALIDATION_DIR` / `oracle_dir(` 的模块，架构规则与标签语法在无语料时仍会失败 | `tests/conftest.py` |

未做（明确留待下一轮）：控件边界对比度 `BORDER/SURFACE` 1.37:1 → 目标 3:1、表格斑马纹 `ROW_ALT`、焦点环 1→2 px、字号阶梯整体抬一档（`-12/-14/-16/-18/-20/-26/-34`）。这四项是"更好看"，不是"读错数"，先让会读错数的部分归零。

## 三轮：按代码审查修掉"跑不动的面"

审查给出 7 条确定缺陷 + 5 条疑似，我按"先修能让整个窗口停摆的那条"的顺序落地。每一条都补了测试，
`tests/test_ui_robustness.py` 19 项，全部锁的是**症状**而不是实现细节。

| # | 缺陷 | 触发条件 | 影响 | 处置 |
|---|---|---|---|---|
| F1 | `_pump` 把 `after()` 写在 `try` 之外 | 任一屏 handler 抛异常 | 轮询永久停止：日志冻结、worker 结果不再投递、`_set_busy(True)` 永不清除（运行按钮永久灰）、子进程继续跑却无人接收；只在 stderr 留一条 traceback | 每条事件单独 `try/except` + `finally: after(100, ...)`；新增 `report_problem()` 把失败写进状态栏；`root.report_callback_exception` 接到同一条通道 |
| F2 | 三个屏的失败分支不清屏 | 先成功评价/计算运行 A，再切到缺列或 NaN 的运行 B | 屏上留着 A 的红色"超限"限值条、A 的轮轴表与 KPI，标题却写"评价失败"——**红色超限条看起来像在指控 B** | 新增 `screen_assess._clear_limits()`（入口先清）、`screen_spectrum._clear_view()`（计算前清）、频谱 caption 加运行名 |
| F3 | 结果没有请求序号 | 快速连点运行下拉（每次 2–5 s 读 history） | 慢的 A 覆盖快的 B：下拉显示 B、图是 A，caption 又不含运行名，读者无从分辨 | 每屏 `self._token`；`done()` 首行 `if token != self._token: return` |
| F4 | `spawn` 单槽、`on_exit` 按当前槽位的 owner 路由 | 运行屏与评价屏都有 spawn；缩放重建界面时子进程在跑 | 取消按钮作用于错误进程、日志进错面板、旧 `ProcessJob` 丢弃后退出码无人处理 | `spawn` 忙时返回 `None` 并提示；`exit` 事件携带 `self`（作业对象），`on_exit(job, code, elapsed, cancelled)` 按 `job.owner` 路由，并兼容旧的 `(code, elapsed, cancelled)` 形状 |
| F5 | `LimitBar` 对 NaN 显示为绿色通过 | manifest 里有 `NaN`，或 `value/limit` 缺失被 `or 0.0` 变成 0/0 | 一条实质"无数据"的限值条以**通过色**呈现 | `_draw` 开头 `isfinite` 判断 → 灰条 + "无有效值" |
| F6 | 过滤后 `self.selected` 悬空 | 选中算例 X，再输入只匹配 Y 的关键字 | 表格里没有 X，右侧契约卡/复制命令/派生仍指向 X，用户以为在派生 Y | `_apply_filter()` 之后选中首行并 `_on_select()`；无可见行则清空卡片与派生 ID |
| F7 | `RunInfo.peak_force_kn` 返回的是**牛顿** | 任何按名字取用的新调用点 | 170610 N 会被当成 170610 kN（或再除 1000 得 0.2 kN） | 改名 `peak_force_n`；`screen_assess` 里那处 `/1000` 一并去掉 |
| F8 | 仍有绕过 `fmt` 的格式化 | `f"{x:+.4g}"`、`{share:.2f} %`、`{static_axle_load_n:.0f}` | NaN 渲染成 `+nan %`；59680.5769 显示 59681 且单位是 N（实为 59.68 kN） | `fmt_percent(..., signed=True)`、`fmt_number(..., signed=True)`；静态轴重卡改 kN 口径；格式化测试正则收紧 |
| F9 | 类型谎言无闸门 | `store.bars()` 注解仍写 5 元组（实现 6 元组）；`Chart._stack_groups` 全仓无调用 | 下次改元组长度只能靠运气 | 删掉过期注解与死代码 |

**故意没做**（审查列为"疑似"，我判断需要证据再动）：`conftest.needs_corpus` 的文本启发式（方向是
fail loud，保留）、`screen_assess.run_cli()` 不传 `--static-axle-load`（界面与 CLI 可能给出两套 H 判定，
需要先确认 `assess` 是否有该参数）、`screen_compare.choose_csv()` 的列猜测、`screen_model3d.load_runs()`
的宽异常。

**没有改动物理**：静载门、八接触峰值、七项 manifest 门、DOP853 路径全部未触碰；`pytest` 454 → **473 passed**，
`--selftest` 7 屏 0 报错，`scripts/auto_accept.py` ACCEPT。
