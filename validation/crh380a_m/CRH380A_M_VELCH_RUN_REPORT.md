# CRH380A_M 在 Velch 上的运行验证报告

生成时间：2026-10-21
算例目录：`F:\ai道岔状态反演辨识\Velch\validation\crh380a_m\`
Velch 版本：v0.4.0（`F:\ai道岔状态反演辨识\Velch\src\velch\`）
车辆数据源：`G:\研究生\动力学\CRH380A_纯刚性模型\database\database`（只读，未改动）
Simpack 基准：`F:\ai道岔状态反演辨识\simpack-mcp-2021x\validation\CRH380A_M_2026-10-19\`（`350.sbr`，sha256 `fa4fdc81…c87d`）

---

## 1. 结论摘要

**能跑通。** 用 CRH380A_M 的真实质量/惯量/悬挂参数与真实 `LMA.prw` + 236 个 `Profile_Mileage_*.prr` 截面，Velch 在 350 km/h、1.2 s 行程下完成积分，两套算例（平直控制段、真实道岔全里程）均通过全部 7 项数值门，`result_status = numerically_checked`。

但两条结论必须分开看：

| 用途 | 状态 | 依据 |
|---|---|---|
| 平直段静载与量级 | **可用作回归基线** | 静态轮轨力 59 680.6 N，与 Simpack 同工况 60 167.7 N 差 −0.81% |
| 道岔段动力学 | **尚不可作结果使用** | 右轨峰值 599.7 kN（Simpack 134.97 kN，4.4×）；2401 个采样中 205 个右轨脱离接触（Simpack 全程接触） |

差异已定位到**几何数据解析**，不是积分器或参数错误。三项独立证据见第 5 节。

`manifest.json` 里 Velch 自己写的 `physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack` —— 本次工作没有改这个字段，它表示"通过了数值门"不等于"与 Simpack 数值等价"。

---

## 2. 做了什么

### 2.1 为跑通 CRH380A_M 必须补的两个缺口

Velch v0.4.0 原本不能直接吃 Simpack 的轮轨型面，本次在**不改求解器**的前提下补齐：

1. **`.prw` 轮对型面接入**：`src/velch/profiles.py` 的 `load_profile()` 按 `file_format` 分派解析器、**不校验文件扩展名**，而 `.prw` 与 `.prr` 同为 Simpack 型面格式（含 `type=1`、`units.len=m`）。因此算例里把 `LMA.prw` 直接写成 `"format": "prr"` 即可被正确解析为 `wheel_lower` 图。**Velch 源码零改动**（初版计划是给 `load_profile` 与 CLI `--format` 放行 `prw`，实测无必要，未做）。
2. **轮对型面坐标基准**：`.prw` 的 z 是"相对名义滚动圆的半径偏移"（`LMA.prw` 实测 z ∈ [−16.926, +28.000] mm，法兰顶 +28 mm、轮缘背面 −16.9 mm），而 Velch 的 `wheel_lower` 图要求**轮心坐标系**（z = −半径偏移）。因此轮对型面必须 `z_sign=-1, z_offset_m=-0.430`；钢轨型面则是 `z_sign=-1, z_offset_m=0`（轨顶为 0，轨底为 +29.942 mm）。

第一次跑失败的报错正是这一条的直接后果：

```
SimulationFailure: vertical preload equilibrium failed: max residual 68186.3 N;
The iteration is not making good progress...
```

轴重级残差 68 186 N ≈ 一个转向架自重 6 860 kg × 9.81，说明静态求解在找一个根本接触不到轨面的平衡位置。修正坐标基准后，静态求解收敛到 q_z = −0.4628 mm（7 个垂向自由度全部一致、残差 0.000 N），与解析预测 0.265 mm（初始几何间隙）+ 0.198 mm（承载所需侵入）= 0.463 mm 完全吻合。

### 2.2 三个算例

| 算例 | 文件 | 几何 | 截面数 | 目的 |
|---|---|---|---|---|
| A 平直控制段 | `case_A_plain.json` | 单一 60 kg 轨截面（`Profile_Mileage_JBG.prr`） | 1 侧各 1 | 分离"车辆模型"与"道岔几何" |
| B 真实道岔 | `case_B_turnout.json` | 右轨 236 个里程截面（0–150 m），左轨 2 个（0.0/150.0，同为 JBG） | 236 / 2 | 真实道岔全里程 |
| B′ 分支敏感性 | `case_B_turnout_branches_inverted.json` | 同上，10 处同里程异截面的先后读法反转 | 236 / 2 | 检验切换语义是否决定结论 |

三算例车辆侧完全相同：35 个广义坐标、`track_dynamics.kind = rigid`、8 个轮轨接触 patch（2 侧 × 4 轴）、`travel_speed_m_s = 97.2222`、`x_start_m = 13.5`、`duration_s = 1.2`、`output_step = 0.0005`（2401 点，与 Simpack 基准点数一致）、`method = DOP853`、`rtol = 1e-6`、`atol = 1e-8`。

### 2.3 车辆参数（从 `.spck` 的 `subvar.str` 提取，非估计值）

| 项 | 值 | 来源变量 |
|---|---|---|
| 车体质量 / Ixx,Iyy,Izz | 34 934 kg / 113 200, 1 711 800, 1 615 300 | `$_CB_mass`, `$_CB_Ixx/Iyy/Izz` |
| 构架质量 / Ixx,Iyy,Izz | 3 300 kg / 2 673, 1 807, 3 300 | `$_BF_mass`, `$_BF_Ixx/Iyy/Izz` |
| 轮对质量 / 回转 | 1 780 kg / Ixx 949, Ispin 118, Izz 967 | `$_WS_mass`, `$_WS_Ixx/Iyy/Izz` |
| 轴距 / 转向架跨距 | 2.5 m / 17.5 m | `$_Wheelset_Distance`, `$_Bogie_Distance` |
| 一系纵向/横向/垂向 | 980, 980, 1 176 kN/m | `$_PrimSpr_c_x/y/z` |
| 二系纵向/横向/垂向 | 160, 160, 240 kN/m | `$_SecSpr_c_x/y/z` |
| 抗蛇行 / 横向减振 / 抗侧滚 | 8 850 kN/m, 2 450 kN·s/m, 17 150 kN/m, 40 kN·s/m, 1e6 N·m/rad | `$_SecDamp_AntiS_*`, `$_SecDamp_LAT_*`, `$_AntiRollBar_c_al` |
| 名义滚动圆半径 / 轨距 | 0.430 m / 1.435 m | `$_WS_RWP_NomWheelRadius`, `$_WS_RWP_TrackGauge` |
| 摩擦系数 / 接触阻尼 | 0.4 / 100 000 | `$_WS_RWP_FricCoeff`, `$_WS_RWP_ContactDamping` |

已知折算差异（必须记录，不能当作"已对齐"）：Simpack 每轴另有 2 个转臂轴箱（48.2 kg/个，一轴共 192.8 kg）。Velch 把轴箱并入轮对，故整车质量 48 654 kg 比 Simpack 反算的 49 066.5 kg 少 412.5 kg（−0.85%）。这个差额与静载力 0.81% 的偏差同量级、同方向，说明静态对比的残差主要来自质量建模差异，而不是接触模型。

---

## 3. 数值门与守恒检查

三算例全部 7/7 通过：

| 门 | 判据 | A | B | B′ |
|---|---|---|---|---|
| `solver_completed` | 积分完成 | ✔ | ✔ | ✔ |
| `finite_states_and_forces` | 无 NaN/Inf | ✔ | ✔ | ✔ |
| `vertical_preload_residual` | ≤ 0.1 N | 5.4e−9 | 5.4e−9 | 5.4e−9 |
| `penetration_within_case_limit` | ≤ 1 mm | 0.198 mm | 0.923 mm | 0.923 mm |
| `friction_bound` | 超限 ≤ 1e−7 N | 0.0 | 2.8e−14 | 2.8e−14 |
| `no_edge_limited_active_contact` | 边缘接触 0 | ✔ | ✔ | ✔ |
| `translational_action_reaction` | ≤ 1e−6 N | 5.8e−11 | 1.7e−10 | 1.7e−10 |

求解规模与耗时（单机、单线程）：

| 算例 | nfev | 墙钟时间 | 相对实时 |
|---|---|---|---|
| A | 151 217 | 209.6 s | 175× |
| B | 233 909 | 354.5 s | 295× |
| B′ | 235 001 | 353.5 s | 295× |

能量记录：初始 12 134 221.7 J → 结束 12 144 137.0 J（A）/ 12 144 287.1 J（B）。**这一项不是守恒检验**：纵向运动被规定（`x = x_start + V·t`）且型面沿程变化，外部做功是正常的，`manifest.json` 的 `note` 字段已声明。真正的守恒由 `translational_action_reaction`（作用反作用）与 `friction_bound` 承担，二者均在 1e−10 量级。

---

## 4. 与 Simpack 的定量对比

### 4.1 静载（最有说服力的一项）

| | Velch | Simpack | 差 |
|---|---|---|---|
| 前轮对单侧法向力 | 59 680.6 N（全程 2401 点完全恒定） | 60 167.7 N | −487.1 N，**−0.81%** |
| 车轮截面 | `LMA.prw` | 未确认（模型中 `$_WS_RWP_WheelProf='LMA-wx.prw'`，但该文件在 `wheel_rail_profiles` 里不存在；实际型面由 `rail.r.prof.file()` 指定） | 可能不同一文件 |
| 轨面截面 | `Profile_Mileage_JBG.prr` | 里程表首个截面 | 同一文件 |

Velch 在平直段是**严格定常**的（8 个 patch 全部 59 680.6 N，2401 点无一波动），这正是纯刚性轨道 + 定常截面的应有结果；Simpack 同段有 0.2% 级波动，来自其柔性/接触阻尼细节。0.81% 的偏差方向与量级都能用 412.5 kg 的质量差解释，因此**可以认为平直段的静力量级已对齐**。

注意：`result_summary.json` 里 Simpack 通道的 `unit` 为 `null`（`unit_status: not_exposed_by_post_qsa`），QSA 不暴露单位。此处把 60 167.7 当作 N 使用，依据是它与 Velch 独立算出、由质量与重力直接确定的 59 680.6 N 只差 0.81% —— 若单位是 kN 或 kgf，这个吻合不可能出现。这是**推断**，不是 Simpack 给出的声明。

### 4.2 10 处同里程异截面处的前轮对法向力

Simpack 侧取跨界前后两个采样点（`sample_before/after`），Velch 侧取 `|t − t_cross| ≤ 1.5 ms` 窗口内的极值。

| 里程 (m) | Simpack 左 (N) | Simpack 右 (N) | Velch 左 (N) | Velch 右 (N) | 判断 |
|---|---|---|---|---|---|
| 50.578 | 59 714 | 56 169 | 60 076 | 66 472 | 量级一致 |
| 52.889 | 62 255 | 58 173 | 59 577 | 59 620 | 一致 |
| 57.304 | 55 346 | 49 693 | 60 326 | **115 425** | 2.3× |
| 60.963 | 56 755 | 58 508 | 65 182 | 68 183 | 偏大 15% |
| 69.479 | 60 036 | 60 097 | 61 481 | 60 925 | 一致 |
| 78.538 | 59 690 | 59 789 | 59 860 | 60 256 | 一致 |
| 79.131 | 60 500 | 58 072 | 58 975 | 65 066 | 偏大 12% |
| 79.440 | 63 941 | 44 783 | 59 899 | 52 378 | 趋势一致 |
| 80.278 | 56 795 | **134 970** | 54 372 | **358 291** | 2.7× |
| 80.911 | 59 134 | 55 533 | 58 026 | **0** | Velch 脱轨接触 |

结论：**10 处里有 6 处量级一致（±20% 内），分歧集中在 57.304、80.278、80.911 三处**。这不是"Velch 整体算错"，而是特定截面切换处的局部响应被放大。

### 4.3 全里程峰值

| | Velch A（平直） | Velch B（道岔） | Simpack B |
|---|---|---|---|
| 左轨峰值 | 59.7 kN | 78.98 kN | 90.72 kN |
| 右轨峰值 | 59.7 kN | **599.75 kN** | **134.97 kN** |
| 右轨最小 | 59.7 kN | **0（205/2401 采样脱离）** | 27.67 kN |
| 左轨最小 | 59.7 kN | 39.84 kN | 34.36 kN |

右轨峰值出现在 t = 0.606 s、前轮对 x = 82.42 m —— **不是** 10 处切换点中的任何一处，而在 80.911 m 那次脱离接触之后 1.5 m。

---

## 5. 差异溯源：几何数据解析，不是积分器

三项独立证据。

### 证据一：峰值力可由侵入量精确反算，说明峰值是"几何逼近"而非"力模型异常"

Velch 的接触是 3/2 幂 Hertz（`effective_radius_m = 0.02`，`tangent_model = sditt_cubic_saturation`）。用平直段的实测标定点 (δ₀ = 0.1976 mm → F₀ = 59 680.6 N) 外推：

```
F = F₀ · (δ/δ₀)^1.5 = 59 680.6 × (0.9229/0.1976)^1.5 = 608 kN
```

观测 599.75 kN，差 1.4%。也就是说：**峰值力完全由"0.92 mm 侵入"这一几何事实决定**，接触本构没有异常行为。0.92 mm 的侵入来自道岔段局部支撑高度比平直段低约 0.5 mm，而刚性轨道下车辆垂向约束由悬挂刚度（1 176 kN/m 一系 + 240 kN/m 二系）提供，无法在 3.9 ms（一个截面间隔 0.38 m / 97.2 m/s）内跟随，于是侵入量被放大到 0.92 mm。

直接接触探测（`probe_local.py`，绕过求解器）证实了这种"局部支撑高度变化"：

| x (m) | 轮对垂向沉量 | 侵入量 | 接触点横向位置 |
|---|---|---|---|
| 13.50 | −0.460 mm | 0.1948 mm | 752.774 mm |
| 60.00 | −0.460 mm | 0.1818 mm | 751.848 mm |
| 70.00 | −0.460 mm | 0.1878 mm | 753.000 mm |
| **80.00** | −0.460 mm | **0.0000 mm** | **738.283 mm** |
| 82.42 | −0.460 mm | 0.2038 mm | 748.195 mm |
| 84.00 | −0.460 mm | 0.2484 mm | 751.466 mm |

同样沉 0.46 mm，在 x = 80.00 m 处侵入为 0 —— 那里的轨面比平直段低，轮对需要再沉约 0.5 mm 才碰到。这就是道岔段几何不平顺的直接量测。

### 证据二：右轨"最高点"沿里程横向迁移最大 64 mm

对 236 个右轨截面，在轮对可达横向带（绝对 y ∈ [725, 815] mm）内取 `argmax(z)`：

- 最高点高度 z 很平（−0.0556 … +0.0040 mm，峰峰值 **0.060 mm**）→ 轨顶没有毫米级垂直凹凸
- 最高点横向位置 y 从 **750.94 mm 移到 814.95 mm**（**64.01 mm**），且是单调、平滑的迁移，不是噪声

轮对型面在该横向带内的滚动半径随 y 变化（LMA 踏面锥度约 1:40，靠外半径更小）。接触点随轨顶最高点外移 64 mm，等效滚动半径变化约 1.6 mm —— 这与证据一量到的"需多沉约 0.5 mm"是同一件事的两种描述，且方向一致。

### 证据三：80.911 m 处的截面横向轮廓跳变约 100 mm

`Profile_Mileage_XG_JJ.prr`（s = 80.911）的原始点列：**y ∈ [−37.224, +139.552] mm，共 2012 点**，即横向总宽 176.8 mm、且是一条**单值连续折线**（点与点之间无 >5 mm 的横向跳变）。它描述的是**道岔区段的多轨合并轮廓**：本地坐标系里 −37…+37 mm 是基本轨（轮对实际走行的那一股），+65…+139 mm 是另一股（直股/导曲线侧）已张开的轨头。s = 80.911 之后的下一个截面（81.290）横向宽度回到约 790 mm 的单轨轮廓。

即：**该处横向轮廓在 0.38 m 里程内收缩约 100 mm**。

这与 Velch v0.4.0 的既有建模限制直接冲突 —— 算例里已经声明：

> `single equivalent rail per side per axle: no stock/switch/wing sub-rail split`

Velch 每侧每轴只有 1 个接触 patch，把整个横断面压成"顶部一条 z(y) 曲线"。当断面里同时存在两股轨头时，这条曲线只能表达其中一股；当最高点在这两股之间跳变时，接触点会突然横移（上表的 752.774 → 738.283 mm 就是实例），轮对的有效支撑高度随之跳变。

### 排除项：分支读法不是原因

把 10 处同里程异截面的 `before/after` 反过来（B′ 算例）后：

| | B（正序） | B′（反序） |
|---|---|---|
| 右轨峰值 | 599 746 N | 599 172 N |
| 右轨脱离采样 | 205 / 2401 | 204 / 2401 |
| 最大侵入 | 0.9229 mm | 0.9232 mm |
| nfev | 233 909 | 235 001 |

差异 < 0.1%。所以"切换语义读反了"不能解释峰值 —— 换向只是把那一次几何跳变挪到相邻站位。真正的成因是**断面本身的横向轮廓包含多股钢轨**，而 Velch 只允许一股。

---

## 6. 对四阶段计划的对应结论

用户给出的第一阶段验收是"接触位置、法向、作用反作用、摩擦功率、网格收敛均有报告"。逐项对照：

| 第一阶段要求 | 当前状态 |
|---|---|
| 读 PRW 与各类 PRR，确定坐标与里程分支 | **已完成**（本轮补齐 `.prw` 与 z 基准；236 截面全里程可读，10 处同里程对已配置） |
| 多轨接触点 | **未完成**。每侧每轴 1 个 patch，无法表达基本轨/尖轨/翼轨分股 —— 这正是 599 kN 的成因 |
| 把 CONTACT 局部力映射到轮对与钢轨 | **未接线**。`contact_native.py` 只提供 `run_contact_hertz_probe()` 这一球面 Hertz 探针（`contact_addon_win64.dll`，三网格 104.352 kN，相对解析 0.0083%），`vehicle_solver.py` 只 import `contact.find_graph_contact` / `evaluate_contact`，`run-vehicle` 恒用 `hertz_effective_radius` |
| 接触位置 / 法向 / 作用反作用 / 摩擦功率报告 | **部分**（作用反作用 1.7e−10 N、摩擦越界 2.8e−14 N 已入 manifest；接触位置与法向逐点存于 `history.csv`；摩擦功率需补输出） |
| 网格收敛 | 仅 CONTACT 独立球面算例有（16/32/64 → 104.52/104.36/104.352 kN）；Velch 接触侧无网格概念，需用 `output_step` 与 `rtol/atol` 收敛性替代 |

第二阶段（车辆—道岔对照）现在有了可比的通道级数据，但**还不能下"精度一致"的结论**：Simpack 侧只有 4 个通道被映射（`carbody_x`、`front_wheelset_x`、前轮对左右接触 z），且单位未暴露；横向位移、接触切换时刻尚未抽取。

第三阶段（轨下结构）在本次算例里被显式关掉了（`track_dynamics.kind = rigid`，35 DOF，无轨道模态）。这是**刻意**的：先把接触几何定位清楚，否则轨道柔性会把接触误差掩盖掉。

---

## 7. 产物与复现

### 7.1 Velch 源码改动

**零改动。** `src/velch/` 下 12 个模块、`tests/` 下 16 项测试均未修改。CRH380A_M 所需的全部适配都通过算例文件表达：

- `LMA.prw` 以 `"format": "prr"` 传入（同一解析器，不校验扩展名）
- 轮对型面 `z_sign=-1, z_offset_m=-0.43`；钢轨 `z_sign=-1, z_offset_m=0`
- `track_dynamics.kind = "rigid"`、`x_start_m = 13.5`、`travel_speed_m_s = 97.2222`

这一点很重要：本次跑通不依赖任何未提交的分支或补丁，随时可用原始 v0.4.0 复现。

### 7.2 新增文件

| 文件 | 内容 |
|---|---|
| `build_case.py` | 从 `.spck` 参数表 + 截面目录生成 `velch-vehicle-v2` 算例；`--mode {plain,turnout}` `--duration` `--branches {forward,inverted}` |
| `case_A_plain.json` | 平直控制段（7 209 B） |
| `case_B_turnout.json` | 真实道岔 236 截面（103 079 B 量级） |
| `case_B_turnout_branches_inverted.json` | 分支敏感性孪生算例 |
| `probe_contact.py` | 绕过求解器复现 `find_graph_contact`，用于定位坐标基准问题 |
| `probe_local.py` | 单点接触探测（侵入量/接触横向位置 vs 里程） |
| `probe_crown.py` | 236 截面轨顶最高点高度与横向位置序列 → `rail_crown_series.csv` |
| `probe_one_section.py` | 单个断面原始点列结构（横向宽度、连续性） |
| `report_track_geometry.py` / `track_geometry_report.txt` | 全里程几何巡览（被 `probe_crown.py` 取代：前者用纯 `z` 极值判定轨顶，遇到多股轨头顶部等高的断面会取错股） |
| `cmp_crossings.py` | 10 处同里程异截面力的双模型对照表 |
| `cmp_branch.py` | 正序/反序算例对照 |
| `summarize_case.py` / `collect_final.py` | manifest 汇总 |
| `out_A_1p2s/`、`out_B_1p2s/`、`out_B_1p2s_inverted/` | 各自 `case_snapshot.json` + `history.csv` + `manifest.json` |

### 7.3 复现命令

```powershell
cd 'F:\ai道岔状态反演辨识\Velch'
$env:PYTHONIOENCODING='utf-8'
python validation\crh380a_m\build_case.py --mode plain   --duration 1.2
python validation\crh380a_m\build_case.py --mode turnout --duration 1.2
python -m velch run-vehicle validation\crh380a_m\case_A_plain.json   --output validation\crh380a_m\out_A_1p2s
python -m velch run-vehicle validation\crh380a_m\case_B_turnout.json --output validation\crh380a_m\out_B_1p2s
```

`--output` 是**目录**；成功判据是 `manifest.json` 里 `summary.result_status == "numerically_checked"`。

### 7.4 回归状态

`python -m pytest -q --basetemp=build\pytest-tmp` → **16 passed**（contact / contact_native / profiles / simpack_database_profiles / solver / vehicle / gui_support 全部通过）。

环境备注：直接 `pytest -q` 会有 8 项因 `PermissionError: [WinError 5] …\AppData\Local\Temp\pytest-of-zjjLOVEzll` 在 fixture 阶段报错 —— 那是本机临时目录的 ACL 问题（历史遗留的沙箱残留），不是测试失败；指定可写 `--basetemp` 后全部通过。

---

## 8. 下一步建议（按优先级，均属第一阶段）

1. **拆分子轨接触（阻塞项）**。把每个 rail template 从"1 条等效轨"扩展为同一侧可并存的多条子轨（基本轨 + 尖轨/翼轨），各自一套 `stations` 与 `ProfileSeries`，接触搜索在全部子轨上取最大侵入。这是让 57.304 / 80.278 / 80.911 三处分歧收敛的前提，也是四阶段计划里"多轨接触点"的实质内容。**在此之前，任何道岔段的力值都不应作为结论引用。**
2. **把 CONTACT 接入 `run-vehicle`**。`contact_addon_win64.dll` 已验证（球面 104.352 kN，三网格收敛 0.0083%），但目前只作为独立探针存在。接入后需要补：接触斑网格收敛报告、法向与切向力分解、摩擦功率输出（`friction_dissipation_w` 已在 `ContactResponse` 里，只需写入 `history.csv`）。
3. **补齐 Simpack 侧可观测通道**。当前只有 4 个标量通道，缺轮对横移、摇头、接触切换时刻。至少补 `front_wheelset_y`、`front_wheelset_yaw`、左右接触 `x/y` 位置，才能把"接触切换时刻"这一项验收做出来。

配套的一致性约束：任何一处改动后，`case_A_plain` 的 59 680.6 N 与 0.198 mm 侵入必须保持（这是当前唯一的回归基线）。

---

## 9. 本报告不主张的内容

- 不主张 Velch 与 Simpack 动力学等价。平直段静力量级一致（−0.81%）不代表瞬态响应一致。
- 不主张 599.75 kN 是道岔的真实冲击力。它是"把多轨断面压成单轨"这一简化下的产物；Simpack 在同一里程峰值 134.97 kN，两者之差不能解释为任一方的物理真实值。
- 不主张已识别出 10 处同里程异截面的正确切换语义。正序/反序差异 <0.1%，说明在该算例里这个语义不是主导因素，但并未证明正序读法正确。
- 不主张截面数据有错。236 个截面全部可读、0 缺失、无几何解析异常；其中横向宽度 176.8 mm 的断面在道岔语义下是合理的（多股轨头合并轮廓）。问题在 Velch 的表达能力，不在数据。
