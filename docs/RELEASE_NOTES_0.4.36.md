# Velch 0.4.36 发布说明

日期：2026-10-26

## 本轮结论

**换一台电脑、不设任何环境变量，包里的模型现在能直接跑 —— 而且这是自动化验证过的，不是承诺。**
上一版把车辆库与柔性轮对模态集打进了包，但算例只能用绝对路径引用模态集；这一版加了资产解析层，
并新增一条"干净机器"验收。

- 新增 `src/velch/assets.py`：**一处解析**，四种写法。普通相对名仍相对算例文件（既有文档一字不改）、
  `case:` 显式同义、`lib:` 指向包内车辆库（`lib:vehicles/modes/...` 与 `lib:modes/...` 都认）、
  `data:` 指向语料根；绝对路径继续接受但失败时会直说"不可移植"。
  失败抛 `AssetRefError`（`FileNotFoundError` 子类，旧的 `except` 仍成立），消息里列出找过的每个根。
- `vehicle.py` 四处引用点（型面、`.tre`、`modal_file`、`flexible_wheelset.file`）全部改走它。
- 新随包算例 `examples/portable/case_flexible.json`：柔性轮对 4 轴，模态集用
  `lib:vehicles/modes/CRH3C_wheelset_fe.json`，型面用 `../vehicle_v2/...`（相对算例文件的一层子目录）。
  实跑：`numerically_checked`、七门 7/7。
- 新 `packaging/clean_room_test.py`（5 步）：拷到临时目录 → **白名单环境**（只保留系统变量，
  任何 `VELCH_*` 都不会漏进去）→ `LOCALAPPDATA` 重定向 → 查 5 台车型 → `--selftest` →
  跑随包柔性算例 → **再搬到含中文与空格的路径重跑，要求 `history.csv` 逐字节相同**。
- 顺带修三处：
  - `track_models.py` 的模态分支用 `q[self.offset:]`，而柔性轮对的模态坐标现在落在轨道块**之后**，
    切片越界（读码 + 同库注释互证）；改为切到 `offset + dimension`；
  - 语料根现在同时接受 `…/velch_data` 与 `…/velch_data/validation`（旧提示词写的上一层会让程序
    去找 `velch_data/crh380a_m` 然后报"空语料"）；自检提示与 `.velch-data.example.json` 一并改正。

## 验证

- `packaging/clean_room_test.py --root dist_installer\Velch` → **ACCEPT · 5 步 · 失败 0**
  （`reports/clean_room_20261026-102738.json`）；
- `packaging/smoke_test.py --readonly-acl` → ACCEPT · 8 步 · 失败 0 · 跳过 0；
- 全仓 `pytest`：819 passed, 1 skipped；
- `scripts/physics_invariants.py` → VERDICT: UNCHANGED（整程峰值 170.61 kN、七门 7/7）；
- 冻结物理未动：静载门 59 680.5769 N / 65.47 µm、八接触峰值 89.68 / 170.61 kN、DOP853 逐位不变。

## 已知边界（与 0.4.35 相同）

- **语料（1.4 GB / 368 个算例）不进包**，且那批算例里的型面与 `.tre` 仍是 `G:`/`H:`/`F:` 绝对路径，
  拷到别的机器要先做一次相对化（`docs/PORTABLE_PACKAGE_DESIGN_2026-10-26.md` 的 P0-2）；
  包内自带算例不受此影响。
- `physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`；
- 未做代码签名，首次运行会弹 SmartScreen。
