# 新增车体 / 新增道岔的接入指南

**结论先说**：接入分三档，只有第三档要改代码。

| 档 | 场景 | 要做什么 | 需要改代码吗 |
|---|---|---|---|
| T1 | **新道岔**（任意号数、任意岔型，直向） | 生成型面目录 → 建算例 → 拆轨体 → 过三道门 | **不用** |
| T2 | **新车体**（同一拓扑：4 轴、2 构架、1 车体） | 换 `vehicle` / `wheels` 参数块 | **不用** |
| T3 | **新拓扑**（3 轴、铰接、轴箱体、双车、牵引电机） | 先把"装配"抽成一层（`dyn/assembly.py`），再加拓扑描述 | **要** |

---

## T1 新增道岔（纯配置）

### T1-1 拿到型面并生成目录

数据来源二选一：

- **Simpack 模型**（推荐，与既有 CRH380A 同源）：从 `CRH380A_M_Wheelset.spck` 取
  `rail.r.prof.file(1..N)` + `rail.r.prof.s(1..N)` 两条参数，以及
  `<model>/wheel_rail_profiles/*.prr`。可用 `simpack-mcp-2021x` 的
  `simpack_trace_prr_profiles` / `simpack_validate_turnout_profile_set` 只读核对。
- **图纸/实测**：自己按里程准备 `.prr`（格式：`header.begin/end` + `spline.begin` + `point.begin/end`，
  `units.len='m'`，每行 `y z`）。

生成的目录格式照抄 `Velch/diagnostics/crh380a_m_track_catalog.json`，关键字段：

```
profile_references[]: {station_m, side, file, format, units, ...}
coincident_stations[]: {station_m, indices[], side}   # 同里程异截面，必须显式
model_files[] / summary{}
```

### T1-2 建算例

```bat
python -X utf8 validation\crh380a_m\build_case.py --mode turnout --catalog <catalog.json> --duration 0.05
python -X utf8 validation\crh380a_m\build_case.py --mode plain   --catalog <catalog.json>
```

`--mode plain` 生成"两侧同一断面"的平直对照，用来分离"几何问题"与"道岔问题"；
`--branches inverted` 做"同里程异截面取另一支"的孪生算例，用来证明结果不依赖分支读法。

### T1-3 拆轨体（辙叉/尖轨区必做）

```bat
python -X utf8 validation\crh380a_m\prep_bodies.py        # → turnout_bodies_raw.json
python -X utf8 validation\crh380a_m\build_body_case.py    # → bodies/main_*.csv, point_*.csv
python -X utf8 validation\crh380a_m\build_wing_case.py    # 辙叉缺连续承载面时补 wing 体
```

判据：合并型面在辙叉区会出现"两体融合成一条宽脊（>100 mm）"，此时单轨体模型必然把轮子掉下去
（历史实测：峰值 599 kN、205/2401 采样脱空）。只要看到"承载带在某一里程段整段消失"，就加 `wing` 体。

### T1-4 三道门（缺一不可）

```bat
python -X utf8 validation\crh380a_m\check_body_equivalence.py   # 拆体没改曲面：worst 0.0000 mm
python -X utf8 validation\crh380a_m\check_static_gate.py        # 静载 59 680.577 N、侵入 65.5 µm
python -X utf8 validation\crh380a_m\minpen_report.py <out>\history.csv   # 脱空 0、min_pen > 0
```

### T1-5 冻结该道岔的 oracle 并写一行文档

新道岔**不能**拿旧结论（89.7 kN / 0.593 mm）当基线。冻结要记：
`case_sha256`、`manifest.summary.{peak_normal_force_n, max_penetration_m, ...}`、
轮对行程、主频、以及 `docs/CHANGELOG_DOCS.md` 的状态表一行。

### 三个最容易踩的坑（都有实测代价）

1. **轮型面 z 是"相对名义滚动圆的半径偏移"**，不是轮心坐标 ⇒ 必须
   `z_sign=-1, z_offset_m=-nominal_wheel_radius_m`。写错时静平衡残差是"一个转向架重量 68 186 N"。
2. **左右侧符号**：右轨 `y_offset_m=+0.753, z_sign=-1`；左轨 `y_sign=-1, y_offset_m=-0.753`；
   轮 `y_sign=±1, lateral_offset_m=±0.7465`。弄反会得到"轮子在两轨外侧"的静平衡。
3. **同里程异截面**必须给 `event_branches{before, after}`，否则抛 `AmbiguousProfileError`。
   另注意：拆体后若站位变成 5 mm 重采样网格，原来那两个同里程站位会合并，**台阶语义会丢失** ——
   需要保留台阶时，两站位都要保留。

---

## T2 新增车体（同拓扑，纯配置）

用例 `case_full12_cap05.json` 的 `vehicle` 块为模板，逐项替换：

```jsonc
"vehicle": {
  "carbody":  {"mass_kg": …, "inertia": {"xx": …, "yy": …, "zz": …}},
  "bogie":    {...}, "wheelset": {...},
  "primary":  {"k_y_n_m": …, "k_z_n_m": …, "c_z_n_s_m": …},
  "secondary":{"k_y_n_m": …, "k_z_n_m": …, "c_z_n_s_m": …, "k_yaw_n_m": …, "c_yaw_n_s_m": …},
  "bogie_half_spacing_m": 8.75, "wheelbase_m": 2.5,
  "wheel_center_height_m": 0.43, "nominal_wheel_radius_m": 0.43,
  "travel_speed_m_s": 97.2222, "gravity_m_s2": 9.81,
  "drive_torque_per_wheelset_nm": 0.0
},
"wheels": [{"id": "L"|"R", "lateral_offset_m": ±0.7465,
            "profile": {"file": "…LMA.prw", "format": "prr", "units": "m",
                        "y_sign": ±1, "z_sign": -1, "z_offset_m": -0.43}}]
```

**状态顺序是固定的**（改不了，改了就是 T3）：
`4×轮对[y,z,roll,spin,yaw] → 2×构架[y,z,roll,pitch,yaw] → 车体[y,z,roll,pitch,yaw]` = 35，
后面接轨道自由度。**轨道自由度的"轨数"不是 `rail_templates` 的长度**：加载器把每个模板按
4 根轴展开，所以本例 `rail_templates` 2 条 → **8 条 `VehicleRail`**。总长 = 35 + 每轨自由度 × 8：

| `track_dynamics.kind` | 每轨自由度 | 本例 q 长度 |
|---|---|---|
| `rigid` | 0 | 35 |
| `local_compliant` | 2 | 35 + 16 = **51** |
| `two_layer` | 4 | 35 + 32 = 67 |
| `layered`（L 层） | `2×(1+L)` | L=2 → 35 + 48 = 83 |

`initial_state.q`/`v` 的长度必须正好等于总数（参考算例 `case_full12_cap05.json` 是 51，`case_AB_slab3.json` 是 83）。

`rail_templates[i].support` 是**扣件**，字段恰为
`{"k_y_n_m", "c_y_n_s_m", "k_z_n_m", "c_z_n_s_m"}`（参考算例：5e8 / 2e4 / 5e7 / 4e4）；
轨道层参数在 `track_dynamics.layers[]`。
换车体后**必须重跑静平衡门**：静载 = 总重/接触数，若与旧值不同是正常的，但要与 `Σm·g` 对上。

---

## T3 新拓扑（要改代码）

当前 `vehicle_solver.py` 是**定形装配**：轮对/构架/车体数量、连接关系、状态布局都写死在代码里。
所以下列需求都不只是"加参数"：

- 3 轴/5 轴车、铰接式列车、双车连挂；
- 轴箱体（真实轴箱加速度观测量，现在是轮对加速度的下界）；
- 牵引电机/齿轮箱独立自由度；
- 纵向 `x` 自由度（现在 `axle{i}_x_m` 是运动学强加）。

接入顺序（与 `docs/ARCHITECTURE_2026-10-21.md` 的 S1 步一致）：

1. 把"装配"抽成 `dyn/assembly.py`：`Body(mass, inertia, dof) + Joint + ForceElement` 的列表，
   `VehicleDynamics` 只吃这张表；现有 35 DOF 变成这张表的一个特例。
   验收：新旧两条路径对同一算例产生**逐字节相同**的 `history.csv`。
2. 加通用连接器（弹簧-阻尼-止档）与超定静平衡（现有 `_static_vertical_equilibrium` 只解
   7 个垂向自由度，多体后要解一般超定系统）。
3. 在装配表上表达新拓扑，`initial_state` 由装配表生成（不再手写）。
4. 回归：冻结 oracle + 新的拓扑各一套；`tests/test_architecture_rules.py` 加一条"装配表之外不许写死 DOF 偏移"。

工作量口径：第 1 步是重构（不改数值），第 2 步是本轮真正的新能力。**在此之前，新拓扑请继续用
Simpack + 我们只做道岔侧（型面/接触/轨道）**——这也是当前分工的实际形态。

---

## 一句话总结

- **新道岔**：换型面目录 + 拆体 + 三道门，一天内可完成，且能复用全部脚本。
- **新车体（4 轴）**：换参数块，半小时；但必须重过静平衡门，并冻结新 oracle。
- **新拓扑**：先做装配层重构，属于"加一层"，不是"加一个参数"。
