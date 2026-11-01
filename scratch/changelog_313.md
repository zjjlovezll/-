## 第 313 轮 — 一条连贯的跑算例路径：一个 setup、八个端口、起点拒绝起跑

用户要的是"改一个小参数就能跑"（m06836）。原来的链有三个断点，这轮全部接上。

**路径**：`setups/one_set_straight.json` + `scripts/s172_run_case.py`。
端口 `--set NAME=VALUE`：`speed.kmh`、`duration.s`、`output_step.s`、`report_launch`、`label`、
`prebalance.equilibrate_vertical`、`prebalance.seat_lateral`、`prebalance.seat_modal_scales`；
未知名拒绝并列出合法名，超范围拒绝，缺 `=` 拒绝。

**顺序是核心**：`velch.setup.resolve` 先把手上的端口写进新 case 文件、再 `load_vehicle_case`，
转速由 loader 从 `travel/r` 派生，因此不可能停在旧值上；随后 `check_kinematics` 独立核
`|spin·r − travel|/travel ≤ 1e-3`。旧的 `apply_speed` 打补丁路线在 60 km/h 上给 **0.3333**，
测试里**故意复现**并要求该状态被拒绝。

**实测（同一算例、同一 0.02 s）**：旧路径前 0.02 s 八轨法向力最大跨度 **43.573 kN**、std **8.317 kN**；
新路径 60 km/h **0.439 / 0.103 kN**、80 km/h **0.417 / 0.096 kN** ⇒ 安静 **99 倍**，
且两速度现在只差 **7 %**（"改一个参数、其余不变"成立）。

**撤回一条自己拍的判据**：`LAUNCH_MODAL_RESIDUAL_N = 0.1` 无测量依据。实测 60 → **106.74 N**、
80 → **101.45 N**；沉降 400 轮与 80 轮**逐位相同** ⇒ 是 `_settle_modal_coordinates`↔`_seat`
交替不动点自身的 **~1e2 N**，与速度无关。改为**上报**（占轮载 **0.170 %** @80、**0.179 %** @60），
`balanced` 只由两条既有门限（预载 0.1 N、转速 1e-3）决定；残差要不要紧交给平稳性审计（`s164`，5 kN）。

**第四个缺陷**：归档标签取了"文件里的 setup"而非"解析后的 setup"，把 60 km/h 那趟命名成
`…-080.00kmh-…`（两个不同 case 同名前缀）。已修为 `resolved.setup`，并删掉错标签目录与索引行（66 → 65）。

**交付**：`src/velch/setup.py`、`scripts/s172_run_case.py`、`setups/one_set_straight.json`、
`src/velch/vehicle_solver.py`（`VehicleResult.launch` + `_launch_report`）、`src/velch/model.py`
（`RunSettings.report_launch`）、`scripts/s99_run_archive.py`（抽出 `write_archive`，meta/index 记 launch/setup/overrides）、
`tests/test_setup.py`（5 项）、`docs/RUN_PATH_2026-11-01.md`。

**边界**：只到 0.02 s；60 km/h 那一行**仍然撤回**（需 ≥1.6 s 且过平稳性）；未改七门；冻结物理未动。
