## 第 315 轮 — 让"平稳"先证明窗口走到了（覆盖性、起点证据、屏幕上的九门）

第 314 轮把门 9 加进求解器，但审查（以及我自己的回读）发现它**只在数样本**：两个 0.02 s 归档在 9 m 的窗口里各放了 41 个样本（`stationarity_samples == frames == 41`），行程只有 0.444 m / 0.333 m，覆盖 **4.9 % / 3.7 %**，却因为 `std = 0.096 / 0.103 kN` 远低于限值而通过。同一轮还留下两个更小的洞：门 8 的证据可能被归档丢掉（`launch_balance: true` 配 `launch: null`），以及屏幕的 `GATE_LABELS` 只有七条、`_render_gates` 只遍历它，于是**门 8 失败会显示成 7/7 PASS**。

这一轮只做三件"让门说真话"的事：

1. **覆盖性**：新增 `stationarity_coverage(stations, window)`——`spacing = median(diff)`、`expected = (high − low) − spacing`、`covered = span ≥ expected`，允许**一个采样间距**的欠额（网格上不可能两端都落样本）。`stationarity_gate` 增加 `covered` 参数，不覆盖即失败。实测 `one_set_reading-080…-0.4050s`：811 帧、`span 9.000 m`、`expected 8.9889`、`spacing 0.01111`、`covered True`、`stationarity` 在 **0.2382 kN** 上通过、9/9、wall 363.5 s；用同一条谓词回算第 314 轮那份 0.02 s 归档 ⇒ **`covered False`，与新判据下必失败**。
2. **入口拒绝**：`velch.setup.resolve` 在 `duration × speed < 窗口长度` 时直接抛错（0.405 s @ 60 km/h = 6.750 m < 9 m），并给三个出路（加时长 / 缩窗口 / `reading.window_m=none`）。因此新增 `setups/one_set_reading.json`（0.405 s、`[56, 65]`、9 门），而 `setups/one_set_straight.json` 改成 `reading.window_m: none`（0.02 s、8 门、12.9 s）——两者的差别就是"是否主张平稳性"。
3. **证据与界面**：`summary["launch"] = launch_report`（与门同源），`s99.write_archive` 在 `launch is None` 时回落 `summary["launch"]`；`GATE_LABELS` 扩到九条、`_render_gates` 把表外的门按原名渲染、`failed` 从合并后的行取。

一并撤掉我这三轮自己造的三把尺子：模态残差 ≤0.1 N（实测不动点恒 101–107 N，与速度无关）、整段 std ≤5 kN（冻结基线 0.015 s 内合法转移 53.88 kN）、`门数 = 7`（改成钉门名集合）。

文档 `docs/LAUNCH_GATES_2026-11-01.md` §10–§13；测试 `tests/test_launch_gates.py`（9 项，含覆盖性两侧与旧归档回算）、`tests/test_setup_window.py`（4 项：统一校验器、装载器用它、不可达拒绝、无窗口不产生门）、`tests/test_gate_labels.py`（3 项）。
