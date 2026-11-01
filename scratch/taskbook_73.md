## 七十三、第 314 轮：第 8、9 条门（第 9 条被自己的闸门否决后收紧）

| 项 | 内容 |
|---|---|
| 起因 | 七门放行了 std 34.75 kN 的 60 km/h 那趟（0–207.75 kN） |
| 第 8 条 | `launch_balance`：预载 ≤0.1 N（既有）且 `\|spin·r−travel\|/travel ≤1e-3`（既有） |
| 不进门的数 | 模态残差（60 → 106.74 N、80 → 101.45 N，400 轮逐位相同）只上报份额 0.170 %/0.179 % |
| 第 9 条第一次 | 整段记录 std ≤5 kN ⇒ 闸门 **REJECT**：基线算例合法转移 **53.88 kN**（`axle1_right_switch`）被当"没静下来"，4 个既有测试失败 |
| 第 9 条现在 | 只在算例声明 `run.stationarity_window_m` 时产生；窗口内（前轴里程、≥3 样本）八轨 std 最大者 ≤ **5 kN**；没声明 ⇒ 不产生 |
| 实测分离度 | 振着 34.75 / 新路径 60、80 → 0.103、0.0962 / 静态 100 → 0.51 / 凸起 0.20–0.80 kN |
| 配套端口 | `start.x_m`、`seat.start_m`、`reading.window_m`（`none` 显式不主张）；setup 声明 `[56,65]`+`46`+`40` |
| 状态 | `numerically_checked` / `physical_gate_failed` / `numerical_gate_failed` |
| 开关 | 起点报告无条件计算，`report_launch` 只决定打印与归档 |
| 归档 | `meta.json` 增 `result_status`、`failed_gates`、`max_rail_force_std_kn`、`stationary_force_std_limit_kn`、`stationarity_window_m`、`stationarity_samples`、`launch` |
| 实测 | 60/80 各 41 帧 **9/9**（窗口 41 样本）；基线无窗口 **8/8**、`stationarity` 不出现 |
| 不追溯 | 旧归档保留原记录；60 km/h 行仍撤回，恢复需 ≥1.6 s 且过窗口门 |
| 测试 | `tests/test_launch_gates.py` 7 项（含"无窗口不产生门"与"窗口 0 样本必失败"）、`test_spin_control.py` 无窗口 8 门 |
