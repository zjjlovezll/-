# 车辆数据库（Stage 1）：一台车只有一个定义

**日期**：2026-10-23　**适用版本**：0.4.24 起

## 为什么要有这一层

在这之前，车辆参数是抄在每个算例的 `vehicle` 块里的。后果很具体：

- 同一台车在 358 个算例里可能有 358 个样子，改一个参数得改 358 处；
- 校验规则无处可写——算例格式不检查"质量是不是正数""左右轮是否对称"；
- 想"选一台车来算"没有入口，因为"一台车"这个概念在文件系统里不存在。

现在它存在了：`Velch/vehicles/CRH380A_M.json`，算例里写一行

```json
"vehicle_ref": "CRH380A_M"
```

就代替了整块 `vehicle`。

## 文件长什么样

```json
{
  "schema_version": "velch-vehicle-model-v1",
  "id": "CRH380A_M",
  "name": "CRH380A 动车（M 车，纯刚性标定版）",
  "kind": "EMU power car",
  "source_case": "case_A_final_law.json（validation/crh380a_m）",
  "layout": {"model": "v2-5dof", "bogies": 2, "axles_per_bogie": 2,
             "dof": {"wheelset": ["y","z","roll","spin","yaw"], …}, "state_dimension": 35},
  "gauge_m": 1.435,
  "vehicle": { … 与算例里那一块逐字相同 … },
  "wheels": [{"id": "L", "lateral_offset_m": -0.7465, "profile_filename": "LMA.prw", …}, …],
  "baseline": {"case": "case_A_final_law.json", "static_contact_force_n": 59680.5768587,
               "static_penetration_m": 6.547e-05, "eight_contact_peaks_kn": [89.68, 170.61]},
  "physics_validation_status": "unvalidated_against_measurement_or_Simpack",
  "provenance": {"carbody.mass_kg": "…", …},
  "not_verified": ["惯性张量只声明了三个方向…", "一系二系无 k_x…", "无轴箱/止挡/抗蛇行…"]
}
```

三条规矩：

1. **`vehicle` 块逐字复制**已标定算例里的那一块，不做单位换算、不补默认值——`test_the_block_is_verbatim_from_the_calibrated_case` 钉住这一条。
2. **`physics_validation_status` 与 `provenance` 必填**。一个数说不出出处，就不许进库；没标定的车必须自己写明没标定。
3. **`not_verified` 是清单不是免责**：换车时要逐条看，因为它说明这台车缺哪些物理。

## 校验规则（`velch vehicle validate`）

- 每个刚体的质量与三个惯性为正；一系二系九个字段齐全，刚度阻尼非负，`half_width_m > 0`；
- 七个标量齐全，`wheelbase_m`/`wheel_center_height_m`/`nominal_wheel_radius_m`/`travel_speed_m_s`/`gravity_m_s2` 为正；
- `layout` 必须是 `v2-5dof`、2 转向架 × 2 轴、`state_dimension == 35`（本版没有拓扑引擎，见 Stage 2）；
- 左右两个车轮横坐标必须一负一正且绝对值相等；
- `provenance` 非空、`physics_validation_status` 非空。

任何一条不过，命令退 2 并逐条说要改哪里。

## 命令

```powershell
python -X utf8 -m velch vehicle dir                    # 车辆库在哪
python -X utf8 -m velch vehicle list                   # 逐车一行
python -X utf8 -m velch vehicle show CRH380A_M         # 整份文件
python -X utf8 -m velch vehicle validate CRH380A_M      # 只校验
```

车辆库位置解析顺序：`VELCH_VEHICLE_DIR` → 仓库 `vehicles/` → 冻结安装目录 `vehicles/`。

## 验收：换了写法，一个数字都不许变

```powershell
python -X utf8 scripts/verify_vehicle_ref.py
```

同一个算例跑两遍（一遍内联 `vehicle`，一遍 `vehicle_ref`），逐位比 `history.csv`：

| 项 | 结果 |
| --- | --- |
| `history.csv` sha256 | `7bfbaa1cc7c464918c08bc05ef6d96f68a4e740f2e2bcc733ecac7468566ad88`（两遍相同，244 404 字节） |
| `result_status` | 都是 `numerically_checked` |
| 七项 manifest 门 | 都是 7/7 通过 |
| **VERDICT** | **EQUIVALENT** |

算例 `case_frog_N_strip05.json`（0.05 s、辙叉区、350 km/h）。这条门也是"批量建车"的地基：只要引用能替代内联而数字不变，新增一台车就只是新增一个 json。

顺带一条实现细节：解析 `vehicle_ref` 时会把**车辆文件的 sha256 也写进 `asset_hashes`**，所以跑完之后再改车辆文件，`save_vehicle_result` 的产物校验会失败——这台车是被钉住的，不是"当时大概是那样"。

## 新增一台车的步骤（同拓扑）

1. 复制 `vehicles/CRH380A_M.json`，改 `id`/`name`/`kind`/`source_case`；
2. 换 `vehicle` 块里的数字（质量、惯量、一系二系、轴距、轮径、速度），**同时改** `wheelbase_m` 与 `bogie_half_spacing_m`——它们决定车辆在轨道上的足迹；
3. 按新车轴重重算静载门与七项门基线，写进 `baseline`（**不能沿用 CRH380A 的 59 680.5769 N**）；
4. `velch vehicle validate <id>`；
5. `scripts/verify_vehicle_ref.py --case <该车的算例> --model <id>`，期望 `EQUIVALENT`；
6. 更新 `vehicles/index.json`（或删掉它让程序现算）。

## 还缺什么（Stage 2 及以后）

- **拓扑写死**：`Velch/src/velch/vehicle_solver.py:120-148` 里是 `body = 30`、`range(2)`、`range(4)`、`for side in (-1, 1)`，即 2 转向架 × 2 轴 × 左右两侧；6 轴机车、3 轴转向架、铰接车都进不来。
- **自由度不全**：轮对是 `(y, z, roll, spin, yaw)`，缺 `x` 与 `pitch`；车体/转向架缺 `spin`；全车没有轴箱。
- **悬挂只有三个方向**：`primary`/`secondary` 各有 `k_y`/`k_z`/`k_yaw`，没有 `k_x`、没有侧滚/点头刚度、没有 6×6 交叉项。
- 因此"更完整的三维状态"要等 Stage 2 的**节点表 + 连接器引擎**（6 自由度/体、6×6 刚度），并且旧 35 自由度必须作为兼容剖面**逐位不变**。

界面里"选车 → 计算"（Stage 1 的最后一块）尚未接线，下一步做。
