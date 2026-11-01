## 七十二、第 313 轮：连贯路径与起点拒绝起跑

| 项 | 内容 |
|---|---|
| 用户要求 | "包装好，只要在端口改速度/预平衡就能跑，借鉴 Simpack"（m06836） |
| 单一入口 | `scripts/s172_run_case.py`（`--setup`、`--set`、`--dry`、`--out-dir`） |
| 唯一 setup | `setups/one_set_straight.json`（label / case / speed / duration / output_step / report_launch / prebalance） |
| 端口 | `speed.kmh`、`duration.s`、`output_step.s`、`report_launch`、`label`、`prebalance.{equilibrate_vertical,seat_lateral,seat_modal_scales}`；未知名与超范围均拒绝 |
| 顺序 | 先写 case 文件再 load，转速由 `travel/r` 派生；`check_kinematics` 独立核 ≤1e-3 |
| 旧路径缺陷 | `apply_speed` 打补丁后 60 km/h 的转速仍是 80 的 **51.6796 rad/s**，相对差 **0.3333**（测试故意复现并拒绝） |
| 起点报告 | `VehicleResult.launch`：`modal_norm_m`、`modal_residual_n`、份额、预载残差、每轴转速、`spin_relative_max`、`balanced` |
| 判据撤回 | `LAUNCH_MODAL_RESIDUAL_N = 0.1 N` 无依据；实测 60 → **106.74 N**、80 → **101.45 N**，400 轮沉降逐位相同 ⇒ 上报，不设门 |
| 实测安静化 | 旧路径前 0.02 s 八轨最大跨度 **43.573 kN** / std **8.317 kN** → 新路径 **0.439 / 0.103 kN**（60）、**0.417 / 0.096 kN**（80），安静 **99 倍**，两速度差 **7 %** |
| 第四个缺陷 | 归档标签用文件里的 setup 而非解析后的 ⇒ 60 km/h 被命名 `…-080.00kmh-…`；已修并删除错标签目录与索引行（66 → 65） |
| 测试 | `tests/test_setup.py` 5 项（12.3 s） |
| 边界 | 只到 0.02 s；60 km/h 行仍撤回（需 ≥1.6 s + 平稳性）；未改七门；冻结物理未动 |
