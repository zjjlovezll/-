# 缺陷账本（BUGS）

"把 bug 修完"不是可验收的目标——一个仓库永远能找出更多 bug。可验收的是**这本账**：每条缺陷都有
编号、复现方式、影响面和状态；账上没有 `open` 的确定缺陷，才能说"这一版可以出"。
新发现的问题先登记再修，修完把状态改成 `fixed` 并写下测试名。

- 最后更新：2026-10-22
- 回归门：`python -X utf8 -m pytest tests -q --basetemp F:\velch_tmp\pytest` → **480 passed**
- 提交前闸门：`.githooks/pre-commit` → `scripts/auto_accept.py --skip-run` → `verdict: ACCEPT`

## 已修复（有测试钉住）

| ID | 症状 | 触发条件 | 影响 | 修复 / 测试 |
|---|---|---|---|---|
| B001 | 界面事件泵永久停摆 | 任一屏 handler 抛异常 | 日志冻结、后台结果不再投递、运行按钮永久灰、子进程无人接收；只在 stderr 留 traceback | `ui/app.py::_pump` 逐事件 try/except + `finally` 重排；`tests/test_ui_robustness.py::test_pump_survives_a_failing_handler` |
| B002 | 失败分支不清屏 | 先成功评价/计算 A，再切到缺列的 B | 屏幕上留着 A 的红色"超限"限值条与 KPI，看着像在指控 B | `screen_assess._clear_limits()` / `screen_spectrum._clear_view()`；同文件 |
| B003 | 结果乱序覆盖 | 快速连点运行下拉（每次 2–5 s） | 下拉显示 B、图是 A | 每屏 `_token`，过期结果丢弃；`test_stale_worker_results_are_dropped` |
| B004 | 子进程归属错乱 | 运行屏与评价屏同时有 spawn / 缩放重建界面 | 取消作用于错误进程、日志进错面板 | `exit` 事件携带作业对象，按 `job.owner` 路由；`spawn` 忙时返回 None |
| B005 | NaN 限值条显示"通过" | manifest 里出现 NaN | 无数据的项以通过色呈现 | `LimitBar._draw` 的 `isfinite` 判断 → 灰条 + "无有效值" |
| B006 | 过滤后选择悬空 | 选中 X 后输入只匹配 Y 的筛选词 | 派生/复制命令仍指向看不见的 X | `_apply_filter()` 后选首行或清空卡片 |
| B007 | `peak_force_kn` 返回牛顿 | 任何按名字取用的新调用点 | 170610 N 被当成 170610 kN | 改名 `peak_force_n`，去掉调用点 `/1000` |
| B008 | 绕过 `fmt` 的格式化 | `f"{x:+.4g}"`、`{share:.2f} %` | NaN 渲染成 `+nan %`；59680.5769 → 59681（单位还是 N） | `fmt_percent(signed=)`/`fmt_number(signed=)`；`test_ui_readability.py` 正则 |
| B009 | 类型谎言无闸门 | `store.bars()` 注解 5 元组实为 6 | 下次改元组长度只能靠运气 | 删过期注解与死代码 `Chart._stack_groups` |
| B010 | ⑤ 限值条读数被裁 | 画布 388 px > 分栏 358 px | `3896 / 4.979e+04` 显示成 `3896 / 4.97`（读成 4.97 N，差 10⁴） | `LimitBar` 宽度交给布局 + `fmt_pair` 从 limit 侧选量级 |
| B011 | 3D 轴标题互相压字 | 130% 字号或默认视角 | 轴标题投影重叠、刻度 9 个挤在 7 px 内 | 删 3 轴标题改画布外一行说明 + `MaxNLocator(nbins=4)` + `set_box_aspect(zoom=1.45)` |
| B012 | 审查残留临时目录 | `pytest --basetemp .pt_tmp_review` | 一百多个小算例文件混进工作树 | 删除并把 `.pt_tmp*/` 写进 `.gitignore` |
| **B013** | **打包后"界面里点运行"整条主路径失效** | 冻结成 exe（`sys.executable` 就是 exe） | `[exe, "-X", "utf8", "-m", "velch", …]` 不是合法引导参数；源码模式永远复现不出来 | 新建 `velch/launcher.py`（`launcher_argv`/`worker_argv`/`console_executable`），6 处调用点收敛；`tests/test_launcher.py` 7 项（含"全仓不得再用 `sys.executable`"扫描） |
| **B014** | **打包后找不到语料且报错不可读** | 冻结后 `__file__` 在 `_internal/` 下 | `REPOSITORY_ROOT = parents[2]` 指向 `_internal`，语料永远找不到；错误只有一句 `FileNotFoundError` | `data_root.frozen_install_root()` + 逐用户标记 `%LOCALAPPDATA%\Velch\.velch-data.json` + `hint()` 打印查找顺序与写法；算例屏空表时显示该提示 |
| **B015** | **版本漂移 + 入口点缺失** | `pyproject.toml` 写死 `version = "0.4.0"`，且没有 UI/agent 入口 | wheel 版本与 `velch.__version__` 可能不一致；用户只能靠记模块路径打开界面 | pyproject 改 `dynamic = ["version"]`（单一事实源 `src/velch/__init__.py`）+ 新增 `velch-ui`、`velch-agent` 两个 script |
| **B016** | **自检的流式探针用 `-c` 内联源码** | 冻结构建 | 打包后的 exe 不接受 `-c`，自检的"子进程通路"项直接失败 | 新建 `ui/stream_probe.py`（`stream_probe_argv()`），自检与 `packaging/entry_console.py` 的 `--selftest-stream` 对应 |

| B021 | `simpack-case` 的默认模式（型面取自模型）在转辙区窗口必然失败，报的是静平衡偏载 `the lightest contact patch carries only 0.0 N while the heaviest carries 119357.0 N`，没说是几何问题、也没说差多少 | **两轮修正**：①先量断面差并把明显不可能挡在积分器之前；②发现该量法本身错（见 B022/B023）后改为"量冠部（仅报告）+ 真跑静平衡裁决"，`seat_report` 坐不住就退出码 2 并打印原因/冠部差/整车足迹与一句明确不推荐窗口的建议 | `tests/test_simpack_crown.py` 7 项 + `docs/SIMPACK_IMPORT` 第五节（含更正） | 8a00009 / 本轮 |
| B022 | 派生算例只导入 `[x_start − 2, x_start + 车速×时长 + 2]` 内的站位，而后轴在 `x_start` 之后 **10 m**（`bogie_half_spacing_m + wheelbase_m/2`）→ 后轴下面没有钢轨，静平衡必然单侧脱空 | 窗口改成整车足迹 `[x_start − 10, x_start + 车速×时长]`（`_axle_reach_m`）；修后 60 m 窗口`seats: true`、`residual 1.1e-07`、`axle1_right 59.68 kN`、`run-vehicle --fast` → `numerically_checked`、`nfev 116`、`max_penetration 65.466 µm` | `tests/test_simpack_window_advice.py::test_a_window_whose_rear_axle_rides_the_step_is_not_offered` + `docs/SIMPACK_IMPORT` 第五节更正 | 本轮 |
| B023 | 断面差量的横向位置错了：在固定 `y = 0.753 m` 取轨顶，而模板包络是 `[−0.790, −0.717] m`、冠部在 `−0.7896 m`，该点落在**轨顶侧面**上、比冠部高 +29.86 mm → 报出的"下沉 5.18/11.24 mm"其实是冠部横向漂移 × 侧面坡度 | 改成量**冠部**（逐站 `argmin(z)` 的高度与横向位置）；冠部高度差实测 0.000–0.155 mm、冠部横移最多 103 mm；阈值降级为 `CROWN_WARN_MM = 0.5` **只报告不拒绝** | `tests/test_simpack_crown.py::test_the_crown_is_the_lowest_point_not_a_fixed_offset` + `docs/SIMPACK_IMPORT` 第五节更正 | 本轮 |

## 已知未修（不是"忘了"，是权衡）

| O009 | 真·只读安装（ACL 拒绝写）未自动测 | 现在自动测的是"安装树不被修改"（`install-dir-untouched`，含负向验证）；ACL 拒绝时的报错文案仍需管理员权限手工跑一次，步骤写在 `docs/PACKAGING` 末尾 |
| O008 | ~~转辙区断面形状差异导致坐不住~~ **已撤销**：60 m 窗口坐不住的原因是 B022（后轴无钢轨），修好后同窗口能坐能跑。仍然存在的是：**冠部横向漂移最多 103 mm，而横向布置尚未导入**（轮对初始横向位置仍取模板的 `y_offset_m = 0.753`），所以接触点相对冠部的位置与模型不完全一致 | 要消除需导入模型自己的轮对横向布置 + 双体（基本轨/尖轨）交接，属下一层 | `docs/SIMPACK_IMPORT` 第五节更正与§三 |


> **0.4.8 进展**：`--import-lateral` 已实现（把每站冠部横向位置写进该站 `y_offset_m`），实测右轨在
> 80–90 m 需要 **−73.8 … +103.0 mm** 的修正、而左轨在该窗口**没有站位**，单侧导入等于拉宽轨距
> 103 mm，实跑果然一侧四个接触全脱空。因此加了 `LATERAL_GAUGE_LIMIT_MM = 5.0` 的拒绝（报出两侧
> 数字并指向 `--allow-gauge-change`），并确认真正的解法是**双体交接**：同一里程上 10 处
> `coincident_stations` 意味着"这一站的冠部"属于基本轨还是尖轨，catalog 不回答。


| ID | 症状 | 为什么不修 / 什么时候修 |
|---|---|---|
| O001 | `tests/conftest.py` 用源码文本启发式判断"是否读语料"，间接读语料的模块会硬失败而非 skip | 方向是 fail loud：漏 skip 的代价是测试报错（看得见），误 skip 的代价是闸门虚假绿（看不见）。要根治就加显式 `@pytest.mark.corpus` |
| O002 | ~~`screen_assess.run_cli()` 不传 `--static-axle-load`，界面与 CLI 可能给出两套 H 判定~~ **已修（0.4.7）**：CLI 的 flag 名是 `--static-axle-load-n`，屏幕现在把「静态轴重 N」里的正数原样传给 CLI，空白则不加（CLI 自己会取自动值）；`tests/test_ui_robustness.py` 有源码级对照钉住两处读同一个字段 | — |
| O003 | `screen_compare.choose_csv()` 用 `"x"`/`"力"`/`"_n"` 子串猜列，猜错无提示 | 需要实测 CSV 样本才能定规则；猜测应在状态栏显示"选了哪两列" |
| O004 | ~~`screen_model3d.load_runs()` 吞 I/O 失败~~ **已修（0.4.7）**：改为在状态栏报 `读不到运行目录：<类型>: <消息>（<路径>）`；空下拉与「首次运行」不再长得一样 | — |
| O005 | Simpack 侧的物理量（轴重、E*、R*、蠕滑、模态）**不做自动映射** | 这是设计约束不是缺陷：自动映射会静默改动物理标定。Simpack 的数只作对照值（reference, not adopted） |
| O006 | ⑦ 屏没有接触斑着色（侵入量画到轨面） | 需要 `_body_cache` 的逐接触几何；属功能增量 |
| O007 | ~~UI 对比度：`BORDER`/`BORDER_STRONG` < 3:1~~ **撤销（0.4.7，量错了对象）**：这两个 token 是装饰性细线与悬停底色，WCAG 1.4.11 只管**控制边界**。实测：`BORDER_CONTROL` 3.61–4.32:1、`ACCENT`（焦点环）7.89–9.43:1、`WARN/FAIL/PASS` 6.26–7.88:1，全部达标；`BORDER` 1.48:1 只作卡片间细线。现在这些对都进 `NON_TEXT_PAIRS` 由 `contrast_violations()` 机器判定，焦点环粗细也提成 `FOCUS_THICKNESS = 2` | — |

### B017 冻结版的输出是 GBK，任何按 UTF-8 读的地方都是乱码

- 现象：`velch-cli.exe --selftest` 抓到的 1629 字节全是乱码，冒烟测试因此判定"自检没跑起来"。
- 根因：冻结的控制台程序继承控制台 ANSI 代码页（本机 cp936），`print` 的中文写成 GBK 字节。
- 处置：`packaging/entry_console.py` 开头 `_utf8_console()`，把 `sys.stdout/stderr` `reconfigure`
  成 UTF-8；冒烟测试同时保留"UTF-8 解不开就按 GBK 再解一次"的兜底。
- 状态：已修（0.4.1）。

### B018 窗口版 exe 没有 stdout，`Velch.exe --selftest` 重定向时永远"没输出"

- 现象：`subprocess.run(["Velch.exe", "--selftest"], capture_output=True)` 退出码 0、抓 0 字节。
- 根因：PyInstaller 的 windowed 构建把 `sys.stdout` 置 None（无控制台），输出无处可去。
- 处置：控制台入口新增 `--selftest` / `--selftest-json` 分派；冒烟测试改用 `velch-cli.exe`。
- 状态：已修（0.4.1）。

### B019 日志管道探针在"自己就是控制台版"时误报缺兄弟 exe

- 现象：冻结自检里日志管道 0 行、退出码 None，提示"打包版里找不到 velch-cli.exe"。
- 根因：`console_executable()` 去找**兄弟** `velch-cli.exe`，而这次自己就是 `velch-cli.exe`，
  于是它与 `sys.executable` 相同，探针据此判定"缺兄弟"。
- 处置：`launcher.console_executable()` 若当前 exe 名含 `cli` 直接返回自身；探针的守卫同步放宽。
- 状态：已修（0.4.1）。

### B020 语料缺失时 `agent doctor` 只说 `cases: 0`

- 现象：打包版首启看不到算例，doctor 的 `cases` 检查只有 `ok:false, detail:0`，读起来像构建坏了。
- 处置：`agent/__main__.py` 在 `total == 0` 时把 detail 写成"0（算例根：…）"并附 `data_root.hint()`。
- 状态：已修（0.4.1）。

- **B024 空语料时 ① 屏按钮被挤到 94 px（已修，2026-10-23）**：`screen_cases` 的空态提示是无换行的
  `tk.Label`，索取整句宽度后把右卡压缩，五个按钮被裁；打包版首启必然触发。处置：提示 `wraplength`
  + `wrap_with`，导航行文案缩短，并把布局闸门改成"有语料/无语料各量一遍"。
