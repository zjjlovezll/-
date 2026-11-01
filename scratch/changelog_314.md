## 第 314 轮 — 第 8、9 条门：起点与平稳性（第 9 条第一次写宽，被自己的闸门否决后收紧）

七条数值门在这一轮之前同时放行了"起点没坐稳"的那趟 60 km/h：前轴右轨法向力 0–207.75 kN（std **34.75 kN**），七门仍 7/7。加两条门，不替换任何既有判据。

**第 8 条 `launch_balance`**：`vertical_preload_residual_n ≤ 0.1 N`（既有预载门限）且
`|spin·r − travel|/travel ≤ 1e-3`（既有 `spin_tracking` 门限）。第 312 轮我拍的
`LAUNCH_MODAL_RESIDUAL_N = 0.1` **不进这条门**：实测 60 → 106.74 N、80 → 101.45 N，
沉降 80 轮与 400 轮**逐位相同**，它是 settle↔seat 交替的不动点，与速度无关，只上报份额
（0.170 % @80、0.179 % @60）。

**第 9 条 `stationarity`**：第一次写成"整段记录 std ≤ 5 kN"，闸门直接 **REJECT**
（`reports/auto_accept_20261101-185212.json`：tests 562.14 s 里 4 failed / 1357 passed，frog 冒烟
`physical_gate_failed`）。根因是判据太宽：冻结基线在头 0.015 s 里把 **53.88 kN** 从 `stock`
合法搬到 `switch`（`axle1_right_switch` 从 0 起跳），整段 std 几十 kN 是道岔的本分。
于是**收紧适用域而不是放宽阈值**：该门只在算例声明读数窗口 `run.stationarity_window_m` 时产生，
窗口内（按前轴里程取样、≥3 个样本）八轨 std 取最大者 ≤ **5 kN**；没声明 ⇒ 不产生该门
（同 `spin_tracking` 只在有伺服时出现）。5 kN 两侧都有实测：振着 **34.75 kN**、
新路径 60/80 **0.103/0.0962 kN**、静下来的 100 **0.51 kN**、凸起算例 0.20–0.80 kN。

**配套端口**（否则窗口到不了）：`setups/one_set_straight.json` 声明 `stationarity_window_m: [56,65]`
+ `start_x_m: 46` + `seat_start_m: 40`；`velch.setup` 新增 `start.x_m`、`seat.start_m`、
`reading.window_m` 三个端口（`reading.window_m=none` 显式不主张）。第一次跑就是因为算例默认从
40 m 起跑（前轴 50 m），窗口 **0 个样本** ⇒ 门失败——这是"没量到不许算过"的正确行为。

**状态改三值**：`numerically_checked` / **`physical_gate_failed`**（只有这两条失败）/ `numerical_gate_failed`。

**开关不再能关掉门**：起点报告改为**无条件计算**，`report_launch` 只决定打印与归档；
`meta.json` 补上 `result_status`、`failed_gates`、`max_rail_force_std_kn`、`stationary_force_std_limit_kn`、
`stationarity_window_m`、`stationarity_samples` 与 `launch`。

**实测**：60 km/h（`…-69281ee8`）与 80 km/h（`…-a18815bb`）各 41 帧 **9/9**，窗口 56–65 m、
41 个样本、max std **0.103 / 0.0962 kN**；冻结基线（无窗口）**8/8** 且 `stationarity` 不出现。
撤回的 0.54 s 归档仍表示 std 34.75 kN，即该门会拒绝它。

**不追溯**：旧归档保留它们自己的记录；60 km/h 那一行的撤回继续有效，恢复仍需 ≥1.6 s 且过窗口门。

**交付**：`src/velch/vehicle_solver.py`（两门 + 四个纯函数 + 窗口取样）、`src/velch/model.py`
（`stationarity_window_m`）、`src/velch/setup.py`（三个新端口）、`scripts/s99_run_archive.py`（meta 补全）、
`tests/test_launch_gates.py`（7 项）、`tests/test_spin_control.py`（无窗口 8 门）、
`tests/test_setup.py`、`docs/LAUNCH_GATES_2026-11-01.md`（§9 记录这次否决）。

**第二个被闸门驳回的点（同一轮内）**：`tests/test_delivery_check.py` 钉着"规范算例 41 帧 + **七门** 7/7"，
而规范算例现在有 **8 条**（第 8 条无条件计算、第 9 条不声明窗口所以不产生）⇒ 断言 8 == 7 失败，
闸门 `reports/auto_accept_20261101-192321.json` = REJECT（736.08 s、1 failed / 1362 passed）。
处理：把"数门"改成**钉住集合**（八条名字逐条列出，多一条少一条都红），D-SMOKE 的判据写成
"**已产生的每条门都通过**"，`D-SMOKE` 文档与 `s144` 的 docstring 同步；这不是放宽，是把
"七"这个会随门演化而漂的常数换成不会漂的集合。
