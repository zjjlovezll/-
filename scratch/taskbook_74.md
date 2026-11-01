## 七十四、第 315 轮：判据的三把尺子与一次覆盖性修复

| 项 | 内容 |
|---|---|
| 触发 | 第 314 轮门 9 在 0.02 s 运行上通过，但窗口 9 m 只走了 0.444 m（`stationarity_samples == frames == 41`） |
| 修法 | `stationarity_coverage`：`expected = (high − low) − spacing`，`covered = span ≥ expected`；`stationarity_gate(..., covered)` 不覆盖即失败 |
| 实测 | `one_set_reading-080…-0.4050s`：811 帧、span 9.000 m、expected 8.9889、spacing 0.01111、covered True、max std 0.2382 kN、**9/9**、wall 363.5 s |
| 回归 | 旧 0.02 s 归档用同一条谓词回算 ⇒ covered False（`test_the_short_archive_that_passed_in_round_314_would_now_be_refused`） |
| 入口 | `resolve` 在 `duration × speed < 窗口长度` 时拒绝：0.405 s @ 60 km/h = 6.750 m < 9 m |
| 证据 | `summary["launch"] = launch_report`；`s99` 在 `launch is None` 时回落 summary（修掉 `launch_balance: true` 配 `launch: null` 的归档） |
| 界面 | `GATE_LABELS` 九条 + 表外键按原名渲染 + `failed` 从合并行取（此前门 8 失败显示 7/7） |
| 撤掉的尺子 | 模态残差 ≤0.1 N（不动点恒 101–107 N）、整段 std ≤5 kN（基线转移 53.88 kN）、门数 = 7（改钉集合） |
| 未做 | 60 km/h 行仍撤回（恢复需 ≥1.6 s 且过覆盖性门）；`Ω_obs` 主门三件待批准 |
