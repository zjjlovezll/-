
## 第 162 轮：六个区段深度重算 —— 速度修正只值 1 %，我上一轮的 +20 % 预测是错的

* `scripts/s20_section_depths.py`：逐区段按其平均速度插值压过区间算子（2.730e4–2.737e4），除以实测幅值。
* 结果：区段均值 **7.7 / 8.0 / 8.0 / 10.2 / 15.2 / 18.1 / 20.3 µm**（S1–S6 排序后的范围 7.7–20.3），
  12 条记录中位 **9.7 µm**（单一算子 9.6，**+1 %**），记录范围 **3.0–37.7 µm**。
* **更正第 161 轮**：预测的「中位 12.6 → 15–16 µm」不成立。那 23 % 只在跨速度外推时出现，而本数据整体 ~76 km/h，
  与标定速度 70.8 km/h 只差 −0.8 %。
* 统计量口径：12 条记录中位 9.7、6 个区段均值中位 12.7、单条记录 3.0–37.7 —— 引用时必须写明哪一种。
* `tests/test_section_depths.py` 4 项。

## 第 161 轮：探针设计 3.3 倍、增益差 0.4 %（第 4.8 节的混淆测开了）

* `s16_operator.model_gain` 增 `crossing_window`：投影窗口 = 前轴压过波磨的区间；`design` 元数据落盘。
* `scripts/s19_operator_design.py`：240 / 790 周期两种设计 × 5 个速度，10 次运行全部 `numerically_checked`。
* 结果：设计差 ≤ **0.4 %**；速度效应 40→80 km/h 增益 +32.3%；70.8 km/h 2.7570e4 与原标定 2.755e4 差 0.07 %。
* **更正第 160 轮**：那 23 % 是投影窗口造成的，不是探针设计；80 km/h 增益应由 2.087e4 改为 2.721e4，
  中位深度需用压过区间算子重算。
# 文档索引（单一入口）

> 先说结论，再给证据链。每份文档都标注了**它回答的问题**、**当前是否仍成立**、
> 以及它的证据来自哪一次运行。已作废的结论单独列出，避免再被引用。

最后更新：2026-10-22

## B3（接触表按批次摊销）2026-10-22 —— 实测复用 782×，批内 4.07×–17.04×

| 交付 | 路径 | 结论 |
|---|---|---|
| 调用计数 | `validation\crh380a_m\probe_table_amortization.py` | 单 run 97 736 次接触搜索、仅 **125** 个 `(站位, roll)` 单元、复用 **781.9×** |
| 批次定价 | `docs\B3_TABLE_AMORTIZATION_2026-10-22.md` | 1 次 4.07×、5 次 10.75×、10 次 13.52×、50 次 17.04×（上限 18.2×） |
| 复用前提 | `b3_amortization_*.json` | C 变 +1 % 时单元格集合 Jaccard **1.00**（125 全共享）⇒ 建表可整批共享 |

## B5（雅可比作事件检测）2026-10-22 —— 负结果，无对比度

| 交付 | 路径 | 结论 |
|---|---|---|
| 扫描实测 | `validation\crh380a_m\probe_jacobian_events.py` | 真正脱空步 ‖ΔJ‖ = **7.85e5**；相邻非事件步 **6.66e5–8.31e5**，事件反而最小 |
| 判定 | `docs\B5_JACOBIAN_EVENTS_2026-10-22.md` | `‖J‖` 由 `C·δ^0.5` 主导（4.5e6–5.4e6），换面为高阶小量 ⇒ 需离散归属量而非力导数范数 |

## A2（C–δ 简并）2026-10-22 —— 刚性偏移是规范不是简并；简并在 C 与支撑刚度之间

| 交付 | 路径 | 结论 |
|---|---|---|
| 规范实验 | `validation\crh380a_m\probe_contact_degeneracy.py` | 轮型面下沉 0.1 mm：静态 **0.000 %**、峰值 **−0.000 %**、主频不变 ⇒ 刚性偏移被静平衡吸收，不可观测 |
| 判定 | `docs\A2_C_DELTA_DEGENERACY_2026-10-22.md` | 真简并是 C↔`k_z`；峰值观测量 ±110 % vs 波形 ±0.63 %（旧实测）⇒ 解法是换观测量 |
| 规则 | 同上 §4 | 禁止用"额定侵入"标定 C；报告 C 必须声明定法 |

## B2（事件化积分）2026-10-22 —— 峰值是采样伪影，事件法不可用，改为步级重建

| 交付 | 路径 | 结论 |
|---|---|---|
| 分辨实验 | `validation\crh380a_m\probe_event_resolution.py` | 输出加密 10× → 峰值 **+2.571 %**；积分加密 4× → **+0.005 %** |
| 实现（默认关） | `RunSettings.refine_peak`、`results.peak_normal_force_step_resolved_n` | 取 `solution.sol.ts`（**不是** `t_eval`）重建，实测 +2.465 %、nfev +15.7 % |
| 判定 | `docs\B2_EVENT_INTEGRATION_2026-10-22.md` | `N(t)` 对状态不可微 ⇒ 接触力阈值事件法不成立；B2 是报告口径修正，不是提速 |

## A3（同步多斑 + 局部弹性分配）2026-10-22 —— 前提不成立，功能已存在

| 交付 | 路径 | 结论 |
|---|---|---|
| 多斑实测 | `validation\crh380a_m\probe_multipatch.py` | 720 组位姿多斑占比 **0.0 %**；质心 vs 最深点差最大 **2.125 mm** |
| 判定 | `docs\A3_MULTIPATCH_2026-10-22.md` | 默认条带律**已**对全部连通区段积分并用质心作力矩臂；仅 `clip_to_engaged_run=True` 会丢斑 |
| 守卫 | `tests\test_multipatch_symmetry.py` | 3 项（双肩全计入、裁剪可见差异、不对称质心偏向） |

## B4（接触状态描述子降维）2026-10-22 —— 负结果，不接入

| 交付 | 路径 | 结论 |
|---|---|---|
| 凸包描述子 | `src\velch\contact_descriptor.py` | 压缩 523→74 节点（7.0×）、速度仅 **1.41×**（31.24 vs 43.67 µs） |
| 实测 | `docs\B4_DESCRIPTOR_2026-10-22.md` | 凹处桥接 1746–3012 µm ⇒ 最差 Δδ **653.5 µm**、Δy **2.131 mm**；只对凸型承载面成立 |
| 测试 | `tests\test_contact_descriptor.py` | 6 项；`geometry_policy` 未新增取值，默认路径未动 |

## B 阶段（可微代理）2026-10-21

| 交付 | 路径 | 结论 |
|---|---|---|
| GP 代理 + 保险丝 | `src\velch\surrogate.py` | 压入误差 p50 0.013 / p95 0.255 / max 4.451 µm；界覆盖 99.8 % |
| 报告 | `docs\STAGE_B_SURROGATE_2026-10-21.md` | 容差 1 µm 回退 7 %、最坏 0.713 µm；**单次 172.7 µs 不敌查表 8.46 µs** |

**判定**：代理精度优于查表（亚微米对 1.023 µm），但成本高 20 倍，**不设为默认快速路径**；
批量/反演的快速路径仍用三线性查表（18×）。代理保留给"需要 C¹ 光滑 + 可核验误差界"的场合。
sklearn 与 numpy ABI 不兼容（`numpy.dtype size changed ... Expected 96 ... got 88`），GP 为
numpy 手写实现，未改动环境。

## C 阶段（第三方对拍）2026-10-21

| 交付 | 路径 | 证据等级 | 结论 |
|---|---|---|---|
| 独立参照模块 | `src\velch\contact_reference.py` | — | 解析基准（两圆弧/线-圆）、证据等级常量、`compare_arms()`；11 项测试 |
| 三方对拍表 | `docs\CONTACT_REFERENCE_THREE_WAY_2026-10-21.md` + `.csv` | **A（analytic）** | 23 组：Δδ 网格 0.122–0.278 µm、样条 0.123–0.279 µm；ΔN 均 +0.047 %（口径差，两臂抵消） |

**结论（重要，且是负结果）**：在光滑单圆弧几何上，45 µm 网格 + 抛物线顶点与分段样条**打平**
（Δδ ≤0.28 µm、力差 ≤0.05 %），样条仅在接触点横坐标上优 ≈0.8 µm。所以"样条更准"不成立为
通用命题；样条的价值仅在折点/槽壁（等级 B 报告里 3.639 µm 的分歧）。默认后端维持 `grid` 是正确的。
脚本：`validation\crh380a_m\report_contact_reference.py`。

## 当前状态

| 项 | 值 | 参考（Simpack CRH380A_M） |
|---|---|---|
| 平直段静载（8 个接触） | 59 680.577 N | 60 167.7 N（−0.81%，质量模型差 412 kg） |
| 静平衡赫兹侵入 | 65.5 µm | 66.2 µm（−1.1%） |
| 整程 1.2 s 前轴右轨峰值 | 89.7 kN | 134.97 kN |
| 整程 1.2 s 前轴最小力 | 37.20 kN | 27.67 kN |
| 整程脱空采样 | 0 / 2401 | 0 |
| 力主频 | 57.14 Hz | 57.97 Hz |
| 力 AC RMS | 9.13 kN | 23.30 kN |
| 轮对垂向行程 | 0.641 mm | 0.5944 mm |
| 单次 RHS 成本（单核） | 1.19 ms | 4.25 ms CPU |
| 整程墙钟 | ≈850 s（67 DOF） | 85.08 s（32 线程） |
| 多进程批量 | 8 工况 8.58× | — |
| 测试 | 423 passed（2026-10-22 20:05 实测，含 16 条架构规则 + 20 条 agent 契约 + 8 条三维几何 + 8 条字号缩放；会随并行会话增加，验收只认 0 failed） | — |

基线组合：条带积分法向律 + 钢轨垂向自由度 + 柔性扣件 5e7/4e4 + 接触阻尼 3e7 且
`damping_force_cap_ratio=0.5`。

### 第 152 轮：18 号道岔侧向跑通——4/8 的真因是站表起点

**真因**：按每根轨自己的轴位里程查 `covers`，后两轴（22.5 m / 20.0 m）在站表（30 m 起）之外，
四个车轮下面没有钢轨。分支、帧、NaN 斜率三个假设逐条证伪（后者还纠正了我自己：`_station_derivative`
的 NaN 是「未覆盖」的文档化标记，30 m 处 0/1999 与 0/1001）。

**修正**：起点进表内（40/41/45/50 m → 8/8、0.97–1.03×、残差 1e-8）+ 座位里程碑与运行起点解耦
（`run.seat_x_start_m`，座位在直股 41–45 m，运行从 69 m）。

**验收**：51 坐标、80 km/h、0.05 s，座位 45/41→运行 69 m 与座位 45→运行 55 m 三组
`numerically_checked` 且 **7/7 门**。

**未闭合**：混源站表覆盖交界处的 `ProfileError`；超高需要车架随坡面倾斜。

### 第 153 轮：反演流水线 L0 通过、L1 以实测差值拒绝

新增 `scripts/s13_admission.py`：L0 数据准入（采样率、里程单调、跨度、非有限值、静止段占比）与
L1 配准（轴箱两列滞后 vs 轴距/速度、里程 vs 速度积分），产出 `verdict.json` 且
`measurement_validation_status` 保持 `not_evaluated`。

实测：**L0 PASS**；**L1 FAIL**——两列滞后 110.5 ms，而 2.5 m 轴距在 17.29 m/s 下应为 144.6 ms
（比值 0.76）。三种可能（列身份、宽带相关峰、速度基准）未排除前不建标定，这是 L1 该有的行为。
记录两个自伤坑：`ravel()` 压掉 `Vi_y (n,2)`；把 km/h 当 m/s 积分得到 9021 m vs 2505 m（3.6 倍）。

### 第 154 轮：L1 改判——两列是共位通道，不是前后轴

按波长分带做互相关：**18–40 mm 带滞后 +2.25 ms**（40–120 mm −0.25、120–400 mm −110.75），
而「轴距 2.5 m / 速度 17.29 m/s」预测 144.6 ms → **轴距假设被否证，共位成立**。
里程那一项在把 km/h 换成 m/s 后通过（速度积分与记录里程差 **0.416 m**）。

判据改为「共位（≤25 ms 配准预算）+ 里程差 ≤5 m」，**L0 与 L1 都 PASS**（`verdict: PASS`）。
不是放松：25 ms 是审查给的预算，轴距假设是被数据否掉的。后果：这份记录每帧只有一个里程点，
L2 不能用它做两轴对比标定。

### 第 155 轮：L2 实测侧建表——27.5 mm 与论文同行，但只有一档速度

`scripts/s14_speed_table.py`：按 25 m/5 m 窗取最强窄带线（150–1800 Hz、突出度 ≥6 dB），用窗内自身
平均速度换算波长。实测 `Run_75kmh_E1toE2.mat`：平均 **70.8 km/h**、中位频率 **713.2 Hz**、
中位波长 **27.5 mm**、**64.7 %** 的窗落在 18–40 mm、中位突出度 **23.1 dB**——与论文 Table 4 的
92–844 Hz ↔ 24.4–30.4 mm 同窗，且**未用论文的 18–40 mm 先验**，属独立复核。

**限制如实**：递归搜到深度 3 只有这一份 `.mat`，60/50/40 三档不存在于本机 → 跨速度比较不可做，
脚本输出 `verdict: SINGLE-SPEED`（不是通过也不是失败），L3 因此只能在这一档内建算子。

### 第 156 轮：L5 验收层落地，结论是 `not_met`——3/6，不是 95 %

`scripts/s15_acceptance.py` 把 L0–L5 合成一份判决并**唯一**写 `measurement_validation_status`。
实测：L0/L1/L2 PASS；**L3 FAIL**（无同速度模型算子，禁外推）；L4 随之跳过；**L5 FAIL**——
两个通道各 **3/6（50 %）**、段级虚警 **5.0 %**（1585 伪区段）、零假设 P(X≥3)=**0.002**。

可引用：区段可分性真实（振动 +3.79 dB / AUC 0.741；声 +6.38 dB / AUC 0.880）。
不可引用：95 % 检出、任何幅值或剖面、跨速度标定。归因：单速度 + 共位通道 + 无剖面真值（数据）；
超 `f_n` 后轴箱响应波长盲、对比度主要来自区段边缘（物理）。

### 第 157 轮：L3 同速度算子建成（2.755e+04 (m/s²)/m），并指出必须做阶次跟踪

`scripts/s16_operator.py`：70.8 km/h、λ 27.5 mm → **715.2 Hz**，30 µm 给 **0.8265 m/s²**，
增益 **2.755e+04 (m/s²)/m**（与 `(2πf_n)²=24 398` 差 13 %）。实测同带相干幅值 **0.0422 m/s²** →
反推 **1.5 µm**。

**1.5 µm 不可引用**：记录速度从 3 到 85 km/h 变化，同一条 27.5 mm 线的频率扫过 121–859 Hz，
用固定频点的相干投影量扫频线必然低估。正解是**按里程重采样（阶次跟踪）**后在空间域做同一投影。
自伤三处（`write_tre` 参数序、`irregularity` 的键是 `tre`、`.tre` 起点 0 而算例 30 m 起）全部被守卫抓到。

## 文档清单

| 文档 | 回答什么问题 | 仍成立？ || [RELEASE_NOTES_0.4.9.md](RELEASE_NOTES_0.4.9.md) | 0.4.9 装什么、修了什么、仍然没有什么 | ✅ 2026-10-23 |
| [RELEASE_NOTES_0.4.10.md](RELEASE_NOTES_0.4.10.md) | 0.4.10 装什么、接触斑怎么看、仍然没有什么 | ✅ 2026-10-23 |
| [SIMPACK_COMPARE_2026-10-23.md](SIMPACK_COMPARE_2026-10-23.md) | 与 Simpack 同里程窗的定量差异（只描述不调参） | ✅ 2026-10-23 |
| [RELEASE_NOTES_0.4.11.md](RELEASE_NOTES_0.4.11.md) | 0.4.11 装什么、冒烟第 6 步、对照报告结论 | ✅ 2026-10-23 |

|---|---|---|
| `validation/turnout18_ref/FROG_WINDOW_BREAKTHROUGH_2026-10-21.md` | 辙叉窗 599 kN → 122.5 kN 的根因与全部对照（§8 静载门、§9 整程、§10 阻尼定标、§11 阻尼上限、§12 轨道板） | ✅ 主结论 |
| `validation/turnout18_ref/CONTACT_ALGORITHM_FINAL_2026-10-20.md` | 三项病因（翼轨缺失、刚度自编、阻尼模型）与整程表 | ✅ |
| `validation/turnout18_ref/S1E_SUPPORT_COMPLIANCE_2026-10-20.md` | 静力柔度是负结果、钢轨自由度是正解 | ✅ §6/§7 |
| `validation/turnout18_ref/STIFFNESS_FROM_CURVATURE_2026-10-20.md` | 曲率导出刚度 0.0655 mm 对上 Simpack 0.0662 | ✅ |
| `validation/turnout18_ref/PROFILE_RECONSTRUCTION_2026-10-20.md` | 型面 C1 重建与圆角对峰值无效 | ✅ |
| `validation/turnout18_ref/BODY_ATTRIBUTION_2026-10-20.md` | 轨体归属窗与迟滞无效 | ✅ |
| `validation/turnout18_ref/SIMPACK_CONTACT_FORENSICS_2026-10-20.md` | Simpack 侧 38 mm 横跳与 0.65 mm 对位 | ✅ |
| `validation/turnout18_ref/CONTACT_MODELS_MATLAB_VELCH_SIMPACK.md` | MATLAB 三层算法与三方差值 | ✅ |
| `docs/SPEED_2026-10-20.md` | RHS 分项、四项等价优化 −24.8%、已否掉的提速手段 | ✅ |
| `docs/OBSERVATION_LAYER_2026-10-20.md` | 观测量层与 Simpack/实测对照 | ✅ |
| `docs/LAYERED_TRACK_2026-10-20.md` | 任意层数轨道栈 | ✅ |
| `docs/RAIL_CANT_2026-10-20.md` | 1:40 轨底坡支点必须在轨顶中心 | ✅ |
| `docs/ASSESSMENT_2026-10-20.md` | 脱轨系数/减载率/横向力评价与 CLI | ✅ |
| `docs/CAPABILITY_INVENTORY_2026-10-20.md` | 逐子系统就绪度 | 部分（反演已补） |
| `docs/ROADMAP_BEYOND_SIMPACK.md` | S1–S4 路线与验收门 | ✅ 状态表见文末 |
| `docs/S2_IMPLICIT_2026-10-21.md` | BDF 第一轮：窗口 1.86×、整车 t≈0.61 s 发散的逐层定位（§6–§8 为三次自我更正） | ✅ |
| `docs/S2_HANDOFF_2026-10-21.md` | S2 交接：已确证事实、已排除假设、两条路的初衷、环境陷阱 | ✅ 结论成立；§1/§2/§4.3/§5 按下一行校正 |
| `docs/S2_REMAINING_PATHS_2026-10-21.md` | 两条路的**施工规格与最终实测**：口径校正、逐文件落点、分步验收门、文件所有权、B0/B1 实测结果与**路线 B 结案判定**、§3.5 的 **A3–A6 全部结果**（解析雅可比落地、整车 1.2 s 140.3 s 跑通、与 oracle 等价） | ✅ 两条路都已收口；现在只剩 §7 第 7 条（能量频段分布）是活问题 |
| `docs/UNIFIED_SCALE_AND_SOFTWARE_READINESS_2026-10-22.md` | **统一口径复核 + 代码体检**：五配置（DOP853 / BDF 解析 4 档容差 / BDF 稀疏差分）在整车 1.2 s 上的 nfev·墙钟·八接触峰值·脱空·四频带全表；两个会话数字差异的定案（nfev 81 647 逐位相同 → 差异只在墙钟负载，不是雅可比项集）；src 15 320 行/48 模块、tests 4 637 行/47 文件、validation 1.4 GB/207 个 out_* 的规模；P0/P1/P2 缺口与 6 步落地顺序 | ✅ 新增。A 部分：nfev 可跨会话比，秒数不可 |
| `docs/UI_CHINESE_LABELS_2026-10-22.md` | 界面中文怎么来的：通道/运行目录标签规则、新通道该在哪儿起名、自查命令 | ✅ 2026-10-22 新增 |
| `docs/UI_READABILITY_2026-10-22.md` | 界面可读性：字号令牌表与 `set_scale`（0.9–1.6，Ctrl+=/-/0、`--scale`、`VELCH_UI_SCALE`）、为什么缩放必须重建控件树、四处"字号放大必然截断"的修法、无头截图验证方式 | ✅ 2026-10-22 新增 |
| `docs/AI_INTERFACE_ARCHITECTURE_2026-10-22.md` | **AI 怎么调用这套软件**（架构）：L0–L4 分层与依赖方向、进程内 `VelchService` 只做编排 + 算的一律 subprocess（import 0.078 s vs 0.489 s 实测）、MCP stdio 是对 AI 的正式形态而 HTTP 等消费者、`gate_failed` 不是 error、幂等键与四道可回退、Phase 0–6 分期与每期下限 | ✅ 新增。Phase 0 已落地，Phase 1 被本切片绕过（registry 是 stdlib 叶子，不必外移） |
| `docs/AGENT_TOOL_LAYER_2026-10-22.md` | **AI 具体能调哪些工具**（契约）：20 个工具 6 域的设计、三层白名单与通配 `[]` 这颗雷、`solver_patch` 第二命名空间、错误码闭集与 `gate_failed` 例外、ledger 只追加成链、成本模型与路由（<60 s 同步 / ≥60 s 后台 / 预算先拒）、三条"自动化下必崩"的实证；**§8 是设计 vs 代码对照（12 个工具已实现、未做的逐条列出、`physics_changed` 认"采样≠物理"、auto_accept 四步）** | ✅ 新增。§1 的 20 个工具里 12 个已实现，其余见 §8.3 |

| `docs/DAMPING_CALIBRATION_2026-10-21.md` | 接触阻尼定标（负结果） | ❌ **已作废（限定量级）**：扫点 ζ ≤ 5e-4；`S2_REMAINING_PATHS` §4.0 在生产量级 1e6→3e7 上测得 rms −44%，结论相反 |
| `docs/ARCHITECTURE_2026-10-21.md` | **架构收口与 Simpack 2021x 对标**：14 行能力矩阵（接触几何/多点接触/法向律/切向律/阻尼/积分器/轨道结构/车辆自由度/执行机构/观测量/反演/UQ/批处理/UI，每行给出 Velch 文件:行号 × Simpack 取证 × 差距性质）、实测 import 图与 4 条真实违规（`io`→`inverse` 类型级反向依赖、`case/spec.py:27`、`vehicle_solver.py:23`、`contact.py:32`）、上帝模块与 6 步拆分顺序、四道结构性缺口（①模态每轨一套 ②钢轨离散化 ③轴箱体 ④轨底应变桥路）的接口+DOF 布局+验收门、UI/CLI 边界与稳定接口清单、三个月四轴路线 | ✅ 新增。行号基准 2026-10-21 11:40 工作树；用 `python -X utf8 _cite_check.py` 重解析、`_arch_scan.py` 重算依赖图 |
| `tests/test_architecture_rules.py` | 架构适应度函数（16 项 AST 静态断言）：前向不得 import `inverse`、`inverse` 不得 import 前向、`contact*` 不得 import 调用者、`case/*` 只许 import `velch.vehicle`、`io.history` 必须是叶子、`vehicle_solver` 只许从 v1 借 `SimulationFailure`、UI 不得 import 前向栈、import 时图无环、`io.measured → inverse` 不得是运行时边 | ✅ 16 passed；失败信息直接打印违规边（含 `kind ∈ runtime/deferred/typing`） |

| `docs/SIMPACK_IMPORT_2026-10-22.md` | **怎么从 Simpack 模型算一个算例**：只读 catalog（238 引用 / 233 PRR / 0 缺失）、两种模式（`--keep-profiles` 与默认全断面）、里程不平移、第五节**断面下沉判据**（两级阈值 3/8 mm、5.18 mm 能坐 / 11.91 mm 不能、旁挂字段）、明确不导入的物理量 | ✅ 2026-10-22 新增 |
| `docs/PACKAGING_2026-10-22.md` | **怎么打成安装包**：onedir + 两个 exe 的分工、`launcher.py` 的冻结口径、语料四级解析顺序、构建命令、打包后必跑的五步冒烟表 | ✅ 0.4.1/0.4.2 均照此验证 |
| `docs/RELEASE_NOTES_0.4.2.md` | 0.4.2 装什么、怎么开、界面四项与 Simpack 三条命令的实测、仍然没有的五项 | ✅ 当前发布物 |
| `docs/RELEASE_NOTES_0.4.3.md` | 0.4.3 装什么、断面导入三条命令、下沉判据的实测矩阵、仍然没有的五项 | ✅ 当前发布物 |
| `docs/BUGS.md` | **缺陷账本**：B001–B021 已修（每条带复现与影响面）+ O001–O008 已知未修及理由 | ✅ 每轮更新 |

## 已作废的结论（不要重走）

1. "断面有 2.76 mm V 形凹陷、需要重建" —— 实测 `worst |body - raw| = 0.0000 mm`，断面没被改；病根是承载面缺失。
2. "接触刚度 0.02 m 是根因，改刚度就能解决" —— 改到 0.5407 反而 716 kN（更硬更弹）。
3. "阻尼不是杠杆" —— 那是在软刚度（侵入 0.198 mm）下测的；刚度改对后侵入 66 µm，阻尼成为决定项。
   **2026-10-21 第三次确认**：在生产量级重扫（1e6→3e7）rms −44%、峰值 −23%、脱空 10→0，
   且 3e7 恰好是 Simpack 幅值最优点（见第 14 轮）。同一条结论已经在扫点区间上栽过三次。
4. "斑平均 2/4 mm 能削峰" —— 626/641 kN，更差。
5. "换体迟滞、轨体归属窗、钢轨级种子、斑间去重能解决" —— 全部无效或更差。
6. "`cached_grid` 策略能提速且等价" —— 相位改变触发双稳，峰值 170.9 → 1447.7 kN，不可采纳。
7. "c = 3e7 可以随意用" —— 无界阻尼把转辙器 0.17 mm 台阶变成 406 kN；必须配 50% 弹性力上限。
8. "加轨道板能补 30-60 Hz" —— 反而更平滑（4.09 → 2.39 kN rms）。
9. "`SRS_RWP_*_Pair` 的 ch_008 要 +17.5 m" —— 它已是轮对里程，加 17.5 会伪造"峰值只剩 63 kN"。
10. "多线程 `--workers 4` 能提速" —— 慢 1.86×（CPython GIL）。批量要用多进程。

## 复现命令

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 -m pytest tests -q --basetemp F:\velch_tmp\pytest
python -X utf8 -m velch run-vehicle validation\crh380a_m\case_full12_cap05.json --output validation\crh380a_m\out_full12_cap05
python -X utf8 validation\crh380a_m\minpen_report.py validation\crh380a_m\out_full12_cap05\history.csv
python -X utf8 validation\crh380a_m\bands_from_history.py validation\crh380a_m\out_full12_cap05\history.csv
python -X utf8 validation\crh380a_m\check_static_gate.py
```

## 2026-10-21 夜间追加（第 12 轮）

- **S2 隐式积分第一轮**：RunSettings.method 支持 `BDF`、新增 `jacobian="sparse_fd"`（一次稠密探测得到稀疏模板）。
  0.05 s 窗口 32.4 → **17.4 s（1.86×）**、0.2 s 跨换体窗口 1.50×，物理逐位一致（80.5 kN / 83.3 µm）。
  整车 1.2 s 两种 BDF 都在 t≈0.61 s 发散——**根因是右端函数的跨调用记忆**（_contact_seed/_active_body/_body_cache），
  不是稀疏模板。修法：按步快照/提交，详见 `docs/S2_IMPLICIT_2026-10-21.md`。
- 新增文档 `S2_IMPLICIT_2026-10-21.md`；测试 **110 passed**。

## 2026-10-21 S2 交接前复核（第 13 轮）

复核 S2 两条剩余路的代码与算例口径，产出 `docs/S2_REMAINING_PATHS_2026-10-21.md`（施工规格）。
**四处口径更正**（旧交接与本文档冲突处，以本节为准）：

1. **测试数**：本表上方"当前状态"原写 106，与第 12 轮追加的 110 冲突——4 项
   `tests/test_implicit_options.py` 正好补上差额，**110 才是当前值**，已改。
2. **三个算例的阻尼律不是同一个**：`case_A_final_law.json` 用 `hunt_crossley`（其
   `normal_damping_n_s_m_1p5 = 1e6` 是**死字段**，该分支根本不读）；`case_full12_cap05.json` /
   `case_imp_bdf_*.json` 用缺省 `fixed_coefficient` + `3e7` + `cap 0.5`。所以"BDF 变体由 89.7 kN
   基线派生"在阻尼律上不严格，两者不可按系数直接比较。
3. **阻尼定标的扫点没落在生产量级**：`calibrate_damping.py` 默认源是 `case_frog_N_strip05.json`，
   扫 `2e4/5e4/1e5/2e5`，对应 ζ = 5.2e-5 … 5.2e-4（近似无阻尼），而生产算例 `3e7` 对应 ζ ≈ 0.078。
   所以"阻尼不是杠杆"只在无阻尼区成立——这是**同一条结论第二次栽在扫点区间上**（第 3 条作废结论
   也是同类问题）。**结论降级为"未在生产量级检验"，B0 实验待补**，暂不列入作废表。
4. **路线 B 的 `c_floor ≈ 1.1e6` 有单位陷阱**：该数单位是有效阻尼 N·s/m，而
   `normal_damping_n_s_m_1p5` 是**系数**（有效阻尼 = 系数 × √δ）；直接把 1.1e6 填进去等于把阻尼
   **减到 1/27**。换算应为 `系数 = c_eff/√δ_ref ≈ 1.36e8`。

另记两条待办：`derivative_pure` 的快照未含 `_body_cache`/`_seed_misses`（当前算例不触发，开启有界搜索
或换体迟滞即失效）；`vehicle_solver.py:495-504` 有一处重复 `return` 死代码。

## 2026-10-21 B0 阻尼定标实测（第 14 轮）

同一辙叉窗（前轴右轨 78.8–82.2 m）、同一源算例 `case_frog_N_strip05.json`，把阻尼扫到**生产量级**：

| 系数 | rms kN | 主频 Hz | 150–250 | 峰值 kN | 脱空 |
|---|---|---|---|---|---|
| Simpack | 23.301 | 57.968 | 4.041 | — | — |
| 1e6（谱面窗原值） | 45.363 | 153.846 | 37.235 | 170.9 | 10 |
| 1e7 | 35.024 | 184.615 | 28.666 | 149.1 | 0 |
| **3e7（生产值）** | **25.206** | 184.615 | 17.313 | 131.3 | 0 |
| 1e8 | 20.067 | 92.308 | 8.148 | 117.8 | 0 |

- **"阻尼不是杠杆"正式作废**：1e6→3e7 使 rms −44%、峰值 −23%、脱空 10→0。旧定标的 2e4–2e5 四个点
  全在 ζ≤5e-4 区（见 `S2_REMAINING_PATHS` §1.3），故 `docs/DAMPING_CALIBRATION_2026-10-21.md` 标 ❌。
- **幅值已无余量**：3e7 恰好落在 Simpack 幅值最优点（1.08×），1e8 已过冲 14%。任何"整体上调等效阻尼"
  的方案都会先破坏基线；`c_floor` 只能是局部下限（推荐 2e4/2e5 档），且 ≤ 243 kN·s/m。
- **cap 0.5 在这个窗上近乎无感**（3e7 时 rms 差 0.12%），过阻尼端反而有害（1e8 时峰值 +24 kN）。
- **残差是频谱不是幅值**：150–250 Hz 带仍是我们 17.3 / Simpack 4.04，一路加到 1e8 也只到 8.1。
- 测试实跑 **119 passed**（第 13 轮记的 110 是当时快照；此后新增 `test_identifiability_resolution.py` 9 项）。
- 产物：`damping_calibration_frog_nocap.json`、`damping_calibration_frog_cap05.json`（旧内容备份为
  `damping_calibration_round13_base.json`；脚本固定输出名 `damping_calibration.json` 已被还原，勿当证据）。
  中间算例 `case_damp_<值>.json` 会跨源撞名，不是证据。

## 2026-10-21 轮 26 追加

- 新增 `src/velch/inverse/estimator.py`：log 空间 Levenberg-Marquardt（中心差分雅可比、逐次阻尼、
  单步 log 范数上限、`sigma^2 (J^T J)^-1` 协方差、`Estimate.scale/sigma/report()/summary()`）。
  配套 `tests/test_estimator.py` 9 项；全仓 **128 passed**。
- 新增判决脚本 `validation/crh380a_m/ab_observable_inversion.py`：对 `rail_k_z`、`rail_c_z` 各 +-10 %
  重跑 20 ms 窗，按整段波形建雅可比列 → 波形 rank 2/2、cond 1.44；峰值 rank 1/2、cond inf、
  c_z 分辨率 872 %。列范数 86.5 / 114.1 kN per ln-unit。
- 新增 `validation/crh380a_m/inversion_waveform_demo.py`：真动态闭环，1 kN 噪声、4 步 LM、30 次正演，
  `rail_k_z` 误差 −0.131 %（1 sigma 1.03 %）、`rail_c_z` 误差 +0.352 %（0.87 %）。产物
  `validation/crh380a_m/inversion_waveform_demo.json`。
- 前向求解器未改一行，冻结 oracle（静载 59 680.577 N、静平衡 65.5 µm、整程 89.7 kN / 0 脱空 /
  0.593 mm 行程）不受影响。

## 2026-10-21 B1 穿透分布诊断 → 路线 B 结案（第 15 轮）

给 `S2_REMAINING_PATHS` 做 B1：统计生产算例的接触侵入分布与激活翻转，判定"δ→0 阻尼退化"这条根因是否存在。
纯后处理（`.tmp/b1_stats.py` 读已收敛的 `history.csv`），**源码未改一行**。

| 指标 | `out_full12_cap05`（生产口径） | `out_Y_base`（刚性轨道对照） |
|---|---|---|
| 池化 δ min/q1/q10/中位/max (µm) | 29.037 / 60.094 / 61.387 / 62.599 / 551.890 | 8.505 / 57.943 / 62.645 / 65.466 / 293.659 |
| `δ < 10 µm` 的 active 样本 | **0（0.00 %）** | 3（0.02 %） |
| `δ < 5 / 1 / 0.5 µm` | **0 / 0 / 0** | 0 / 0 / 0 |
| active 翻转次数（8×2401） | **0** | **0** |

- **BDF 崩溃时刻是常规工况**：`t=0.606500 s` 时 8 个接触 δ = 63.46/69.56/62.88/68.20/67.10/67.17/66.93/65.98 µm、
  N = 60.9/70.4/59.6/68.1/60.2/60.5/59.9/58.8 kN，全部 active。没有脱空、没有侵入塌缩、没有激活集跳变。
- **判定：路线 B 结案，不做代码改造。** `δ→0` 退化在 1.2 s 内一个样本都不存在（最浅 29 µm）；
  事件检测也没有对象（0 次翻转）。失败发生在**刚性接触（∂N/∂δ≈1.37e9 N/m）+ 184 Hz 几何强迫**下的
  条件数问题，不是光滑性问题。
- **路线 A（解析雅可比）成为唯一剩余杠杆**，且正当性增强：崩溃点雅可比良定义、接触无跳变。
- `damping_floor_n_s_m` 不再实现（原计划要兜一个不存在的问题）。

**同时更正两条目录口径（此前一直被误读）：**

1. **整程 89.7 kN 基线来自 `out_full12_cap05`**（`axle1_right` 峰值实测 89.68 kN），不是 `out_A_final_law`。
   `out_A_final_law` / `out_final_strip1p2s` / `out_final_patch1p2s` / `out_A_1p2s` / `out_A_smoke_0p05s` /
   `out_C_smoke` / `out_flat_A_135` / `out_curv_flat` / `out_V_base` / `out_W_base_frog` 这批目录的
   history **2401 帧逐位不变**（`out_A_final_law` 恒为 59.68 kN / 65.466 µm），只能当静载门，
   **不能用来挖动态或频谱结论**。详见 `S2_REMAINING_PATHS` §1.6。
2. `out_Y_base` 与 `out_final_full1p2s` 是同一次运行（case_id `S_hc_e0.5_v0.1`、rigid、`track_dof=0`）
   的两次落盘，不是两个独立算例。
- 测试数本轮又变：**128 passed**（第 14 轮记 119 时 `tests/test_estimator.py` 尚未落地，那是轮 26 会话加的）。
  **验收门不要写死数字，只认 0 failed。**

## 2026-10-21 P0 地基落地（第 16 轮）

把 `S2_REMAINING_PATHS` §2 的五条 P0 全部实现，目的：让隐式右端真正是 `(t, state)` 的纯函数，
后续解析雅可比才有意义。**物理结果不变，只有数值卫生性与模板结构变了。**

| 编号 | 改动 | 落点 |
|---|---|---|
| P0-1 | 稀疏探测改用 `derivative_pure`；`t` 改为参数传入（原硬编码 `0.0`） | `src/velch/vehicle_solver.py` `_rhs_sparsity(dynamics, state, t_s)` |
| P0-2 | 快照从 3 个键扩到 5 个：加 `body`（`_body_cache`）与 `misses`（`_seed_misses`） | `snapshot_contact_state` / `restore_contact_state` |
| P0-3 | 模板 = FD 探测 ∪ 结构骨架（`q'=v` 对角块 + 每个 `Connector` 的 `support(jac)×support(jac)`） | `_rhs_sparsity` |
| P0-4 | 删掉 `_project_*` 里重复的 `return` | 同上文件 |
| P0-5 | 新增 `tests/test_rhs_purity.py`（9 项） | `Velch/tests/` |

为什么 P0-2 重要：`derivative_pure` 原先只快照 `seed/age/active`，而 `_body_cache` 每次求值都被覆盖、
`_seed_misses` 到 40 次会清种子。生产算例因为 `contact_search_half_width_m=None`、`body_hysteresis=False`
没走这两条路，所以"纯"是偶然成立；一旦开启有界搜索或换体迟滞，右端立刻变成与调用顺序相关的函数。
新测试用 `contact_search_half_width_m=1e-3` + `contact_seed_scope="rail_hold"` 显式覆盖这两条路径，
并断言"先被 `derivative` 弄脏、再调 `derivative_pure`"仍逐位复原。

**回归（物理逐位不变）**

| 检查 | 结果 |
|---|---|
| `pytest tests` | 146 passed |
| `check_purity.py` 四条判据 | 全 `0.000e+00` |
| BDF 稀疏 0.05 s 窗口 | nfev **11 038**（旧 11 071）、峰值 80.5 kN、最大侵入 83.3 µm、`numerically_checked` |
| BDF 稀疏 0.2 s 窗口（跨换体） | nfev **24 547**（旧 24 535）、83.6 µm、`numerically_checked` |

**代价要记住**：P0-3 让模板非零数 652 → 877（6.27 % → 8.43 %），同机背靠背对照
探测-only 19.0 s vs 探测∪骨架 21.9 s ≈ **+15 % 墙钟**。这是用速度换正确性的自觉选择；
解析雅可比落地后给出精确结构，骨架即可退场。绝对值受并行会话负载影响，不要与旧墙钟直接相减。
路线 A 的收益门基线更新为 **nfev < 11 038 / < 24 547**。

## 2026-10-21 路线 A 第 1 步（A1）：FD 参照物及其噪声地板（第 17 轮）

**做了什么**：新建 `validation/crh380a_m/check_jacobian.py`。它**不生成解析导数**，只回答一个前置问题——
"拿中心差分当参照物，这个参照物本身准到什么程度？" 从 `out_full12_cap05/history.csv` 取 4 个状态
（t = 0 / 0.3 / 0.6065 / 1.2 s），对 `derivative_pure` 扫步长 1e-4…1e-8（相对 `max(1,|state|)`），
同时算前向与中心差分，并检查"1e-9 m 微扰下是否有导数项跳变"。

**实测（四态一致）**

| 步长 | 中心差分 vs `h=1e-6` | 前向 − 中心 |
|---|---|---|
| 1e-4 | 1.2e-1 … 1.8e-1 | 约 4e-1 |
| 1e-5 | 3e-3 … 2e-2 | 约 4e-2 |
| 1e-6 | 0（基准） | 约 1e-2 |
| 1e-7 | 8.4e-3 … 1.8e-2 | **4e-7 … 6e-6** |
| 1e-8 | 8.4e-3 … 1.8e-2 | **4e-8 … 1e-6** |

四项判定：
1. **参照物取中心差分 `h=1e-7`，不是 1e-6、不是 1e-9。** 1e-7 与 1e-8 相对 1e-6 漂了 1e-2 却彼此一致到 1e-7，
   说明漂的是粗端：接触 `N ∝ δ^1.5` 的曲率让 `h=1e-6` 已偏约 1 %（`(3/8)·h/δ`，δ≈65 µm 得 0.6 %，量级吻合）。
2. **FD 参照物自身精度是相对 `max|J|` 的 1e-7 量级**，所以"解析 vs FD 小于 1e-6"可达，但必须按 `max|J|` 归一。
3. **不能逐元素判相对误差**：`max|J| ≈ 1.15–1.28e7`，`min|J|>0 ≈ 1e-13`（纯舍入噪声），跨度 1e19–1e20。
   判据改为 `max|Ja-Jfd|/max|Jfd| < 1e-6`，外加在 `|Jfd| > 1e-6·max|Jfd|` 的元素上逐元素相对误差小于 1e-4。
4. **四个状态都没有切换面**（1e-9 m 扰动下变化超过 1 % 的项为 0），与 B1 实测的"active 翻转 0 次"互证。

**量级口径纠正**：最刚项不是 1.37e9（那是 N/m）。`derivative` 返回 `f/m`，接触刚度落在**钢轨**自由度
（质量 120 kg），故 `max|J| ≈ 1.37e9/120 ≈ 1.14e7 s^-1`，对应 `omega_max ≈ 3.4e3 rad/s ≈ 537 Hz`——
卡步长的是这个模式，不是轮对的 139 Hz。`max_step=1e-4` 是 DOP853 遗留，但**终局门优先先跑通，暂不动**。

**文档**：`docs/S2_REMAINING_PATHS_2026-10-21.md` 新增 §3.0，§3.1 数值门按上述改写，§3.4 把 A1 标为已完成
（P0 与 A1 均已完成，A 会话从 A2 开始）。

## 2026-10-21 路线 A 第 2 步（A2）：串联接触的隐函数导数（第 18 轮）

**做了什么**：`src/velch/support_compliance.py` 新增 `series_normal_force_slope(depth_m, stiffness_n_m_1p5, support_compliance_m_per_n)`。
原 `series_normal_force` 用固定 5 次 Newton 解 `delta = (N/C)^(2/3) + N*G`，迭代次数随 delta 分段常数，
对它做差分会把"阶梯"带进导数。新函数改为隐函数求导：

    dN/ddelta = 1 / ( (2/3) * (N/C)^(-1/3) / C + G )

`G` 缺省时退化为纯 Hertz 的闭式 `1.5 * C * sqrt(delta)`。原函数一行未改。

**测试**：`tests/test_support_slope.py`（44 项）——20 个 delta 点对中心差分相对误差 < 1e-8；
Hertz 分支与 `1.5*C*sqrt(delta)` 逐位一致（rel 1e-12）；柔度使斜率变软；delta<=0 时力与斜率都为 0；
斜率随 delta 单调；非法刚度在带柔度分支上抛 ValueError。

**顺带测出的关键事实：生产算例没有启用串联支承柔度。** 扫 `G`（`C = 1.1393e11`）：

| G (m/N) | delta=5 um | 30 um | 65.5 um | 200 um |
|---|---|---|---|---|
| 无（纯 Hertz） | 1.27 kN / k=3.82e8 | 18.72 kN / 9.36e8 | **60.40 kN / 1.383e9** | 322.3 kN / 2.42e9 |
| 5e-9 | 0.48 kN | 3.89 kN | 9.33 kN | 31.5 kN |
| 2e-8 | 0.18 kN | 1.25 kN | 2.85 kN | 9.07 kN |

冻结 oracle 静载 59 680 N @ 65.47 um 只与"无柔度"行吻合，任何 `G >= 5e-9` 都会把力砍到 1/6。
所以生产算例走纯 Hertz 分支，`G` 那支只在 `layered` 轨下结构启用。
同时 `max|J| ≈ 1.14e7 = 1.383e9 / 120 kg`，独立验证了第 17 轮"最刚路径经由 120 kg 钢轨自由度、
omega_max ≈ 537 Hz"的量级纠正。

**全仓回归**：`pytest tests` 全绿（0 failed；本次 193 passed，数字随并行会话上涨，不作验收门）。

**文档**：`docs/S2_REMAINING_PATHS_2026-10-21.md` §3.3 表 a 行标已完成、新增 §3.3b（上面的 G 表）、
§3.4 把 A2 标为已完成、三处"从 A1 开始"改为"从 A3 开始"。

## 2026-10-21 路线 A 第 3-6 步（A3/A4/A5/A6）：解析雅可比落地，整车 1.2 s 跑通（第 19 轮）

**结论先行**：`jacobian="analytic"` 让 BDF 第一次跑完整车 1.2 s——
**140.3 s、`numerically_checked`、7 门全过、与 DOP853 轨迹等价、nfev 110 461 vs 331 949（3.0x）**。
但收益不是旧文档预期的"迭代次数减半"：窗口 nfev 几乎不变（11 052 vs 11 038、24 629 vs 24 547），
省下来的是**每次迭代的代价**（墙钟 -24 %）与**整车收敛域**。

**新增** `src/velch/jacobian.py`（346 行）。核心是一个显式的建模决定：

> **冻结接触几何**——接触站点沿轨位置、法向 `(ny,nz)`、力臂 `(lever_y,lever_z)` 取当前状态而不对 `q` 求导，
> 只对侵入深度 `delta` 求导。

`J = [[0, I], [d(f/m)/dq, d(f/m)/dv]]`；两条导数行分别来自 `_kinematic_row`（`delta` 对 `q`）与
`_generalized_rows`（每单位法向力/横向切向力/纵向力的广义力）。线性部分（连接器 + 轨道层）是常数矩阵：
连接器按 `-k*jac(x)jac`、`-c*jac(x)jac` 一次装配，轨道层用单位列探测（`internal_force` 对 `(q,v)` 线性，
探测即精确，注意落到 `[35:, index]`）。`blocks()` 全程包在 `snapshot_contact_state()` / `restore_contact_state()`
里，**求雅可比不会污染轨迹**。

**A3 数值口径（`frozen_geometry_error`）**

- 无接触（四轮抬高 1 mm，`case_frog_N_strip05.json`）：线性部分与中心差分差 **2.2e-11**（纯舍入）。
- 有接触（t=0.3，`case_full12_cap05.json`）：`{dq: 0.209, dv: 0.0139}`。最差项 `(44,44)` rail4.z：
  解析 -1.2481e7 vs FD -1.0057e7；wheel 行 2.03e-2、**rail 行 2.09e-1**。
  机理：`normal_policy="strip_integral"` 下条带多切片共同承力，钢轨上抬时最深切片换位，
  真实 `dN/d(delta)` 小于"最深点局部刚度" `1.5*C*sqrt(delta) = 1.43e9`，FD 反推约 1.16e9 = 0.81x。
  **这是口径的固有误差，不是装配 bug**——而且不影响收敛（inexact Newton）。
- 装配 2.5 ms/次，FD 全雅可比约 245 ms（204 次 RHS x 1.19 ms）；`nnz(Jq)=417`、`nnz(Jv)=272`。

**A4 接线**：`model.py` 白名单 `{None, "sparse_fd", "analytic"}`；`_integrate_vehicle` 改用 `solver_options` 字典，
`"analytic"` 走 `solver_options["jac"] = lambda t, y: assembler.full(t, y[:n], y[n:])`。
`tests/test_implicit_options.py` 已同步（接受 `"analytic"`、仍拒 `"fd"`）。

**A5 两窗口（背靠背同机）**

| 窗口 | 配置 | nfev | 墙钟 | 峰值 | 最大侵入 |
|---|---|---|---|---|---|
| 0.05 s | sparse_fd | 11 038 | 19.5 s | 80.504 kN | 83.3 um |
| 0.05 s | analytic | 11 052 | **14.9 s** | 80.504 kN | 83.3 um |
| 0.2 s | sparse_fd | 24 547 | 43.7 s | 81.582 kN | 83.6 um |
| 0.2 s | analytic | 24 629 | **33.4 s** | 81.582 kN | 83.6 um |

**A6 整车 1.2 s**：sparse_fd 现崩在 `non-finite v2 force at t=0.547528664 s`（P0-3 改模板后的新失败点，
比旧记的 0.606528 s 早 59 ms）；analytic **跑通 140.3 s**，与冻结 oracle 逐项一致：
8 个接触峰值（analytic / DOP853）61.19/61.19、61.08/61.08、61.17/61.17、61.07/61.07、**89.67/89.68**、
**170.61/170.61**、90.76/90.77、170.45/170.45；最大侵入两边同为 0.5519 mm；位移相对差 <=1.4e-3、
力差 <=230 N。

**一个必须记住的口径纠正**：**"整程峰值 89.7 kN"只是前轴右轨 `axle1_right`**。整程最大值是
`axle2_right` 的 **170.6 kN，出现在 t=0.3575 s、delta=0.548 mm**，DOP853 基线里本来就有（同值）。
以前把它当"整程峰值"来引用是错的。

**新增算例**：`case_imp_bdf_analytic.json`（0.05 s）、`case_frog_long_bdf_analytic.json`（0.2 s）、
`case_full12_cap05_bdf_analytic.json`（1.2 s）。新产物 `out_a5_analytic12/`，**未覆盖任何 oracle**。
生成脚本 `.tmp/make_analytic_cases.py`，跑测脚本 `.tmp/a5_windows.py`、`.tmp/a5_analytic_12s.py`。

**测试**：新增 `tests/test_jacobian.py`（5 项：块布局、无接触时线性部分 < 1e-9、冻结几何误差落在
0.40/0.10 包络内、求雅可比不污染接触记忆、扰动态各块有限）。全仓 `pytest tests` 全绿 **233 passed**（0 failed）。

**文档**：`docs/S2_REMAINING_PATHS_2026-10-21.md` 新增 §3.5（A3-A6 全部实测）、原 §3.5 降为 §3.6 备查、
§3.1 三条验收门逐条标注"现实怎么修正了它"、§3.4 全绿、§5 命令换成 analytic 版、§7 第 4 条（`dC/dq`）
答"不需要"、头部横幅改为"两条路都已收口"。

## 2026-10-21 路线 A 之后的速度收尾（第 20 轮）

**结论先行**：整车 1.2 s 从 140.3 s 压到 **73.7 s**（`rtol=1e-4` + `max_step=1e-3`），比 Simpack 的
85.08 s 快 13 %；相对 DOP853 的 850 s 是 **11.5×**。所有上报量（八接触峰值、脱空 0、辙叉窗 rms 与
三个频带）到两位小数不变，七项门全过。

1. **`max_step=1e-4` 不是瓶颈**：四档 5e-4/1e-3/2e-3 的 nfev 只差 4 %（105 954 / 105 683 / 105 683
   vs 110 461），1e-3 与 2e-3 完全相同 → 求解器早已不被它卡住，删掉省 5 %。
2. **`rtol` 是旋钮**：1e-6→1e-5→3e-5→1e-4 对应 140.3 / 109.2 / 95.5 / 81.7 s，nfev
   110 461 / 87 681 / 76 764 / 64 709，频带逐位不变。
3. **代价**：`rtol=1e-4` 下个别帧的单切片侵入差 34.5 µm（t=0.3315、`axle1_right`，190.4 vs 225.0 µm），
   同帧法向力 66.49 vs 66.48 kN 一致（条带积分下最深入侵不是承力深度）。**未改默认值**，只记录为
   可选"快速预设"。
4. **模态普查（副产品）**：解析雅可比的特征值给出全部模态——35.0–36.4 Hz（轮对垂向/侧滚，8 个）、
   324.3 Hz（钢轨横向，8 个）、500–565 Hz（钢轨垂向+接触，ζ≈0.34–0.37，8 个）；**40–320 Hz 无模态**。
   故 153.85 Hz 不可能是共振，独立证实了 `SPECTRUM_SOURCE_2026-10-21.md` 的冲击指纹判读。
5. **频带口径更正**（§7 第 7 条）："150–250 Hz 4.3×"是柔性扣件上线前的旧基线；当前生产基线
   `out_full12_cap05` 同窗为 rms 9.13 / 主频 57.14 / 30–60 5.68 / 150–250 1.75 / 250–400 2.25
   （Simpack 23.30 / 57.97 / 14.84 / 4.04 / 2.33）。**主频与 250–400 已对齐，150–250 不再偏高，
   唯一缺口是 30–60 Hz 带 0.38×**，属轨下结构自由度（S1-g），不是接触斑。
6. 文档：`S2_REMAINING_PATHS_2026-10-21.md` 新增 §3.7（速度收尾）与 §3.8（模态普查）、§7 第 7 条重写。
7. 复现：`.tmp/a7_max_step.py`、`.tmp/a8_rtol_sweep.py`、`.tmp/modal_probe.py`、
   `validation/crh380a_m/bands_from_history.py out_full12_cap05 out_a5_analytic12`。

### 2026-10-21 分段样条落地（A1 前置，goal round 3）

1. **新增 `fit_segmented` / `SegmentedProfile`**（`src/velch/contact_geometry.py`）：按 2 µm 超调门递归二分，
   失败段落到最小节点数时保留整段并把超调记入 `relaxed_residual_m`——**覆盖必须完整**，因为带内留洞会
   让接触搜索静默外推。`SegmentedProfile` 提供 `z/dz/d2z/spline`，与 `swept_contact` 鸭子兼容。
2. **关键纠正**：分段只用于“表示”，接触仍要在拼回的连续带上求一次全局最小间隙。上一版“各分段配对
   取最深”会让轮缘对填实轮缘槽的假接触压过踏面真接触（辙叉 25.7 mm 假侵入即此因）。
3. 实测（`case_I_wing.json` 右股，240站 × 5横移 × 2下沉 = 2400 样本/档，网格 45 µm）：
   改用**轨顶参考面 ±30 mm 走行带**定位轮子（原为断面全局 `argmax`）后
   直向 **max|Δδ| = 3.639 µm**（1440 可比）、辙叉 **3.639 µm**（1122 可比）、尖轨 0 可比；
   非物理侵入（>2 mm）直向 960、辙叉 1278、尖轨 2400。分段样条由 25 722.9 µm → **3.639 µm**。
4. **辙叉档曾整体作废，修夹具后重获可信**：`probe_frog_overshoot.py` 抓到最差样本（s = 80.5586 m、
   下沉 0.6 mm、横移 −4 mm）两侧侵入 **24 457 / 24 750 µm**，接触点落在 y = 859.5 mm（距参考面 106 mm，
   不在走行带内）——两个荒谬答案之差。根因是 `argmax(section.z)` 把轮子锚在 24 mm 让位槽壁上。
   改用参考面 ±30 mm 走行带后辙叉落到 3.639 µm。
5. **仍存在的夹具缺口（未解决）**：尖轨档 2400/2400、辙叉约 53 % 样本仍判为 >2 mm 非物理——被让位槽
   占据的走行带内没有真轨顶可锚，仅靠“带内最高点”无法决定轮子横向落位。正确做法是**解轮子横向
   平衡**（让接触搜索定落位），而不是锚一个点；这属于 A1 接线时由求解器承担的事。
   直向/辙叉两档的 3.639 µm 已可入论文，尖轨档暂缺数据。
5. 测试：`tests/test_contact_geometry_segmented.py`（6 项，含“分段带必须完整覆盖”“接触可落在第二段”）。
   全套 **286 passed**（280 → 286）。
6. 复现：`python -X utf8 validation\crh380a_m\report_spline_segmented.py case_I_wing.json [网格步长 µm]`。
7. 下一步（未做）：定位辙叉最差站位的 499 µm 超调段是否就是接触点所在段；是则该段必须再分或被门拒绝。

### 2026-10-21 A1 接线：`geometry_policy="spline"`（goal round 6）

1. 新增 `find_spline_contact`（`src/velch/contact.py`）：**样条只回答“接触在哪”**，法向、杠杆臂、曲率、
   蠕滑仍走既有装配——把样条定位到点后在 ±2·`grid_step_m` 的微窗上调用 `_contact_on_span`，因此换策略
   不会悄悄换掉本构。`GEOMETRY_POLICIES` 增加 `"spline"`，默认仍 `"grid"`。
2. `find_graph_contact` 在 `patch` 分支之后、合并网格之前插入 spline 分支。
3. 测试 `tests/test_geometry_policy_spline.py`（3 项）：策略已注册且默认仍为 `grid`；平直算例上 spline 与
   grid 侵入深度一致（rel 2 %）、接触 y 差 <1 mm（近平对上横向落位本就病态，故不锁 y）；连调两次 grid
   逐位相同。**289 passed**（286 → 289）。
4. 架构规则：`test_contact_layer_does_not_import_its_callers` 放行 `velch.contact_geometry`——它是
   叶子原语（不 import 项目内任何模块），与 `velch.profiles`、`velch.contact_law` 同级，不是向上依赖。
   同时把 `test_contact_patch_geometry` 里用作“非法策略”的字符串从 `"spline"` 改成 `"not_a_policy"`。
5. **已定位的缺口（未修，重要）**：`case_frog_N_strip05` 上 grid 与 spline 两跑**逐位相同**
   （峰值 170 859.5 N、零载 10/101、最大侵入 0.154773 µm）。原因：`find_graph_contact` 在
   `normal_policy == "strip_integral"` 时**先**返回 `find_strip_contact`，spline 分支根本到不了——
   生产算例走的正是条带积分，所以该策略当前只在点 Hertz 路径生效。
   修法二选一：①把样条定位出的中心传进 `find_strip_contact` 作为条带中心；②在 `find_strip_contact`
   内部复用同一分支。在做到之前，A4 误差表不能声称“已接入生产路径”。
6. 复现：`python -X utf8 validation\crh380a_m\ab_spline_policy.py`（自建两份算例、跑完自动删除）。

## A 阶段收口（2026-10-21，goal-1422de51 第 7 轮）

1. `docs\CONTACT_GEOMETRY_ERROR_BOUND_2026-10-21.md` 重写为**误差界总账**，三组实测并列：
   解析基准（两圆弧）／真实断面全局三次样条（证伪）／真实断面分段样条。
   - 全局样条：`Δδ` max 15.87 µm（straight）、14.49 µm（switch），`ΔR*` 错到 18.9 cm → 禁用。
   - 分段样条：straight 1440 样本、frog 1122 样本，`Δδ` max **3.639 µm**（p50 0.162），
     比 45 µm 网格节点低一个数量级；`edge_limited` 全为 0，说明接触判据未被改变。
   - `Δy` 0.255 mm 与 `ΔC` 51 % 均已论证为 δ、`R*` 误差的换算，不是独立缺陷。
2. 复现命令（**必须带算例名，否则默认 `case_B_turnout.json` 没有辙叉档，会写出 frog=0 的表**）：
   `python -X utf8 validation\crh380a_m\report_spline_segmented.py case_I_wing.json`。
   该脚本在任一档 0 样本时返回 1，属预期信号，不是崩溃。
3. 夹具缺陷已解决（第 ⑥ 次尝试）：改为**首接触逐体定位**——轮子最低点置 0，逐体算
   `h_b = max(rail_z − wheel_z)`，落到 `h_b` 最大的体再下沉 `sink`（最深侵入按构造恰为 `sink`）。
   三档全部出数：straight 1920 / switch 1427 / frog 2395 样本，`Δδ` p50 0.588 / 0.571 / 0.095 µm。
   遗留：straight 档 p95 = max = **655.885 µm**（约 96 样本，疑轮缘/踏面支路差异，未逐样本确认），
   因此直向档数字只可用于 p50 量级。前五次尝试（坡度过滤 0.25/0.6、按指定侵入锚定、首接触单件、
   每体自身轨顶）的实测否决记录保留在 `CONTACT_GEOMETRY_ERROR_BOUND_2026-10-21.md` §5。
4. 全套 `pytest` **289 passed**；oracle 五项门（59 680.577 N / 65.47 µm）由
   `tests/test_oracle_frozen.py` 守卫，未动。
5. A 阶段结论：几何层误差已量化到 3.6 µm 级，但**尚未接入生产条带路径**（摊销比 1:40，
   需按站建表）。这一句是 A 阶段的边界，不能省。

## A1 接触窗（2026-10-22，goal-ac4fccd8）—— 机制不成立，但修掉一个真 bug

1. **实现**：`ContactParameters.strip_half_width_m`（有界窗半宽）+ `strip_center_policy ∈
   {deepest, reference, run}`；`find_strip_contact(..., clip_to_engaged_run=True)` 把重叠网格裁到
   “含最深条带的连续啮合段”。默认仍 `None` / `"deepest"`，数值与 oracle 逐位一致。
2. **真 bug**：`edge_limited` 原为 `engaged[0] or engaged[-1]`，把**窗端点**当成几何边缘 →
   每一次有界运行都被 `no_edge_limited_active_contact` 门判死（力已从 170.9 降到 131 kN 也不放过）。
   改为“窗端真的落在重叠边界上且啮合才置位”。回归测试 `tests/test_strip_window.py` 9 项。
3. **宽度扫描**（`case_frog_N_strip05`，0.05 s）：无界 170.860 kN／10 零载 → ±3 mm 116.639/0、
   ±4 mm 123.971/0、±5 mm **131.066/0**、±6 mm 157.616/10、±7–10 mm 与无界几乎一致。Simpack 同窗
   134.97 kN／27.67 kN／从不脱空。代价：nfev +21 %、墙钟 +32 %。
4. **判定不成立的三条硬理由**：①宽度无可辩护取值（转折 5/6 mm 就是把第二个非承载面拉进来的位置）；
   ②5 mm 比真实赫兹半宽 6.1 mm 还窄（`a=(3NR*/4E*)^(1/3)`，R*=0.585 m、N=60 kN）⇒ 真实斑宽救不了脱空；
   ③峰值对上、谷值没对上（0.094 vs 27.67 kN，仍贴零）。
5. `reference` 策略不可用：轨顶参考面是基准不是轨顶，辙叉轨顶横移 73 mm → 0.9 s 内
   `vertical preload equilibrium failed: no seed converged`。`run` 策略在辙叉**退化**为无界
   （整段 δ>0，无重新啮合边界），实测与基线逐位相同——规则正确但判据该用**深度**而非连续性。
6. 文档 `docs/A1_STRIP_WINDOW_2026-10-22.md`；复现 `python -X utf8 validation\crh380a_m\ab_strip_window.py 0.05`
   + `report_a1.py`。全套 **309 passed**（300 → 309）。
7. 辙叉脱空的正解仍未找到：需要**按轨体分体 + 每体独立接触 + 体间法向连续**（与转辙器双体交接同一件事），
   不是积分窗整形。
8. **A3（轨底坡 1:40 压平）本轮受阻**：1:40 烘焙在 PRR 型面里，算例 profile spec 只有
   `{file, format, units, y_sign, y_offset_m, z_sign}`，**无 roll/cant 字段** ⇒ 只能重生成型面，
   而历史上两次同类改动（全局 1:40 横坡、绕轨距面旋转 1 930 kN）都是事故。留给下一轮，且须先立
   “旋转后静载/侵入不变”门。
9. 操作教训：算例 JSON 是**单行**文件，`Select-String`/`Get-Content` 会把整份 1 MB 倒进终端
   （本轮实测一次 11 KB 截断），查键必须用 `python -c "json.load(...)"` 取子结构。

## 2026-10-22 统一口径复核 + 代码体检（第 21 轮）

**A. 两个会话的整车数字不一致，已定案。** 同一算例 `case_full12_cap05.json`，固定 `atol=1e-8`，
对照归档 oracle `out_full12_cap05`（不重跑）：

| 配置 | 墙钟 s | nfev | 峰值 kN | 最大侵入 um | 脱空 | 四频带 |
|---|---|---|---|---|---|---|
| DOP853（归档） | 约 850 | 331 949 | 170.61 | 551.89 | 0 | 9.13 / 57.14 / 5.68 / 1.75 / 2.25 |
| 解析 rtol 1e-6 max_step 1e-4 | 172.5 | 109 628 | 170.61 | 551.90 | 0 | 同上 |
| 解析 rtol 1e-5 max_step 1e-4 | 123.7 | 87 239 | 170.61 | 551.89 | 0 | 同上 |
| 解析 rtol 1e-5 max_step 2e-3 | 118.2 | **81 647** | 170.58 | 551.89 | 0 | 同上 |
| 解析 rtol 1e-4 max_step 1e-3（快速预设） | **79.0** | 58 113 | 170.72 | 550.54 | 0 | 同上 |
| 稀疏差分 rtol 1e-6 max_step 1e-4 | 122.6 | — | FAILED t=0.547528664 s | — | — | — |

- **nfev 81 647 与上一会话报的逐位相同** -> 两个会话跑的是同一套算法、同一条雅可比；
  差异只在**墙钟**（并行会话负载）。**以后报速度先报 nfev，秒数必须标注同批测量。**
- 四档解析的八接触峰值差 <=0.11 kN、频带到两位小数全同、脱空全 0；最差单帧法向力差 230 N（0.4 %）。
- **稀疏差分不是慢，是跑不完** -> 解析雅可比是隐式路径的准入条件，不是优化项。
- 默认值保持 `rtol=1e-6 / max_step=1e-4`；79 s 那档作显式快速预设，不设默认。
- 与 Simpack 85.08 s（32 线程）比秒数无意义，应比 nfev 或同核数墙钟。

**B. 代码体检（为"建立软件"打地基）。** `src/velch` 48 模块/15 320 行；`tests` 47 文件/4 637 行
（`pytest tests` -> 325 passed in 14.9 s，不依赖 1.4 GB 的 validation）；`docs` 57 篇；
`validation` **1 402 MB / 14 604 文件 / 207 个 out_***（其中 10 个是常数静载门，曾被误当动态基线）；
仓库根 **57 个游离 .py**；`dist/` 4 个旧 wheel + `build/` 残留。

做对的：架构由 `tests/test_architecture_rules.py`（419 行 AST 规则，含 headless import 与无环检查）
强制执行；`TODO/FIXME` 全 0，`type: ignore` 仅 9 处；公共面收窄（`vehicle_solver` 只 2 个入口）；
`test_oracle_frozen.py` 钉住静载门；`pyproject.toml` 完整，从外部 cwd 只设 `PYTHONPATH` 即可
`import velch...ui` 且 `python -m velch --help` 正常。

P0 缺口（不解决不能叫软件）：①**没有版本控制**（`fatal: not a git repository`，15 320 行源码无历史）；
②**没有 LICENSE**（pyproject 也无 license 字段）；③1.4 GB `validation/` 与源码同树混放；
④**默认路径仍是最慢那条**（`jacobian=None` + DOP853 + `max_step=1e-4` -> 850 s，解析与快速预设无入口）。
P1：57+190 个脚本无归属；`contact.py` 1573 行/9 公共函数是上帝模块；无 CI/覆盖率门/lock；
README 里"尚未与 Simpack/实测物理验证"已过期。P2：docstring 覆盖偏低；v1/v2 双求解路径需标注；
207 个 `out_*` 无索引。落地顺序（先建仓再搬 validation，否则搬动不可回退）见文档 B.4 六步表。

文档：`docs/UNIFIED_SCALE_AND_SOFTWARE_READINESS_2026-10-22.md`（已登记入本索引）。
脚本：`.tmp/o1_unified.py`、`.tmp/o2_inventory.py`。

## 2026-10-22 代码审查处置：两条真缺陷落在柔度分支（第 22 轮）

外部代码审查（只读）报两条确定缺陷，均经本机复现后修复，全部落在 `support_compliance` 非空的算例上；
全仓 358 个算例只有 5 个打开柔度、**没有一个进验收门**，所以 325 项测试全绿也拦不住。

**D1｜strip 力梯度归一化用错斜率**（`src/velch/jacobian.py` `_blocks_at`）：
`partials.normal_force_n` 是 strip 自己的 Hertz 型 dN/dq（不含串联软化），却被除以**软化后**的
`elastic_slope`；两个链因子相互抵消，柔度被从 q 块里整体删掉。实测 `case_X_support`：
`dq` **53.4**（最差列 88.0、12 列越界），解析 `Jq[ax1.z,ax1.z] = -4.3514e6` vs FD `-7.8328e4`（55.6 倍）。
**修法**：除以原始 `1.5*C*sqrt(depth)`。修后 `dq` **4.835e-3**（最差列 0.153、4 列）。

**D2｜阻尼分支多乘 `elastic_slope/raw`**（同文件 `_normal_slopes`）：RHS 的阻尼是
`c*sqrt(depth)*approach`，作用在几何侵入上、不经串联链，因此不存在该链因子。实测
`case_X_support` `rate_slope` 478.49 vs 真值 26307（55 倍）；`dv` 0.041（X）/ 0.976（Y）。
**修法**：删掉 `* correction` 与该段注释。修后 `dv` **1.9e-10 / 2.9e-11**，坏列 12 → 0。

**D5｜`jacobian` 与 `method` 组合未校验**：`solve_ivp(method="DOP853", jac=...)` 只发一条
`UserWarning` 就忽略，配置静默无效。**修法**：`RunSettings.__post_init__` 抛 `ValueError`
（已确认全仓无算例是 DOP853 + jacobian 组合）。

**D6｜`body_contacts` 返回内部缓存本体**：`restore_contact_state` 会重新绑定 `_body_cache`，
调用者手里的 dict 静默失效。**修法**：返回 `dict(...)` 拷贝。

**新增回归门** `tests/test_jacobian_support_compliance.py`（7 项）：柔度算例 `dv<1e-6`、`dq<1e-2`、
深穿透 `dq<5e-2`（界限）、无柔度 `dq/dv<1e-8`、DOP853+jacobian 必须报错、`body_contacts` 必须快照。
全仓 **332 passed in 16.98 s**。

**未修（有实测、未定位到行，已记录）**：D3 蠕滑饱和交叉偏导从未装配（生产算例 `slip_lateral` 恒 0，
结构上看不见）；D4/C1 深穿透柔度算例的滚转↔横移交叉耦合仍差 ~15 %（`dq` 2.4e-2），
且已否证"4/3 常数因子"假设（修完 D1 后大项一致到 0.99999–1.00222，偏差只集中在两个交叉项）；
C4 稀疏模板只在 t=0 采样；C5 cap 与 3μN 邻域无测试。

**默认路径未动**：`case_full12_cap05.json` 修前修后同为 `dq` 8.5e-10 / `dv` 1.6e-10；
冻结 oracle、静载 59 680 N / 65.47 µm、整车 1.2 s 八接触峰值全部未变。
文档：`docs/UNIFIED_SCALE_AND_SOFTWARE_READINESS_2026-10-22.md` 新增 §B.5。

## 2026-10-22 验收门扩容 + D4/C1 根因定位（第 23 轮）

**门扩容**：`validation/crh380a_m/s2_analytic.py` 的 `gate()` 新增 `compliant_gate()`——
把 `case_X_support.json`、`case_Y_full_support.json` 纳入正式门。判据分两级：`dv` 严格
`< 1e-6` 且坏列 0（D2 修完即精确），`dq` 只做上界（X `1e-2`、Y `5e-2`，最差列 `< 1.5`，
坏列 `<= 25`）。打印 `BOUNDED` 而不是 `PASS`，避免把"已知未修"读成"正确"。
当前：X `dq` 4.84e-03 / 最差列 0.153 / 坏列 4；Y `dq` 2.37e-02 / 最差列 1.06 / 坏列 8；
两者 `dv` 均 < 3e-10、坏列 0。生产算例六个时刻仍全 `PASS`，总判定 `GATE PASS`。

**D4/C1 根因（已定位，未修）**：`_contact_modes()`（`src/velch/jacobian.py:258-260`）在
`geometry.partials is None` 时返回 `None`，装配退回"冻结力臂 + 冻结法向"形式；而 `partials`
只由条带积分分支（`contact.py:855 _band_partials`）生成。`case_Y_full_support.json` 的
`normal_policy` 是 `point_hertz`，因此 `d lever/dq`、`d normal/dq` 两项**一项都没装**。
残差因此全部集中在滚转/摇头与横移的耦合（axle1 块实测：`∂M_roll/∂y` 解析 2.0503e+03 vs
FD 8.9061e+02 = 2.30 倍；`∂M_yaw/∂y` 解析 0.13 vs FD −87.67，整项缺失；
`∂M_yaw/∂roll` 解析 −4.14 vs FD +2653，整项缺失）。
生产算例走 `strip_integral`、partials 在位，同一套代码 `dq = 8.5e-10`，所以缺项只在这条分支上。
另实测 `∂C/∂roll = 9.54e12`（相对 83.7 /rad，`local_circular` 下刚度随接触点走），
按串联链估算只占总误差 ~4 %，是第二个缺项但不是主项。

**口径修正**：轮对五个坐标的顺序是 `(y, z, roll, spin, yaw)`（见
`validation/crh380a_m/check_jacobian.py` 的 `_labels`），此前按 `(y, z, roll, yaw, spin)`
读索引会错位。数值结论不变。

**下一步**：①给点接触分支发布 `d y_c/dq`（接触点横向游走）与法向旋转，让 `_contact_modes`
不再是 `None`；②修完把柔度门收到 1e-5、`BOUNDED` 改回 `PASS`；③钉住 `∂C/∂q`。
文档：`docs/UNIFIED_SCALE_AND_SOFTWARE_READINESS_2026-10-22.md` 新增 §B.6。

## 2026-10-22 AI 接口切片落地 + 建仓（第 24 轮）

**一句话**：软件现在有一个机器可调用的面——12 个工具、一套错误码、一条只追加的审计链、
一条命令的自动验收；同时仓库第一次有了版本控制（`9e47611` / `v0.4.0`）。

| 交付 | 路径 | 结论 |
|---|---|---|
| 工具层 | `src/velch/agent/tools.py` | `ToolSpec` 单一声明 → `manifest()` / MCP `tools/list` / `velch agent call` 三处同源；**12 个工具**（meta 1、case 5、run 5、result 1） |
| 核心 | `src/velch/agent/core.py` | `ErrorCode` 13 码闭集；`case_root()`/`agent_home()` 可用环境变量改；`within_allowed()` 路径监狱；72 参数 schema；`normalise_patch()` 显式拒 `[]` 通配 |
| 算例 | `src/velch/agent/cases.py` | `derive_case()` 是唯一写入口（转调 `apply_patch`）；父算例 sha256 前后复核；`materialise_case()` 把作业私有化并把**任意层级** `file` 引用绝对化 |
| 作业 | `src/velch/agent/jobs.py` + `worker.py` | ≤60 s 内联、否则独立进程（`DETACHED_PROCESS`）；状态由 `state.json`+`manifest.json` 派生（`succeeded`/`gate_failed`/`failed`/`abandoned`）；无 manifest 读结果即 `artifact_integrity` |
| 协议 | `src/velch/agent/server.py` | MCP stdio：`initialize`/`tools/list`/`tools/call`，同时接受行分隔 JSON 与 LSP `Content-Length` 两种帧，未知方法 `-32601` |
| 成本模型 | `core.predict_wall_s()` | 校准两轮：`NFEV_PER_STEP={DOP853:138, Radau:30, BDF:46}`、`BAND=(0.5,2.2)`。1.2 s 整车估 848 s vs 实测 850 s；短窗高估约 2×（**宁可高估**） |
| 契约测试 | `tests/test_agent_contract.py` | 20 项：通配拒绝、4 组坏 `solver_patch`、derive 不改父、ledger 成链、越狱路径、`gate_failed` 是状态、MCP 协议面、**import 不拖入内核**（子进程断言 `vehicle_solver`/`contact`/`jacobian` 不在 `sys.modules`） |
| 自动验收 | `scripts/auto_accept.py` | 四步：pytest → `agent doctor` → `capabilities` 信封 → 派生+真跑 0.05 s+读结果；写 `reports/auto_accept_<时间戳>.json`；`--skip-run` 可跳过第 4 步 |
| 建仓 | `.gitignore` / `LICENSE` / `git` | 未过滤 `git add -A` 会吞 14 134 文件 / 1.06 GB；过滤后 **2 013 文件 / 213 MB**，两个冻结 oracle 的 `history.csv`+`manifest.json` 刻意入库。首提 `9e47611`，标签 `v0.4.0`，MIT |

**实测**：`pytest tests` → **352 passed in 17.3 s**（332 基线 + 20 契约）；
`scripts/auto_accept.py` 一次全通（`j20261022-165859-yidl` → `result_status=numerically_checked`）；
`python -m velch.agent doctor` → `ok: true`（registry 72 / cases 358 / ledger 2）。

**一个语义更正**：`derive_case` 的 `physics_changed` 原先把任何 `run` 编辑都算物理改动，
但 `output_step_s` 只决定写多少行（自适应步长由 `rtol`/`atol`/`max_solver_step_s` 决定）。
现在 `SAMPLING_ONLY_SOLVER_KEYS={"output_step_s"}` 不算物理改动，`comparable_to_parent` 随之
为真——否则每个"重采样变体"都会被标成不可比，验收冒烟也会声称自己改了模型。

**踩坑（都记进 `docs/AGENT_TOOL_LAYER_2026-10-22.md` §8）**
1. `agent/__init__.py` 既导出 `tools` 又被 `tools` 反向 `from . import __version__` → 循环 import。
   改为 `from velch import __version__`。**子包的 `__init__` 不能既导出模块又被模块反向导入。**
2. PowerShell 5.1 没有 `Join-String`，一条统计命令抛上千行 `CommandNotFoundException` 并转后台
   （`pwsh-83` 已 kill）。**PS 5.1 里做聚合统计一律用 python。**
3. `python -c` 里带引号的中文/反斜杠会被 PowerShell 解析坏 → 一律落 `.py` 再跑。
4. 契约测试首跑 4 项失败：fixture 返回值被当函数调用；`derive_case` 只给 tag 被正确拒
   （"nothing to derive"）；"profile 引用绝对路径"的断言找错了键（实体在
   `wheels[].profile.file` / `rail_templates[].stations[].profile.file`，不是 `payload["bodies"]`）。

**没做（`AGENT_TOOL_LAYER` §8.3 逐条列了原因）**：`case.policy` 三档（当前 72 参数对 agent 全可写，
需要人拍板哪些不能碰）、`run.submit(mode="batch")`（先要修 `parallel._solve_case` 吞异常）、
`result.series/assess/compare/observations`、`inverse.estimate`、`dev.gates`、HTTP、
跨进程文件锁、`ai_provenance.json`。

**下一步**：①把 `AGENT_TOOL_LAYER` §1 剩下的工具按 §8.3 的顺序补（先 `result.series`，列白名单
必须从 manifest 现读）；②修 `parallel._solve_case` 的 `except Exception` 后再接批量；
③接 `inverse`（先用 `materialise_case` 绕开 `CaseSpec.resolve()` 的临时目录问题）；
④`case.policy` 三档需要人类拍板。

文档：`docs/AGENT_TOOL_LAYER_2026-10-22.md` 新增 §8（设计 vs 代码对照）；
`docs/AI_INTERFACE_ARCHITECTURE_2026-10-22.md` §9 的 Phase 0/2/3 已部分落地。

## 第 25 轮（2026-10-22 傍晚）：UI 第 ⑦ 屏「三维模型」

目标（用户）："先把软件做好，有相应的中文ui界面可以操作，并且是否可以将相应的三维模型展示在我的UI界面上？"

结论：能，且**未引入新依赖**——Tk 内嵌 matplotlib `mplot3d`（本机已装）。`pyproject.toml` 新增
`[project.optional-dependencies] ui = ["matplotlib>=3.6"]`；没有 matplotlib 时这一屏降级为一句安装提示，
其余六屏照常，窗口不崩。

### 几何口径（两处，都是靠探针数值抓出来的）
1. 车轮型面的 z 是"**轮心以下的高度**"：`case_frog_N_strip05.json` 实测 `z_m ∈ [-0.458, -0.4131]`，
   所以子午点半径 `R = -z`（踏面约 0.413–0.43 m、轮缘 0.458 m，比踏面大 28 mm，正是轮缘高出踏面量）。
   先写成 `R = R0 - z` → 整车低了 0.5 m，图上一眼可见、数值上无声。
2. `initial_q` 的 z 是**位移**不是绝对高度：绝对轮心高 = `wheel_center_height_m + q_z`。
   修后车轮最低点（轮缘尖）落在 **-0.0285 m**、踏面贴轨面 **z≈0**，与
   `src/velch/contact.py:618 _absolute_arrays`（`depth = rail_z - wheel_z > 0`）的符号一致。

### 新增
- `src/velch/ui/model3d.py`（307 行，纯几何，不 import Tk/matplotlib、不做接触搜索）：
  `QuadGrid` / `WheelState` / `Scene`；`axle_x_positions`、`initial_states`、`states_from_history`、
  `rail_grids`（**逐 body 画**：stock/switch/wing/point 是不同承载面，合并正是求解器刻意避免的错误）、
  `wheel_grid`、`wheel_grids`、`skeleton`、`build_scene`（可传已解析的 `case`，省掉 13.5 MB 算例的 0.5 s 解析）。
- `src/velch/ui/screen_model3d.py`（约 430 行）：左栏算例下拉、里程窗起点/长度、站位数/横向点/周向点、
  轴位多选、叠加运行（`history.csv` 帧滑块）、显示开关（钢轨/车轮/骨架）；右栏 3D 画布 +
  工具栏（重画、等轴/正视/侧视/俯视、PNG 导出）；底部注记与统计。
- `tests/test_ui_model3d.py`（9 项，无 Tk、无 matplotlib、无求解）：面片覆盖里程窗、**接触斑落在轨面**
  （轮缘尖 -28.5 mm、踏面 |z|<30 mm）、轮心绝对高度、history 缺通道时回退到轮心高度、分辨率上限、
  窗口越界时 `notes` 说明、骨架在车轮之上、轴位随速度平移。
- `src/velch/profiles.py`：`ProfileSeries` 新增 `lowest_m` / `highest_m` / `mileages()`（原先只能摸私有字段）。
- `ui/app.py`：`SCREENS` 加 `("model3d", "⑦ 三维", "钢轨型面与车轮的三维视图", "Ctrl+7")`、
  `_build_screen` 加映射；快捷键文案改 Ctrl+1…Ctrl+7（`_bind_keys()` 按 `enumerate(SCREENS)` 自动绑，
  新增屏不需要另写绑定）。

### 实测
- `python -m velch.ui --selftest` → **7 屏 / 404 控件 / 0 个屏报错**，新屏一行：
  `model3d (三维模型) 52 16 case_frog_N_strip05 轨面 8 车轮 8 顶点 19040 302 ms`。
- `pytest tests` → **361 passed in 17.6 s**。

![三维模型屏预览](images/model3d_preview.png)

*第七屏的实机渲染（`case_frog_N_strip05.json`，里程窗 78.6–80.4 m）：四条轨面、两个车轮
（按型面回转出的走行面）、轮对轴线与轨面；轮缘尖落在轨面下 28 mm。*

### 诚实边界（屏内注记也写了）
- 车厢/转向架轮廓是**示意尺寸**：算例只给质量与惯量，不给车厢图。
- 车轮按四个实际轮对位置画、钢轨只画所选里程窗，所以车体常常超出轨面窗——这是视图取舍，不是错位。
- 视图**不做接触搜索**：看不到侵入量与接触斑。要这些去 ⑤ 评价屏（读求解器产物），别在这里自己算一份。

**第二个几何 bug（同一屏，同日修）**：回转角只扫了 x，没扫 z——`z_local` 写成常值 `-R`，
车轮被压成一块贴着轨面的平板。正解是把子午点绕 **y 轴**（车轴方向）回转：
`x = x_w + R cosθ`、`z_local = R sinθ`、`y_local = 横移`，再叠 `roll` 的 y–z 耦合。
`tests/test_ui_model3d.py` 现在钉住"车轮是圆的"：`z` 与 `x` 的跨度都等于 2×轮缘半径 0.458 m、
且圆盘以轮心为心（中点 = `state.z_m`）——再压平就会先坏测试而不是先被眼睛发现。

**下一步**：①接触点/侵入量着色（`depth` 从 history 的 penetration 通道取，不要自己算）；
②左侧 `left:main` 在该窗内只有 2 个站位，抽样会退化成长条，需按 body 的 `s_lo_m/s_hi_m` 补齐；
③把 ⑦ 屏写进 `docs/ONBOARDING_2026-10-21.md` 的操作路径。

## 第 26 轮（2026-10-22 傍晚）：把"默认太慢"这件事从文档挪到入口

**决策（用户拍板顺序 2 → 1 → 3）**：默认路径决定别人的第一印象 → `validation/` 外移决定仓库能否
长期维护 → `contact.py` 拆分风险最高，等 CI 兜底后再动。本轮做第 2 项。

### 问题
算例声明的求解器（`DOP853` + `max_step=1e-4`）是为对齐 Simpack 标的，1.2 s 整车 ≈850 s。
解析雅可比与 `rtol=1e-4` 的快速档实测早已存在，但**没有入口**——只能靠临时脚本，
所以"第一次跑"必然是等 14 分钟。

### 做法：预置 + 派生算例，而不是就地改算例
- `src/velch/case/derive.py`（新）：`solver_override()`（`--fast` 打底、显式参数覆盖、只返回变化的键）、
  `absolutise_profile_paths()` / `relative_profile_references()`、`write_derived_case()`。
- `cli.py` 的 `run-vehicle` 新增 `--fast`、`--method`、`--jacobian`、`--rtol`、`--atol`、`--max-step`。
- **关键设计**：覆盖不写进内存里的 `case.run`，而是写一份**派生算例**到 `<输出目录>/case_used.json`
  再加载它运行。理由是 `save_vehicle_result` 会快照"它拿到的算例字节"并在收尾时复核哈希——
  内存里改 `run` 会让快照描述一套**从未运行过的设置**，manifest 看着可审计、其实在撒谎。
  派生时把型面引用改成绝对路径（该算例的辙叉 body 用的是 `bodies/point_r07xxxxx.csv` 相对引用，
  拼到输出目录下就加载不到），并且父算例一个字节不动。
- 命令行输出的 `solver` 段同时给 `declared` / `effective` / `preset` / `derived_case`。

### 实测（同机同批）
| 算例 | 声明 | `--fast` | 峰值最差偏差 | 最大侵入 |
|---|---|---|---|---|
| `case_full12_cap05.json`（1.2 s） | 850 s / 331 949 | **79 s / 58 113** | 0.11 kN | 550.54 vs 551.89 µm |
| `case_frog_N_strip05.json`（0.05 s） | 17.8 s / 10 253 | **3.7 s / 1 553** | 0.30 kN（0.14 %） | 155.03 vs 154.77 µm |

脱空样本数（13 / 0）两边一致，均 `numerically_checked`；`manifest.case_sha256 == case_snapshot.json`
的 sha256 在两种运行下都成立。

### 踩坑
1. `--fast` 第一次跑就炸：`FileNotFoundError: ...fast_smoke\validation\crh380a_m\bodies\main_r0791310.csv`。
   根因是命令行给的是**相对路径**，`source.parent` 也就相对，绝对化等于没做。修法：`write_derived_case`
   先 `Path(source).resolve()`；`absolutise_profile_paths` 再以 `Path.cwd()` 兜底找不到的相对引用。
   已加回归测试 `test_derived_case_handles_a_relative_source_path`。
2. `write_derived_case` 原先先查"目标已存在"再查"目标是源文件"，导致覆盖源文件时报的是
   `already exists`。顺序调换：**先拒绝写源文件**，再谈重复。
3. `--fast` + `--method DOP853` 仍会被 `RunSettings` 拒（`jacobian is only used by the implicit
   methods`），这是 D5 那条规则在起作用，不是新 bug。

### 测试
新增 `tests/test_cli_solver_override.py`（16 项）：预置内容、显式参数优先、`jacobian="none"` 清空、
非正容差被拒、`--fast` 产物能通过 `RunSettings`、DOP853+解析被拒、派生算例只改 `run`、
型面引用绝对化（含相对源路径）、父算例字节不变、拒写源文件、拒写已存在目标（`overwrite=True` 例外）、
校验失败时**不留下输出目录**。全仓 **377 passed**。

文档：README §快速运行 增补 `--fast` 前置说明与两行实测表；本轮起"要报告数字用声明配置、要趋势用 `--fast`"成为写进 README 的规矩。

## 第 27 轮（2026-10-22 傍晚）：把 1.4 GB 语料搬出软件包

**决策**：用户拍板顺序 `2 → 1 → 3`，本轮做第 1 项。目标不是"删掉语料"，而是让
**软件包目录里只有软件**：`src/` 1.6 MB，语料 1.37 GB，两者同树是仓库显得不可维护的主因，
但语料又不能删——358 个算例、208 个运行目录、223 个测量脚本仍是判据的出处。

### 做法：把"位置"变成一个只有一处实现的问题
- 新增 `src/velch/data_root.py`：解析顺序 **`VELCH_DATA_ROOT` 环境变量 → `.velch-data.json`
  标记文件 → 仓内 `validation/`**；对外只暴露 `data_root()/case_dir()/case_path()/explain()`。
- `ui/store.py` 的 `VALIDATION_DIR`、`agent/core.py` 的 `case_root()`、以及**九个测试模块**
  原本各自从 `__file__` 往上走重新拼 `<repo>/validation/crh380a_m`——现在全部改成问 `case_dir()`。
  这一步让"搬家"从一次九文件重构降级成一份标记文件。
- `tests/test_data_root.py`（12 项）钉住优先级与失败行为：默认路径、环境变量压过标记、
  **带 BOM 的标记也要能读**、相对路径标记、6 种坏标记回落而不抛异常、`case_path()` 不猜。
  理由写进 docstring：静默回落到空目录会让所有门"通过"——没有算例就没有矛盾。

### 实际搬运
```powershell
Move-Item F:\ai道岔状态反演辨识\Velch\validation\crh380a_m F:\velch_data\validation\crh380a_m
'{ "data_root": "F:/velch_data/validation" }' | Set-Content .velch-data.json -Encoding utf8
```
- `crh380a_m`（1 392 MB / 14 431 文件 / 358 算例 / 208 `out_*` / 223 脚本）→ `F:\velch_data\validation\crh380a_m`
- `turnout18`、`turnout18_ref`（15.7 MB 判据长文）**留仓内**——它们是文档而不是数据。
- 两个"冻结 oracle"随语料外移；**判据值仍在代码里**：静载 59 680.5769 N @ 65.47 µm
  （`tests/test_oracle_frozen.py`）、1.2 s 动态基线 89.68 / 170.61 kN 与 551.9 µm（文档）。
- `.velch-data.json` 入库排除（机器相关），同时新增 `.velch-data.example.json` 作模板。

### 踩坑（重要，差点误判成代码坏了）
PowerShell 5.1 的 `Set-Content -Encoding utf8` **写 BOM**，`json.loads` 读到 `\ufeff` 抛错 →
标记被静默忽略 → 回落到此刻已经空了的仓内路径 → `31 failed / 14 errors`。
`data_root._root_from_marker()` 改用 `encoding="utf-8-sig"` 读取，并加测试钉住。

### 验证
- `pytest tests` → **389 passed in 15.9 s**（377 + 12 项 data_root）
- `python -m velch.ui --selftest` → 退出码 0，7 屏正常，Simpack 对照仍可用
- `python -m velch.agent doctor` → `ok: true`，`case_root detail: 358`，ledger 4 条
- `validation/INDEX.md` 重写为路标：现在在哪、怎么解析、哪些目录是常数静载门、门脚本的仓外路径

### 顺带
- `reports/` 入库排除（验收报告与临时渲染可再生，docs 需要的那张图已入库）。
- 下一个提交点仍是第 3 项 `contact.py` 拆分——按用户要求**等 CI 兜底**后再动。

## 2026-10-22 界面中文化：把数据标识符讲成人话（第 28 轮）

用户的原话是「软件当中的一些部件等元素都改写成中文，要不然很难看懂」。先做审计，再决定改什么。

### 审计：字面量本来就是中文，看不懂的是数据
`​.tmp/audit_ui_language.py`（AST 抓 `text=` / `title=` / `set_xlabel` / `insert`）在 `src/velch/ui`
里找到 264 个候选字面量，只有 8 个需要翻译，22 个 mixed —— 其余是 `insert(index="end")`、`state="readonly"`、
`Card.TLabel` 这类 Tk 管线字符串，不是给人看的。真正让人看不懂的是**从数据里长出来的名字**：

| 位置 | 之前 | 一条运行里的数量 |
| --- | --- | --- |
| 时程/频谱通道 | `axle1_right_normal_n` | 123–6127 |
| 运行目录 | `out_A_final_law` | 208 |
| 算例编号 | `S_hc_e0.15_v0.5` | 358 |
| 算例屏标签 | `SHA-256`、`schema` | 2 |

`​.tmp/ui_text_dump.py` 真建一个 Tk 窗口逐屏走 widget 树，量出每个屏还剩多少含 ASCII 的字符串：
③ 191、④ 321、⑤ 226、⑥ 204、⑦ 538 —— 其中绝大多数就是上面的通道名与目录名。

### 做法：文法化的中文标签，不认识的宁可不译
- `src/velch/ui/store.py` 重写 `channel_unit` / `channel_group` / `channel_label`：
  按**有文档的通道文法**拆词（`axleN` / `bogieN` / `carbody` / `track_modeN` / `railN` / `sleeperN`），
  出 `第2轴右轨 法向力 [N]`、`第1轴 横移速度 [m/s]`、`车体 摇头角 [rad]`、`钢轨 模态位移 12 [m]`、
  `第1轴左轨 钢轨垂向位移 [m]`。三条规则值得记住：
  1. **速度后缀 `_per_s` 必须比 `_m` 先匹配**，否则每个速度都会被叫成位移；
  2. `avle1_left_active` 这类通道把词写在**单位后缀里**（`_active`），剥掉后缀会丢失唯一的语义，
     所以加了 `_SUFFIX_QUANTITY` 把词捡回来；
  3. **不认识的通道回落到原始名**，不猜。错的汉语词读起来像定义，比不译更坏。
- 新增 `channel_short_label()`（去掉单位，给窄表格用）与 `run_label()`：
  `out_full12_cap05 · 2401 帧 · 155 通道 · 隐式 BDF · 门 7/7`；没有 manifest 的运行目录也会带
  `（manifest 缺失）`/`（无 history 表头）`，不再退化成一行标识符。③④⑤⑥ 屏的下拉统一改用它。
- ④ 频谱的通道下拉改为**显示中文、内部映射回原始列名**（`_column_by_label`），图例与状态行给
  `第1轴右轨 法向力（axle1_right_normal_n）` —— 中文给人读，原始名给人复制。
- ① 算例屏：`算例 ID` → `算例编号`，`schema` → `算例格式`，`SHA-256` → `文件哈希（SHA-256）`。
- `src/velch/ui/widgets.py` 图表刻度：matplotlib 默认会为"几乎不变"的力给出 `1e-17+5.96e4`
  这种偏移标签，关掉偏移后又变成 `59680.5768588`（十二位噪声）。改为统一 4 位有效数字的自定义
  `FuncFormatter`：`1e-3 ≤ |v| < 1e4` 用 `%.4g`，其余用 `%.2e`。**调用方显式给的刻度标签（频带频率、
  里程站号）必须保留**，所以 `x_ticks` 非空时不装这个 formatter。

### 度量（`​.tmp/ui_identifier_audit.py`：只统计"像标识符"的字符串，不算单位符号）
纯标识符 **21 条 → 2 条**：`crh380a_m`（数据目录名，就是要留着）与 `s`（秒的单位）。
③ 时程与 ④ 频谱各 0 条。截图 `docs/images/ui_chinese_labels.png`（④ 频谱屏，真实运行 `out_full12_cap05`）。

### 测试与验证
- 新增 `tests/test_ui_labels.py`（**26 项**）：19 条文法对照表（改一个词就会红）、未知通道回落、
  速度后缀优先、七项门的名字里不得有 ASCII 字母、`run_label` 两例（有/无 manifest），
  以及**覆盖测试**——把两个真实 history 文件的每一列都翻一遍，断言没有列掉回原始名。
  这条覆盖测试抓到了固定表看不出来的两类漏译：`axleN_left_rail_z_m`（柔件轨道的钢轨/轨枕通道）
  与 `track_modeN_m`（模态轨道）。
- `pytest tests` → **415 passed in 13.9 s**（389 + 26）
- `python -m velch.ui --selftest` → 退出码 0，7 屏 / 404 控件 / 0 个屏报错

### 踩坑（两次，都是我自己造的）
1. `_compact_ticks` 写成 `@staticmethod` 却引用 `self.x_ticks` → 每次重绘抛
   `NameError: name 'self' is not defined`，而 Tk 把回调异常打到 stderr 后**照样出图**，
   只有看到 stderr 才知道。判据：改完 UI 必须看 stderr，不能只看图。
2. 先装的 `FuncFormatter` 把 ④ 频谱的 `set_xticks(pos, freq)` 覆盖掉了，横轴标签从
   `6.2079 … 793.7` 变成 `0.7924 … 2.9`（即 log10 位置）——**图看着正常，轴是错的**。
   这是"显式标签必须优先于全局格式化"的教训。

## 2026-10-22 本地闸门与界面可读性（第 29 轮）

**起因**：仓库没有远端，"CI"只能是本地闸门；此后要把界面的可读性提高。

### 一、提交前闸门（`.githooks/pre-commit`）

- `scripts/auto_accept.py` 的四步（pytest / agent doctor / 契约 / 端到端）本来就存在，这一轮把它接到
  唯一每次都会发生的动作上：`git config core.hooksPath .githooks`，`pre-commit` 跑 `--skip-run` 版，
  **本机实测 16.0 s**（pytest 15.5 s + doctor 0.1 s + 契约 0.05 s）。
- 失败即阻断提交，并提示报告位置（`reports/auto_accept_*.json`）与临时跳过方式（`VELCH_SKIP_HOOK=1`）。
- 顺手修掉一个**已经失效**的路径：`auto_accept.py` 里的 `FAST_CASE` 仍是
  `validation/crh380a_m/case_frog_N_strip05.json`，而语料已在第 1 项外移到 `F:\velch_data`；现在改为
  经 `velch.data_root.case_dir()` 解析。**没有语料的新克隆**上，端到端一步打印 `SKIP` 而不是假 PASS
  （其余三步照跑），这是"较弱的闸门"，要在输出里说出来。

### 二、界面可读性

- 字号从写死的常数变成**参数**：`theme.BASE_FONT_SIZE` + `set_scale(factor)`（0.9–1.6，步长 0.1），
  同步缩放 `LINE_HEIGHT` 与 `TREE_ROW_HEIGHT`；`VELCH_UI_SCALE` 环境变量与 `--scale` 都能在启动时设定。
- 窗口内快捷键 **Ctrl+= / Ctrl+- / Ctrl+0**；缩放后**重建控件树**，因为 Tk 在创建时就把字体烤进去了，
  只改令牌会让界面声称 130 % 而一半控件仍是 100 %。
- 修掉四处**字号放大必然截断**的地方：表格列宽按缩放（`widgets.ListPanel.columns`）、固定侧栏宽度
  （③④⑤⑥⑦ 的 `minsize`/`width`）、写死的 `wraplength` 改为跟随容器（`screen.py:wrap_with`）、
  ① 算例屏三个按钮由向左堆叠改为等宽网格。
- 顺带给顶部统计条减负：自由度分布只显示前 4 名 + `等 N 种`，不再把 13 种拼成一条被裁掉的长条。
- 文档：`docs/UI_READABILITY_2026-10-22.md`（令牌表、用法、四处截断、验证方式、两个不再重复的坑）。

### 三、验证

- `pytest` **423 passed**（415 + 8 项 `tests/test_ui_scale.py`）；
- `python -m velch.ui --selftest` → 7 屏 / 0 报错；
- 截图对比：100 % 与 130 % 的 ① 算例屏、125 % 的 ④ 频谱屏（`reports/` 下，可再生的验证件）；
- `pre-commit` 实跑：16.0 s，`verdict: ACCEPT`。

---

## 2026-10-22 拆开 `contact.py`（拆分第 30 轮）

### 一、为什么现在做

`docs/ARCHITECTURE_2026-10-21.md` §2.3 把 `contact.py` 记成上帝模块：1573 行里塞了四件互不相关的事
（参数契约、站位栅格缓存、三条接触点搜索、法向/切向力律）。拆它一直排在最后，理由是**没有兜底**——
现在有了：`pytest` 423 项 + `scripts/auto_accept.py` 四步闸门 + `pre-commit`。

### 二、拆成什么

| 模块 | 行数 | 职责 |
|---|---|---|
| `src/velch/contact_models.py` | 302 | 四个策略常量 + `ContactParameters`/`ContactPartials`/`ContactGeometry`/`ContactResponse` + `merge_contact_responses`/`deduplicate_contacts` |
| `src/velch/contact_grid.py` | 157 | `_build_rail_grid`/`_merge_grid`/`_grid_slope`/`_grid_curvature`/`_rail_node_slopes` 与两个 LRU 缓存、`RAIL_SLOPE_TABLE` 开关 |
| `src/velch/contact_search.py` | 804 | `_contact_on_span`、`find_patch_contact`、`find_strip_contact`、`find_spline_contact` 与它们的私有助手 |
| `src/velch/contact.py` | **384**（原 1573） | 策略分派（`find_graph_contact`/`find_graph_contacts`）+ 力律（`evaluate_contact`/`saturate_creep_force`）+ **显式 re-export 23 个旧名** |

依赖方向 `contact_models ← contact_grid ← contact_search ← contact`，无环。三个新模块仍以
`velch.contact` 开头，所以 `tests/test_architecture_rules.py::test_contact_layer_does_not_import_its_callers`
自动把它们纳入"叶子不许 import 调用者"的约束，不用改规则。

### 三、为什么调用方一行都不用改

`contact.py` 逐名 re-export（不用 `import *`），包括**私有** `_contact_on_span`——`tests/test_contact_patch.py`
一直在用它。`__all__` 显式列出 23 个公开名，任何一个从兄弟模块消失都会在 import 时就报错，而不是等到运行时。
新增 `tests/test_contact_split.py`（6 项）把这条约定钉住：facade 名字齐全、各名字的 `__module__` 落在该落的模块、
重活已经搬出 facade、兄弟模块不许反向 import facade、兄弟模块不许越过 contact 叶子。

### 四、验证

- `pytest tests` → **429 passed**（423 + 6）；
- `scripts/auto_accept.py` → `PASS tests / PASS doctor / PASS contract / PASS end-to-end`，`verdict: ACCEPT`；
- 冻结 oracle 与静载门（59 680.5769 N / 65.47 µm）未动：这次是纯移动，没有一行算法改动。

### 五、下一步没做的

`vehicle_solver.py`（812 行）仍在 `§2.4 S2` 的清单上，它比 `contact.py` 更难：跨调用可变状态五个
（`_contact_seed`/`_body_cache`/`_seed_misses`/`_contact_age`/`_active_body`）与 `save_vehicle_result`
的落盘字节耦合，拆之前要先把这些状态收进一个对象。

---

## 2026-10-22 ② 运行屏的求解器选择（第 31 轮）

### 一、问题

`--fast`（第 26 轮）与 `--method/--jacobian/--rtol` 只在命令行存在。界面里的人点"启动单次运行"，
永远拿到算例声明的配置——也就是新用户第一次必然等 14 分钟。这不是性能问题，是**入口缺失**。

### 二、做法

`src/velch/ui/screen_run.py` 新增"求解器"一行：

- 复选框 **快速预设（BDF + 解析雅可比 + rtol 1e-4）** → `--fast`，下面一行小字写清代价
  （约 4–5× 墙钟、八接触峰值偏差 ≤0.2%、派生算例写在输出目录的 `case_used.json`、原算例不动）；
- 两个下拉 **方法**（按算例声明 / 显式 DOP853 / 隐式 Radau / 隐式 BDF）与 **雅可比**
  （按算例声明 / 解析 / 稀疏差分 / 不用），外加 **rtol** 输入框；
- 首项"按算例声明"映射为空字符串 → **不加任何 flag**，界面不会偷偷覆盖算例；
- `--fast` 与显式选择同时出现时按 CLI 的既定顺序（预设打底、显式优先）。

界面只做翻译，不写算例、不解析几何、不 import 求解器：`_solver_flags()` 把控件状态变成参数列表，
`_argv_single()` 拼进 argv，其余照旧走子进程。

### 三、验证

- 新增 `tests/test_ui_run_solver_flags.py`（6 项）：标签与取值索引对齐、CLI 仍有这四个 flag、
  默认行**不产生任何 flag**、勾选预设只产生 `--fast`、预设与显式覆盖并存时的参数顺序、
  以及"该屏源码里没有 `write_text`/`json.dump`/`replace(`"——不碰算例文件这条要能被测试证明；
- `pytest` **435 passed**（429 + 6）；
- 截图：`reports/` 下 ② 运行屏（可再生产物）。

## 2026-10-22 界面可读性二轮（第 32 轮）

**触发**：`@UI 设计师 @UI 视觉验收设计师 @软件架构师` 三位专家评审，视觉验收给出 **HOLD，7 屏全 FAIL**（② 阻断级），并逐条给出触发条件与证据。处置见 `docs/UI_READABILITY_2026-10-22.md` 的"二轮"一节。

**会读错数/找不到的三处（本轮全部修掉）**：
1. ② 运行屏四个按钮在 1280×820 上 `mapped=0`，"启动单次运行"根本点不到 —— 左卡改 `grid`，列表是唯一弹性行。
2. ⑤ 评价屏限值条画布比列宽宽 30 px，`3896 / 4.979e+04` 被裁成 `3896 / 4.97`，看起来像 4.97 —— 画布宽度交给布局，数值改由 `fmt.fmt_pair` 与限值同量级渲染（`3.896 / 49.79 kN`），并补 80% 预警刻度与"超限"字样。
3. ① 算例表哈希列被切掉两个字符 —— 六列改四列，哈希移入右侧契约卡；`ListPanel` 加横向滚动与 `minwidth`。

**两处状态缺陷**：`app._job_done` 是单槽，两个异步作业会互相覆盖回调（频谱屏因此抛 `AttributeError: 'Series' object has no attribute 'column'` 并静默显示上一次的数）；`tests/conftest.py` 在语料缺失时把**全部**用例 skip，连架构规则都不跑 —— 闸门"绿得虚假"。前者改 `_job_handlers[job_id]`，后者只 skip 真正读语料的模块。

**新增**：`src/velch/ui/fmt.py`（全局唯一的数字格式出口，支持 SI 前缀、缺测显示 `—`、`fmt_pair` 保证两侧同量级）、`tests/test_ui_readability.py`（19 项）。

**验证**：`pytest` **473 passed**；`--selftest` 7 屏 0 报错；`scripts/auto_accept.py --skip-run` → **ACCEPT**。

## 2026-10-22 代码审查后的健壮性修复（第 33 轮）

审查（`@代码审查工程师`）给出 7 条确定缺陷，全部落在"界面会骗人"这一类，而不是算错物理：

- **F1 事件泵永久停摆**：`VelchUI._pump` 的 `after(100, ...)` 在 `try` 之外，任一 handler 抛异常即
  停止轮询——日志冻结、worker 结果不再投递、运行按钮永久灰、子进程继续跑。改为逐事件 `except`
  + `finally` 重排，并新增 `report_problem()` 与 `root.report_callback_exception` 把异常送进状态栏。
- **F2 失败分支不清屏**：评价屏失败时旧 `LimitBar`（可能红色"超限"）与轮轴表留在屏上；频谱屏失败时
  留着上一次的柱子、表格与五张 KPI 卡，且 caption 不含运行名。新增 `_clear_limits()` / `_clear_view()`，
  频谱 caption 加运行名。
- **F3 结果乱序**：快速连点运行下拉时，慢请求覆盖快请求。每屏加 `_token`，过期结果直接丢弃。
- **F4 子进程归属**：`spawn` 单槽 + `on_exit` 按当前槽位 owner 路由 → 取消作用于错误进程。`exit` 事件
  携带作业对象，`on_exit(job, ...)` 按 `job.owner` 路由；`spawn` 忙时返回 `None`。
- **F5 NaN 限值条显示通过**：`isfinite` 判断 → 灰条 + "无有效值"。
- **F6 过滤后选择悬空**：`_apply_filter()` 后选中首行（或清空卡片），避免"派生的是看不见的那一行"。
- **F7 `peak_force_kn` 实为牛顿**：改名 `peak_force_n`，去掉调用点的 `/1000`。
- **F8/F9**：`fmt_percent(signed=True)`、静态轴重卡改 kN；删掉过期元组注解与死代码 `Chart._stack_groups`。

新增 `tests/test_ui_robustness.py`（19 项，含一条真建 Tk 窗口验证"坏事件之后队列继续被消费"的用例）。
验证：`pytest` **473 passed in 17.1 s**、`--selftest` 7 屏 0 报错、`scripts/auto_accept.py` ACCEPT。

## 第 37 轮 2026-10-22 深夜：0.4.2 发布（可读性四项 + Simpack 导入）

- 版本 0.4.2：`src/velch/__init__.py` 与 `packaging/version_info.txt` 四处字面量同步（`filevers`/`prodvers`/`FileVersion`/`ProductVersion`）。
- 重建 onedir 包：`dist_installer/Velch/` 195.5 MB / **1618 文件**，`Velch-0.4.2-win64.zip` **88.97 MB**。
- 打包冒烟 5 步 **ACCEPT**：`selftest`（7 屏 / 424 控件 / 3550 行 / 0 屏报错 / 日志管道 3 行 exit 0）、`cli-run`（`numerically_checked` + 七门）、`missing-corpus`（退出码 1、提到 `VELCH_DATA_ROOT` 与标记文件、无 traceback）、`unicode-path`（中文+空格路径）、`readonly-install`（SKIP，写明手工步骤）。
- `pytest` **492 passed, 1 skipped**（skip = 真实 Simpack 模型不在时跳过的那条）。
- 新增 `docs/RELEASE_NOTES_0.4.2.md`：装什么、两个 exe 分工、界面四项对照表、Simpack 三条命令与实测数字、验证清单、以及"仍然没有的"五项。
- 标签 `v0.4.2`。

## 第 36 轮 2026-10-22 深夜：读 Simpack 模型算一个算例

- 新增 `src/velch/simpack_case.py` 与 `velch simpack-case` 子命令：几何（里程布置、型面文件）从
  Simpack catalog 来，物理从模板算例来，并写 `<算例>.simpack.json` 溯源旁挂。
- 实测真实模型 `CRH380A_M_Wheelset.spck`：238 条型面引用 / 233 个唯一 PRR / 0 缺失 / 10 处同里程
  多表面 / 里程 0–150 m / `geometry_readable = true`。
- `--keep-profiles`（只导入里程布置）：跑通，`numerically_checked`、七门全 true、静载
  59 680.5769 N、侵入 65.47 µm、BDF nfev 116。
- 默认模式（导入模型自己的断面）：静平衡失败 `the heaviest carries 119316.3 N`（单侧承担两倍载荷）
  —— 原因是同里程多表面 + 横向布置未导入，属已知未做的下一层，已写进文档而不是当成 bug 修。
- 派生规矩：里程不位移（越界直接拒绝）、四种错误一律 `SimpackCaseError` 且不落半个算例。
- 新增 `tests/test_simpack_case.py`（10 项，真实模型未设置时 skip）；`pytest` **492 passed, 1 skipped**。
- 文档：新增 `docs/SIMPACK_IMPORT_2026-10-22.md`。

## 第 35 轮 2026-10-22 夜间：可读性剩余四项（对比度/斑马纹/焦点环/字号）

按视觉验收的清单做完最后四项，全部带可测判据：

- **对比度**：`BORDER_CONTROL`/`SURFACE` 1.37→**3.99:1**、`/BG` 1.83→**4.32:1**（WCAG 1.4.11 的 3:1）；`contrast_violations()` 拆成文本 4.5:1 / 控件边界 3:1 / 装饰豁免三类，`BORDER`/`BG` 1.48:1 属装饰，不再当缺陷。
- **斑马纹**：`ListPanel.restripe()` 用 `theme.ROW_ALT` 每两行一条，五个建表的屏在填充后各调一次；`INK` 14.03:1、`INK_MUTED` 6.92:1 仍达标。
- **焦点环**：1→2 px，`theme.FOCUS_RING` 单一来源。
- **字号阶梯**：micro 10 / tiny 11 / body 12 / body_lg 13 / section 15 / title 20 / display 26，行高 28；`tests/test_ui_scale.py` 把下界钉住（body ≥ 12、micro ≥ 10、title ≥ 20）。

抬字号后暴露的两处新问题，都用"减法"而不是"再压字号"解决：① 算例表四列 476 px 放不下 → 砍掉"起始里程 m"（值仍在右侧契约卡，有断言保证），三列 396 px；② 横向滚动条常驻像"右边还有内容" → `_sync_scrollbars()` 按 `<Configure>` 比较列最小宽与控件宽，放得下就隐藏。

验证：`pytest` **492 passed, 1 skipped**、`velch.ui --selftest` 7 屏 / 424 控件 / **0 屏报错**。

## 第 34 轮 · 0.4.1 安装包（2026-10-22 22:30）

- 包装：`pyproject.toml` 版本改为单一事实源（`dynamic` + `attr = "velch.__version__"`）、
  补 `velch-ui`/`velch-agent` 入口；新增 `packaging/`（`Velch.spec`、`entry_console.py`、
  `entry_window.py`、`version_info.txt`、`build_installer.py`、`smoke_test.py`）。
- 两个 exe：`Velch.exe`（窗口）+ `velch-cli.exe`（控制台）。控制台**不能**叫 `velch.exe`：
  Windows 文件名大小写不敏感，会与 `Velch.exe` 在同一个 COLLECT 里相撞、只剩一个（实测）。
- 冻结构建四个坑（都写进 spec 注释）：Anaconda 里 PyInstaller 会拖进 PyQt5→torch（要 EXCLUDES）；
  `distutils` 不能排除（pre-safe-import hook 冲突）；屏是动态 import 的必须 `collect_submodules("velch")`；
  PIL 不能排除（matplotlib 三维路径要它）。
- 数据根安装态：`data_root` 新增 frozen 安装根、`%LOCALAPPDATA%` 标记、`hint()`；① 算例屏空表给原因。
- 入口点统一：`velch/launcher.py`（`launcher_argv` / `worker_argv` / `console_executable` /
  `child_environment`），六处 `sys.executable` 全部收敛，测试禁止新出现（白名单三处）。
- 修 B017–B020（见 `BUGS.md`）：冻结输出改 UTF-8、窗口版无 stdout、日志管道探针误报、doctor 提示。
- 验证：`pytest` **492 passed, 1 skipped**；`smoke_test.py` **ACCEPT**；产物 `Velch-0.4.1-win64.zip` 88.9 MB。
- 新文档：`docs/RELEASE_NOTES_0.4.1.md`、`docs/PACKAGING_2026-10-22.md`（含构建命令与 5 步冒烟）。

## 第 38 轮（2026-10-22 夜间）：读模型自己的断面能跑了，跑不了时给准话

**问题**：`simpack-case` 的默认模式（型面取自模型）在转辙区窗口必然失败，报的是一句静平衡偏载
（`the lightest contact patch carries only 0.0 N while the heaviest carries 119357.0 N`），
既不说是几何问题，也不说差多少；而 82 m 窗口其实能跑通，用户无从判断"该换窗口还是该怀疑模型"。

**做法**（`Velch/src/velch/simpack_case.py`、`Velch/src/velch/cli.py`）：

1. 新增 `_surface_delta_mm()`：按算例的横向口径（`y_sign × y_offset_m`、`z_sign`）逐站求轨顶高度，
   与模板同里程同位置相减，返回"窗口内最大下沉量与所在里程"；量不到时返回 `None`。
2. **只在行驶窗口上量**（`x_start − 2 m` 到 `x_start + 车速 × 时长 + 2 m`），否则 82 m 起跑的算例会被
   26 m 外 15.85 mm 的转辙器断面否决。
3. 两级阈值：`SURFACE_DROP_WARN_MM = 3.0` 只记 `surface_drop_warning`；`--max-surface-drop`（默认 **8.0 mm**）
   才拒绝。之所以不是一个数：**5.18 mm 实测能坐、11.91 mm 实测不能**，单一阈值必然误伤一边。
4. 旁挂 `*.simpack.json` 增 `surface_delta_mm{max_abs, at_m, measured_stations, ride_window_m}`、
   `surface_drop_allowed`、`surface_drop_warning`。
5. 里程不再整体平移（早期实现把模型里程挪到 `--x-start`，右轨只剩 13.5–163.5 m，首个车轮位置即越界）；
   越界改为在派生时报 `… leaves the model's coverage …`。
6. `--keep-profiles`：只用模型的里程布置、型面沿用模板，旁挂 `profiles_from: "template"`。

**实测**

| 起点 | 行驶窗口内最大下沉 | 结果 |
|---|---|---|
| 60.0 m | 0.09 mm @ 58.317 m | 断面几乎对齐，**静平衡仍失败**（轻 0.0 N / 重 119 315 N） |
| 65.0 / 70.0 m | 0.01 / −0.01 mm | 同上：断面平了不等于能坐住 |
| 75.0 / 80.0 m | **11.24 mm** @ 79.867 m | 被拒（> 8 mm），消息含下沉量/里程/阈值 |
| 82.0 m | 5.18 mm @ 80.004 m | 构建成功 + warning；`run-vehicle --fast` → `numerically_checked`、七门全 true、八接触峰值 60.59/66.85/63.55/60.56/60.79/68.52/71.89/60.75 kN、最大侵入 88.63 µm、BDF `nfev 1094` |
| 60.0 m + `--keep-profiles` | 不适用（型面用模板） | 跑通，`max_penetration_m = 6.546612428690518e-05`、每接触峰值 **59 680.5768587 N**（冻结静载门）、`nfev 116` |

**这一轮推翻了自己一个想当然的因果**：60–70 m 三档的冠部高度与模板差不到 0.1 mm，却仍然坐不住——
转辙区的断面**形状**（承载面宽度、圆角、轨距面位置）逐站都在变，"冠部对齐"因此是**必要但不充分**
条件。判据只负责把明显不可能的窗口挡在积分器之前，不承诺剩下的窗口一定跑得通。

**测试**：`Velch/tests/test_simpack_case.py` 10 项（既有）+ 新增 `Velch/tests/test_simpack_surface_drop.py`
5 项（超限拒绝且消息带四个数、3–8 mm 构建成功并写 warning、≤3 mm 不吵、`allow_surface_drop` 放行、
量不到时记 `None` 视为未知）。全仓 **497 passed, 1 skipped**。

**教训**：几何差异必须在派生阶段量出来并说出数值，等到积分器报偏载就太晚了；而"量不到"必须
与"没有差异"分开记录——否则默认值会替用户做出一个它没有证据的判断。

**文档**：`docs/SIMPACK_IMPORT_2026-10-22.md` 增第五节"断面下沉判据"（量法、两个实测边界、两级阈值表、
旁挂字段样例、以及"这一层也不导入物理"）。

## 第 39 轮（2026-10-22 深夜）：拒绝的时候给一个能用的里程

**问题**：断面下沉判据拒绝窗口时只说"换个窗口"，用户并不知道往哪换——尤其模型有 236 个站位、
可起点是连续量。

**做法**（`Velch/src/velch/simpack_case.py` 新增 `suggest_window()` 与 `_advice()`）：

1. 遍历模型自己的站位里程作为候选起点，只保留 `x_start + 车速 × 时长 ≤ 模型覆盖上界` 的；
2. 对每个候选按行驶窗口（`±2 m` 余量）量一次下沉，取不超过 `SURFACE_DROP_WARN_MM`（3 mm）的；
3. 在合格的候选里选**离用户请求最近**的那个，把 `起点 + 最差下沉` 写进拒绝消息；
4. 一个都没有时明说 `No window in this model measures within 3 mm of the template`。

实测（75 m 起跑被拒）：`The nearest start that measures within 3 mm is 72.7 m (worst 1.24 mm).`

**它只是建议**：不会自动替换用户给的起点，也不会承诺"跑得通"——72.7 m 的冠部量得很干净，
但 60–70 m 三档同样干净却坐不住（O008）。

**测试**：`Velch/tests/test_simpack_window_advice.py` 6 项（命名合格窗口、取最近、无候选时承认、
越界窗口不推荐、消息带里程、无解时的措辞）。全仓 **503 passed, 1 skipped**。
| docs/RELEASE_NOTES_0.4.4.md | 0.4.4 唯一改动：被拒时给一个具体里程；为什么不承诺换过去就能跑 | ✅ 当前发布物 |

## 第 40 轮：Simpack 断面——两次量错，一次改对

起因是上一轮留下的那个反直觉事实：**只差 0.09 mm 的 60 m 窗口坐不住，差 5.18 mm 的 82 m 窗口反而跑通**。
追下去发现不是物理问题，是我自己量错了两次：

1. **量的位置在轨顶侧面上。** 旧代码在固定横向 `y = 0.753 m` 取轨顶高度，而模板断面载入后的测量包络是
   `y ∈ [−0.790, −0.717] m`、冠部在 `−0.7896 m`：`0.753` 落在 flank 上，比冠部高 **+29.86 mm**。
   于是"下沉 5.18 / 11.24 mm"记录的其实是**冠部横向漂移 × 侧面坡度**。按冠部重测：226 个右轨站位冠部
   高度差 **0.000–0.155 mm**，真正在动的是**冠部横向位置**（0.714–0.868 m，最多漂移 **103 mm**）。
2. **行驶窗口只向后看了 2 m。** 后轴在 `x_start` 之后 **10 m**，旧窗口里没有后轴要压的断面 → 导入的站位表
   缺了后轴下面那段 → 静平衡必然报"单侧脱空、最重接触 119 315 N"。窗口改成整车足迹
   `[x_start − 10, x_start + 车速×时长]` 后，**同一个 60 m 窗口能坐也能跑**。

### 改法（`simpack_case.py` / `cli.py`）

| 项 | 之前 | 现在 |
|---|---|---|
| 几何量 | `_surface_delta_mm`：固定横向位置减模板 | `_crown_delta_mm`：逐站 `argmin(z)` 得冠部高度与横向位置 |
| 阈值 | 3 mm 警告 / 8 mm **拒绝** | `CROWN_WARN_MM = 0.5`，**只报告不拒绝** |
| 窗口 | `[x_start−2, +2]` | `[x_start − 10, x_start + 车速×时长]`（`_axle_reach_m`） |
| 裁决 | 几何阈值 | `seat_report()` 真跑一次静平衡；坐不住 → 退出码 2 + 原因/冠部差/足迹 + 不推荐窗口的建议 |
| 开关 | `--allow-surface-drop` / `--max-surface-drop` / `--lateral-m` | `--no-seat-check`（跳过静平衡裁决） |
| schema | `velch-simpack-case-v1` | `velch-simpack-case-v2`，旁挂 `crown_delta_mm` / `crown_warning` |

### 实测

| 窗口 | `crown_delta_mm.max_abs` | 足迹 | `seats` | 结果 |
|---|---|---|---|---|
| 60 m | 0.155 mm | 50.0–64.861 m | **true** | `numerically_checked`、`nfev 116`、最大侵入 **65.466 µm**、`axle1_right 59.68 kN` |
| 82 m | 0.155 mm | 80.0–88.861 m | true | `numerically_checked`、`nfev 1094`、最大侵入 88.63 µm、八接触 60.59–71.89 kN |

60 m 那次的最大侵入与 `axle1_right` 恰好是冻结静载门（65.47 µm / 59 680.5769 N），说明导入链路没动物理。

### 顺带

- 删 `tests/test_simpack_surface_drop.py`（随阈值一起废），新增 `tests/test_simpack_crown.py`（7 项，含
  "冠部是最低点而不是固定横向位置"与"大冠部差只报告不拒绝"）。
- 重写 `tests/test_simpack_window_advice.py`（7 项）：核心用例是"起步 65 m 的后轴压到 55 m 的台阶，因此
  推荐 80 m"——这条正是 B022 的回归。
- `docs/SIMPACK_IMPORT_2026-10-22.md` 第五节加"更正"块并给旧表加注；`docs/BUGS.md` 记 **B022**、**B023**、
  重写 B021、**撤销 O008**（改为"冠部横移未导入"）。
- `pytest` **506 passed, 1 skipped**。

## 第 41 轮：界面里也能读 Simpack 模型

命令行能做的 `simpack-case`，现在在 ① 算例屏里点一下也能做，而且做的是**同一条命令**。

- 新增 `Velch/src/velch/ui/simpack_dialog.py`（`SimpackImportDialog`）：断面目录 JSON、模板算例、
  起点/时长/采样站数、侧别/轨别、`型面沿用模板`（`--keep-profiles`）、`派生后裁决`（默认开，
  关掉即 `--no-seat-check`）。
- ① 算例屏新增按钮「从 Simpack 模型派生算例…」，默认把**当前选中的算例**当模板。
- 命令由 `velch.launcher.launcher_argv()` 组装 → 冻结版走 `velch-cli.exe`，源码版走
  `[python, -X, utf8, -m, velch, ...]`；界面**不 import 前向求解栈**（有测试盯着）。
- 失败不清零：退出码 2（静平衡坐不住）时状态行写「静平衡没坐住…」，**不刷新列表**、不把拒绝当成功。
- 新增 `Velch/tests/test_ui_simpack_dialog.py`（8 项）：命令与 CLI 一致（`simpack-case` + 各参数）、
  两个开关是 opt-in、缺 catalog 给可读错误而不是 traceback、拒绝不触发 `on_done`、成功把文件交回、
  报告解析能穿过噪声、状态行区分三种结局、对话框不 import 前向栈。
- 截图入库 `docs/images/ui_simpack_dialog.png`；`docs/SIMPACK_IMPORT` 新增第八节说明"界面 = 同一条命令"。
- `pytest` **514 passed, 1 skipped**。

## 第 42 轮：把"按钮被裁掉"从靠眼睛改成靠量

上一轮之后我们仍在靠截图判断有没有被裁。这一轮补上了**量**，它一上线就抓出五个被裁的控件——
其中两个是**宽度 1 px**，也就是"在界面里存在、但谁也点不到"。

### 量的方法（`tests/test_ui_layout.py`，4 项）

- 真建窗口、逐屏 `show()`，遍历每个 `ttk.Button`/`ttk.Checkbutton`，比较**分配宽度**与**它自己要求
  的宽度**（容差 2 px，Tk 会有取整）；
- 在 **100 % 与 130 %** 两档字号各量一次，7 个屏算一遍；
- 另有两条守卫：①每屏必须建出控件且 `selftest_detail()` 非空；②**任何屏只要文本里出现
  「该屏加载失败」就算失败**——⑦ 三维屏曾带着 `KeyError: 0` 上线，而 `Screen.reload()` 把异常吞成
  一句提示，文件级测试全绿。

### 量出来的真实缺陷（全部已修）

1. **Windows 的 `vista` 主题要求按钮最少 11 个字符宽**（`TButton -width` 默认 `-11`）。12 px 中文字面下
   这就是 **约 153 px/按钮**：六键工具栏要 918 px，最后两个键各分到 **1 px**。修法：`BUTTON_MIN_CHARS
   = -3` 写进 `.`/四个按钮样式，按钮宽度改由标签决定（下限约 34 px，仍满足 28 px 的触控底线）。
2. ③ 时程工具栏六键 → 拆两行（缩放/导出在上，平移在下，标签从 `←/→` 改为 `◀ 左移 / 右移 ▶`）。
3. ③ 通道预设四个键挤在 320 px 列里（「侵入量」差 4 px）→ 改 **两行两列**。
4. ⑦ 三维四个视角键 → 合并成一个 **视角下拉框**（重画 / 视角 / PNG 三个控件）。
5. ① 新增的「从 Simpack 模型派生算例…」放进导航行时被挤成 1 px → 与「在运行屏打开」「刷新列表」
   三等分，文案缩为「Simpack 导入」。
6. ② 的「快速预设（BDF + 解析雅可比 + rtol 1e-4）」需要 434 px 而只分到 375 px → 文案改
   「快速预设（隐式 BDF + 解析）」，rtol 细节留在下方提示行。

### 顺带

- `pytest` **517 passed, 2 skipped**；`--selftest` 7 屏 / 0 报错 / 退出码 0。
- 截图复核：130 % 下 ⑦ 只占三个控件、模型填满画布；100 % 下 ①②③ 无裁切。

## 第 43 轮：把三条"已知未修"改成"已量、已修"

缺陷账本里的 O 项不是无处可去，是没排上。这一轮清掉三条，其中一条的结论是**当初量错了对象**。

### O002 两个入口拿不同的分母评同一条运行（已修）

`Velch/src/velch/ui/screen_assess.py` 自己用 `store.assess(run, 静态轴重)` 算三项限值，而「运行 velch
assess」按钮起 CLI 时**没带**轴重——同一屏上，卡片用你填的数算，日志用自动值算，轮重减载率可能一个
判 PASS 一个判超限。CLI 的 flag 是 `--static-axle-load-n`（不是 `--static-axle-load`），现在：填正数就
`argv + ["--static-axle-load-n", f"{typed:g}"]`，留空则不加（CLI 自己取自动值，语义不变）。
`tests/test_ui_robustness.py` 新增一项源码级对照：读的必须是同一个 `self.load_var.get()`。

### O004 读不到运行目录时，三维屏摆出"首次运行"的样子（已修）

`load_runs()` 原来 `except Exception: self.runs = []`。语料根写错、权限不足、目录写了一半——
在这屏上全长得像"还没有运行"。现在状态栏报 `读不到运行目录：<类型>: <消息>（<路径>）`。

### O007 对比度这条是量错了对象（撤销）

原条目说 `BORDER/SURFACE` 1.37:1、`BORDER_STRONG` 1.83:1 低于 WCAG 3:1。这两个 token 在
`theme.py` 里本来就注明是**装饰**（卡片间细线、悬停底色），而 1.4.11 管的是**控制边界与状态**。实测：

| 用途 | token | 对比度 | 判定（1.4.11 3:1） |
|---|---|---|---|
| 输入框/表格边界 | `BORDER_CONTROL` on `RAISED`/`SURFACE`/`BG` | 3.61 / 3.99 / 4.32 | 达标 |
| 焦点环 | `ACCENT` on `RAISED`/`SURFACE`/`BG` | 7.89 / 8.71 / 9.43 | 达标 |
| 状态色 | `WARN`/`FAIL`/`PASS` on `SURFACE` | 7.88 / 6.26 / 7.79 | 达标 |
| 卡片间细线 | `BORDER` on `BG` | 1.48 | 装饰，豁免 |

为了让这条结论不再靠人记：`theme.NON_TEXT_PAIRS` 扩到 9 对（含 `ACCENT`、`WARN/FAIL/PASS`），
`contrast_violations()` 按 3:1 机器判定；焦点环粗细提成 `FOCUS_THICKNESS = 2` 并被
`tests/test_ui_scale.py` 钉住（1 px 在 130 % 下会消失）。

### 验证

`pytest` **520 passed, 1 skipped**（skip 仍是"真实 Simpack 模型在时才跑"那条）。

### 同一轮：只读安装从 SKIP 变成实测

`packaging/smoke_test.py` 的第五步原来恒为 `SKIP`（理由：要复制 195 MB 到 `C:\Program Files`）。
现在改为 **`install-dir-untouched`**：记下安装树的"路径 → 字节数"签名，跑一次冻结自检和一次
`run-vehicle --fast`，再记一次；**任何新增、删除、改大小都算失败**。探测器本身也验证过（写一个
新文件、改一个文件的长度，两处都报出来）。

它证明的是"程序不往自己脚下写"，这正是锁死目录里最容易踩的坑（把配置写在 exe 旁边）。它**不能**
证明 ACL 拒绝时给出的是人话——那仍是 `docs/PACKAGING_2026-10-22.md` 末尾的四步手工清单。

冒烟现在 **5 步全跑、0 跳过**。

## 第 44 轮：横向布置不是顺手能补的一活

O008 剩下的那一层（冠部横向漂移 103 mm 未导入）看起来像"再写个 delta 就行"。这一轮真做了，然后被
自己的量测挡下来——**这才是它该有的结局**。

- 新增 `--import-lateral`：每个站位的冠部横向位置写进该站自己的 `y_offset_m`，侧挂记
  `crown_lateral_m`（最大位移 / 里程 / 站位数）。
- 实测（80–90 m）：右轨 38 个站位需要 **−73.78 … +102.99 mm** 的修正；**左轨 0 个站位**，没有数据。
- 只改一侧 = 改轨距：第一次实跑 `seats: false`，一侧四个接触全脱空
  （`0.0 N` vs `119330.9 N`）。
- 因此加 `LATERAL_GAUGE_LIMIT_MM = 5.0`：`build_case` 先量两侧差，超限抛错并报出
  `+103.0 mm at 80.911 m (this side +103.0 mm, other side +0.0 mm)`，指向 `--allow-gauge-change`
  （放行则侧挂留 `lateral_gauge_mm`）。
- 两条测试钉住：超限必拒且消息含 `103.0 mm` 与 `--allow-gauge-change`、拒绝时不写算例文件；放行时
  侧挂有 `lateral_gauge_mm`、算例里 `y_offset_from == "simpack crown"` 且偏移确实动了。
- 仍未解决（写进 O008）：同一里程上有两个表面（10 处 `coincident_stations`），"冠部属于基本轨还是
  尖轨"catalog 不回答——横向布置属**双体交接**，不是单侧修正。

`pytest` **522 passed, 1 skipped**。

## 第 45 轮：没有语料的那条路径，三个按钮被自己挤扁

打包版首启时语料往往没挂，① 算例屏会显示一段很长的"我去哪儿找过"提示。这段提示是个
**没有换行的 `tk.Label`**，`pack` 让它索取整句话的宽度——它索要到了，右侧卡片被压窄到
按钮文字放不下，`在「运行」屏打开` 只剩 94 px（需要 152 px），五个按钮全部被裁。

**为什么一直没发现**：所有界面测试都在"语料在"的环境里跑，那条分支根本不会显示；而布局闸门
（第 42 轮）也只在同一套环境下量过一次。这一轮把闸门扩成**两种环境各量一遍**：

- `VELCH_DATA_ROOT=F:\velch_tmp\no_corpus`（空目录）→ 之前 **3 failed / 385 passed / 141 skipped**，
  现在 **389 passed / 140 skipped / 0 failed**；
- 正常语料 → **528 passed / 1 skipped**。

### 修的两处

1. `Velch/src/velch/ui/screen_cases.py` 的 `problem_label` 加 `wraplength=int(360 * theme.SCALE)`
   并接 `wrap_with(self.problem_label, body, reserve=16)`——提示按卡片宽度折行，不再索取整句宽度。
2. 同一屏导航行的 `在「运行」屏打开` 改 `在运行屏打开`（130 % 下三等分只给 174 px，需 184 px）。

### 顺带把"标记"变成声明

`tests/conftest.py` 原来靠**扫源码文本**判断某模块是否需要语料。文本里出现 `case_dir(` 就
整模块跳过——既会漏（间接读语料的模块照跑照炸），也会误（文档字符串提到 `VALIDATION_DIR` 就跳过）。
现在模块显式声明 `pytestmark = pytest.mark.corpus`（12 个模块已加），文本扫描只作**遗漏兜底**；
`tests/test_corpus_marker.py` 断言"扫描会跳的模块必须带标记"，漂移会先在 CI 暴露。标记已在
`pyproject.toml` 的 `markers` 里注册，不再有 `PytestUnknownMarkWarning`。

同时把 O003 收尾：CSV 列不再"默默猜"，选择后在状态栏报出选中的里程列/力列，并报**还有几个候选**、
可下拉改；`x` 这种单字母 token 只匹配 `x` / `x_m` / `x.…`，不会把 `max_force` 抢成里程列。

### 补：提示本身被挤出卡片

把空态提示挪到表格**上方**后才真正可见——原先它排在表格下面，卡片高度不够时父容器直接把它裁掉，
截图里只剩最后一行。现在五行提示（查过哪些位置、怎么设置标记、标记 JSON 示例）全部在屏上，
表格让出空间。凭据：\docs/images/ui_empty_corpus.png\；无语料套件 390 passed / 139 skipped。

## 第 46 轮：⑦ 屏把接触斑画到轨面上（O006 关闭）

③④ 能读出力，⑤ 能判定，但"这个 170 kN 落在哪一段钢轨上"只能靠想象。这一轮把
`history.csv` 里记录的接触状态画到三维视图上。

### 画的是什么、依据是什么

- 位置：**车轮正下方**（轮对的 `y_m`/`z_m` + 车轮自身 `lateral_offset_m` ±0.7465 m），
  高度取踏面最低点再下压一个侵入量。
- 大小：圆环半径 `sqrt(2Rδ)`——把半径 R 的轮圆下沉 δ 得到的弦长，`R=0.43 m`、`δ≈65 µm`
  时约 **7.5 mm**。这是几何，不是 Hertz 解，屏上注记写明。
- 颜色：按该接触承载的法向力，绿 <80 kN、黄 <120 kN、红 ≥120 kN（与限值条同一套 token）。
- 数值：每个接触标一个整数 kN，读的就是 `history.csv` 的 `axleN_side_normal_n`。

### 为什么不是"求解器重算一遍"

架构规则禁止 UI import 求解栈（`contact`/`vehicle_solver`/`jacobian`）。所以视图**不重跑接触搜索**，
只消费已记录的通道——好处是图与 ⑤ 屏的表格不可能互相矛盾，代价是它只能显示算过的帧。
`tests/test_ui_model3d.py` 里有源码级守卫：`screen_model3d` 里不得出现那三个名字。

### 一个必须记下来的量测错误

第一版按接触通道的 `axleN_side_y_m`/`_z_m` 定位，结果**八个斑全叠在轨道中心线**上——实测量到
`y_m ≈ 0`、`z_m ≈ −1.2 mm`，那是相对量而不是绝对位置。改用轮对状态 + 车轮横向偏置后，
八个斑分别落在 ±0.7465 m，与车轮对齐。

### 一个看不见但真实的问题

7 mm 的圆环在 1.2 m 视窗里几乎不可见。**没有放大它**（那会谎报接触斑尺寸），而是加了一根
**20 mm 的竖直指示杆**，注记里写明"杆是指示杆、不是斑高"。

### 证据

- `pytest` **533 passed, 1 skipped**；`--selftest` 7 屏 0 报错
- 截图 `docs/images/ui_contacts3d.png`（帧 716/2401、t=0.3575 s、`out_full12_cap05`）：
  `4 位右 171 kN` 显示为红色，其余六个约 60 kN 为绿色
- 新增 5 项测试：力与侵入取自记录、半径 = sqrt(2Rδ)、八个斑落在各轮下方、非活动接触不画、
  颜色阈值与限值条一致、源码不 import 求解栈

## 第 47 轮：O008 定性——模型只有一侧断面表

横向导入被拒不是缺一个开关。数过 catalog 之后（右轨 236 站 / 233 个 PRR，左轨 **2** 站且都是基准
`Profile_Mileage_JBG.prr`），结论是**这个模型只在一条轨上定义了变断面**，所以"两侧一起导入"无从做起，
单侧导入就是改轨距——闸门拒绝是正确行为。

代码改动只有一处，但把死路变成可读的话：`_gauge_implication()` 增加 `other_side_stations`，
拒绝消息在对方侧站数 <3 时改为

```
This model defines only 2 station(s) on the left rail, so importing both sides is not possible
from it -- use --keep-profiles ... or supply a model whose two rails both carry section tables.
```

旁挂 `lateral_gauge_mm.other_side_stations` 让脚本能区分"不对称模型"与"调用方少传了一侧"。
新增 1 项测试（右 13 站 / 左 2 站的合成 catalog，断言消息含 `defines only 2 station(s) on the left rail`
与 `--keep-profiles`）。`pytest` **533 passed, 2 skipped**。

## 第 48 轮：⑤ 的第二半——与 Simpack 的定量对照（只描述不调参）

目标里唯一还没有证据链的一步。做法：从 Simpack 结果 `350.mat`（HDF5，sha256 见报告）读出
`SRS_RWT_WS/ch_001 SumQ`（前轮对垂向支反力之和）与 `ch_003 s`（里程），与已归档的
`out_full12_cap05` 的 `axle1_left_normal_n + axle1_right_normal_n` 在 **79.0–138.5 m** 重叠段、
0.05 m 等距网格上逐点比较。

六条读数：均值差 −0.97 kN（0.8%）、峰值 194.29 对 136.29 kN（**差 58 kN，同在 80 m 道岔区**）、
整段差值 rms 4.57 kN 而单点最大偏差 −66.0 kN（**不是整体偏移，是尖峰**）、三个频带 0.62×/0.31×/0.74×
（越往高频差得越多）、允许平移时最优位移只有 +0.2 m（**里程轴配准正确**）、主导频率 31.65 对 37.19 Hz。

两处方法学修正都记在报告里：①空域 FFT 的"Hz"要先乘速度，改成直接用两侧各自的时间轴
（都是 0.5 ms 采样）；②频带 rms 必须走 Parseval（首版算出 118 kN 的"30–60 Hz rms"，超过信号
自身的 4.8 kN，一眼就是错的）。

产出 `docs/SIMPACK_COMPARE_2026-10-23.md`：出处表（含 sha256）、数字表、六条读数、**这页不能证明什么**
（不能证明谁对；不是同工况验证；不构成标定）。`pytest` 534 passed / 1 skipped。

## 第 49 轮：文档索引从"42 篇提到过"变成"73 篇全覆盖 + 测试看守"

`AGENTS.md` 把 `CHANGELOG_DOCS.md` 称作单一入口。实际量了一下：**74 篇文档里只有 42 篇被这个名字
提到**，其余 32 篇（`CONTACT_*`、`DIVERGING_ROUTE`、`MEASURED_VALIDATION`、`RACK_CASE_DATA_CONTRACT`
等）在索引里根本不存在。手写清单必然漂移，所以改成生成 + 校验：

- `.tmp/gen_docs_index.py` 在 `## 第 81 轮：柔性轮对从 STEP 做到振型文件，论文表 2-3 只用来核对族序

§11 交的是框架（论文频率 + 空振型）。这一轮把**振型**做出来了，用的是用户给的 CRH3C 轮对 STEP 和本机 Abaqus 2022。

| 步骤 | 工具 | 产物 |
|---|---|---|
| ① 剖分 | gmsh 4.15.2，HXT + 二次四面体 + HighOrderOptimize=2 | 85 371 节点 / 43 291 C3D10 / 256 113 自由度，质量 1.023795 t |
| ② 自由模态 | `abaqus job=wheelset_modal cpus=4 interactive` | 6 刚体 + 35 弹性，首阶 76.79 Hz |
| ③ 踏面振型 | `abaqus python` + odbAccess | 41 阶 × 8 476 节点 |
| ④ 归并出货 | `scripts/wheelset_fe_modes.py` | `vehicles/modes/CRH3C_wheelset_fe.json`，33 阶 × 772 节点，1.75 MB |

**三次失败都不是调参问题**：拿 `getElements` 的连接关系喂 Abaqus，43 291 个单元全被判零/负体积（gmsh 的 C3D10 节点顺序与 Abaqus 不同，必须让 gmsh 自己写 INP）；`*SOLID SECTION` 要单元集而不是节点集；过盈配合按 96–105 mm 取半径取到了座面**倒角**（96.70 mm），`*TIE … ADJUST=YES` 把孔节点拖到轮平面外 95 mm，改成 `|r − 95.50| < 0.75` 后每侧 580/592 主面节点、789 从节点，20 mm 网格上 1537 个孔节点里 1541 个调整、只有 22 个绑不上（98.6%）。

**收敛性**：30 mm 首阶 75.71 / ND2 348.76 / ND3 961.0；20 mm 76.79 / 347.08–347.12 / 957.28–957.36（差 1.4%，取 20 mm）；15 mm 因个别 HXT 坏单元直接报 `The volume of 41 elements is zero, small, or negative`，不追。

**节径数是量出来的**：踏面环取 455–465 mm（第一次用"最大半径 − 6 mm"取到轮缘尖 485.77 mm），径向分量沿环做傅里叶分解取主阶次。**族序与节径和论文表 2-3 逐条对上**（含 ND2 四阶、ND3 四阶的族大小），但频率低 5–39%，车轮盘面类 0.61–0.71、轴弯曲类 0.82–0.95 —— 这张 CAD 车轮的辐板比论文那套刚性梁轴 + MASS21 软，**两者是不同结构**，所以表 2-3 只能核对振型归属，不能当频率标定目标。

出货时两个约束：FE 一族内频率差 0.04–0.08 Hz（0.01–0.1%，网格不对称）而 `ModeSet._pairs()` 要求严格简并，故按**族均值**报；只有 1748.90 Hz 那一阶因 40 阶请求截掉了兄弟而被丢弃（脚本会打印）。

新增 `tests/test_wheel_modes_fe.py` 8 项（格式、踏面振型非零、滚动半径 0.460、每阶行波都有配对且分裂 = ND×转数/秒、族大小、最低阶频率、截断族被拒、分裂用轮半径）。写测试时改正了三处自己的错：分裂断言差 2π（`ND×spin` vs `ND×n`）、`76.792` 直接与 `76.79` 相等比较、截断测试用 `index == 9` 过滤导致什么都没删（改成按频率选第一个匹配，并在删完后重编号、同步 shapes，才能测到配对规则本身）。

文档：`FLEXIBLE_WHEELSET_PORT_2026-10-24.md` 新增 **§12**（流水线、三次失败、收敛表、节径测量、与论文的对比表、出货约束、装进求解器后的样子、S8-2/S8-3 入口）。`pytest tests/test_wheel_modes_fe.py tests/test_wheel_modes.py` → 22 passed。

**还没有的**：模态块仍未与力耦合（车体、一系、接触力都没经 Φᵀ 映射，所以振型装上也激不起来，S8-2）；接触点仍在未变形踏面上找（S8-3）；阻尼比仍是论文的按节径取值。

## 第 82 轮：S8-2 —— 接触力终于推得动振型，顺带抓到一个 1000 倍的单位错

§12 交出了振型文件，但模态块仍只与自己耦合，第一版柔性算例的 `max |q| = 0.000e+00` 就是证据：不是数值稳，是没有输入。

| 新增 | 内容 |
|---|---|
| `src/velch/modal_coupling.py` | `TreadRing`（按 y 符号取一片车轮、量出环中心、胎面点核函数、`generalised_force`、`displacement`）+ `ModalContact`（side→ring、axle→偏移、`block()` 切片） |
| `vehicle_solver.evaluate()` | 每个接触斑在刚体力之后追加 `force[coupling.block(axle)] += coupling.generalised(...)`，法向/横向力按振型投影；左右侧用仓库既有约定（L = −0.75 m） |
| `tests/test_modal_coupling.py` | 11 项：单位分解、刚体平移传力、虚功 `Q·q == f·d(x)`、对力线性、块切片、无振型给路、m/kg 归一、接触力到得了模态坐标、刚性算例无耦合 |

**两条把权重写成判据**：权重和为 1（力不能被投影吃掉），且**同一套权重既算力也算位移**（否则虚功不闭合，而峰值力看不出来）。

**抓到的两个洞**：
1. 振型存在 **CAD 装配坐标系**里，原点不是轮对中心（这辆车轮环中心 x ≈ −1.2476 m）。接触点放 `x = 0` 时核函数落到 1.25 m 外，但 `weights` 仍归一化、`generalised_force` 仍非零——一切"看起来正常"。现在 `TreadRing.centre` 是量出来的，测试钉住接触点必须跟随环中心。
2. **Abaqus 用 mm/t，求解器用 m/kg**：odb 位移是 mm，Abaqus 归一化是 `Σ m_t·u_mm² = 1`，换到 SI 只剩 `1e-3`，出货须乘 `1/√1000`。修前实测 `max|φ| = 3.561`、5 ms 内胎面模态位移 **0.17 m**，而**力、七门、状态全部正常**（因为接触仍在未变形踏面上找，S8-3），是最难发现的一类错。修后 `max|φ| = 0.1126`、`max|q| = 3.555e-03`、胎面位移 **2.49e-04 m**（0.25 mm，与 65 µm 静侵入同量级），比值 31.5 ≈ √1000 与推导一致。

`pytest tests` → **783 passed, 1 skipped**。文档 `FLEXIBLE_WHEELSET_PORT_2026-10-24.md` 新增 §13（模块接口、接线点、两条单位洞、修前/修后对照表、11 项测试、S8-3 入口）。

**还没做的**：接触仍在未变形踏面上搜索（S8-3，也是"柔性轮对能改多少力"的答案所在）；纵向力未进模态；一系/重力未过 Φᵀ（缺轴座振型）；阻尼比仍是按节径取值。

## 第 83 轮：S8-3 —— 踏面变形进入侵入量，顺带证明那个"1.13 而不是 1.49"是我的分母错了

§13 之后模态块能被推动了，但接触仍在**未变形**踏面上搜索，所以振型再大也不改力。这一轮把深度接上。

| 改动 | 内容 |
|---|---|
| `vehicle_solver._deform_geometry()` | 取该轴模态块、该侧胎面环，用**与力投影同一组权重**读出接触点 z 位移，`penetration_m -= move_z`、`wheel_z_m += move_z`；非有限值报 `SimulationFailure`；模态 q 全零时原对象返回 |
| 插入位置 | `_evaluate_patch` 里 `evaluate_contact` **之前**——力律是 `C·δ^1.5`，若在力上打补丁而 δ 不变，`√δ` 刚度永远看不到变形 |
| `tests/test_modal_deformation.py` | 5 项：零 q 原样返回、侵入按位移精确平移（1e-15）、两侧镜像、**力比等于 `((δ−d)/δ)^1.5`（1e-6）**、刚性算例永不形变 |

**抓到的是我自己的分母错**：首测 +20 µm 给 0.8707、−20 µm 给 1.1351，而我按冻结基线 δ = 65.5 µm 预期 1.49 / 0.579，一度以为是条带积分把效应抹平了。实际量这个算例本来的侵入是 **226.9 µm / 64.4 kN**，代入 δ = 226.9 µm 后 `((δ∓20)/δ)^1.5` 给出 **0.8707 / 1.1351，逐位吻合到 1e-6**。所以不是"接近"，是恒等式；可疑的那条曲线是拿别的算例的侵入量当分母画出来的。

**镜像这件事值得单独记**：同一组 q 在右环给 `d_z = −0.030362 m`、左环给 `+0.031220 m`（符号相反、幅值差 2.8% 来自网格不对称）。所以对称算例上"全局峰值比"会把两侧混在一起——+20 µm 时右轨 0.8707、左轨 1.1259，看起来像机理只做了一半。修正方式不是加修正项，而是在度量上分侧。

**同轮追加（文献 L11 的第二半）**：查到的算法是 Gao & Dai 的接触线法（AMM 105-107, 2012, 1284 —— 先取**变形后的法向**，再用接触线与轨面竖直距离最小定位接触点）。据此把法向也接上了：

| 改动 | 内容 |
|---|---|
| `TreadRing.contact_point(u, δ)` / `TreadRing.deformation(q, u, δ)` | 变形按**接触点真实横向位置**读取（示例算例 `0.754 − 0.750 = 4 mm`），同一核函数做 10 mm 中点差分得横向斜率 |
| `_deform_geometry(..., lateral_m)` | `δ' = δ − dz`，且法向与切向**同转** `θ = atan(slope)`（`n' = R(θ)n`、`t' = R(θ)t`），正切基保持正交 |
| `tests/test_modal_deformation.py` | 7 项：新增"弹性力跟新深度走（1e-6）"、"法向随踏面斜率转（`n_y/n_z == −s`，1e-6）"、"垂向力 = 法向力 × 倾斜后 n_z" |

**量级要摆明**：满幅 `q = 1` 时斜率 7.27e-2 rad（4.16°），但实测柔性算例 `max|q| = 3.555e-03` 只对应 **2.58e-4 rad（0.015°）**，`1 − n_z ≈ 3.3e-8` —— 这一层在当前幅值下是几百分之一的修正。写它的理由是"与变形后踏面的定义一致"，不是"它会改结论"；真要有分量，需要多边形磨耗/扁疤那个量级的踏面变形。

一条自学到的教训：力律那条判据只有在**相同的 u** 上标定 `q` 时才成立——差 4 mm 就偏 0.14%，正好把"读错位置"变成一个会红的数，而不是一个说不清的偏差。

`pytest tests` → **790 passed, 1 skipped**；`docs/LITERATURE_LOG.md` 新增 **L11**（接触线法 + Baeza/Kaiser 这一脉的四篇经典），文档 `FLEXIBLE_WHEELSET_PORT_2026-10-24.md` §14.6。

**还没做的（下一个增量）**：接触点本身仍在未变形型面上搜索（`x = x_rigid + Φq` 只进了深度与法向）；变形滚转角重建（论文用 `WOut`/`WBack` 反算 roll/yaw）；一系/重力的 Φᵀ 投影（缺轴座振型）；**解析雅可比不知道 ∂δ/∂q 与 ∂n/∂q**，`jacobian.py` 模态块只有 `−K`、`−C`，所以 `jacobian="analytic"` + 柔性轮对会退化成不精确牛顿——这条必须在启用前处理。



## 第 86 轮：辙叉窗拉到 0.45 s，弹性带从“不可测”变成“3.89 倍但小 19 倍”（S9-3b）

第 85 轮（S9-3）只用 0.05 s 辙叉窗测 300--400 Hz，结论写得很清楚：**那个窗回答不了这个问题**
（101 样本、19.8 Hz 分辨率、带内只有 5 个频点；而且刚性 5 坐标轮对也在该带读出 10.61 m/s²，
那是冲击泄漏）。本轮把同一辙叉算例跑 0.45 s，取后一半作分析窗。

| 量 | 刚性（35 坐标） | 柔性（167 坐标） | 比值 |
|---|---|---|---|
| 结果状态 | `numerically_checked` | `numerically_checked` | — |
| 样本 / 分辨率 | 901 / 2.2 Hz | 901 / 2.2 Hz | — |
| 最大侵入 | 189.60 µm | 145.27 µm | 0.766 |
| 后窗 rms | 0.253 g | 0.179 g | 0.708 |
| 后窗峰值 | 0.83 g | 0.55 g | 0.657 |
| **300--400 Hz rms** | **0.02332** | **0.09076** | **3.89×** |
| 最强谱线 | 193 Hz（2.14） | 171 Hz（1.55） | — |

三条判读：

1. **弹性带存在**：同算例、同窗、同通道，柔性比刚性高 3.89 倍，且这个窗足够长，刚性侧只剩 0.0233 的泄漏本底。
2. **但比总能量小一个多数量级**：柔性侧 300--400 Hz 是 0.0908 m/s²，后窗 rms 是 1.756 m/s²，
   差 **19.3 倍（−25.7 dB）**；刚性侧是 2.481 对 0.0233，差 106 倍（−40.5 dB）。所以柔性轮对贡献的是
   **高频细节**，不是量级 —— "柔性轮对决定轴箱加速度"这个说法在数据上不成立。
3. **最强谱线 193 → 171 Hz**：柔性没有消掉 193 Hz 的尖峰，而是把它摊宽到 171 Hz 与 300--400 Hz 一带；
   与 §17 的模态参与表一致：肇事的是 76--256 Hz 的轮盘族，不是论文的 345/378 Hz 族。

**不能证明的东西**：没有复现论文的 345/378 Hz（我们的对应族在 347.10 Hz，幅值小 5.6 倍）；单轴单侧、
刚性轨、`--fast`；前 0.225 s 未进统计但侵入 189.60 → 145.27 µm 说明仍在往稳态走。

本轮改动：新增 `scripts/s9e_turnout_acceleration.py`；`docs/FLEXIBLE_WHEELSET_PORT_2026-10-24.md` 新增
**§18**（18.1 为什么换窗、18.2 三条判读、18.3 不能证明什么、18.4 复算，约 22 分钟）。
产物：`F:\velch_tmp\s9e\acceleration.json`。

---

## 第 87 轮：柔性轮对上的长波反演 3.8 %，闭环 1.20 %，标定门差 0.8 点（S9-4）

沿用 S7e 的估计器（`scripts/s9_inversion.py` 直接 import `s7e_longwave`），只把模型换成 218 坐标的
柔性轮对车型；带 20/40 m，2.0 s（194 m），0.10 mm 探测，真值 0.083/0.103 mm。

**H（每单位轨面幅值的响应）**

| 激励 | V@20 m | V@40 m | D@20 m | D@40 m |
|---|---|---|---|---|
| 20 m | **583.69** | 52.19 | **0.8261** | 0.4056 |
| 40 m | 14.41 | **131.33** | 0.0270 | **0.5900** |

对照刚性 S7e（V 589.02 / 79.55、D 0.7931 / 0.2744）：柔性把 20→40 m 的交叉项削掉 34 %，对角项只动 1 %
—— **柔性改的是带间串扰，不是各带灵敏度**。

| 通道 | 条件数 | 标定 | 逐带（20/40 m） | 闭环 |
|---|---|---|---|---|
| V | 1.49 | **3.8 %（门 ≤3 %，FAILED，差 0.8 点）** | +1.2 % / −4.8 % | **1.20 %（通过）** |
| D | 1.94 | 15.1 % | −12.5 % / +16.6 % | — |
| V+D | 1.67 | 6.5 % | −10.0 % / +2.4 % | — |

最优是单通道 V，与 S7e 在刚性车上"多一个通道不改善"一致。**结论："大致反演"（20--40 m 幅值误差
≤30 %）在柔性轮对上成立；"≤3 % 标定"没成立，差 0.8 个百分点，刚性车是 0.7 %。**

差的 3.1 个点有两个候选，需要重跑 8 相位（约 88 min）才能分辨，本轮没做：①协议差（S7e 8 相位相干平均
压掉相位上的偶次残差，本轮只一对 ±）；②模型差（2 s 里模态被几何过渡点亮，± 相消后残留与幅值无关的项）。

**一个自身错误**：第一版闭环算的是 `replay_matrix @ ones/len(BANDS)` —— 用固定权重 0.5 平均两个探测列，
**没有用上复原幅值**，于是报出 100.4 %（看起来"完全对不上"）。按 S7e 口径（`|V_回灌|` 对 `|V_目标|`，
取模所以与相位无关）重算为 **1.20 %**。脚本已改并注释说明；`inversion.json` 保留 `closure_recomputed`
与原因。这类错误的特征是**数字像物理、不抛异常**，只能靠与已发表同口径结果对照发现。

本轮改动：`docs/FLEXIBLE_WHEELSET_PORT_2026-10-24.md` 新增 **§19**（19.1 协议、19.2 H、19.3 结果、
19.4 门没过两半、19.5 闭环 100.4 % 的自身错误、19.6 与"大致反演"定义对照、19.7 复算）；
`scripts/s9_inversion.py` 的闭环改为 S7e 口径。

---

## 第 88 轮：把采样提到 20 kHz，短波从"不可定量"变成"一次除法约 10 %"（S9-6）

S4 表里 0.1 m 波长的增益 96.5 (m/s²)/m 是在 **2 kHz 输出**下测的 —— 972 Hz、一个周期只有 2.06 个样本，
**无效**。本轮把 `output_step_s` 提到 5e-5（20 kHz）、`max_solver_step_s` 压到 1e-4（10 kHz 上限），
在 80 km/h 上用真实 `.tre` 正弦波磨（深 30 µm）测 25 / 50 / 100 mm 三种波长：

| 波长 | 激励 | 谱峰 | 增益 (m/s²)/m | 一次除法复原 | 误差 |
|---|---|---|---|---|---|
| 25 mm | 888.9 Hz | 888.8 | **26 761** | 32.9 µm | +9.7 % |
| 50 mm | 444.4 Hz | 444.4 | **26 459** | 32.9 µm | +9.7 % |
| 100 mm | 222.2 Hz | 222.2 | 36 618 | 45.0 µm | +50.0 % |

**机理**：轴箱通过一系弹簧（1.176e6 N/m / 48.2 kg → f_n = 24.86 Hz）挂在轮对上，f_n 以上轴箱几乎不动，
弹簧压缩量就是轨面幅值 `A`，所以 `a_box ≈ (2π f_n)² · A = 24 398 · A`，**与波长无关**。
444 与 889 Hz 两档实测差 1.1 %，正是这个常数的验证；222 Hz（8.9 倍 f_n）还没进渐近区，所以偏 50 %。

**因此短波反演退化为一次除法**：`A_rail ≈ |a_box| / 24 398`，25/50 mm 两档复原到 +9.7 %，
那 9.7 % 是**可标定常数**（阻尼与轴箱-一系耦合），不是随波长变的传递函数。

两条必须记下的边界：①**纵向通道是哑的**（`axle1_box_left_x_acc` 谱峰 0.000 m/s²），因为轮对没有纵向
自由度，文献的"垂向+纵向双通道"在我们模型上暂时无法复现；②柔性档多出一个 208 Hz 环（ζ=1e-3，
衰减 0.76 s），短波反演用刚性档更干净。

本轮改动：新增 `docs/SHORTWAVE_INVERSION_2026-10-25.md`、`scripts/s9f_shortwave.py`、
`scripts/s9f_wavelengths.py`；`docs/S4_BAND_TABLE_2026-10-23.md` 顶部加口径更正框。

---

## 第 112 轮：拿真实测量数据第一次验证（26 mm 波磨：声学 5/6、轴箱 3/6）

用户给来一套地铁实测（`F:\ai道岔状态反演辨识\75kmh数据\Run_75kmh_E1toE2.mat`，117.8 MB）、它的 README 和论文（Soto-Ocampo et al., *Mathematics* 2025, **13**, 2815）。这是第一次用**真实数据**检验我们的东西。

- **数据**：里程 3.798–6.303 km（2.505 km），`Vi_y` 两个轴箱垂向加速度 4 kHz、`So_y` 车内麦克风 48 kHz、`Vi_Speed` 多普勒；rms 10.79 / 0.132。`Vi_pks` 已经是 **km**。
- **真值**：论文 Table 3 六段（S1 4.243–4.300、S2 4.718–4.805、S3 4.855–4.927、S4 5.250–5.352、S5 5.438–5.577、S6 5.729–5.829 km）；Table 4 给出波长 **24.4–30.4 mm**（75 km/h 下 692–844 Hz）。
- **指标**：25 m 空间窗、5 m 步长，带内 Welch 峰/中位（dB），波段由**当地速度**把固定波长换算而来；判据先写死（AUC + 段外 95 分位 = 5 % 虚警）。
- **第一次波段错了**（20–350 mm）：振动 AUC 0.659 / 2 段，声学 **0.297**（比随机还差）——这个数字本身证明指标对波段极敏感。
- **改用论文实测的 18–40 mm**：声学 AUC **0.880**、段内 +6.38 dB、**5/6** 检出（S6 差 0.5 dB）、定位误差 0；振动 AUC **0.741**、+3.79 dB、**3/6**。
- 判读：论文的"波长恒定、频率随速度"被独立指标复现；**轴箱通道有信号但更弱**，与模型预测（`f > f_n` 后对波长不敏感 + 宽带冲击污染）一致；声学优于轴箱这一点**只有实测能告诉我们**。
- 新 `scripts/s10_measured_corrugation.py`（494 窗 × 两通道，写 `F:\velch_tmp\s10\detection.json`）、新 `tests/test_measured_detection.py`（6 项）、新 `docs/MEASURED_VALIDATION_2026-10-26.md`。
- 两个自造错误：`Vi_pks` 重复除 1000（窗口全空、`percentile` 报 `IndexError`）、波段过宽。

## 第 111 轮：在连续的 PRR 文件里怎么模拟波磨——把"多密才够"算出来

上一轮把波磨写成"补片内每 2.5 mm 一个 PRR"，能算但没说清**为什么是 2.5 mm**，
也没有告诉别人换个波长该怎么办。这一轮把它变成一条可反解的规则。

**新增 `src/velch/corrugation.py`**：`Corrugation(period_m, depth_m, harmonics=…, phase_origin_m=…)`
给出解析抬升 `at(s)`、峰-峰、第 n 阶波长与通过频率；`track(...)` 生成 `.tre`；
`write_station_table(...)` 生成密集站位表（只重写 PRR 点块的两个数值列，单位/注释/样条头逐字节保留，
`z_sign` 参数让 ±1 两种约定共用一份实现）；`station_mileages(...)` 强制表从 `0.0` 起、越过 `run_end_m`。
密度规则由 `interpolation_gain(h, λ) = |sinc(πh/λ)|²` 与 `required_step_m(λ, tolerance=)` 给出，
混叠上限由 `alias_free_step_m(λ, order)` 给出。

**实测（`scripts/s9af_corrugation_density.py`，2 m 补片、10 µm 拟合网格）**：解析式与
"真的采样后线性插值再拟合"一致到 **5e-7**；`h/λ = 1/4 / 1/8 / 1/10` 分别把基波削到
**0.8106 / 0.9496 / 0.9675**，与波长无关。按 3 % 容差反解：25 mm → **2.40 mm**（2 m 补片 834 个文件）、
50 mm → 4.80 mm（418）、100 mm → 9.61 mm（210）、200 mm → 19.21 mm（106）；高阶分量再除以阶次。
因此"补片内 2.5 mm"对 50 mm 的单频是 1 % 级、对 25 mm 的二阶才是 3 % 级。

**两处坑写进文档**：站位表不从 0 m 起会落到悬挂分支（`120307.1 N`/斑，O010 同族）；
站位太稀**不报错，只把波磨变浅**——40 mm 间距写 25 mm 波形读回来约 0.4 倍深度。

**与 `.tre` 的一致性**（`x_start = 30 m`，四个轴都扫过补片）：`zero` 0.19213 m/s²、
`.tre` 0.87302、PRR 密集站位 0.87186 ⇒ 两条路差 **0.13 %**，远小于任何一档插值损失。

新增 `tests/test_corrugation.py`（9 项：解析抬升、阶次波长/频率、`.tre` 与解析一致到 1e-15、
插值增益与实测一致、`required_step_m` 反解、±1 两种 `z_sign`、站位表 0 起与越过前轴、
补片外不动、9 条拒收信息），并修掉自己两处浮点边界（`floor(0.2/0.0025)` 少一站）。

文档：[CORRUGATION_IN_PRR_2026-10-26.md](CORRUGATION_IN_PRR_2026-10-26.md)。

## 第 110 轮：反演算法升级——用谐波阶梯恢复短波缺陷的**形状**，并修掉审查提出的两条回归

本轮按用户的布置先做算法升级、后做反演，并按审查意见修掉 `portable_models` 与 `assets` 的两条确定性回归。

**两条回归（审查发现，均已修并有测试）**

| 编号 | 症状 | 修法 |
|---|---|---|
| 🔴 R1 | `packaging/portable_models.py` 去掉 `rmtree` 后 `assets_dir.mkdir(parents=True)` 缺 `exist_ok`，**任何重建**（含已发布的打包语料）都 `FileExistsError: [WinError 183] …'profiles'` | `mkdir(parents=True, exist_ok=True)`；重建现有包后 `verdict: ACCEPT · 0 处失败` |
| 🔴 R2 | `src/velch/assets.py` 的"不得越界"检查也套在**裸相对路径**上，于是随包发布的 `examples/portable/case_flexible.json`（`../vehicle_v2/wheel_lower.csv`）无法解析 | 只对 `lib:`/`case:`/`data:` 前缀做越界检查；`tests/test_assets.py` 6 passed，示例算例加载出 **191 坐标** |

**算法升级：`src/velch/inverse/harmonics.py`（新）**

一次运行只给一个数（`a_box ≈ (2π f_n)²·A`）是短波反演的病根；真实缺陷非正弦，第 n 次谐波在加速度里产生自己的谱线，**一次运行给 N 个独立观测**。模块提供 `harmonic_amplitudes`（相干投影）、`calibrate_gains`（逐阶复增益）、`HarmonicModel`、`DepthProfile`、`invert_corrugation`（每阶两条方程 + 先验 → `mean ± σ`）、`coverage_across_orders`（BKF 的覆盖率判据）。

与文献的分工写进模块 docstring：BKF（MSSP 209 (2024) 111097）给"显式后验 + 覆盖率"；双卡尔曼（Eng. Struct. 365 (2026) 123194）用 `n·f_sleeper` 谐波更新刚度，这里把谐波换成**缺陷自身周期**、更新**深度**，因此不依赖我们模型从未证实的轨枕周期激励。

**实测（80 km/h、刚性轨道、轴箱车型、20 kHz、2 m 补片在 42.8–44.8 m）**

| 阶次 | 真值 | 反演 | 偏差 | σ（仅噪声） | z |
|---|---|---|---|---|---|
| 1 | 30.00 µm | 30.56 µm | **+1.9 %** | 0.42 µm | 4.3 |
| 2 | 9.00 µm | 13.46 µm | +49.6 % | 0.53 µm | 8.4 |

四通道冗余后 16 条方程 / 4 个未知数：残差 rms **0.00037** m/s² **低于**底噪 0.00764 m/s² ⇒ 两谐波模型与测量自洽，但解有系统偏差。

**三条读数**：① 形状拿到了（单幅值估计给不出二阶）；② 二阶 +49.6 % 是**接触斑对 25 mm 分量的额外滤波**，说明不同阶次的增益不能按"波长相同"互换——"没有常数算子"的第二处证据；③ σ 只含底噪，覆盖率不过，**不能**声称是总不确定度（残差低于底噪，把模型误差并入也不改数值），要可信 σ 必须用多组独立缺陷统计。另记：一级增益轴 1 为 18 046、轴 2 仅 2 395（差 7.5 倍），**增益逐轴**，实现必须按轴标定。

**过程中修掉的三个自己的错**（都写进了脚本注释，避免重犯）：补片放在车轮走不到的 30–34 m（"加了激励但没车轮经过"，读到 0.003 m/s² 对底噪 0.005）；把模板 0 的站点字典套给两条轨（右轨被镜像，静平衡落到悬挂分支，120 kN/斑）；分析窗取整段而非过缝窗（激励早已结束）。

**验证**：`tests/test_harmonics.py` 9 项、`tests/test_uncertainty.py` 10 项、`tests/test_assets.py` 6 项全绿；`pytest tests` 见下；文档 [HARMONIC_LADDER_INVERSION_2026-10-26.md](HARMONIC_LADDER_INVERSION_2026-10-26.md)；复算 `scripts/s9ac_harmonic_inversion.py`、`scripts/s9ae_harmonic_redundant.py`。


### 第 246 轮 — 横向力不是蠕滑：切向严格为零，67 % 是轮对采样的阶梯（B050）

第 245 轮把 +718.4 N 净横向力归给"切向/蠕滑贡献不对称"。本轮直接把它量了，**归因错了**，并顺手把 M2 的漂移砍到 0.10 mm。新增 `scripts/s107_lateral_creep.py`、`scripts/s108_lateral_seat.py`、[LATERAL_FORCE_SAMPLING_2026-10-31.md](LATERAL_FORCE_SAMPLING_2026-10-31.md)；`s101_one_set_case.py` 新增 `--wheel-density` 与 `--seat-lateral`；`s106_lateral_drift.py` 不再钉死旧 run id。

**切向严格为零**：座椅态逐轨打印，八个接触 `slip_lateral = 0.000000`、`tang = Fy − N·n_y = 0.00 N`，`Fy` 与 `N·n_y` 逐位相等（左 +1490.40、右 −1310.80）。所以净 +718.38 N **全部**是左倾角 `+0.024766` 比右 `-0.021802` 大 0.002965（12 %），不是蠕滑推的。复刻 `_integrate_vehicle` 的初始状态（`_seat` → 2×(`_settle_modal_coordinates` + `_seat`)）后归档 t=0 帧被逐位复现。

**也不是座椅没做完**：交替 0…8 轮，净力 `-0.00 → +668.54 → +718.37 → … → +737.78 N` 单调收敛，固定点在 +737.8 N。

**67 % 是采样（B050）**：把 `LMA.prw`（282 点、点距 0.5 mm）沿原折线共线加密——几何一字不改——再座椅：

| 采样 | 点数 | tilt 和 | 净力 | 每轴 |
|---|---|---|---|---|
| 1× | 282 | +0.002963 | **+717.88 N** | +179.47 |
| 4× | 1 128 | +0.000967 | **+238.11 N** | +59.53 |
| 10× | 2 820 | +0.000965 | +237.87 N | +59.47 |
| 40× | 11 280 | +0.000966 | +238.01 N | +59.50 |

**4× 之后收敛**，所以 480 N 是"接触搜索取最深采样点"把倾角量化成 0.004 台阶造成的假力；两侧落点相距 0.1 mm 正好跨在台阶两侧。

**横向平衡不是加一个标量方程**：`_seat_lateral`（只解 `y`）内部收敛到 0.208 N，但随后的模态沉降把倾角差拉回 `+0.005246`、净力回 **+1216.92 N**；交替 6 轮 `y` 涨到 +1.04 mm、残差在 −457…+846 N 跳。加 `roll` 更糟：固定 `z` 下 `±0.2 mrad` 就抬起一侧车轮（8 个接触剩 4 个，净力 +33 342/−32 232 N），2×2 牛顿发散到 `y = −4.6 mm`、残差 6.2e4 N。⇒ `(y, roll)` 必须**与竖向座椅一起解**，本轮不硬塞。

**时程验证**：规范算例改用 4× 车轮（`LMA_x4.prw`，不动 `LMA.prw`——51 坐标基线用的是它），0.40 s、80 km/h：

| 算例 | wheelset1..4 漂移 (mm) | 斜率 (mm/s) | 七门 |
|---|---|---|---|
| 282 点（`8886e594`） | +0.7128 / +0.7305 / +0.6947 / +0.6937 | 1.73–1.83 | 7/7 |
| **1 128 点（`fcd6f093`）** | **+0.0946 / +0.0999 / +0.0977 / +0.0976** | **0.24–0.25** | 7/7 |

**7.3 倍**。预注册门照实报：`L1a` ≤1.0 mm **PASS（0.0999）**、`L1b` 不得单调 **FAIL（仍单调）**、`L2` 同号 **PASS（4/4）**；另报更紧的 `|dy| ≤ 0.1 mm` = **0.0999 mm 压线**。所以只能说"67 % 是采样假力、已消掉，剩余 0.10 mm 与 238 N 同源"，不能说"漂移已解决"。

**测试**：`tests/test_wheel_sampling.py` 3 项（4× 点全部落在原折线上、偏差 ≤1e-6；规范算例指向 `LMA_x4.prw` 且 `run.seat_lateral` 缺省关闭；最新一组模型的 0.40 s 漂移 ≤0.25 mm），0.95 s 全过。`freeze_baseline --check` = **UNCHANGED**（`295809cb24c8e24b` / `7b1daef7e80664ac`）。

### 第 245 轮 — M2 时程：整车横向游走 0.73 mm / 0.40 s，源头是 +718 N 净横向力

B047 退役后 M2 只剩时程问题。本轮**不新跑仿真**，只读已归档的 0.40 s 运行（801 帧、七门 7/7），并补上归档缺的一列。新增 `scripts/s106_lateral_drift.py`、[LATERAL_DRIFT_2026-10-31.md](LATERAL_DRIFT_2026-10-31.md)。

**四个轮对一起走，不是转向架失稳**：`wheelset1..4` 在 0.40 s 内漂移 **+0.7128 / +0.7305 / +0.6947 / +0.6937 mm**，同号、极差 **0.037 mm（5 %）**、斜率 1.73–1.83 mm/s。⇒ 这是**整车横向平移**；历史第 235 轮"导向轮对横向游走"的说法要按这条改口径。

**预注册门要诚实报**：`L1a` 幅值 0.7305 mm ≤ 1 mm **PASS**；`L1b` 不得单调漂移 **FAIL**（0 → +0.73 mm 单调）；`L2` 力—位移同号 **不可测**——`series.npz` 里没有 `wheel_force_y_n`，只有法向力。**判不了不是我分析得不够，是数据契约缺一列。**

**补通道**：`s99_run_archive.py` 新增 `lateral_force_n`（帧 × 轨，取 `response.wheel_force_y_n`，非承载帧记 0），`meta.json` 的 `python_notes` 同步列序。0.01 s 冒烟 `(21, 8)`：四条左轨 **+1490.4 N**、四条右轨 **−1310.8 N**，净和 **+718.4 N**。

**这解释了整条链**：① 左轨 `N·n_y = 60.15 kN × 0.02458 = +1478 N`、右轨 −1478 N 本该抵消，实测差 14 % ⇒ 两侧**切向/蠕滑贡献不对称**（左 +12 N、右 +167 N）；② `a = 718.4 / 49 040 = 0.0146 m/s²`，0.40 s 自由加速 `½at² = 1.17 mm`，实测 0.73 mm（差额被 `3.0e7 N/m` 一系横向刚度吸收）；③ 外推 1.6 s 给 **18.7 mm**——足以把轮对推到轨距角并触发 `graph slope limit`，与历史 1.6 s 在 `x=67.03 m` 的失败点自洽。

**下一轮判据（写死）**：三个候选——A 轮断面未按侧镜像（查 `wheel_profile(side, y_sign)` 四处调用参数）、B 踏面左右不对称（把右轨镜像后 `|lever−冠|` 左右差应从 0.10 mm 降到 ≤0.02 mm）、C 蠕滑不对称（打印 spin 符号与两侧蠕滑）。验收：座椅态 `|净 ΣFy| ≤ 20 N`、0.40 s 内 `|dy| ≤ 0.1 mm` 且不单调、冻结基线 UNCHANGED、不新增任何容差。

### 第 244 轮 — 条带宽度不是原因（0.05 %），B047 的两条读数退役

第 243 轮把"接触落在冠顶 2 mm 内"判成写错的门；本轮把 M2 剩下的两条候选一并了结：**条带积分是不是把阻抗放大的元凶**，以及 **B047 那句"硬 927 倍"到底在比什么**。新增 `scripts/s105_strip_convergence.py`、[B047_RETIREMENT_2026-10-31.md](B047_RETIREMENT_2026-10-31.md)；任务书 §十一 追加 M1/M2 关闭表。

**条带收敛（判据预注册在脚本 docstring）**：规范算例（234 坐标、80 km/h）只把 `contact.strip_dy_m` 在内存里换掉、每档重新座椅：

| strip_dy (m) | 座椅残差 (N) | 贯入 左/右 (µm) | dN/dy 左 | dN/dy 右 | 配对 | 墙钟 (s) |
|---|---|---|---|---|---|---|
| 5.0e-4 | 6.93e-09 | 63.70/63.70 | −31.61 | +46.62 | −78.23 | 0.57 |
| 2.5e-4 | 2.49e-08 | 63.70/63.70 | −31.60 | +46.67 | −78.27 | 0.58 |
| 1.0e-4 | 1.55e-08 | 63.70/63.70 | −31.60 | +46.67 | **−78.27** | 0.66 |

带宽细化 5 倍，配对阻抗只动 **0.05 %**，贯入三位小数不变 ⇒ `G1 PASS / G2 FAIL / G3 PASS`，`VERDICT: the impedance is geometry, not the strip width`。**把 `strip_dy_m` 调小修不好任何东西**，M2 的这条候选关闭。

**这个阻抗是不是物理：可直接算**。斜率 `s` 的锥面压半径 `R` 的圆弧，横移 `p` 时最大贯入 `δ(p) = s·p + s²R/2` ⇒ `dδ/dp = s`（**与 R 无关**）。乘 Hertz 斜率 `1.5N/δ = 1.5 × 60 153 / 63.70 µm = 1417 kN/mm` 得 **35.4 kN/mm**；实测左 −31.61（= 22.3 µm/mm）、右 +46.62（= 32.9 µm/mm），围绕 25 µm/mm 不对称是因为 LMA 不是纯锥面、横移把一侧推进更陡的踏面段。**量级与符号都对**。

**B047 退役**：原话"横向定位硬 927 倍（`k_force = 5404.5 kN/m` vs `k_grav = 5.83 kN/m`）"有两处问题——① `k_force` 是**载荷再分配斜率**，与 Wickens `W·λ/(4r)` 的**定位刚度**是两个不同的量（后者由滚动半径差→纵蠕滑→摇头→横蠕滑给出）；② 老读数出自 `effective_radius_m = 0.02` 时代（B048 已退役），按现在的规范算例同一物理量是 31–47 kN/mm，比老读数大 6–9 倍而**不是 927 倍**。替代陈述：接触位置由斜率相等定（`R·s = 7.5 mm`，实测 8.03 mm、倾角 0.0246）；`dN/dp` 是几何；**横向定位行为只能由时程回答**。

**门的口径修正（保留原判、另立新门）**：`on_crown` → `tangent`（`|lever−冠| ∈ [R·s±2] mm` 且 `| |tilt| − s | ≤ 0.005`）；`stiffness` → `impedance`（`dN/dp` 必须等于 `1.5N/δ · s` 的 0.9–1.4 倍，且 `strip_dy` 细化 5 倍变化 ≤2 %）；`follows_wheel` 适用域收窄为 `|tilt| > 3s`（陡面接触才要求接触点跟轮走）。

**测试**：`tests/test_strip_convergence.py` 2 项（细化 5 倍后左右 `dN/dy` 变化 ≤2 % 且座椅贯入差 ≤0.1 µm；两侧 `|dN/dy|` 落在解析值 0.5–2.0 倍内且符号相反），3 s 内全过；与第 243 轮的 `tests/test_crown_tangent.py` 合计 5 项 3.97 s。

**写这两项时我自己的一个错**：解析常数写成 `1.5N/δ /1e3 * s *1e3`（量纲两次互抵只留 1e1），`ANALYTIC_KN_PER_MM` 一度是 3.5e7；断言当场把它顶出来，改成 `*1e-6 * s`（N/m → kN/mm）。

### 第 243 轮 — 冠偏移扫描：五档全不成立，并查出"接触落在冠顶 2 mm 内"这条门本身是错的

第 242 轮把 B047 的根因指向 `scripts/s85_db_case.py:81` 的 `CROWN_OFFSET_M = 13.0e-3`（一个在 35 坐标车上拟合的常数）。本轮按预注册的四条门去重拟它：`CROWN_OFFSET_M ∈ {13, 10, 8, 4, 0}` mm 各建一个**变体**算例（做法是把每站 `y_offset_m` 平移 `±(offset−13) mm`，落在 `scratch/s104/`，**规范算例不被覆盖、`s85` 不改**），每个变体座椅后横移 −3…+3 mm 共 7 档只求值。新增 `scripts/s104_crown_offset_sweep.py` 与 [CROWN_OFFSET_SWEEP_2026-10-31.md](CROWN_OFFSET_SWEEP_2026-10-31.md)。

**结果：五档全部不成立**（预注册判据写死在脚本 docstring 里，运行前就定好）：13.0 mm 档座椅 6.93e-09 N、八轮 1.00–1.00，但 `|lever−冠| = 8.03/−7.93 mm`（门 ≤2 mm）、`d(lever_y)/dy = −0.0016`（门 [0.5,1]）、`k_lat = −2640.7 kN/mm`（门 10–100）、±3 mm 脱空；10.0 mm 档更差（10.58 mm、−0.0025、−6637.2）；8.0 mm 档再差（13.22 mm、−0.0034、−52090.0）；4.0 mm 档**座椅即触发** `graph slope limit at axle1_left/left:main, x=50 m`；0.0 mm 档**座椅不收敛**（`gtol`）。脚本末行按预注册给 `VERDICT: no offset satisfies all four -- the registration is not a constant to re-fit`。

**机制（绝对位置）**：冠偏移 13 → 10 → 8 mm 时，左冠从 −759.602 移到 −756.602、−754.602，而接触点从 −751.573 移到 **−746.024**、**−741.379**——**接触点比轨动得更快**（3 mm 换来 5.58 mm，2 mm 再换来 4.65 mm），并伴随倾角 0.02458 → 0.03325 → 0.04988 与横向"刚度" −2641 → −6637 → −52090 kN/mm（**19.7 倍**）。所以接触位置由**两侧斜率相等**这个条件决定：把轨往轮平面里挪，车轮只能拿自己更陡的一段去配平。→ 注册**不是**一个可以重拟的常数。

**这一轮真正查出的错是我自己的门**：第 2 条门"接触落在冠顶 2 mm 内"在几何上不可能满足——`1:40` 踏面（s = 0.025）压在 300 mm 冠上，斜率相等点距冠顶 `R·s = 7.5 mm`；实测 8.03 mm、倾角 0.02458（比 0.025 低 1.7 %，0.66 mm 残差说明接触处局部半径约 327 mm 而非名义 300）。更要紧的是**冻结基线自己就不满足这条门**（座态倾角 0.02458 ≈ 2.5 % 锥度、接触距冠 8 mm），所以这条门判的不是模型而是我的写法。按"不许看过结果改阈值"，处理方式是**保留原判 + 另立一条门并写明它为什么必须另立**：`tangent`（`|lever−冠| ∈ [R·s−2, R·s+2] mm` 且 `| |tilt| − s | ≤ 0.005`）。按这条门 13.0 mm 档**通过**，10.0/8.0 两档不通过（倾角已不是 1:40 在接触）。两条判定并列写进文档，原门作废记录保留。

**判据修正（下一轮，先写死）**：M2 要修的不是接触点位置（位置由斜率相等定、倾角与冻结基线一致），而是**接触阻抗**。做条带宽度收敛 `strip_dy_m ∈ {5e-4, 2.5e-4, 1e-4}`，三档各座椅 + ±1 mm 横移：三档 `dN/dy` 相对变化 ≤5 % ⇒ 不是条带离散化；若随 `strip_dy` 单调显著变化 ⇒ 是条带积分，改它（不动接触刚度、不动容差）。无论哪种，冻结基线必须 UNCHANGED。

**测试**：`tests/test_crown_tangent.py` 3 项（接触落在 `R·s` ±2 mm 内；倾角符号朝内且模值在 0.025 ±0.005；`R·s` 随冠半径缩放——0.02 m 冠给 0.5 mm），1.36 s 全过。写这两项时我自己也错了两次：`crown_y` 取了 `max(z)`（那是高度不是位置，要 `y[argmax(z)]`），倾角符号写成 `side*tilt`（实测左右都朝内，是 `−side`）——都由断言当场顶出来。

### 第 242 轮 — 横向注册在规范算例上重测：接触内移 8.0 mm、`d(lever_y)/dy = −0.0016`、`k_lat = −2827 kN/mm`

B047 的三句描述（"硬 927 倍"、"倾角冻结"、"内移 16.7 mm"）全部出自 `effective_radius_m = 0.02` 还在生效的年代，而等效半径直接决定 `dδ/dy`；B048 退役了它，所以那批数不再是当前模型的数。本轮用**规范算例**（234 坐标的一 组模型）把横向注册重测一遍。新增 [LATERAL_REGISTRATION_BASELINE_2026-10-31.md](LATERAL_REGISTRATION_BASELINE_2026-10-31.md) 与 `scripts/s103_lateral_registration.py`。

**方法**：dy = 0 处座椅（残差 6.927e-09 N），之后只加减 `wheelset1.y`、**只求值不重解座椅**——每档重解会把"接触几何如何随横移变化"换成"座椅如何找另一个平衡"，是两个问题。冠部一律取同站同轨**基本轨体**断面的 `max(z)`（z 向上为正；`min(z)` 是断面底边，B049 教训）。

**实测（50.000 m、80 km/h）**：冠距 **1519.102 mm** 对轮平面距 **1493.000 mm**（每侧差 13.05 mm），接触点落在 **±751.573 mm**，即冠内侧 **8.0 mm**；`d(lever_y)/dy = **−0.0016**`（车轮横移 3 mm、接触点动 0.005 mm，判据 [0.5,1.0]）；`k_lat = **−2826.78 kN/mm**`（判据 10–100，且**符号正确**——位移 +y 给 −y 合力，问题是量级不是符号）；±3 mm 内卸载体脱空；倾角全程 0.023–0.033。1 mm 横移把 45 kN 从一侧搬到另一侧 ⇒ **所谓"横向刚度"其实是两侧法向力的分配斜率，不是轮对定位刚度**。

**根因指向一个拟合常数**：`scripts/s85_db_case.py:81` 的 `CROWN_OFFSET_M = 13.0e-3`，注释记录"12.0–13.7 mm 窗口内八轮 1.000× 均分、<10 mm 压肩部 1087 kN、>14 mm 脱空"——但它是拿 **35 坐标刚性轮对车**拟合的，而规范算例是 86 坐标完备车 + 柔性轮对，悬挂不同、落点不同，窗口不能直接搬。**这不是"改个 0 就好"**：offset 0 的实测会压外侧肩部并在 50 m 触发斜率门。

**下一轮判据（先写死）**：`CROWN_OFFSET_M ∈ {0,4,8,10,13}` mm 各建一次算例（`--crown-offset-mm` + 独立 `--out`，规范算例不许被覆盖），四条全中才算通过：① 座椅 8/8 ∈[0.625,1.6]× 且残差 ≤1e-5 N；② 两侧 `|lever−冠| ≤ 2 mm`；③ `d(lever_y)/dy ∈ [0.5,1]`；④ `k_lat ∈ [10,100]` kN/mm 单调且 ±3 mm 不脱空。若五档全不成立，结论就是"注册不能靠调常数修"，转去改接触搜索（窗口随轮心平移 / 整型面搜索）。

### 第 241 轮 — 一组模型装进同一算例：234 坐标、八轴箱、柔性轮对、真道岔几何，七门 7/7

任务书 M1 的定义是"把四件东西装进同一个算例并跑通七门"。此前它们分散在四个算例里：**完备车辆**（`CRH380A_M_axlebox`，86 坐标、15 刚体含 8 个轴箱）**没有任何算例**；**柔性轮对**只在 12 站合成几何的 `examples/portable/case_flexible.json`；**柔性轨道 + 真道岔几何**在 `cases/straight.json`，而它挂的是 35 坐标刚性轮对车。新增 [ONE_SET_CASE_2026-10-31.md](ONE_SET_CASE_2026-10-31.md)。

**装配**：`scripts/s101_one_set_case.py` 以 `straight.json` 为底本，把内联车辆换成 `vehicle_ref`（车辆只有一份定义，不复制、不漂移），加 `flexible_wheelset`（`modes/CRH3C_wheelset_fe.json`、四个轴），产物 `cases/straight_one_set.json`。结果 **234 = 86 车 + 16 轨（8×2）+ 132 模态（4×33）**、15 刚体、16 接触体、`local_compliant`。

**为了走到这条路径，修了两个第一次被走到的加载器缺陷**：① `vehicle_ref` 不认识 `lib:`/`case:`/`data:` 前缀（`vehicle_db.load` 把 `lib:...` 当裸文件名按 cwd 解析）⇒ `vehicle.py:423` 先 `resolve_asset`；② `run.speed_profile` 的常量分支写 `raw["vehicle"]["travel_speed_m_s"]`，而 `vehicle_ref` 算例没有 `raw["vehicle"]` ⇒ `KeyError: 'vehicle'` ⇒ 改为先记 `scheduled_speed`、拿到车辆块后 `dict(v, travel_speed_m_s=...)`。对**内联车辆**算例这是等价变换，由冻结基线证明：`straight_rigid 295809cb24c8e24b` / `straight_flexible 7b1daef7e80664ac`，**UNCHANGED**。速度必须由算例声明，否则会继承车辆的线路设计速度 **350 km/h**。

**座椅（G2）**：`dimension 234  seat residual 6.927e-09 N`、八轮各 `1.000×` 均分（`60153.0 N`）、贯入 **63.70 µm**、座椅墙钟 **0.6 s**。贯入不是冻结的 65.4661 µm，因为这款车更重（481 078.5 N / 9.81 = **49 039.8 kg** vs 35 坐标车 48 654 kg）——**51 坐标算例的历史数字不得与本算例混用**。

**积分（G3–G5）**：0.02 s（41 帧、**9.3 s** 墙钟）与 0.40 s（801 帧、**180.0 s**）均 `gates 7/7`。0.40 s 时前轴到 **58.889 m**，越过尖端 50.578 m 与几何首触 57.733 m；尖轨首载 **58.144 m**（比几何首触晚 **+0.411 m**，与 51 坐标算例的 +0.395 m 同源——1 kN 检测门 + 6.4 m 弹性坡道），峰值 **40.77 kN @ 58.589 m**，同一里程基本轨已降到 **19.35 kN**，即右股 **67.8 %** 载荷在尖轨上；整段逐轨份额 **0.966–1.029**（门 [0.625, 1.6]）。

**边界**：只跑直向、80 km/h 一档、单一进场点；这不构成曲线能力，也不含 M2（B047）与 M3（3.3 m 仲裁）的任何结论，目标主门（Ω_obs 上 p95 ≤ 22 µm）尚未开始。14 个声明接触体里只有 **10** 个在本运行中出现（`frog` 在 103 m 之后、`blade` 只在坡道上承载），是几何决定的，不是丢数据。

**成本**：0.02 s = 9.3 s、0.40 s = 180 s、座椅 0.6 s ⇒ 约 **450 s / 模拟秒**（234 维）。

**测试**：`tests/test_one_set_case.py` 5 项（86/15/8 轴箱；四轮对 33 阶模态；维数 = 86+16+132；算例自己声明 80 km/h；右股每轴 stock+blade+frog 且尖端 gap −14.94 ±0.2 mm），0.41 s 全过。`tests/test_run_archive.py` 增 1 项（`--case` 用文件名做标签，两个不同算例不得共用 run_id），4 项全过。

### 第 240 轮 — 40–100 km/h 四次过岔：尖轨首载里程只动 5.6 mm

按用户 2026-10-31 的指令（可重复跑、数据必须留存供代理模型、多组速度），本轮把"跑一次看一个数"换成**数据契约 + 四速度采集 + 第一个消费者**。新增 [SPEED_CAMPAIGN_BLADE_2026-10-31.md](SPEED_CAMPAIGN_BLADE_2026-10-31.md)。

**先补上逐体力，否则这批数据测不了降低值**：合并后的轨级力是各体之和，"有多少载荷在尖轨上"在合并里就消失了。`VehicleResult` 因此新增 `body_contacts`（逐帧、按 `rail_id → (ContactResponse, ...)` 的逐体拆分，与 `contacts` 同一次 `evaluate`，不额外算 RHS）与 `body_ids`（**同序**体名）。为什么体名必须单独存：`_evaluate_patch` 只把 `active_at(x)` 的体算进结果，50.0 m 处右轨只报 `stock`，而站表声明三个体——**体名无法从轨反推**。`series.npz` 多出 `body_normal_force_n` 列块，`meta.json` 记 `body_labels`；整列求和与 `normal_force_n` **逐位相等**（0.01 s 冒烟两处都是 `10022035.036756517`）。

**采集**：`scripts/s99_run_archive.py` 四个速度，route `straight`，`campaign=blade-lowering-2026-10-31`，全部七门 7/7：

| 速度 (km/h) | 时长 (s) | 帧数 | 墙钟 (s) |
|---|---|---|---|
| 40 | 1.80 | 3601 | 428.7 |
| 60 | 1.20 | 2401 | 288.4 |
| 80 | 0.90 | 1801 | 218.1 |
| 100 | 0.72 | 1441 | 173.7 |

**消费者的读数**（`scripts/s100_speed_campaign.py`，几何基准由 s98 独立给出：首触 57.733 m、齐平 58.423 m）：

| 速度 | 输出一格 (mm) | 前轴首载 (m) | 相对几何首触 | 前轴峰值 (kN) | 峰值里程 (m) |
|---|---|---|---|---|---|
| 40 | 5.56 | 58.106 | +0.373 | 41.48 | 59.728 |
| 60 | 8.33 | 58.108 | +0.375 | 41.40 | 59.725 |
| 80 | 11.11 | 58.111 | +0.378 | 41.35 | 59.722 |
| 100 | 13.89 | 58.111 | +0.378 | 41.37 | 59.722 |

**能说**：首载里程散布 **5.6 mm**、峰值散布 **0.13 kN（0.3 %）** ⇒ 在这个速度带里降低值定位对速度不敏感，一次标定可跨速度搬。
**不能说**：那 **+0.37 m** 的差不是噪声（1 kN 检测门 + 弹性鼓形坡道）；s97 用钩子在求解器内部时刻读同一算例给 **58.128 m**，故真值应写 **58.11–58.13 m** 并注明分辨率；"5.6 mm 不变"是**在输出网格之内**不变，要 ±1 mm 得用亚帧读数或 1e-4 输出步长（未做）；只测直向、刚性轮对、单一进场点。本轮**不做幅值反演**。

**修掉的两个自己的错**：初版把四个轴的 blade 列相加当"一轴力"，读出 81.9 kN，被 `stock@peak = 156.8 kN`（= 2.6× 均分）当场顶出来；初版还从 case JSON 里找 `vehicle.axle_offsets_m`，而它并不存储（由 `bogie_half_spacing_m` 与 `wheelbase_m` 推出：`+a+b, +a−b, −a+b, −a−b`），改走 `load_vehicle_case`。

**测试**：`tests/test_body_attribution.py` 增第 5 项，把"体名必须与逐体响应同序、且只含该轨真的挂着的体"钉住（`5 passed in 1.08 s`）。

**成本**：40/60/80/100 合计 **1109 s** 墙钟，单位 **≈240 s / 模拟秒**（含座椅）。

### 第 239 轮 — M0 关闭：尖轨降低值被注入了第二遍（B049），逐体归属本身是对的

M0 的两条硬门用一次运行同时判定，结论是**归属门通过、几何门失败**——而失败的样子（尖轨在埋深 13 mm 处顶起 1.08 MN）先被误读成"归属记错"，最后定位到建库脚本把设计降低值写了两遍。新增 [BLADE_LOWERING_DOUBLE_INJECTION_2026-10-31.md](BLADE_LOWERING_DOUBLE_INJECTION_2026-10-31.md)。

**M0-1 逐体归属：通过，而且是逐位相等**

`scripts/s97_body_attribution.py` 在运行期间接管 `versus.merge_contact_responses` 与 `BODY_CONTACT_HOOK`，按调用序号把"各体之和"与"合轨总力"配对。0.85 s / 1701 帧 / **912 928 对**，`max |sum(bodies) − merged| / merged = 0.000e+00`（门 1e-9）。⇒ 历史上那条"尖轨在 50.627 m 就吃到 69.69 kN"**不是**归属记账错。

**M0-2 几何门：失败，1 079 365 N**

`tests/test_body_attribution.py` 把前轴放到 51.978 m（尖轨区内 1.4 m）断言尖轨不承载，实测 `axle1_right: the blade carries 1079365.53873064 N while it is still millimetres down`（18× 均分）。逐站读冠（`max(z)`，`z` 向上为正）后原因清楚：**52 m 处尖轨比基本轨高 3.313 mm**，车轮真骑在尖轨上。

**根因 B049：降低值在断面里，建库又加了一遍**

站表实测 `z_offset_m = 0.01494`（按 3 mm 宽插值到 14.94 mm）+ `z_sign = −1`，而断面本身已经含降低值：

| 断面 | `z_offset_m` | 冠 `max(z)` | 相对基本轨 +0.072 |
|---|---|---|---|
| `zjg-…-3`（3 mm 宽） | **0** | **−14.935 mm** | **−15.007**（设计 14.94 ✔） |
| `zjg-…-3` | +0.01494 | +0.005 | −0.067（被抬到齐平） |
| `zjg-…-30` | **0** | −1.159 | −1.231（设计 1.16 ✔） |
| `zjg-…-72` | **0** | +0.094 | +0.022（设计 −0.09 ✔） |

`s85_db_case.py` 的 `with_lowering()` 依据的注释读的是 `min(z)`（断面底边），才得出"抄过来与基本轨齐平、需补偏移"的错误结论。修法：删 `BLADE_LOWERING_MM` / `blade_lowering_m()` / `with_lowering()`（连同只服务它的 `numpy` 顶层导入），尖轨站表原样装载、`z_offset_m = 0`；重建 `cases/straight.json`（139 kB）与 `cases/diverging.json`（141 kB），站数不变（left 76 / stock 76 / blade 161 / frog 65）。

**修后几何（`max(z)` 判据）**：尖端 **−15.007 mm**、首触（gap = 65.4661 µm）**57.733 m**、冠齐平 **58.423 m**、全程最多高过基本轨 **+0.021 mm**。五种"尖轨何时到走行面"的读法并存（断面首触 57.733 / 断面齐平 58.423 / SDITT 里程表 57.019 / 宽度插值 64.9 / 旧预注册 68.16），旧预注册被断面几何否掉 10 m——这条留给 M3 仲裁。

**修后 0.85 s 运行（206 s 墙钟、1701 帧、七门 7/7）**

```
axle1_right blade 首载 58.128 m（1.018 kN）峰值 41.72 kN @ 59.731 m
axle2_right blade 首载 58.127 m（1.014 kN）峰值 41.67 kN @ 59.731 m
axle1_right stock 首载 50.000 m（59.680 kN）峰值 59.73 kN，59.731 m 处降到 19.27 kN
```
尖轨首载比断面首触晚 **+0.395 m**（1 kN 检测门在 6.4 m 坡道上的必然结果），59.731 m 处 **67.6 % 载荷已转移到尖轨**——这正是后续要反演的观测量。

**新增工具与守卫**

- `scripts/s98_m0_verdict.py`：纯几何先算（5 mm 步长、`flush` 取**第一个** gap ≥ 0，不再用全局 `argmin(|gap|)`——坡道后两冠在几十微米内摆动会把最小值骗到 71.003 m），再读运行并落 `scratch/s98/m0_verdict.json`。
- `scripts/s99_run_archive.py`：代理模型数据的唯一入口，`run_id` 只由输入（route / 速度 / 时长 / 步长 / case sha256）决定，落 `series.npz`（含 `accelerations (n,31)`，`axle1_z_acc` 是主观测量）、`meta.json`、`manifest.json`、`index.jsonl`。
- `conftest.py`（根级，新建）：本机 `%TEMP%\pytest-of-<user>` 已坏死（`os.listdir`、`icacls`、`rename` 全部 WinError 5），`tmp_path` 在 fixture 阶段直接 PermissionError，`tests/test_assets.py` 5 项全 ERROR——与代码无关。守卫在 `tmp_path_factory` 解析 base 之前探测该目录，不可列就把 `PYTEST_DEBUG_TEMPROOT` 指到 `scratch/pytest_tmp`。修后 `test_assets` 6 passed。
- 测试：`tests/test_body_attribution.py` 4 项（逐体之和、钩子逐体、埋深不承载、B049 几何回归）；`tests/test_run_archive.py` 3 项。合计与 `test_assets` 一起 **13 passed in 4.85 s**。

**影响面**：`cases/*.json` 摘要已变，`scratch/s86/*` 与 `s87` 的 −10.03 / −17.53 m 读数作废；求解器与冻结物理未动（七门 7/7、`freeze_baseline --check` 复核）。

**本轮成本实测**：0.01 s 仿真 2.2 s 墙钟、0.85 s 206 s ⇒ **≈240 s / 模拟秒**（含座椅）。

### 第 238 轮 — 最终任务书：把"精度 90%"改写成可判定门，并把四件模型装进一个算例

用户下达最终目标（反演尖/心轨走行面、与 PRR 拟合面逐点对照、精度 ≥90% 验证算法、再扩展到随机与波磨）。本轮只做三件事：写任务书、核实现状、把待批准项摆到桌面上。新增 [TASKBOOK_FINAL_GOAL_2026-10-31.md](TASKBOOK_FINAL_GOAL_2026-10-31.md)。

**核实现状（我逐字段读的，不是转述）**

- `vehicles/turnouts/CN60-1100-1_18/cases/straight.json`：`track_dynamics = local_compliant`（柔性轨）、7 体车辆（carbody 34934 / bogie 3300 / wheelset 1780，**刚性轮对**）、右轨 3 body（stock 76 / blade 161 / frog 65 站）。
- `run = {x_start_m 40.0, duration_s 0.02}` ⇒ 只走 **0.44 m**，而尖轨区起点 **50.578 m**、预注册首触 **68.16 m** ⇒ **现有道岔算例从未走到尖轨**。
- 全仓 `velch-vehicle-v2` 扫描：完备车辆（`CRH380A_M_axlebox`，86 坐标）**没有任何算例**；柔性轮对只在 12 站合成几何的 `examples/portable/case_flexible.json` 里 ⇒ **"完备车辆 + 柔性轮对 + 柔性轨道 + 真道岔几何"四者从未同时出现**。
- `contact.effective_radius_m = 0.02` 在 `stiffness_policy = local_circular` 下仍留在算例里（B048 只改了策略，字段没删）⇒ 读数陷阱。

**"精度 ≥90%" 在物理上没有判别力**：14.94 mm 的 10 % = **1.49 mm**，是静侵入 65.4661 µm 的 **23 倍**——把尖轨面做错 1.5 mm，相对门照样通过。因此任务书把主门定为**绝对误差**：Ω_obs 上 p95 ≤ **1/3 静侵入 ≈ 22 µm**，并配 G-LOC（首触里程 ≤ ±0.2 m）、G-COV（覆盖率）、G-NULL（降低值置 0 须回本底）；相对值只作逐 2 mm 分档报告。

**自证陷阱写进任务书**：反演面与"自建正演面"比是自证（零注入恒等 100 %），故证据分 A（数字闭环，只许标 `numerically_checked`）/ B（留出站，只写内插能力）/ C（独立真值，才许写"验证算法"）三级；C 级数据今天不存在。

**另外两条硬事实**：单次通过只能观测接触斑扫过的窄带（10–20 mm），故反演对象改为 **`z(s,y)|Ω_obs`**（Ω_obs 由 `history.csv` 的 `lever_y` 统计生成，不许估算）；全三维面用逐列有限差分不可行——1 s 仿真 **707 s**、161 站雅可比 **94 h/次迭代**，只能走准静态 + 代理模型。

**待批准三项**（任务书 §10）：Ω_obs 定义（接触带面 vs 全平面）、主门用绝对误差、C 级真值（≥3 区段轨面实测）。

## 第 247 轮：横向座椅联立 —— 净横向力 +238 → +44.75 N，但平衡点是平谷

* 先量为什么"只解轮对 `y`"无效：`wheelset1.y` 偏移 0.6 µm 让该行广义力变 121 N ⇒ 轮对与轴箱之间
  是 **2.0e8 N/m**；两个连接件在座椅位置各给 **−29.611 N**，合计抵掉该轮净横向力。第 5 轮那次
  "只挪 0.296 µm、净力 +236.88 N"由此解释。
* 改为**整链联立**：`run.seat_lateral` 时把 15 个体的 `y` 与 `roll` 全部追加进最小二乘
  （23 → **53** 未知量），解完再做一次竖向抛光。
* 实测（234 维一组模型、80 km/h）：净横向力 **+238.11 → +44.75 N**、每轴最差 **+59.53 → +11.19 N**、
  倾角和 **+9.67e-4 → +1.42e-4**、份额 0.999–1.001、残差 5.009e-02 → **9.859e-08 N**、墙钟 4.5 s。
  预注册四门：G1 PASS / **G2 视路径（11.19 过、另一次 21.12 不过）** / G3 PASS / G4 PASS。
* **平谷**：交替"模态沉降 ↔ 联立座椅"7 轮，`y` 在 **+1.70 与 −0.31 mm** 间跳，净力 42–112 N，
  第 5 轮座椅不收敛 ⇒ "使净横向力为零的 `y`"是病态目标，不该当交付判据。
* 0.40 s 时程（`straight_one_set-080.00kmh-0.4000s-500us-55d6fd49`，4× 车轮 + 横向座椅，801 帧、7/7）：
  起始 y **−0.4088 mm**、漂移 **0.1345 / 0.1413 / 0.1226 / 0.1215 mm**，方向**朝平衡点**（与载荷不平衡
  4/4 同号）。同尺子的无横向座椅那档是 0.0999 mm —— 量级略大，但性质从"一路走开"变成"收敛到平衡点"。
  **M2 的 `|Δy| ≤ 0.05 mm` 两档都没过，如实记为未达标。**
* 交付：`src/velch/vehicle_solver.py`（联立未知量 + 分档容差 `_SEAT_LATERAL_TOLERANCE = 20 N` + 竖向抛光 +
  `VELCH_SEAT_DEBUG`）、`scripts/s108_lateral_seat.py`、`scripts/s109_lateral_stiffness.py`、
  `tests/test_lateral_seat_joint.py` 4 项、`docs/LATERAL_SEAT_JOINT_2026-10-31.md`。
  规范算例 `straight_one_set.json` 现在带 `seat_lateral: true`（座椅 +1.6 s，换来倾斜对称与收敛方向）。
* `freeze_baseline --check` **UNCHANGED**（`295809cb24c8e24b` / `7b1daef7e80664ac`）——默认关闭，
  竖向路径逐位不变。

## 第 248 轮：M3 收口 —— 五个"尖轨到达走行面"的读数，两处错在插表而不插断面

* 同一事件历史上写过五个数：57.733 / 58.423 / 57.019 / 64.900 / 68.160 m，差 10.4 m。
  `scripts/s110_lowering_readings.py` 把每个数从**同一份里程表 + 同一批断面**重算：
  宽度直接读断面文件名（`…-44.txt` = 44.0 mm），冠高 = `max(z)`，`d(s) = 冠_基 − 冠_尖`。
* 实测（145 个有宽度站位、2 mm 步长）：**断面首触 57.844 m、齐平 58.476 m**；插值扫描（s98 口径）
  57.733 / 58.423；**宽度三点表 60.452 / 60.650**；**退役里程表 64.584**（复现当时写下的 64.900，
  差 0.32 m，因为当时是逐站 0.193 m 的更密表）。
* 两处错都是"插表"：① 宽度三点表 `(3,14.94)(30,1.16)(72,−0.09)` 是对一条**凸**曲线拉直线——
  在 57.844 m（44 mm 宽）它说尖轨还低 **0.743 mm**，断面说只低 **0.0554 mm**，高估 0.688 mm，
  于是晚 2.6 m；② 退役里程表末两个锚点 `60.047:+0.178`、`70.848:−0.090` 都在平坦段，线性插值把
  65.4661 µm 放到 64.584 m，晚 **6.740 m**。
* 结论与口径：主口径用断面插值 **57.733 / 58.423 m**，几何读数不确定度 **±0.11 m**（站距 0.193 m）；
  **64.900 与 68.160 正式退役**；**57.019 是 SDITT 按"宽度到全断面"判的，不是冠高齐平**，引用必须写明。
* 交付：`scripts/s110_lowering_readings.py`、`tests/test_lowering_readings.py` 4 项、
  `docs/LOWERING_READING_ARBITRATION_2026-10-31.md`、任务书 §11 M3 行。
* 只读几何，不涉及求解器；`freeze_baseline --check` 仍 UNCHANGED。

### 第 249 轮（2026-10-31）一次过车只能看见一条带：Omega_obs 覆盖率 25.7 %

- `scripts/s99_run_archive.py` 归档接触点与接触带半宽（`contact_lateral_m` / `contact_half_width_m`，
  无接触帧为 NaN），重跑 0.40 s：`straight_one_set-080.00kmh-0.4000s-500us-55d6fd49`，801 帧、七门 7/7。
- `scripts/s111_obs_region.py`：把"整个三维面"变成可判定的数。单元 = 0.2 m 站位 × 1 mm 横向（相对该站
  基本轨冠）；`Omega_obs` = 至少一个接触斑覆盖的单元；`Omega_design` = 冠下 `HEAD_DEPTH` 内的走行面单元，
  **只统计运行真的走过的站位**（没走到不是横向漏测，否则覆盖率随运行时长变化）。
- 实测（一组模型、80 km/h、0.40 s）：接触带中位宽度 **16.0 mm**（14–17 mm），头宽在冠下 1 mm 处 **37.15 mm**、
  5 mm 处 **61.46 mm**；覆盖率 **41.7 %（1 mm）/ 32.8 %（2 mm）/ 25.7 %（5 mm，主口径）/ 22.9 %（10 mm）**，
  逐轨 24.3–27.0 %。预注册判定 **contact band only**：结果里不得使用"面"这个词。
- 由此得到的算术：要覆盖 90 %，`ceil(0.9 × 37.15 / 16.0) = 3`，即**至少三条不同横向偏移的过车**；
  同一位置跑十次仍是 42 %。精度必须与覆盖率并列报。
- `tests/test_obs_region.py` 4 项：带宽中位数 16.0 mm、主口径覆盖率 0.257、覆盖率随分母深度单调不增、
  三条偏移的算术被钉住。`4 passed in 0.55 s`。
- 文档 `docs/OBSERVED_REGION_2026-10-31.md`；任务书 §十一 M4 行与新增 §十八。

## Round 250 - the forward operator on a known surface bump (M5 step 1)

Added `scripts/s112_surface_sensitivity.py` and `docs/SURFACE_SENSITIVITY_2026-10-31.md`. A Gaussian
bump (50/100/200 um, sigma 1.2 m at 58.5 m) on the blade body's stations was run through the canonical
one-set case four times (0.60 s, 80 km/h, 1201 frames, 7/7 gates each). The axle-box response is
visible (29-84 % of the baseline's own peak), localised to the bumped rail (L/R 0.14-0.18) and to the
bumped station (peak within 1.0 m), but **not monotone**: the gain is 0.01273 -> 0.01859 -> 0.00924
(m/s^2)/um. The reason is a branch switch, not a gain: the stock body drops out for 0 / 37 / 161 of
the 314 crossing frames while the blade maximum goes 59.5 -> 61.5 -> 62.1 kN, and the static
penetration is 63.70 um, so the linear regime ends at about 0.8 of it. Consequence recorded for M7:
acceleration is the localiser, the per-body load split is the amplitude carrier. The run index now
carries `notes` so a training set can be built from it without opening every `meta.json`.

## Round 251 - inverting the bump out of the load split (M5 step 2)

Added `scripts/s113_profile_inversion.py`, `docs/LOAD_SPLIT_INVERSION_2026-10-31.md` and
`tests/test_load_split_inversion.py`. The split between the two bodies of the right rail
(`blade/(stock+blade)`, median-filtered over 0.20 m) is inverted through a monotone table fitted on the
50 um run only, and applied to the two amplitudes it never saw.

  amplitude   peak_true   peak_est   rel err   p95 |e|   peak at   gates
       50 um       50.0       56.8    0.0137     15.0      58.36   pass/pass/pass
      100 um      100.0       76.5    0.0469     49.0      58.24   fail/fail/fail
      200 um      200.0      101.7    0.1966    147.5      57.98   fail/fail/fail

Hold-out verdict: fails. The reason is an extrapolation failure of the calibration set, not silence of
the observable: the table spans u in [-58.6, +14169] um because a 50 um bump never closes the gap
further, while a 100/200 um bump drives u to -109/-209 um where the estimator clamps. Inside the range
the same estimator gives +13.7 % on the peak and p95 15.1 um (0.23 x the static penetration), with the
peak 0.14 m from truth. Recorded for M7: parametrise by amplitude (solve for z inside the contact
model) instead of tabulating one amplitude's samples, and keep masking frames where the blade carries
nothing -- those are unobserved, not zero.
## Round 252 - three estimators for one bump, and why one pass cannot give its amplitude (M5 step 3)

Added `scripts/s114_parametric_split.py`, `docs/THREE_ESTIMATORS_2026-10-31.md` and
`tests/test_parametric_split.py`. Two further estimators are tested against the same three known bumps
and the same pre-registered gates:

  T  monotone table (round 251)      in range: peak +13.7 %, p95 15.0 um, station 0.14 m
                                     out of range: clamps (76.5 / 101.7 for 100 / 200 um)
  P  two-parameter tanh, leave-one-out   extends past its samples but inverts badly near sigma = 1:
                                     peaks 127.6 / 217.5 / 227.1 um for 50 / 100 / 200 um -- 0/3 folds pass
  S  zero-parameter transfer station   z = d(s*): 21.2 / 36.9 / 60.4 um against 48.6 / 93.0 / 167.8 um

The single number behind all three failures: the gap at which the load halves is 27.4 / 56.1 / 107.4 um
below flush for the three amplitudes, i.e. it moves, because the stock is being unloaded at the same time
(round 250: its zero-force frames go 0 / 37 / 161). So the split is not a function of the gap alone and
any sigma = f(u) estimator is mis-specified once the bump unloads the stock. Recorded for M7: put the
contact/load-transfer model inside the inversion, and treat a single pass as one transfer-station
equation -- the ensemble of >= 3 lateral offsets that M4's arithmetic already demanded is also what the
amplitude needs.
## Round 253 - the contact model inside the inversion, and the physics it still lacks (M5 step 4)

Added `scripts/s115_model_inversion.py`, `docs/MODEL_BASED_INVERSION_2026-10-31.md` and
`tests/test_model_inversion.py`. Round 252's prescription was to stop tabulating one amplitude's samples
and solve for the surface inside a forward model of the split. That model is now in: each body carries
`F = C * max(0, penetration) ** 1.5`, the common wheel height is solved so the two forces add to the
measured axle load, and the stock clips at zero (the branch). Inversion is a root find per frame; the two
stiffnesses are fitted on two amplitudes and applied to the third.

  fold   calibration      C_stock          C_blade      held out  peak_true  peak_est  p95 (um)  at s
         (100, 200)       4.704e10         4.033e10     50        50.0      102.8     63.5    58.51
         (50, 200)        5.426e10         4.613e10     100      100.0      129.7     88.6    58.29
         (50, 100)        1.276e11         7.998e10     200      200.0      121.7    113.9    58.02

0/3 folds pass all three gates. The fitted stiffnesses are physical (the frozen contact stiffness is
1.1267e11 N/m^1.5), which is the useful part: the model is not absurd, it **compresses the amplitude
scale** -- 50 um reads 102.8, 200 um reads 121.7 -- and the fold that only sees small amplitudes fits a
softer C (4.7e10) than the fold that sees both large ones (1.28e11).

The missing physics is named rather than absorbed: the canonical case is `local_compliant`, so **both
bodies sink by tens of micrometres under load, of the same order as the bump**, and that sink is not in
the model. It also explains the C drift, because the sink depends on the load. Four estimator families
now fail with four different modes (table, tanh, transfer station, contact model), localisation works in
all of them (<= 0.52 m), and the conclusion is about the measurement: one pass of one axle does not
determine the bump amplitude. The ensemble of >= 3 lateral offsets is the mechanism, and its forward
model must carry both bodies' support compliance.

## Round 254 - the split law measured, and round 253's explanation retracted (M5 step 5)

Added `scripts/s116_support_sink.py`, `scripts/s117_split_law.py`, `docs/SPLIT_LAW_MEASURED_2026-10-31.md`
and `tests/test_split_law.py`. Round 253 named "the two bodies' support compliance" as the missing physics.
It was measured first, and it is **wrong**: a `local_compliant` track has one node pair per rail and the
stock and blade are two bodies on that same node, so they cannot sink differently.  Seated, all eight rails
sink by identically **-1202.6962 um** (`F/sink = -5.002e7 N/m` against the case's `k_z = 5.0e7`), the span
across rails is **0.00 um**, and the gap `d = stock - blade` is a difference of two surfaces on one node, so
the common descent cancels.  The mechanism is retired in the document rather than quietly deleted.

So the law itself was measured: lift or lower the whole blade body and re-seat, with the probe seated at
**58.0 m** (inside the blade body's 50.578-104.419 m range; the canonical 50.0 m has no blade geometry at all,
which is why the first attempt returned sigma = 0 for every offset).

  offset (um)  stock (kN)  blade (kN)  sigma   half width (mm)
      -250.0        0.00       60.20   1.0000       6.000
      -150.0        6.05       53.86   0.8990       5.750
       -80.0       37.95       22.16   0.3687       6.472
       -40.0       55.71        4.45   0.0739       7.468
       +20.0       60.15        0.00   0.0000       7.468

The split reaches one half at **-97.3 um** of blade raise, the whole dynamic range occupies about **210 um**
of blade height (steepest 0.00758 per um), and the contact half-width moves **5.750 -> 7.468 mm (1.30x)**
across it, because the blade's strip is narrower than the stock's.  That is the compression: the bumps under
test are 50/100/200 um, the law lives in 210 um, and one stiffness per body has to average over a 30 % change
in the footprint -- which it does by rescaling the height axis (round 253: 50 um read as 102.8, 200 um as
121.7).  A descriptive two-parameter fit `sigma = 1/(1 + (g/g0)^p)` gives `g0 = 72.6 um`, `p = 6.000`
(rmse 0.028 in sigma); p = 6 is the measure of how far the real law is from a one-stiffness Hertz law.

Recorded for the next step: the estimator's forward model must carry the **footprint width as a function of
the split**, not a single `C` per body; and the split law now has to be checked for mileage and speed
dependence, since the blade's own section narrows towards the tip.

## Round 255 - the split law does not collapse: it shifts with the blade's section width (M5 step 6)

Added `scripts/s118_split_law_vs_station.py`, `docs/SPLIT_LAW_VS_MILEAGE_2026-10-31.md` and
`tests/test_split_law_station.py`. Round 254 measured the law at one station; the question here is whether it
collapses onto one curve in height-above-flush coordinates, which is what an estimator keyed on `u = d - z`
needs. It does not.

The coordinate mattered: at 52 m the blade sits 7.8 mm down, so a +-250 um absolute offset never reaches it.
The probe therefore raises the blade by `d(s) + delta` (delta = height above flush) at 52/54/56/58/60/62 m.

  station   design gap   +250   +100    +50     +0    -50   -100   -200   half width at delta=0
    52.0        7811.0    nan   0.071  0.019  0.000  0.000  0.000  0.000        7.468
    58.0          41.1  1.000   0.836  0.453  0.080  0.000  0.000  0.000        7.468
    60.0         -14.0  1.000   1.000  0.923  0.519  0.106  0.000  0.000        6.234
    62.0         -21.3  1.000   1.000  0.909  0.497  0.089  0.000  0.000        6.472

Two things fall out. The probe's zero is right: where the design gap is ~0 (60.0, 62.0 m) the split at
delta = 0 is **0.519 / 0.497**, i.e. level surfaces share the load in half. And the height at which the blade
wins half the load, in absolute raise, is **+97.3 um at 58.0 m (45 mm section), -16.3 um at 60.0 m (63 mm),
-21.0 um at 62.0 m (72.2 mm)** -- it moves 113 um between the narrow and the wide section and then saturates.
The section width is read from the station file names, so the predictor is geometry, not a fitted constant.

The footprint moves too: half width at delta = 0 is 7.468 mm from 52 to 58 m, 6.234 mm at 60 m, 6.472 mm at 62 m.

**A pre-registered verdict is corrected in the document.** The script carried "spread <= 100 um = collapses"
and printed that verdict because the three measurable crossings span 58.4 um. That threshold is wrong for this
question: the shift is monotone in section width and 4.6 times the threshold's slack, so the honest statement
is the opposite -- the law shifts with width, and an estimator keyed only on `u = d - z` will be biased
wherever the section is narrow, which is exactly the switch panel (10 -> 45 mm over 52-58 m).

Coverage is stated rather than glossed: only 3 of 6 stations reach sigma = 0.5 inside the grid, because at
52/54/56 m the blade is 7.8/2.5/1.1 mm down and a lift that large leaves the stock carrying nothing, so the
vertical seat has no solution (those cells are recorded as nan with the failure string).

## Round 256 - resolve the split law by section width: the small fold improves, the observable saturates

Added `scripts/s119_width_aware_inversion.py`, `docs/WIDTH_AWARE_INVERSION_2026-10-31.md` and
`tests/test_width_aware_inversion.py`.  Round 255 found the split law does not collapse in height-above-flush
coordinates; this applies the width-resolved law and re-runs the three amplitudes with **no fitting to the
bump runs at all** (law from the s118 static probes, geometry from the case, widths from station file names,
split from the archived runs), so all three are hold-outs.

A sign had to be fixed first: the first version took `u = -delta` and every anchor came out mirrored.  In
s118 `delta_um` *is* the gap the probe imposed, so `u = +delta`; the anchors then read 45.2 mm -> +56.15 um,
62.5 mm -> -2.27 um, 72.2 mm -> +0.34 um, and 41.1 + 56.15 = 97.25 reproduces the absolute-raise number
quoted in round 255.

  amp   peak_est  peak_true   rel%    p95(um)   at s    w(mm)   gates
   50       52.6       50.0    0.53     160.8   57.98    45.0    Y/n/n
  100       63.0      100.0    7.41     210.6   57.81    43.7    n/n/n
  200       62.1      200.0   27.59     236.2   57.58    42.0    n/n/n
  folds passing all three gates: 0/3

Two things are true at once and are reported separately.  Width-awareness does correct the small end: the
50 um fold goes from 1.37 % to 0.53 % relative.  It does not carry the large ones, and the reason is the
observable, not the model: once the bump closes the gap past about -50 um the split saturates at sigma -> 1
and the inversion is clamped at the end of the measured curve, so 100 and 200 um both read about 62 um.

What survives in the saturated regime is *where* saturation starts: the peak station moves 57.98 -> 57.81 ->
57.58 m for 50 -> 100 -> 200 um, monotone, 0.17-0.23 m per step.  That is the same quantity the zero-parameter
family of round 252 called the transfer-station equation, now read through a width-aware law.

Known blind spot, stated: 11 of 158 blade stations sit below the 45 mm measurement floor and are clamped.

## Round 257 - the saturation-onset station carries the amplitude, down to 1.4 um per frame

Added `scripts/s120_onset_resolution.py`, `docs/ONSET_STATION_2026-10-31.md` and
`tests/test_onset_resolution.py`.  Round 256 left exactly one quantity alive above the knee of the load split:
where the split saturates.  This round defines it on the rising flank (first station with a smoothed blade share
of 0.95) and measures it across six new amplitudes chosen to straddle the knee (20, 30, 40, 60, 80, 120 um), each
a 0.60 s run at 80 km/h, 1201 frames, seven gates 7/7.

  amp    onset      peak     share max   step
  20     never saturates       < 0.95     -
  30     never saturates       < 0.95     -
  40     never saturates       < 0.95     -
  50     58.500 m   58.511     0.959      -
  60     58.422 m   58.511     0.995      7 frames
  80     58.322 m   58.367     1.000      9 frames
 100     58.256 m   58.300     1.000      6 frames
 120     58.178 m   58.233     1.000      7 frames
 200     57.989 m   58.033     1.000     17 frames

  monotone PASS / resolvable (>= 1 frame) PASS / collapsed no
  onset = 58.610 m - 3.270 mm per um * amplitude, max residual 53 mm

One output frame (11.11 mm) is worth 3.4 um of amplitude on average, and 1.4 um at the 50-60 um end where the
slope is steepest (7.8 mm/um) -- between five and sixteen times finer than the 22 um absolute gate, and the only
amplitude observable so far that is not limited by saturation.

Two boundaries are recorded rather than smoothed over.  The observable **does not exist below about 50 um**: at
20, 30 and 40 um the split never reaches 0.95 in the pass, so there is no onset station, and small corrugation
still has to go through the acceleration bands.  And it is calibrated on one bump shape (centre 58.5 m, sigma
1.2 m, blade only, one speed), so it is a local calibration and not yet a general operator.

The previous turn's summary described this campaign as already finished, with case digests that did not exist on
disk.  That was wrong, the campaign was built and run here, and section 7 of the document records the correction
along with the real digests.

## 第 258 轮：起始站位锚在坡道上（2026-10-31）

第 257 轮那张"站位给幅值"的表是在一个形状上量的，本轮先预注册塌缩假设（`onset − centre = σ·F(幅值)`），再
用四个 0.6 s 运行（σ 0.6/2.4、中心 57.5/59.5，各 1201 帧、七门 7/7）去判它——**两条都否掉**：σ 变 4 倍只挪
33 mm，鼓包平移 ±1 m 只挪 67 mm，onset 始终停在 ~58.3 m。

**所以 onset 跟的是坡道，不是鼓包**：形状与位置在坡道区内合计 144 mm，而幅值 50→200 µm 给 511 mm ⇒ 幅值主导
3.5 倍，一张表可跨形状与位置搬。代价是近 100 µm 的局部斜率 3.3 mm/µm 把 144 mm 折成 **~44 µm**，是 22 µm
绝对门的两倍，必须进误差预算而不是被忽略。

新增 `scripts/s121_shape_collapse.py`、`tests/test_shape_collapse.py`（10 项，含"两条塌缩保持被否"的回归）、
`docs/ONSET_SHAPE_2026-10-31.md`、报告 `reports/load_split_inversion_2026-10-31/shape_collapse.json`；
任务书 §二十五；冻结基线 UNCHANGED。

## 第 259 轮：目标改成"光带"，横向可辨识宽度 4 mm，过车次数 3 → 9（2026-10-31）

用户口径定案：只要轮轨接触面（光带），不要整个三维曲面。本轮把"光带有多宽"量出来：预注册两个曲率模型
（双曲率 `w(100 µm)=6.9 mm`、只算轨冠 7.7 mm），用七趟 0.6 s 运行把 100 µm 凸起沿横向扫 0/2/4/5/6/8/10 mm，
**两者都被否掉，实测更窄**——2 mm 掉到 41.7 %、4 mm 只剩 1 %，半宽 ≈1.7 mm、1 % 宽 ≈4.0 mm。

由此改写 M4 的过车次数：`ceil(0.9×37.15/4) = 9` 趟（50 µm 约 13 趟）；原先"3 趟"用的是条带搜索窗 16 mm，
那不是可辨识宽度，作废。反推 `R_eff ≈ 80 mm`，说明决定可辨识性的是接触的有效横向尺寸，不是两个名义半径。

新增 `scripts/s122_lateral_observability.py`、`tests/test_lateral_observability.py`（7 项）、
`docs/LATERAL_OBSERVABILITY_2026-10-31.md`、报告 `reports/load_split_inversion_2026-10-31/lateral_observability.json`；
任务书 §二十六；冻结基线 UNCHANGED。

<!-- DOCS:ALL:BEGIN -->
## 完整文档清单（由 `scripts/gen_docs_index.py` 生成，测试会检查是否过期）

| 文件 | 首行标题 |
|---|---|
| [A1_STRIP_WINDOW_2026-10-22.md](A1_STRIP_WINDOW_2026-10-22.md) | A1：条带接触窗（bounded strip patch） |
| [A2_C_DELTA_DEGENERACY_2026-10-22.md](A2_C_DELTA_DEGENERACY_2026-10-22.md) | A2 C–δ 简并排查（2026-10-22） |
| [A3_MULTIPATCH_2026-10-22.md](A3_MULTIPATCH_2026-10-22.md) | A3 同步多斑 + 局部弹性分配 —— 实测：**前提不成立，局部分配已经存在** |
| [AGENT_TOOL_LAYER_2026-10-22.md](AGENT_TOOL_LAYER_2026-10-22.md) | Velch AI 调用层设计（Agent Tool Layer，2026-10-22） |
| [AI_INTERFACE_ARCHITECTURE_2026-10-22.md](AI_INTERFACE_ARCHITECTURE_2026-10-22.md) | Velch 软件分层与 AI 接口架构（设计草案） |
| [ALIGNMENT_CONVENTIONS_2026-10-28.md](ALIGNMENT_CONVENTIONS_2026-10-28.md) | 物理层审查：线形、蠕滑、离心力、超高，一共四处手性 |
| [ARCHITECTURE_2026-10-21.md](ARCHITECTURE_2026-10-21.md) | Velch 架构收口与 Simpack 2021x 对标（2026-10-21） |
| [ASSESSMENT_2026-10-20.md](ASSESSMENT_2026-10-20.md) | 标准评价指标（assess）：把仿真输出变成可判读的结论 |
| [AUDIT_FIXES_2026-10-26.md](AUDIT_FIXES_2026-10-26.md) | 2026-10-26 只读审查的七个缺陷与修法 |
| [AXLEBOX_RESTRAINT_2026-10-26.md](AXLEBOX_RESTRAINT_2026-10-26.md) | 轴箱的转动约束：13.094 Hz 无阻尼模态从哪里来，怎么去掉 |
| [B047_RETIREMENT_2026-10-31.md](B047_RETIREMENT_2026-10-31.md) | B047 退役：横向"刚度硬 927 倍"是两条不同刚度的比较，不是缺陷（2026-10-31） |
| [B2_EVENT_INTEGRATION_2026-10-22.md](B2_EVENT_INTEGRATION_2026-10-22.md) | B2 事件化积分 / 峰值分辨率（2026-10-22） |
| [B3_TABLE_AMORTIZATION_2026-10-22.md](B3_TABLE_AMORTIZATION_2026-10-22.md) | B3 接触表按反演批次摊销（2026-10-22） |
| [B4_DESCRIPTOR_2026-10-22.md](B4_DESCRIPTOR_2026-10-22.md) | B4 接触状态描述子降维 —— 实测**负结果** |
| [B5_JACOBIAN_EVENTS_2026-10-22.md](B5_JACOBIAN_EVENTS_2026-10-22.md) | B5 雅可比作事件检测（2026-10-22） |
| [BAND_ASSEMBLY_2026-10-31.md](BAND_ASSEMBLY_2026-10-31.md) | M7 assembly: one light band, reconstructed end to end — and judged |
| [BAND_CAPABILITY_2026-10-26.md](BAND_CAPABILITY_2026-10-26.md) | 分带反演能力表：修掉三处测量错误之后 |
| [BAND_CLAIM_CLASS_2026-10-28.md](BAND_CLAIM_CLASS_2026-10-28.md) | 带幅值必须带"标定谱类"：从约定变成构造约束 |
| [bench_toolchain_design.md](bench_toolchain_design.md) | Velch 性能基准与剖析工具链（v1 最小可用设计） |
| [BLADE_LOWERING_DOUBLE_INJECTION_2026-10-31.md](BLADE_LOWERING_DOUBLE_INJECTION_2026-10-31.md) | 设计降低值被注入两次：尖轨比基本轨高 3.3 mm（B049） |
| [BUGS.md](BUGS.md) | 缺陷账本（BUGS） |
| [CAPABILITY_INVENTORY_2026-10-20.md](CAPABILITY_INVENTORY_2026-10-20.md) | 能力清单：现在的 Velch 到底准备好了什么（2026-10-20） |
| [COMPUTE_BUDGET_2026-10-19.md](COMPUTE_BUDGET_2026-10-19.md) | Velch 计算效率：与 Simpack 的同工况对比、热点归因与提速路线 |
| [CONTACT_GEOMETRY_ERROR_BOUND_2026-10-21.md](CONTACT_GEOMETRY_ERROR_BOUND_2026-10-21.md) | 接触几何误差界：样条解析 vs 密网格 2026-10-21 |
| [CONTACT_GEOMETRY_ERROR_BOUND_REAL_2026-10-21.md](CONTACT_GEOMETRY_ERROR_BOUND_REAL_2026-10-21.md) | 接触几何误差界（真实断面）2026-10-21 |
| [CONTACT_GEOMETRY_SEGMENTED_2026-10-21.md](CONTACT_GEOMETRY_SEGMENTED_2026-10-21.md) | 分段样条 vs 密网格（真实断面）2026-10-21 |
| [CONTACT_MAP_2026-10-21.md](CONTACT_MAP_2026-10-21.md) | 接触图（contact map）：把每步几何搜索降级为插值 |
| [CONTACT_MAP_AMORTIZATION_2026-10-21.md](CONTACT_MAP_AMORTIZATION_2026-10-21.md) | 接触图：摊销不可能，接线前必须先算清这笔账 |
| [CONTACT_NATIVE_INTEGRATION_2026-10-19.md](CONTACT_NATIVE_INTEGRATION_2026-10-19.md) | CONTACT 原生接触求解接入记录（2026-10-19） |
| [CONTACT_POLICY_ARCHITECTURE_2026-10-20.md](CONTACT_POLICY_ARCHITECTURE_2026-10-20.md) | 接触策略层：可插拔接口、首轮 A/B 结果与创新路线（2026-10-20） |
| [CONTACT_REFERENCE_THREE_WAY_2026-10-21.md](CONTACT_REFERENCE_THREE_WAY_2026-10-21.md) | 三方对拍：解析真值 / 45 µm 网格 / 分段样条 2026-10-21 |
| [CONTACT_SEARCH_LOCAL_2026-10-19.md](CONTACT_SEARCH_LOCAL_2026-10-19.md) | 轮轨接触搜索：型面表化 + 局部连续搜索（2026-10-19） |
| [CORRUGATION_IN_PRR_2026-10-26.md](CORRUGATION_IN_PRR_2026-10-26.md) | 在连续的 PRR 文件里模拟波磨：表示、密度与两个坑 |
| [COVERAGE_HELDOUT_2026-10-28.md](COVERAGE_HELDOUT_2026-10-28.md) | Held-out coverage, and why the measured verdict had to be made reproducible first |
| [CRH380A_M_REAL_SIMPACK_VALIDATION_2026-10-19.md](CRH380A_M_REAL_SIMPACK_VALIDATION_2026-10-19.md) | CRH380A_M 刚性模型真实 Simpack 验证记录（2026-10-19） |
| [CRH380A_M_VALIDATION_2026-10-19.md](CRH380A_M_VALIDATION_2026-10-19.md) | CRH380A_M 刚性模型作为 Velch 验证算例的检查记录 |
| [CROWN_OFFSET_SWEEP_2026-10-31.md](CROWN_OFFSET_SWEEP_2026-10-31.md) | M2 第一轮：冠偏移扫描——四条门无一成立（2026-10-31） |
| [CURVE_ALIGNMENT_VELOCITY_2026-10-28.md](CURVE_ALIGNMENT_VELOCITY_2026-10-28.md) | 曲线：把路线自己的横向速度装回去，以及为什么几何路由仍然拿不住这条曲线 |
| [CURVE_APPROACH_DECISIONS_2026-10-27.md](CURVE_APPROACH_DECISIONS_2026-10-27.md) | 曲线走进哪一侧：四条被实测否掉的路，和一条还没被否的 |
| [CURVE_CANT_DECISION_2026-10-27.md](CURVE_CANT_DECISION_2026-10-27.md) | ADR：几何路由上的超高，为什么仍然拒绝 |
| [CURVE_COROTATING_FRAME_2026-10-28.md](CURVE_COROTATING_FRAME_2026-10-28.md) | 曲线：站表路线 + 帧的横向加速度，以及为什么它现在还不能引用 |
| [CURVE_GEOMETRY_2026-10-26.md](CURVE_GEOMETRY_2026-10-26.md) | 曲线：先把"几何"和"力"分开（S1 实测） |
| [CURVE_LATERAL_CAPABILITY_2026-10-28.md](CURVE_LATERAL_CAPABILITY_2026-10-28.md) | 曲线缺口到底是不是"算法不够好"：把接触能提供多少横向力量出来 |
| [CURVE_LATERAL_RESTORING_2026-10-28.md](CURVE_LATERAL_RESTORING_2026-10-28.md) | 横向回复刚度：模型不是「没有回复」，而是硬了 927 倍（2026-10-28，第 206 轮） |
| [CURVE_LATERAL_SIGN_2026-10-28.md](CURVE_LATERAL_SIGN_2026-10-28.md) | 曲线工况的离心力符号：一个符号翻转把净横向力从 −78 % 变成 +69 % |
| [CURVE_PATH_RATE_DEFECT_2026-10-28.md](CURVE_PATH_RATE_DEFECT_2026-10-28.md) | 曲股工况为什么跑不过 81 m：路线的横向速率被当成了横向蠕滑 |
| [CURVE_QUASISTATIC_SEAT_2026-10-28.md](CURVE_QUASISTATIC_SEAT_2026-10-28.md) | 曲股能不能"坐"出一个静态平衡？——滚动静平衡实验（否定结论） |
| [CURVE_RAIL_GEOMETRY_2026-10-28.md](CURVE_RAIL_GEOMETRY_2026-10-28.md) | 曲股右轨的站位表不是一条一致的轨道几何（B041） |
| [CURVE_ROUTE_COMPARISON_2026-10-28.md](CURVE_ROUTE_COMPARISON_2026-10-28.md) | 曲线两条路线各自的缺口（2026-10-28） |
| [CURVE_SEAT_AND_CREEP_2026-10-27.md](CURVE_SEAT_AND_CREEP_2026-10-27.md) | 曲线：先把静平衡问对，再把曲率放进蠕滑 |
| [CURVE_TILTED_FRAME_2026-10-28.md](CURVE_TILTED_FRAME_2026-10-28.md) | 倾斜坐标系：超高让曲线从"不可能"变成"可行"（2026-10-28，第 205 轮） |
| [CURVE_YAW_BALANCE_2026-10-28.md](CURVE_YAW_BALANCE_2026-10-28.md) | 曲线为什么停不下来：摇头平衡被量到闭合（2026-10-28） |
| [CURVE_YAW_STABILITY_2026-10-28.md](CURVE_YAW_STABILITY_2026-10-28.md) | 摇头刚度与 Kalker 蠕滑都不能让曲线稳定（2026-10-28，第 204 轮） |
| [DAMPING_CALIBRATION_2026-10-21.md](DAMPING_CALIBRATION_2026-10-21.md) | 接触阻尼定标：无效（负结果） |
| [DEVELOPMENT_GATES.md](DEVELOPMENT_GATES.md) | Velch 后续开发与验收门 |
| [DIVERGING_ROUTE_2026-10-21.md](DIVERGING_ROUTE_2026-10-21.md) | 曲向（diverging route）装配 — 阶段 1 记录（2026-10-21） |
| [EFFECTIVE_RADIUS_RETIRED_2026-10-30.md](EFFECTIVE_RADIUS_RETIRED_2026-10-30.md) | 20 mm 等效半径退役：模型终于在自己写的 oracle 上运行（B048，选项 A） |
| [ELEMENT_CATALOGUE_2026-10-23.md](ELEMENT_CATALOGUE_2026-10-23.md) | 元件目录与 Simpack 对照 |
| [EVIDENCE_MAP.md](EVIDENCE_MAP.md) | 证据地图：这一版凭什么可以说「可以发布」 |
| [FLEXIBLE_WHEELSET_PORT_2026-10-24.md](FLEXIBLE_WHEELSET_PORT_2026-10-24.md) | 柔性轮对移植：SDITT 的数据契约与我们的落点（2026-10-24） |
| [FORCE_ELEMENT_LIBRARY_2026-10-23.md](FORCE_ELEMENT_LIBRARY_2026-10-23.md) | 力学元件库 |
| [FROG_WINDOW_BREAKTHROUGH_2026-10-21.md](FROG_WINDOW_BREAKTHROUGH_2026-10-21.md) | 辙叉窗突破：脱空归零，宽带频谱塌回 Simpack 量级 |
| [GOAL_STATUS_2026-10-23.md](GOAL_STATUS_2026-10-23.md) | 整体目标：完成度与差距 |
| [HARMONIC_LADDER_INVERSION_2026-10-26.md](HARMONIC_LADDER_INVERSION_2026-10-26.md) | 谐波阶梯反演：用一条缺陷的谐波序列恢复它的**形状**（2026-10-26） |
| [INNOVATION_SPRINT_2026-10-22.md](INNOVATION_SPRINT_2026-10-22.md) | 创新冲刺 2026-10-22（B1 步长上限 → A1 接触窗 → B4 描述子降维 → …） |
| [INVERSION_DEMO_2026-10-20.md](INVERSION_DEMO_2026-10-20.md) | 合成反演：可辨识性门 + 高斯‑牛顿（2026-10-20） |
| [INVERSION_PIPELINE_2026-10-27.md](INVERSION_PIPELINE_2026-10-27.md) | 反演流水线 L0/L1：先把数据准入与配准做成可判定的门 |
| [INVERSION_VERDICT_2026-10-28.md](INVERSION_VERDICT_2026-10-28.md) | 实测反演的判定页（L0–L5） |
| [JOINT_INVERSION_2026-10-31.md](JOINT_INVERSION_2026-10-31.md) | M7 step 2: joint forward fit — 2 parameters instead of 25 |
| [LATERAL_DRIFT_2026-10-31.md](LATERAL_DRIFT_2026-10-31.md) | M2 时程：整车横向游走 0.73 mm/0.40 s，源头是 +718 N 的净横向力（2026-10-31） |
| [LATERAL_FORCE_SAMPLING_2026-10-31.md](LATERAL_FORCE_SAMPLING_2026-10-31.md) | 横向力的来源：不是蠕滑，是采样的阶梯（B050） |
| [LATERAL_OBSERVABILITY_2026-10-31.md](LATERAL_OBSERVABILITY_2026-10-31.md) | 光带（接触面）作为目标：横向可辨识宽度实测（第 259 轮，2026-10-31） |
| [LATERAL_REGISTRATION_BASELINE_2026-10-31.md](LATERAL_REGISTRATION_BASELINE_2026-10-31.md) | 横向注册的当前基线（M2 第一步）：对"最完备的车"重新量一遍，结果比旧数更糟 |
| [LATERAL_SEAT_JOINT_2026-10-31.md](LATERAL_SEAT_JOINT_2026-10-31.md) | 横向座椅联立：链条一起解，还是逐个轮对解？（B051） |
| [LAYERED_TRACK_2026-10-20.md](LAYERED_TRACK_2026-10-20.md) | 分层轨道（layered track）：钢轨 / 扣件 / 轨枕 / 板下胶垫 / 轨道板 |
| [LITERATURE_LOG.md](LITERATURE_LOG.md) | 文献日志（任务书要求：碰到具体问题才查，登记 DOI/URL 与"它解决了什么"） |
| [LOAD_SPLIT_INVERSION_2026-10-31.md](LOAD_SPLIT_INVERSION_2026-10-31.md) | Inverting the bump out of the load split (M5, step 2) |
| [LONGITUDINAL_WHEELSET_2026-10-25.md](LONGITUDINAL_WHEELSET_2026-10-25.md) | 轮对纵向自由度：让轴箱纵向通道有物理来源（2026-10-25） |
| [LOWERING_INVERSION_2026-10-29.md](LOWERING_INVERSION_2026-10-29.md) | 降低值反演：尖轨能定位、幅值不可辨识；心轨降低值本来就在几何里 |
| [LOWERING_KNOB_2026-10-29.md](LOWERING_KNOB_2026-10-29.md) | 降低值旋钮可用，但两条刚性路线都卡在同一处站表拼接 |
| [LOWERING_READING_ARBITRATION_2026-10-31.md](LOWERING_READING_ARBITRATION_2026-10-31.md) | M3 收口：R2 尖轨"何时到达走行面"的五个读数，是谁算错了 |
| [LOWERING_VALUE_TRUTH_2026-10-29.md](LOWERING_VALUE_TRUTH_2026-10-29.md) | 用「降低值」做反演验证：想法成立，但真值不在现有几何数据里（2026-10-29，第 207 轮） |
| [MEASURED_MULTIPASS_2026-10-28.md](MEASURED_MULTIPASS_2026-10-28.md) | 四次过车 × 六个区段：单次 3–4/6，融合 6/6 |
| [MEASURED_VALIDATION_2026-10-21.md](MEASURED_VALIDATION_2026-10-21.md) | 实测数据接入验证（2026-10-21） |
| [MEASURED_VALIDATION_2026-10-26.md](MEASURED_VALIDATION_2026-10-26.md) | 实测数据第一次验证：26 mm 波磨，声学 5/6、轴箱 3/6 |
| [MEASUREMENT_CAPABILITY_2026-10-27.md](MEASUREMENT_CAPABILITY_2026-10-27.md) | 实测侧能力声明（2026-10-27） |
| [MODEL_BASED_INVERSION_2026-10-31.md](MODEL_BASED_INVERSION_2026-10-31.md) | Putting the contact model inside the inversion (M5, step 4) |
| [NONLINEAR_ELEMENTS_2026-10-23.md](NONLINEAR_ELEMENTS_2026-10-23.md) | 非线性力元 |
| [OBSERVATION_LAYER_2026-10-20.md](OBSERVATION_LAYER_2026-10-20.md) | 观测量层：仿真对仿真 + 实测对模型（2026-10-20） |
| [OBSERVED_REGION_2026-10-31.md](OBSERVED_REGION_2026-10-31.md) | 一次过车只能看见一条带，不是一张面（M4：Ω_obs 与覆盖率） |
| [OMA_MEASURED_2026-10-27.md](OMA_MEASURED_2026-10-27.md) | 运行模态识别（SSI-FCM）接到实测：算法通过，实测上不收敛 |
| [ONBOARDING_2026-10-21.md](ONBOARDING_2026-10-21.md) | 新增车体 / 新增道岔的接入指南 |
| [ONE_SET_CASE_2026-10-31.md](ONE_SET_CASE_2026-10-31.md) | 一组模型装进同一算例：完备车辆 + 柔性轮对 + 柔性轨道 + 真道岔几何（M1） |
| [ONSET_SHAPE_2026-10-31.md](ONSET_SHAPE_2026-10-31.md) | The onset station is anchored to the ramp, not to the bump (round 258, 2026-10-31) |
| [ONSET_STATION_2026-10-31.md](ONSET_STATION_2026-10-31.md) | The saturation-onset station: an amplitude carrier that survives the split's knee |
| [OPEN_SOURCE_WHEEL_RAIL_CONTACT_SURVEY_2026-10-19.md](OPEN_SOURCE_WHEEL_RAIL_CONTACT_SURVEY_2026-10-19.md) | 开源轮轨接触算法调查（2026-10-19） |
| [PACKAGING_2026-10-22.md](PACKAGING_2026-10-22.md) | 打包与安装包（Windows） |
| [PARALLEL_AND_SIMPACK_RWP.md](PARALLEL_AND_SIMPACK_RWP.md) | 多核并行、Simpack RWP 机制与 CONTACT 接入 |
| [PHYSICS_INVARIANTS.md](PHYSICS_INVARIANTS.md) | 物理不变量复算门 |
| [PORTABLE_PACKAGE_DESIGN_2026-10-26.md](PORTABLE_PACKAGE_DESIGN_2026-10-26.md) | 设计方案：把安装包拷到干净机器就能跑模型（含 33 阶柔性轮对） |
| [RACK_CASE_DATA_CONTRACT_2026-10-21.md](RACK_CASE_DATA_CONTRACT_2026-10-21.md) | 齿轨过岔算例：数据契约（2026-10-21） |
| [RAIL_CANT_2026-10-20.md](RAIL_CANT_2026-10-20.md) | 轨底坡 1:40：把"整体倾斜"换成"绕轨顶中心旋转" |
| [RANDOM_SPECTRUM_BANDS_2026-10-28.md](RANDOM_SPECTRUM_BANDS_2026-10-28.md) | 随机不平顺（随机相位带限谱）逐带反演：3/8 带达标，而且这次不是非线性的错 |
| [RANDOM_SPECTRUM_INVERSION_2026-10-25.md](RANDOM_SPECTRUM_INVERSION_2026-10-25.md) | 随机谱 → 加速度 → 反演随机谱：三次实测与它们各自的结论 |
| [RELEASE_NOTES_0.4.1.md](RELEASE_NOTES_0.4.1.md) | Velch 0.4.1 · 发布说明（2026-10-22） |
| [RELEASE_NOTES_0.4.10.md](RELEASE_NOTES_0.4.10.md) | Velch 0.4.10 发布说明（2026-10-23） |
| [RELEASE_NOTES_0.4.11.md](RELEASE_NOTES_0.4.11.md) | Velch 0.4.11 发布说明（2026-10-23） |
| [RELEASE_NOTES_0.4.12.md](RELEASE_NOTES_0.4.12.md) | Velch 0.4.12 发布说明 |
| [RELEASE_NOTES_0.4.13.md](RELEASE_NOTES_0.4.13.md) | Velch 0.4.13 发布说明 |
| [RELEASE_NOTES_0.4.14.md](RELEASE_NOTES_0.4.14.md) | Velch 0.4.14 发布说明 |
| [RELEASE_NOTES_0.4.15.md](RELEASE_NOTES_0.4.15.md) | Velch 0.4.15 发布说明 |
| [RELEASE_NOTES_0.4.16.md](RELEASE_NOTES_0.4.16.md) | Velch 0.4.16 发布说明 |
| [RELEASE_NOTES_0.4.17.md](RELEASE_NOTES_0.4.17.md) | Velch 0.4.17 发布说明 |
| [RELEASE_NOTES_0.4.18.md](RELEASE_NOTES_0.4.18.md) | Velch 0.4.18 发布说明 |
| [RELEASE_NOTES_0.4.19.md](RELEASE_NOTES_0.4.19.md) | Velch 0.4.19 发布说明 |
| [RELEASE_NOTES_0.4.2.md](RELEASE_NOTES_0.4.2.md) | Velch 0.4.2（2026-10-22 夜间） |
| [RELEASE_NOTES_0.4.20.md](RELEASE_NOTES_0.4.20.md) | Velch 0.4.20 发布说明 |
| [RELEASE_NOTES_0.4.21.md](RELEASE_NOTES_0.4.21.md) | Velch 0.4.21 发布说明 |
| [RELEASE_NOTES_0.4.22.md](RELEASE_NOTES_0.4.22.md) | Velch 0.4.22 发布说明 |
| [RELEASE_NOTES_0.4.23.md](RELEASE_NOTES_0.4.23.md) | Velch 0.4.23 发布说明 |
| [RELEASE_NOTES_0.4.24.md](RELEASE_NOTES_0.4.24.md) | 0.4.24：一台车只有一个定义 |
| [RELEASE_NOTES_0.4.25.md](RELEASE_NOTES_0.4.25.md) | Velch 0.4.25 |
| [RELEASE_NOTES_0.4.26.md](RELEASE_NOTES_0.4.26.md) | Velch 0.4.26 发布说明 |
| [RELEASE_NOTES_0.4.27.md](RELEASE_NOTES_0.4.27.md) | Velch 0.4.27 发布说明 |
| [RELEASE_NOTES_0.4.28.md](RELEASE_NOTES_0.4.28.md) | Velch 0.4.28 发布说明 |
| [RELEASE_NOTES_0.4.29.md](RELEASE_NOTES_0.4.29.md) | Velch 0.4.29 发布说明 |
| [RELEASE_NOTES_0.4.3.md](RELEASE_NOTES_0.4.3.md) | Velch 0.4.3 发布说明（2026-10-22 夜） |
| [RELEASE_NOTES_0.4.30.md](RELEASE_NOTES_0.4.30.md) | Velch 0.4.30 发布说明 |
| [RELEASE_NOTES_0.4.31.md](RELEASE_NOTES_0.4.31.md) | Velch 0.4.31 发布说明 |
| [RELEASE_NOTES_0.4.32.md](RELEASE_NOTES_0.4.32.md) | Velch 0.4.32 发布说明 |
| [RELEASE_NOTES_0.4.33.md](RELEASE_NOTES_0.4.33.md) | Velch 0.4.33 发布说明 |
| [RELEASE_NOTES_0.4.34.md](RELEASE_NOTES_0.4.34.md) | Velch 0.4.34 发布说明 |
| [RELEASE_NOTES_0.4.35.md](RELEASE_NOTES_0.4.35.md) | Velch 0.4.35 发布说明 |
| [RELEASE_NOTES_0.4.36.md](RELEASE_NOTES_0.4.36.md) | Velch 0.4.36 发布说明 |
| [RELEASE_NOTES_0.4.37.md](RELEASE_NOTES_0.4.37.md) | Velch 0.4.37 发布说明 |
| [RELEASE_NOTES_0.4.4.md](RELEASE_NOTES_0.4.4.md) | Velch 0.4.4 发布说明（2026-10-23 凌晨） |
| [RELEASE_NOTES_0.4.5.md](RELEASE_NOTES_0.4.5.md) | Velch 0.4.5 发布说明 |
| [RELEASE_NOTES_0.4.9.md](RELEASE_NOTES_0.4.9.md) | Velch 0.4.9 发布说明（2026-10-23） |
| [RELEASE_SERIES.md](RELEASE_SERIES.md) | Velch 发布序列 |
| [RESIDUAL_SMOOTHNESS_2026-10-21.md](RESIDUAL_SMOOTHNESS_2026-10-21.md) | 残差曲面光滑性：反演的准入条件 |
| [ROADMAP_BEYOND_SIMPACK.md](ROADMAP_BEYOND_SIMPACK.md) | Velch 路线图：借鉴 Simpack 并超越它（2026-10-20 起） |
| [S1_CHECKPOINT_2026-10-20.md](S1_CHECKPOINT_2026-10-20.md) | S1 检查点：解析接触几何（2026-10-20） |
| [S1C_GEOMETRY_POLICY_2026-10-20.md](S1C_GEOMETRY_POLICY_2026-10-20.md) | S1-c：接触点几何策略（`geometry_policy`）——实现、A/B、以及为什么它是空结果 |
| [S1D_STRIP_CONTACT_2026-10-20.md](S1D_STRIP_CONTACT_2026-10-20.md) | S1-d：分布接触（条带积分）——实现与 A/B |
| [S2_HANDOFF_2026-10-21.md](S2_HANDOFF_2026-10-21.md) | S2 工作交接：隐式积分（BDF）为什么跑不动，以及两条待走的路 |
| [S2_IMPLICIT_2026-10-21.md](S2_IMPLICIT_2026-10-21.md) | S2 隐式积分第一轮：BDF + 稀疏模板（2026-10-21 夜间） |
| [S2_IMPLICIT_DONE_2026-10-22.md](S2_IMPLICIT_DONE_2026-10-22.md) | S2 完成：隐式积分跑通，整程 8.4× 提速且物理不变 |
| [S2_REMAINING_PATHS_2026-10-21.md](S2_REMAINING_PATHS_2026-10-21.md) | S2 剩余两条路：施工规格与口径校正 |
| [S3_SAMPLE_FLEET_2026-10-21.md](S3_SAMPLE_FLEET_2026-10-21.md) | ﻿# S3 样本批量：theta 敏感度第一测（2026-10-21） |
| [S4_BAND_TABLE_2026-10-23.md](S4_BAND_TABLE_2026-10-23.md) | S4 决定性实验：逐波长带增益与噪声本底（第一次可用的表） |
| [S5_BLMA_2026-10-24.md](S5_BLMA_2026-10-24.md) | S5c 第一版 BLMA：条件数降到 15、0.1 m 与 2 m 带可复原到 13 %，0.5 m 带仍失手 |
| [S5_BLMA_ROUND32_2026-10-24.md](S5_BLMA_ROUND32_2026-10-24.md) | S5d：两带可用、0.5 m 卡在边界上——四判据的逐条结论 |
| [S5_CLOSURE_2026-10-24.md](S5_CLOSURE_2026-10-24.md) | S5e：闭环 8.39 % 通过、盲测通过，但绝对误差 65 % 未过 30 % 判据 |
| [S5_DUAL_2026-10-24.md](S5_DUAL_2026-10-24.md) | S5f：双带同时激励测出的 2×2 —— 两个估计器互相矛盾，线性反演到此为止 |
| [S5_INVERSION_2026-10-23.md](S5_INVERSION_2026-10-23.md) | S5 第一轮：按波长反演是**非唯一**的（本工况），并且能给出非唯一的量 |
| [S5_LINEARITY_2026-10-24.md](S5_LINEARITY_2026-10-24.md) | S5b 结论：线性可加性在任何测试幅值下都不成立——分带定量反演在本设计中不可达 |
| [S6_LIFTED_NEGATIVE_2026-10-24.md](S6_LIFTED_NEGATIVE_2026-10-24.md) | S6a：提升特征（Koopman 式）没有帮助 —— 但这次实验本身也不足以判决 |
| [S6_MULTICHANNEL_2026-10-24.md](S6_MULTICHANNEL_2026-10-24.md) | S6c：三个测点一起看 —— 多一个传感器买到的是什么 |
| [S6_MULTILEVEL_2026-10-24.md](S6_MULTILEVEL_2026-10-24.md) | S6b：波长 × 测点，信息量表（第一次尝试，含三条重要限制） |
| [S7_OBSERVATION_DESIGN_2026-10-24.md](S7_OBSERVATION_DESIGN_2026-10-24.md) | S7：该装哪一个通道——按"新增方向"而不是按"条件数下降"判 |
| [S7B_LATERAL_2026-10-24.md](S7B_LATERAL_2026-10-24.md) | S7b：把轴箱横向加速度装进观测集，然后量它到底买到了什么 |
| [S7C_CROSS_DIRECTION_2026-10-24.md](S7C_CROSS_DIRECTION_2026-10-24.md) | S7c：横向加速度能不能把"垂向/轨向"分开——可以，但代价是条件数 |
| [S7D_DISPLACEMENT_2026-10-24.md](S7D_DISPLACEMENT_2026-10-24.md) | S7d：车体↔轴箱相对位移能救 2 m 带吗——不能，而且否掉它的数字解释了文献为什么能 |
| [S7E_LONGWAVE_2026-10-24.md](S7E_LONGWAVE_2026-10-24.md) | S7e：长波段（20 m / 40 m）上相对位移真的带信号了——可它买不到精度 |
| [SAME_MODEL_COMPARISON_2026-10-22.md](SAME_MODEL_COMPARISON_2026-10-22.md) | 同模型效率对比：为什么不能直接吃 SDITT 的 6204 阶，以及怎么才算公平 |
| [SDITT_LINES_READER_2026-10-30.md](SDITT_LINES_READER_2026-10-30.md) | 照 SDITT 的做法读三条轨线：降低值全在断面里（2026-10-30） |
| [SDITT_TRACK_PROFILE_USAGE_2026-10-30.md](SDITT_TRACK_PROFILE_USAGE_2026-10-30.md) | SDITT 是怎么用这套道岔轨道的（第 224 轮，学习而非猜） |
| [SDITT_TRACK_TIMING_2026-10-22.md](SDITT_TRACK_TIMING_2026-10-22.md) | 采用 SDITT 柔性轨道参数时的耗时与对比（2026-10-22） |
| [SELFCHECK_2026-10-23.md](SELFCHECK_2026-10-23.md) | 第一次运行先跑自检（`velch selfcheck`） |
| [SHORTWAVE_INVERSION_2026-10-25.md](SHORTWAVE_INVERSION_2026-10-25.md) | 短波反演：把采样提到 20 kHz 之后，结论反过来了 |
| [SIMPACK_BOGIE_MINING_2026-10-23.md](SIMPACK_BOGIE_MINING_2026-10-23.md) | CRH380A 转向架子模型的深度挖掘（2026-10-23） |
| [SIMPACK_CARBODY_MINING_2026-10-23.md](SIMPACK_CARBODY_MINING_2026-10-23.md) | 车体子模型：把 `CRH380A_M_Carbody.spck` 读成数字 |
| [SIMPACK_COMPARE_2026-10-23.md](SIMPACK_COMPARE_2026-10-23.md) | Simpack 与 Velch 的定量对照（前轮对，23.5–138.5 m） |
| [SIMPACK_IMPORT_2026-10-22.md](SIMPACK_IMPORT_2026-10-22.md) | 从 Simpack 模型算一个算例（2026-10-22） |
| [SIMPACK_IRREGULARITY_MINING_2026-10-23.md](SIMPACK_IRREGULARITY_MINING_2026-10-23.md) | Simpack 里"轨道不平顺"是怎么装进模型的（齿轨模型取证） |
| [SINGLE_BAND_SWEEP_2026-10-28.md](SINGLE_BAND_SWEEP_2026-10-28.md) | 逐分量幅值扫描：非线性是**逐带**的，85–94 Hz 线性、142–195 Hz 不是 |
| [SOFTWARE_AND_INVERSION_2026-10-25.md](SOFTWARE_AND_INVERSION_2026-10-25.md) | Velch：软件怎么建起来的，以及长波 / 短波不平顺怎么反演 |
| [SOFTWARE_ARCHITECTURE_V0_4.md](SOFTWARE_ARCHITECTURE_V0_4.md) | Velch 0.4 软件架构与模型边界 |
| [SPECTRAL_BANDS_2026-10-28.md](SPECTRAL_BANDS_2026-10-28.md) | 频率分辨反演：6/8 —— 但这一轮真正的结论是"真值的定义比估算子更重要" |
| [SPECTRUM_SOURCE_2026-10-21.md](SPECTRUM_SOURCE_2026-10-21.md) | 153.85 Hz 是什么：速度标定实验 |
| [SPEED_2026-10-20.md](SPEED_2026-10-20.md) | 提速：先量再改（2026-10-20） |
| [SPEED_CAMPAIGN_BLADE_2026-10-31.md](SPEED_CAMPAIGN_BLADE_2026-10-31.md) | 尖轨降低值的速度谱：40–100 km/h 四次过岔，首载里程只动 5.6 mm |
| [SPEED_SWEEP_2026-10-28.md](SPEED_SWEEP_2026-10-28.md) | Five drawn speeds: the straight-route amplitude claim is one band wide, not six-of-eight |
| [SPLIT_LAW_MEASURED_2026-10-31.md](SPLIT_LAW_MEASURED_2026-10-31.md) | Where the amplitude compression actually comes from: the split law, measured |
| [SPLIT_LAW_VS_MILEAGE_2026-10-31.md](SPLIT_LAW_VS_MILEAGE_2026-10-31.md) | Does the split law collapse? Measured across mileage, with a self-corrected verdict |
| [STAGE2_MODAL_2026-10-21.md](STAGE2_MODAL_2026-10-21.md) | 阶段②：钢轨模态扩阶（60 → 320 阶）对接触力频谱的影响 |
| [STAGE3_EFFICIENCY_2026-10-21.md](STAGE3_EFFICIENCY_2026-10-21.md) | 阶段③：与 SDITT 的效率对标 |
| [STAGE_B_SURROGATE_2026-10-21.md](STAGE_B_SURROGATE_2026-10-21.md) | B 阶段：可微代理与保险丝 2026-10-21 |
| [STRAIGHT_BLADE_SEAT_2026-10-29.md](STRAIGHT_BLADE_SEAT_2026-10-29.md) | 直向尖轨降低值反演：静平衡能坐住，时程走不出 53.74 m |
| [STRAIGHT_LATERAL_B047_2026-10-29.md](STRAIGHT_LATERAL_B047_2026-10-29.md) | 直向横向：起点偏移是零，漂移是 B047（横向定位刚度 ~10³ 倍） |
| [STRAIGHT_PAIR_2026-10-29.md](STRAIGHT_PAIR_2026-10-29.md) | 直向刚性算例：四个缺陷，一段 10 m 的干净运行 |
| [STRAIGHT_RANDOM_SPEED_2026-10-28.md](STRAIGHT_RANDOM_SPEED_2026-10-28.md) | 直向过岔 + 随机速度：波磨反演的六段判定（第 6 门的直向半边） |
| [SURFACE_SENSITIVITY_2026-10-31.md](SURFACE_SENSITIVITY_2026-10-31.md) | The forward operator's answer to a known surface bump (M5, step 1) |
| [SWITCH_TWO_BODY_2026-10-29.md](SWITCH_TWO_BODY_2026-10-29.md) | 把降低值装进算例：双体尖轨区（2026-10-29，第 213 轮） |
| [TASKBOOK_AXLEBOX_INVERSION_2026-10-23.md](TASKBOOK_AXLEBOX_INVERSION_2026-10-23.md) | 任务书：用轴箱加速度反演钢轨型面不平顺（2026-10-23 22:40 → 2026-10-24 10:00） |
| [TASKBOOK_FINAL_GOAL_2026-10-31.md](TASKBOOK_FINAL_GOAL_2026-10-31.md) | 最终任务书：反演道岔结构不平顺（尖轨/心轨走行面）2026-10-31 |
| [TASKBOOK_FLEXIBLE_WHEELSET_NIGHT_2026-10-25.md](TASKBOOK_FLEXIBLE_WHEELSET_NIGHT_2026-10-25.md) | 任务书：柔性轮对嵌入 + 反演链路（2026-10-25 夜） |
| [TASKBOOK_INVERSION_NIGHT_2026-10-26.md](TASKBOOK_INVERSION_NIGHT_2026-10-26.md) | 任务书：长波与短波不平顺反演，以及问题到底出在哪里（2026-10-26 夜） |
| [TASKBOOK_SHORTWAVE_INVERSION_2026-10-23.md](TASKBOOK_SHORTWAVE_INVERSION_2026-10-23.md) | 任务书：短波轨面反演（2026-10-23 拟定，待批准后执行） |
| [TASKBOOK_TURNOUT_SOFTWARE_2026-10-29.md](TASKBOOK_TURNOUT_SOFTWARE_2026-10-29.md) | 道岔动力学软件：剩余开发任务书（2026-10-29） |
| [THREE_ESTIMATORS_2026-10-31.md](THREE_ESTIMATORS_2026-10-31.md) | Three estimators for one bump, and why one pass cannot give its amplitude (M5, step 3) |
| [THREE_LINE_CASE_2026-10-30.md](THREE_LINE_CASE_2026-10-30.md) | 照 SDITT 组三条线算例：几何装得进，座椅卡在左右基准（2026-10-30） |
| [TONE_CALIBRATION_2026-10-28.md](TONE_CALIBRATION_2026-10-28.md) | 单音标定 3/8：不是"传递测不准"，是"多音不满足叠加" |
| [TRACK_IRREGULARITY_2026-10-23.md](TRACK_IRREGULARITY_2026-10-23.md) | 轨道不平顺进求解器（0.4.31 前的功能层，2026-10-23） |
| [TURNOUT_DB_2026-10-30.md](TURNOUT_DB_2026-10-30.md) | 道岔数据库：一套 18 号道岔，直向基准（2026-10-30） |
| [TURNOUT_LOWERING_DESIGN_2026-10-29.md](TURNOUT_LOWERING_DESIGN_2026-10-29.md) | 降低值的真值找到了：在轨道梁设计表里，不在断面文件里（2026-10-29，第 208 轮） |
| [TURNOUT_PROFILE_ATLAS_2026-10-30.md](TURNOUT_PROFILE_ATLAS_2026-10-30.md) | 道岔廓形认图：文件夹里到底是什么形状（第 222 轮） |
| [TWO_POINT_CONTACT_2026-10-28.md](TWO_POINT_CONTACT_2026-10-28.md) | 两点接触：把接触算法补齐，并量清它对曲线能力的影响 |
| [UI_CHINESE_LABELS_2026-10-22.md](UI_CHINESE_LABELS_2026-10-22.md) | 界面中文命名规则（Velch UI） |
| [UI_READABILITY_2026-10-22.md](UI_READABILITY_2026-10-22.md) | 界面可读性：字号缩放与不截断 |
| [UNIFIED_SCALE_AND_SOFTWARE_READINESS_2026-10-22.md](UNIFIED_SCALE_AND_SOFTWARE_READINESS_2026-10-22.md) | 统一口径复核 + 代码体检（2026-10-22） |
| [VEHICLE_DATABASE_2026-10-23.md](VEHICLE_DATABASE_2026-10-23.md) | 车辆数据库（Stage 1）：一台车只有一个定义 |
| [VEHICLE_SPEED_PROFILE_2026-10-27.md](VEHICLE_SPEED_PROFILE_2026-10-27.md) | 车辆速度剖面：先把基线冻住，再把「v」变成一个值 |
| [VEHICLE_TOPOLOGY_2026-10-23.md](VEHICLE_TOPOLOGY_2026-10-23.md) | 车辆拓扑：从写死的 35 个坐标到节点表 |
| [VEHICLE_V2_DESIGN_AND_EVIDENCE.md](VEHICLE_V2_DESIGN_AND_EVIDENCE.md) | Velch v0.2：车辆—轮对—道岔轨道耦合的证据与实现 |
| [WIDTH_AWARE_INVERSION_2026-10-31.md](WIDTH_AWARE_INVERSION_2026-10-31.md) | 宽度感知的分离律反演：50 µm 折到 0.53 %，但载荷分配在膝点饱和（2026-10-31） |
<!-- DOCS:ALL:END -->` 之间生成
  "文件 → 首行标题"表（73 行，机械取自每篇自己的标题，不改写内容）；
- 新增 `tests/test_docs_index.py`（5 项）：清单块存在且 ≥60 行、**每篇 `docs/*.md` 都被索引提到**、
  索引里每个 `.md` 链接都能解析到真实文件、**生成块与当前标题一致（漂移守卫）**、
  **当前 `__version__` 必须有对应的 `RELEASE_NOTES_<ver>.md` 且已登记**。

最后那条正是"文档与版本一致"的可执行版本：以前版本号改了、发布说明漏写，没人会发现。

顺带记一个判断错误：最初还写了"发布说明在索引里必须按 semver 排序"，跑起来立刻失败——索引表是按
**书写顺序**追加的，不是 semver 顺序。排序在这个位置没有意义，已替换为"当前版本必须有说明"。
`pytest` **539 passed, 1 skipped**。



## 第 50 轮：把"物理数值不变"从一句承诺变成一道门

至今为止，发布说明里那句"物理一根线没碰"背后只有 `tests/test_oracle_frozen.py` 钉的静载门，
**没有任何东西**拿一次发布去比归档的 1.2 s 结果，八个接触峰值尤其没人复算。

### 新增 `scripts/physics_invariants.py`

两个独立来源，与 `docs/physics_invariants.json` 里 committed 的参考值逐项比较：

- **归档**（不重跑）：`out_full12_cap05/history.csv` 2401 帧 → 八接触峰值、最大侵入、脱空样本、
  78.8–82.2 m 窗口的 rms / 主导频率 / 三频带、`manifest.json` 的 `result_status` 与七项门；
- **现跑**（`--fast`，0.05 s 辙叉算例，约 4 s）：当前代码还能不能跑出 `numerically_checked` 与
  七门全过、首帧与八接触峰值。

判据：接触峰值 ±1.0 kN、侵入 ±1.0 µm、窗口 rms ±0.2 kN、主导频率 ±1.0 Hz、频带 ±0.2 kN、脱空
样本必须完全相同、首帧静载 ±1.0 N；现跑要求 `numerically_checked` 且八个接触都在、七门无失败。
退出码 0 / 2。报告写到 `reports/PHYSICS_INVARIANTS_LATEST.md`（运行产物，不入库）。

参考值实测：`axle2_right_normal_n 170.61 kN`、`axle1_right 89.677 kN`、最大侵入 551.89 µm、
脱空 0、窗口 `rms 9.126 kN / 主频 57.14 Hz / 5.677 / 1.75 / 2.25`、`gates 7/7`、
`result_status numerically_checked` —— 与文档里引用的数字逐位一致。

已接入 `scripts/auto_accept.py` 作为第四步（`--no-run`，0.2 s），每次提交都会跑。

### 四个"看起来对其实错"的地方（都是自己抓到的）

1. **窗口数字差点用错算法**：我先用手写 FFT，得到 `rms 10.715 kN`；而文档引用的 **9.13 kN** 来自
   `bands_from_history.py`（去均值 + 矩形窗 + `2/N` 标度）。`band_metrics` 回答的是另一个问题
   （5–999 Hz 滤波、裁瞬态、主频按 1/3 倍频程中心报，同一窗给 11.59 kN / 396.85 Hz）。改成复刻
   文档口径后，参考值与文档逐位一致，差别写进 `docs/PHYSICS_INVARIANTS.md`。
2. **`manifest.json` 的 `result_status`/`gates` 在 `summary` 下一层**：读顶层得到 `None`，
   参考值会带着两个 `None` 落地，门就变成瞎的。
3. **静载门不是这个归档的**：`59 680.5769 N` 属于模板算例（`test_oracle_frozen` 钉住），
   归档从 13.5 m 起算、首帧是 `59 680.3756 N`；复算门比"归档自己的首帧"，硬要比那个常数会
   在没人动过代码的情况下报漂移。
4. **辙叉算例的首帧不是静载门**：它过辙叉，首帧一侧只有 37.1 kN。现跑只要求"能跑、门全过、
   八个接触都在"，不要求首帧等于 59.68 kN。

### 顺带修掉 B025：`bandpass` 在短窗上会抛异常

70 个样本、2 kHz 的窗口让 scipy 抛 `ValueError: Filter not stable due to sum(a) == 0`——上边缘
贴着 Nyquist；同样的滤波器在 2401 点长记录上正常。现在滤波失败会依次收窄上边缘
（0.999 → 0.97 → 0.90 × Nyquist）重试，长记录结果逐位不变，短窗不再崩。
`tests/test_physics_invariants.py` 有一条 70 点用例钉住它。

### 验证

- `tests/test_physics_invariants.py` **6 passed**（参考值完整、与文档一致、归档仍匹配、
  改一个数会被报出、容差表齐全、短窗滤波不崩）
- `python scripts/physics_invariants.py` → **VERDICT: UNCHANGED**
- `python scripts/auto_accept.py --skip-run` → 四步全 PASS
| [RELEASE_NOTES_0.4.12.md](RELEASE_NOTES_0.4.12.md) | 发布说明 | ✅ 0.4.12 |

## 第 51 轮：证据地图——一页回答「凭什么可以发布」

五十轮下来，证据是齐的，但散在五十条日志里：要回答"这版能不能发"，得把日志从头读到尾。
这一轮加的是**一页能复核的东西**，不是又一份说明。

### `scripts/evidence_map.py` → `docs/EVIDENCE_MAP.md`

按目标的六个分项（①代码稳定 ②bug 清理 ③界面 ④安装包 ⑤Simpack + 物理不变量）各列一行：
**凭什么 / 复核命令 / 最近一次结果 / 期望**，再列每个证据文件的**最后一次提交**。
表里的结果都是**跑出来的**：

| 分项 | 运行的东西 | 本次得到 |
|---|---|---|
| ① | `pytest tests/test_architecture_rules.py tests/test_docs_index.py` | 21 passed |
| ② | `scripts/auto_accept.py --skip-run` | ACCEPT（4 步） |
| ③ | `pytest tests/test_ui_layout.py tests/test_ui_scale.py` | 13 passed |
| ④ | 最近一份 `reports/packaging_smoke_*.json` | ACCEPT · 6 步 · 0 失败 · 0 跳过 |
| ⑤ | `velch inspect-simpack-track` | `geometry_readable = True`、`missing_profile_references = 0`、238 个断面引用 |
| 不变量 | `scripts/physics_invariants.py --no-run` | UNCHANGED（整程峰值 170.61 kN） |

### 生成它的过程中抓到的两个错（正是它该抓的）

1. **命令名是错的**：我按记忆写了 `velch simpack-catalog`，实际子命令叫 `inspect-simpack-track`，
   参数是 `--model-root` / `--output` 而不是 `--root` / `--out`。生成器把退出码原样写进表里，
   于是"证据地图"第一版当场显示 `catalog 生成失败（exit 2）`——比手写的文档诚实。
2. **①②③ 三行原本引用的是全仓测试数**（同一个数字抄三遍）。改成**各跑各的命令**，
   于是 ① 21 passed、③ 13 passed 各自独立。

### `tests/test_evidence_map.py`（6 项）

分项齐全、引用的文件都存在、命令里的脚本都存在、每行都有命令与期望、必须写清"不在这张表里的
东西"（标定 / 未签名 / 只读 ACL），以及**与本脚本 `--check` 的判定一致**——两处判断不能分叉。

### 验证

- `tests/test_evidence_map.py` 6 passed；全仓 **550 passed, 1 skipped**
- `scripts/auto_accept.py --skip-run` → ACCEPT（4 步）
- 文档索引覆盖 **76** 篇，`test_docs_index` 5 项全绿

## 第 52 轮：⑤ 那一行从"读得进来"走到"算得出来"

证据地图的 ⑤ 行之前只证明 catalog 里 `geometry_readable = true`——几何能读进来，但"读进来之后
能不能算"还是散的（在 `SIMPACK_IMPORT` 的正文里）。这一轮给生成器加 `--with-run`：同一行里
把导入后的算例**真跑一次**。

### 新增 `evidence_map.py --with-run`

流程与命令行完全一致，只是把中间产物放进临时目录：

1. `velch inspect-simpack-track <wheelset>.spck --model-root <db> --output catalog.json`
   → `geometry_readable = True`、`missing_profile_references = 0`、`profile_references = 238`
2. `velch simpack-case --catalog … --template case_A_final_law.json --x-start 82 --duration 0.05
   --sample 400` → 派生算例，**静平衡裁决 `seats: true`**，八个接触各 **59.68 kN**、
   最大侵入 **65.47 µm**（与冻结静载门 59 680.5769 N / 65.47 µm 同一个数）
3. `velch run-vehicle <派生算例> --fast` → `numerically_checked`、**七门 7/7**、`nfev 116`

于是 ⑤ 那一行现在读起来是：`geometry_readable = True、missing_profile_references = 0、
profile_references = 238；seats: true（8 个接触、最大侵入 65.47 µm）；现跑 numerically_checked、
门 7/7、nfev 116`。

### 两个坑

- **内存顺序写错**：`Path(os.environ.get(..., "")).strip()` —— `Path` 没有 `.strip()`，
  抛 `AttributeError: 'WindowsPath' object has no attribute 'strip'`；正确写法是先 strip 再 `Path()`。
- **模型不在 `F:\项目` 那一份**：`F:` 下的同名 `CRH380A_M_Wheelset.spck` 不含轨道断面
  （catalog 报 `geometry_readable` 为假/引用为 0），真正带 238 个断面引用的是
  `G:\研究生\动力学\CRH380A_纯刚性模型\…`。所以 ⑤ 行依赖环境变量而不是硬编码路径。

### 代价与边界

`--with-run` 约 10 s（catalog 2 s + 派生含裁决 4 s + 现跑 4 s），**不进提交闸门**——闸门那一步
用的是 `physics_invariants.py --no-run`（0.2 s）。地图默认（不带 `--with-run`）仍只写 catalog 结果，
需要完整证据时显式加参数，这比"每次都跑 10 s 但不看"更诚实。
| `RELEASE_NOTES_0.4.13.md` | 0.4.13 装什么、证据版包含哪三份可复算材料、与 Simpack 的对照摘要、仍然没有的五项 | ✅ 2026-10-23 新增 |
| `RELEASE_NOTES_0.4.14.md` | 0.4.14 新增 `selfcheck`（六项首次运行检查）与冒烟第 7 步 | ✅ 2026-10-23 新增 |
| `RELEASE_NOTES_0.4.15.md` | 0.4.15：只读安装（O009）自动化，自检在只读目录下的预期输出 | ✅ 2026-10-23 新增 |
| `RELEASE_NOTES_0.4.16.md` | 0.4.16：`SimpackCaseError.detail`，拒绝带结构化数字 | ✅ 2026-10-23 新增 |
| `RELEASE_NOTES_0.4.17.md` | 0.4.17：① 屏「环境体检」，结果按 PASS/WARN/FAIL 着色 | ✅ 2026-10-23 新增 |
| `RELEASE_NOTES_0.4.18.md` | 0.4.18：状态栏常驻「这版跑过什么」证据行 | ✅ 2026-10-23 新增 |
| `RELEASE_NOTES_0.4.19.md` | 0.4.19：⑤ 屏常驻「本运行不是标定」横幅 | ✅ 2026-10-23 新增 |
| `RELEASE_NOTES_0.4.20.md` | 0.4.20：页眉「发布证据」只读窗口 + 两个动作搬家 | ✅ 2026-10-23 新增 |
| `RELEASE_NOTES_0.4.21.md` | 0.4.21：页眉「已知问题」窗口 + 账本双向守卫 | ✅ 2026-10-23 新增 |
| `RELEASE_NOTES_0.4.22.md` | 0.4.22：⑥ 对照屏常驻显示选中的两列，O003 关闭 | ✅ 2026-10-23 新增 |
| `RELEASE_NOTES_0.4.23.md` | 0.4.23：首页与证据地图指向三份可复算材料，发布序列成表 | ✅ 2026-10-23 新增 |

## 第 53 轮：只读安装变成可验证的一条（O009 关闭）

`C:\Program Files\Velch` 是真实部署的形状：目录不可写，`.agent` 建不出来。以前这只是文档里
一句"要手工试一遍"，现在是冒烟测试的第 8 步（`--readonly-acl`，Windows 专用，约 40 s：复制
195 MB + 改 ACL + 跑两次）。

它断言三件事，缺一不算过：

1. **算力不受影响**：从被禁写的副本里 `run-vehicle --fast` 仍然产出 `manifest.json`（输出目录在
   别处，安装目录只读不该妨碍计算）；
2. **自检说得出原因**：`selfcheck` 退出码 2 且打出 `[FAIL] 可写目录`；
3. **不是崩出来的**：输出里没有 `Traceback`。

三次试错（都值得记下来）：

| 试法 | 结果 | 原因 |
|---|---|---|
| `icacls /deny user:(OI)(CI)(W)` | 整个 GUI 报 `Can't find a usable init.tcl` | **`(W)` 里包含 SYNCHRONIZE**，而 Tcl 用它打开自己的库目录 |
| 只禁文件夹本身 `(W)` | 自检仍然 PASS | 上一轮跑过的副本里已经带着 `.agent`，它依然可写 |
| `(OI)(CI)(WD,AD,WEA,WA)` + 先删 `.agent` | 全过 | 只禁"建文件/建子目录/写属性"，不动 SYNCHRONIZE |

顺带修掉自检里的一个真缺陷：`_write_check()` 只在 `mkdir` 外面包 `try`，而只读安装下
`agent_home()` **自己就会抛 `PermissionError`** —— 整条自检会带着 traceback 退 2，正好在最需要
解释的机器上死掉。现在把调用一起包住，失败时给 `[FAIL] 可写目录` 与 `VELCH_AGENT_HOME` 的指路。
`tests/test_selfcheck.py` 增两项钉住（`agent_home` 抛错时自检不炸、报告仍给"1 项必须修"）。

## 第 54 轮：拒绝也要带上数字（O008 收尾）

`simpack-case --import-lateral` 拒绝单侧导入时，过去只在中文句子里说"这个模型左轨只有 2 站"。
脚本没法据此行动，只能去解析句子。现在 **`SimpackCaseError` 带 `detail`**，CLI 把它一并打印：

```json
{
  "status": "failed",
  "error_type": "SimpackCaseError",
  "message": "importing this side's crown lateral positions changes the gauge by +81.7 mm …",
  "detail": {
    "code": "lateral_gauge_change",
    "gauge_mm": 81.69,
    "this_side_mm": 81.69,
    "other_side_mm": 0.0,
    "other_side_stations": 2,
    "at_m": 80.278,
    "limit_mm": 5.0,
    "both_sides_possible": false,
    "ways_out": ["--keep-profiles", "--allow-gauge-change", "a model with both rails"]
  }
}
```

`both_sides_possible: false` 就是 O008 的机器可读结论：**这个模型不能两侧一起导入**（左轨只有 2 站，
都在 0 与 150 m）。`other_side_stations < 3` 是判定依据，写进 `detail` 而不是只写在句子里。

`tests/test_simpack_refusal_detail.py`（3 项）：拒绝带全部键与 `limit_mm`、CLI 把 `detail` 打进 stderr
的 JSON、**其它失败（目录不存在）不带 `detail`** —— 不能让"没有数字"的失败看起来像有数字。

## 第 55 轮：体检从命令行搬进界面

`velch selfcheck` 上一轮就有了，但它只活在终端里。打包版用户第一次打开界面、看到算例表是空的，
最自然的反应是"装坏了"——而体检恰好就是回答这个问题的。现在 ① 算例屏的导航区多了**「环境体检」**：

```
[PASS] 版本与发布说明         0.4.16，发布说明在位
[PASS] 算例语料            358 个算例，位于 F:\velch_data\validation\crh380a_m
[PASS] Tk 界面库          tkinter 可用
[PASS] 绘图库 matplotlib  可用
[WARN] Simpack 模型      未设置 VELCH_SIMPACK_MODEL / VELCH_SIMPACK_ROOT
[PASS] 可写目录            F:\ai道岔状态反演辨识\Velch\.agent 可写
```

`[FAIL]` 红、`[WARN]` 黄、`[PASS]` 灰；底部一句结论文案分三档——**「全部通过」「可用，有 N 项提示」
「N 项需要处理」**（WARN 退 0，但它确实在说某个能力没开，不该和"全部通过"共用一句话）。

### 三个实现选择

- **走子进程，不 import 自检**：冻结包里 `Velch.exe` 没有 stdout，自检必须跑 `velch-cli.exe`；
  统一经 `launcher_argv("selfcheck")`，源码版与打包版同一条路。
- **打开即跑**：点这个按钮的人已经表达了意图，不再要一次"再点确定"。
- **文本区只读**：唯一的写入者是一个 `_append`，写完立刻回 `disabled`（测试钉住"只有一个解锁点"）。

### 顺带修的两个自己的错

- 加按钮那次批量替换把 `import_from_simpack` 里**函数内**的 `from .simpack_dialog import ...`
  当成了模块级 import，替换后 `screen_cases.py` 直接 `IndentationError` → ① 屏显示
  「该屏加载失败：IndentationError」，**布局闸门当场抓到**（这正是它存在的理由）。
- `from ..launcher import ...` 与 `from .. import launcher` 的区别：后者在架构规则里被记成
  `velch`（包根），presentation 不许 import 包根；改成取叶子后规则通过。

## 第 56 轮：状态栏多一句"这版跑过什么"

发布前有两份证据躺在磁盘上：`reports/packaging_smoke_*.json`（装完能不能跑）与
`reports/PHYSICS_INVARIANTS_LATEST.md`（物理数值有没有漂）。过去只有记得去翻文件的人才知道。
现在状态栏右侧常驻一行：

```
证据：冒烟 ACCEPT · 8 步 ｜ 不变量 未移动
```

绿 = 两项都过；黄 = 有一项找不到（**"没找到"必须说出来**，留空会被读成"跑过了"）；红 = 有失败或漂移。

### 三个判断

- **新模块 `velch/ui/evidence.py`**（纯函数、无 Tk）：`latest_smoke()` 取 mtime 最新一份、坏文件跳过
  （坏在解析上不该让整条证据消失）；`latest_invariants()` 读第一行带 `VERDICT`/「未移动」的结论；
  `summary_text()` 返回 `(文案, 语气)`。
- **`跳过 N` 要显示**：跳过和通过不是一回事，冒烟里 `readonly-acl` 曾经是 SKIP。
- **放在状态栏而不是某个屏**：它属于整个程序，不属于任何一屏。

### 一个被布局闸门当场驳回的设计

第一版把这句话放在状态栏的**第二行**。结果状态栏变高，① 屏右卡被挤，`环境体检` 那四个导航按钮
在 1.3 倍字号下**只剩 1 px**——`tests/test_ui_layout.py` 报 `「在运行屏打开」 1px < required 146px`。
改成与「就绪」「算例/运行」同一行（`row=0, column=1`）后恢复。**加一行文字也是一次布局改动**。

## 第 57 轮：把"这不是标定"写在判定旁边

⑤ 评价屏会给出"通过 / 超限"的判定——那是**这套算例参数下**的自洽结果，但屏幕本身没有说过这件事；
这句免责声明此前只活在文档里，而引用数字的人未必读过文档。现在它是屏顶一条常驻的黄色横幅：

> 本运行不是标定：物理参数未与实测或 Simpack 对齐，这里的「通过 / 超限」只在这套算例参数下成立，
> 不能当作对真实道岔的结论（见 docs/BUGS.md 的 O008 与 docs/PHYSICS_INVARIANTS.md）。

### 三个判断

- **常驻、不可关闭**：一条可以关掉的警告等于没有警告。
- **写在判定上方**：先读到边界，再读到结论；写在页脚会被当成脚注。
- **给出可查的两个文件**：不写"仅供参考"这种空话，直接指 `docs/BUGS.md` 的 O008 与
  `docs/PHYSICS_INVARIANTS.md`。

### 一个自己的错

常量先用直引号写了「通过/超限」（`"…这里的"通过/超限"只在…"`），文件直接 `SyntaxError`；
改成「」引号。**引号在中文句子里的替换不是排版问题，是语法问题。**

`tests/test_ui_calibration_banner.py`（3 项）：文案必须写明边界与两份文件、一进屏就在、
`wraplength` 必须走 `wrap_with`（写死宽度会在缩放时溢出）。

## 第 58 轮：界面里能看「凭什么可以发布」

`docs/EVIDENCE_MAP.md` 是发布前最该被读的一页（六个分项各自跑出来的最近结果），但它是磁盘上的
markdown。现在页眉有**「发布证据」**：一个只读窗口，显示原文 + 文件时间 + 大小。

### 三个判断

- **显示原文，不解析**：那张表每次任务都在改列，重新实现的解析器会成为第三份真相。窗口只负责
  把"哪一版"（时间、KB）和"写了什么"（原文）同时摆出来。
- **找不到就说查过哪里**：`describe(None)` 会把 `docs/EVIDENCE_MAP.md` 的三个候选路径列出来，
  并给重新生成的命令 `python -X utf8 scripts/evidence_map.py --with-run`。
- **目录解析复用 `selfcheck.docs_roots()`**：PyInstaller 6 把 `datas` 放 `_internal`，
  `parents[2]` 只对一种布局成立——再猜一次就是第三个猜测。

### 两个动作搬到了页眉

「环境体检」和「发布证据」原来挤在 ① 屏右卡的导航格子里。加到第 5 个按钮时**卡片放不下**：
`grid` 仍然建出按钮，但父容器裁掉了它——**布局闸门量的是"按钮分配宽度 vs 所需宽度"，
量不到父容器裁切**，所以这次是我看截图发现的。它们本来就是"整程序"的动作，不属于任何一屏，
搬到页眉后 ① 屏的导航回到三键。

### 一个被架构规则拦下的 import

`evidence_map_dialog` 想用 `velch.selfcheck` 的目录解析，规则先报
`velch.ui.evidence_map_dialog -> velch.selfcheck`。**这条规则是对的**：presentation 不该随手
import 任意模块。处理方式是把它加进 `PRESENTATION_MAY_IMPORT` 并写明理由——`selfcheck` 只回答
"这台机器装了什么、可写在哪"，不碰数值路径。

## 第 59 轮：把「还差什么」和「已通过什么」摆在同一个页眉

上一轮让「凭什么能发」变得一键可达；这一轮补另一半：**已知未修项**。页眉第三个按钮
「已知问题」列出 `O001`、`O003`、`O005`、`O008`（外加已关闭的四项，标成灰），每条一行标题加一段
"该怎么办"。

### 为什么另建 `velch/open_items.py` 而不是解析 markdown

`docs/BUGS.md` 是给人读的账本；程序要读的是同一份事实的**结构化**副本。解析 markdown 会成为第三
份真相（表头一改列就静默失效）。所以数据在 `velch/open_items.py`，并用
`tests/test_open_items.py` **双向守**：模块里的每个 id 必须出现在 `BUGS.md`，`BUGS.md` 里每个
`O###` 行与标题也必须出现在模块里。哪边先漂移，测试立刻红。

### 三个状态，不是两个

- `open`：真的缺东西（`O001` 语料探测靠源码文本、`O003` CSV 列靠猜、`O008` 横向布置不可双侧导入）
- `by_design`：**故意不做**（`O005` Simpack 侧物理量不自动映射——自动映射会静默改动物理标定）
- `closed`：只为让旧笔记里的 id 还能对上（`O002`/`O004`/`O006`/`O007`/`O009`）

把它们混成一个"未修 N 项"会误导：设计约束不是债。

### 顺带更正一行过期账本

`BUGS.md` 里 `O006` 还写着"⑦ 屏没有接触斑着色，属功能增量"，而它已在 0.4.10 实现。这类
"关了但账本没改"的漂移正是双向守卫要防的，这次是我先读到才发现的——所以守卫生效之后我把这一行
就地改成 ✅ 已实现并注明截图。

## 第 60 轮：对照屏的列选择从"猜"变成"看得见"

`O003` 记的是：⑥ 对照屏用 `"x"`/`"力"`/`"_n"` 子串猜 CSV 的里程列与力列，**猜错不提示**。
上一版已经会把结果写进状态栏，但状态栏那句话下一次操作就没了——而"力列猜成另一根轨"会让整张对照图
安静地比较两件不同的东西。这一轮把它变成面板上常驻的一行：

   里程列 ← ch_003（自动）；力列 ← SumQ（自动，另有 2 个候选）
   —— 猜错的代价是整张对照图比较了两根不同的轨，请确认

- 改了下拉框立刻重写这一行，措辞从「自动」变「手动选择」；
- 自动且**有多个候选**时把"另有 N 个候选"写出来，并在句末提醒代价；
- 列名一个都不认识时写「列名无法识别，请确认」，而不是静默取第一列。

数据流没有变：仍然是 `store.measured_reference(path, station_col, force_col, scale)`，改的只是
"用户能不能看见自己比较的是哪两列"。

## 第 61 轮：一夜 23 个包，压成一页可核对的序列

`docs/RELEASE_SERIES.md`：每个 git 标签 → 打标签时间 → 提交 → **那一版解决了什么** → 对应发布
说明。整张表**由脚本生成**（`scripts/release_series.py`），一句话取自各版发布说明的第一句实质描述。
手写的索引一定会落后于标签，所以它同时被两处守着：

- `tests/test_release_series.py`：文件内容必须等于 `render()` 的结果，且每个标签、每份发布说明都在表里；
- `scripts/auto_accept.py` 新增第五步 `release-series`（`--check`）：打标签忘了更新这页，提交被拦。

接进去的第一次它就把我拦了——不是因为漏更新表格，而是我把脚本路径拼成了 `src/scripts/...`
（`SOURCE` 与 `REPO` 用错）。同一轮 `test_docs_index.py` 也拦了一次：新增文档没重新生成索引块。

### 首页指向三份"能一条命令复核"的材料

`README.md` 新增"这版凭什么可信"一节，用一张三行表指向：证据地图（跑过什么）、发布序列（一夜
怎么走到今天）、物理不变量（数值有没有漂移）。还没修的东西也在软件里——页眉「已知问题」。

## 第 62 轮：收尾核查（这一夜的最后一组数字）

全量跑一遍，把"能不能交付"变成六个可复算的判定：

| 核查项 | 命令 | 结果 |
| --- | --- | --- |
| 全仓测试 | `python -X utf8 -m pytest tests -q` | **614 passed, 1 skipped**（唯一 skip 是没有 `VELCH_SIMPACK_MODEL`） |
| 自动验收（含端到端） | `python -X utf8 scripts/auto_accept.py` | **ACCEPT**：tests 61.8 s / doctor / contract / invariants / release-series / end-to-end |
| 发布序列与标签 | `python -X utf8 scripts/release_series.py --check` | 一致（**24 个标签**） |
| 物理不变量 | `python -X utf8 scripts/physics_invariants.py` | **VERDICT: UNCHANGED** |
| 安装包冒烟 | `python -X utf8 packaging/smoke_test.py --readonly-acl` | **ACCEPT · 8 步 · 失败 0 · 跳过 0**（`reports/packaging_smoke_20261023-083640.json`） |
| 工作区 | `git status --short` | 干净（HEAD `e3bb36f`，`v0.4.23`） |

五个目标项各自的落点：①架构规则/文档索引/版本一致性由测试守着，发布序列表由闸门比对标签；
②缺陷账本 `docs/BUGS.md` 已修 B001–B025、仍开 O001 与 O008、设计约束 O005，界面页眉「已知问题」
与账本由测试双向对齐；③七屏 × 100 %/130 % 由布局测试量过、对比度由主题测试算过；
④0.4.23 onedir 双 exe 出包并八步冒烟；⑤Simpack 几何能读、能派生、能裁决、能算，
横向布置仍是 O008（模型本身左轨只有 2 个断面）。

仍然没有的：与实测/Simpack 的物理标定（`physics_validation_status` 仍未置位）、安装包签名、
曲向双体交接、Kalker 级切向律。这些都写在 `docs/EVIDENCE_MAP.md` 的"不在这张表里的东西"。

## 第 63 轮：车辆数据库 Stage 1（一台车只有一个定义）

新增 `Velch/vehicles/CRH380A_M.json` + `index.json`、`src/velch/vehicle_db.py`、
`velch vehicle list|show|validate|dir`、`tests/test_vehicle_db.py`（17 项）、
`scripts/verify_vehicle_ref.py`、`docs/VEHICLE_DATABASE_2026-10-23.md`。

算例可以写 `"vehicle_ref": "CRH380A_M"` 代替整块 `vehicle`；两个来源同时出现会被拒绝（避免漂移），
解析时车辆文件的 sha256 进 `asset_hashes`（改车即让产物校验失败）。

**验收**：`scripts/verify_vehicle_ref.py` 用 `case_frog_N_strip05.json` 跑两遍，
`history.csv` sha256 相同（`7bfbaa1c…`，244 404 字节）、`result_status` 相同、七门 7/7，
`VERDICT: EQUIVALENT`。

**未解决**（写进文档与发布说明）：拓扑仍写死 2×2×2、自由度缺 x/pitch/spin、悬挂无 6×6、界面选车未接线。

## 第 64 轮：把 Simpack 模型文件读成数字，而不是读成描述

用户指出 `CRH380A_M_Bogie.spck` 就是转向架的悬挂定义，要求继续深挖。这一轮做了两件事：一个能复算的
读取器，一页能对账的结论。

### 读取器（`Velch/src/velch/simpack_model.py`，9 项测试）

`.spck` 是 ASCII 模型库，难点不在解码而在**求值**：值经常是符号（`$G_PrimSusp.$_Prim_Damp_d`），
符号又可能是表达式（`{ $G_PrimSusp.$_Prim_Damp_c/2 }`），而"这个数是什么"只写在 GBK 编码的
行尾中文注释里。三处都做了，并且**解不出就报 `None` 并列进 `unresolved`，不猜**。

三处最容易写错的地方，都由测试钉住：①限定名 `$G_PrimSusp.$_xxx` 必须按**尾段**回落到短名
（否则真实文件 39 个力元的参数全是符号）；②符号正则必须把 `$G_X.$_y` 当一个 token
（否则只匹配到 `$G_X` 就判解不出）；③类型号在文件里只有一句 `! Type`，元素类型只能**按参数槽位判读**
（type 5 = 三向衬套、type 6 = 并联弹簧-阻尼、type 13 = 扭转类、`{ 6 }` = 只有刚度的弹簧）。

### 结论（`Velch/docs/SIMPACK_BOGIE_MINING_2026-10-23.md`）

- 该文件 2 341 条记录 / 85 个全局参数（解出 82）/ 6 刚体 / 39 力元 / 8 铰 / 75 标记。
- **和我们车辆定义逐位对得上的**：一系横向 980 000、一系垂向 1 176 000、一系垂向阻尼 10 000、
  二系横向 160 000、二系垂向 240 000、二系垂向阻尼 20 000、抗蛇行 8 850 000 / 2 450 000、
  构架 3 300 kg 与 2 673/1 807/3 300 kg·m²、转向架中心距 17.5 m、轴距 2.5 m、车轮半径 0.43 m。
- **我们缺的，现在有确切数值**：一系纵向 980 000 N/m、轴箱转臂节点 13.7e6 / 5.49e6 N/m、
  二系横向减震器 17.15e6 N/m + 40 000 N·s/m、抗侧滚扭杆 1e6 N·m/rad、牵引拉杆 7.88e6 N/m、
  轴箱 4 × 48.2 kg（含转动惯量）、一系减振器接头刚度 4.9e6 N/m、齿轮箱吊杆 2e6/1e5/7e6 N/m。
- **一个容易记错的细节**：Simpack 的二系垂向减震器**只有刚度、没有阻尼槽位**，
  所以 `secondary.c_z = 20 000` 的来源是空气弹簧 `$_SecSpr_d_z`，不是减震器。
- `primary.k_yaw = 1 960 000` 是"轴箱节点约束"的集总替身，Stage 2 换成节点力元后它就没有物理对应物了，
  替换时必须重跑静载门与八接触峰值并在文档里分清"标定值"与"模型值"。

### REA 这一步的边界

用 Ghidra 工具箱的静态取证方式扫了安装目录 460 个 exe/dll，确认 `Spring-Damper`/`Bushing`/
`Bump Stop`/`Air Spring` 这些元素名确实在这套安装里（`FortranInterface.dll`、`GUI.dll`、`IO.dll` 等），
结果落 `Simpack_REA_Ghidra_Batch_V1/output/element_name_strings.json`。但**没有**用反编译去给类型号贴名字：
字符串表里名字与号码不在一处，而参数槽位已经把类型判死；`O005`（Simpack 侧物理量不自动映射）仍然成立。

### 数字

`pytest` **644 passed / 1 skipped**（新增 9 项）。文档索引 92 篇。

## 第 65 轮：车体的数字齐了（0.4.25）

用户要求"继续完善车体"。这一轮把 `CRH380A_M_Carbody.spck` 读干净，并把结果**落到唯一一份
车辆定义里**——不是写在报告里让人再去抄一遍。

**读出来的**：12 个全局参数全部解出（627 条记录 / 1 刚体 / 39 力元条目）；车体的
**质量 34 934 kg 与三个惯量 113 200 / 1 711 800 / 1 615 300 kg·m² 与我们原有数值逐位相同**
——说明当年从算例抄进 `vehicle.carbody` 的数是对的，这一轮补的是它们的**位置**：
质心 (0, 0, −1.55 m)、参考点 13.5 m、定距 17.5 m（前 22.25 / 后 4.75）、轴距 2.5 m。

**新增 `geometry` 块**（`vehicles/CRH380A_M.json`，3 613 B → 7 225 B）：`frame` 写明坐标约定
（z 轨面为 0 向下为负、y 中心线右正、x 车体参考点）、`carbody`、`bogies`、`primary`、
`secondary`（空簧上下表面、垂向/横向/抗蛇形减震器两端坐标）、`carbody_mounted`
（抗侧滚扭杆、横向止挡、牵引拉杆及其刚度），外加 `provenance.geometry`（两个 `.spck` 的
sha256 与读取器名）与三条 `not_verified`。

**校验**：`velch/vehicle_db.py` 新增 `_geometry_problems()`，把记录几何与求解器真正用的数字
用恒等式对齐——`17.5 = 2 × 8.75`、`−1.0 − (−1.55) = 0.55`、`−0.8 − (−0.51) = −0.29`、
一系两条按 1 mm 容差（原模型自己有 1 mm 取整，容差不抹平）；任何一条不成立，`load()` 直接拒绝。
`velch vehicle show` 多打两行"车体几何 / 车体位置"。

**证据**：`tests/test_vehicle_db.py` 新增 6 项（自洽通过 + 四类矛盾被拒 + 报告含几何）；
全仓 `pytest` **652 passed, 1 skipped**；`scripts/verify_vehicle_ref.py` →
**`VERDICT: EQUIVALENT`**（`history.csv` sha256 `7bfbaa1c…8566ad88`、244 404 B、
`numerically_checked`、七门全 true）——几何块是旁挂证据，一个数字都没动。

**为什么分两步**：车体纵向自由度、抗侧滚扭杆、牵引拉杆、横向减震器、横向止挡、轴箱体都还
没有对应的自由度或元件。它们现在"有值、有出处、有校验、没有装配"，`bogies` 里的 `cg_z_m`
同样如此。这一步不假装能做，只保证下一步有据可依。

文档：`docs/SIMPACK_CARBODY_MINING_2026-10-23.md`。

## 第 66 轮：车辆拓扑从代码搬到数据（0.4.26）

**做了什么**：新增 `velch/topology.py`（`Body`/`LinkSpec`/`Topology`、`legacy_topology`、
`node_topology`、`axial_spec`/`torsional_spec`、`topology_of`），把求解器里写死的 35 坐标改成
按拓扑求索引；`VehicleCase` 携带 `topology` 块，`vehicle_db` 校验 `v2-node` 并允许算例从
`vehicle_ref` 继承；新增两台车型定义 `CRH380A_M_node`（等价重述）与 `CRH380A_M_6dof`
（装上牵引拉杆 7.88e6 N/m、抗侧滚扭杆 1.0e6 N·m/rad、二系横向减振器 17.15e6 N/m + 40 kN·s/m）。

**怎么知道没有改坏**：`scripts/verify_vehicle_ref.py` 冻结基线 `history.csv` sha256 仍是
`7bfbaa1cc7c464918c08bc05ef6d96f68a4e740f2e2bcc733ecac7468566ad88`（244 404 B、七门全 true）；
节点表与冻结连接器**逐元件按 (刚体, 坐标) 比较雅可比系数，最大差 0.000e+00**。

**两处自己写错的物理约定**（已修）：二系垂向弹簧在冻结模型里没有点头力臂——车体锚点放在
转向架站位的 x、转向架锚点放在自己中心；先写成对称多出 −8.75，再改成两侧都 0 又丢了车体那一侧。

**还没对上的**：同一辙叉窗口最大侵入 154.97 µm vs 155.03 µm，但各轨峰值的**归属轮换**了
（峰值集合相同），因此**不能称轨迹等价**；下一步查轮对与轨道站位的时间对齐。

**验证**：`pytest` 657 passed / 1 skipped；新增 `tests/test_topology.py`（5 项）与
`tests/test_topology_corpus.py`（3 项，带 corpus 标记）；冒烟 8 步全过。

## 第 67 轮：力学元件变成"类型"，不再只有两种原语（0.4.27）

**起点是用户的一句话**：Simpack 最强的地方是有成套可调用的力学元件，我们没有。

**做了什么**：新增 `velch/elements.py`——`PARAMETERS` 类型表（`spring`/`damper`/`spring_damper`/
`bushing`，旧的 `axial`/`torsional` 作为别名保留）、`parse()` 按表校验并给出带单位的中文报错、
`build()` 产出连接、`catalogue()` 供文档与 `vehicle` 命令；`topology.node_topology` 的装配改为
先把 `"$vehicle.…"` 解析成数字、再交给元件库，求解器一行没改；`axial_spec` 允许"只有阻尼没有
刚度"（纯减振器）。

**bushing 的做法**：对 3×3 刚度矩阵做特征分解，把每个主方向变成一个轴向弹簧-阻尼，因此行
结构不变；矩阵不正定在装配阶段就报错并列出特征值；两个刚体都没有的坐标方向**跳过**而不是报错。

**等价性**：节点表与冻结布局的 30 个连接器仍逐元件系数相同（最大差 `0.000e+00`）；
`pytest` 669 passed / 1 skipped；新增 `tests/test_elements.py` 11 项（类型/单位/缺参/负值/
未知类型/重名/继承解析/主方向跳过/不正定拒绝）。

**踩到自己两次**：①元件库第一次接管装配时丢了 `convention`，二系垂向弹簧的点头项符号翻转
（+8.75 而非 −8.75），逐元件比较当场抓到；②`axial_spec` 的"必须有正刚度"未放宽，纯减振器
装配报错——测试先红后绿。

## 第 68 轮：力律不再必须是直线（0.4.28）

**起点**：用户问"能不能把 Simpack 的力学元件库全搬过来"，我答"能搬的是元件类型与力律，搬不动的
是求解器内部"，并按"先建好再优化"开工。

**做了什么**：`Connector` 增加可选 `law`；力来自 `law.force(δ, δ̇)`，雅可比用 `law.stiffness(δ)` /
`law.damping(δ̇)` 在**工作点**现算（线性连接仍在构造时缓存，所以冻结基线一位没动），机械能用
`law.potential(δ)`。新增两种元件：`bump_stop`（自由行程 + 止挡）与 `damper_blowoff`（两段阻尼）。
`axial_spec` 允许"只带力律、没有名义刚度"。

**验证**：`tests/test_elements_nonlinear.py` 7 项；其中端到端那条把真实算例的二系垂向连接换成
"已压到限位"的止挡，用 `frozen_geometry_error` 确认解析雅可比与中心差分一致（两列误差 < 2e-4），
解耦后该行刚度归零。全仓 `pytest` 676 passed / 1 skipped；`verify_vehicle_ref.py` 仍
`VERDICT: EQUIVALENT`。

**踩到的三处**：①`_axial` 没转发 `law`（`TypeError: unexpected keyword argument`）；
②`axial_spec` 的"必须有正刚度或正阻尼"把带力律的元件挡在门外；③势能导数与力的**符号**我一开始
写反了——`dV/dδ = F`（不是 `−F`），测试在间隙点还多测了一个单侧导数不可用的位置。

**没做**（写进文档）：间隙/阀门切换的事件检测、元件内部状态（滞回）、空气簧、查表力、元件对照报告。

## 第 69 轮：让止挡可平滑、让曲线能当元件（0.4.29）

**做了什么**：①`BumpStopLaw` 增加 `transition_m`（C1 过渡段，默认 0）；②新元件 `force_table`
（`points`/`rate_points`，段内线性、斜率=割线、表外斜率 0）。

**一处必须记下的算术**：第一版过渡段只把 `t<T` 换成抛物线，`t≥T` 仍用 `−k·t`，于是 `t=T` 处力从
`−k·T/2` 跳到 `−k·T`——**C0 都不成立**。正解是线性段同时抬高 `k·T/2`（`F = −(k t − kT/2)`），这样力与
斜率都连续；势能也要跟着改成 `½k(t−T/2)² + …`。测试里直接量 `t=T±1e-9` 两侧的力与斜率，不靠读代码。

**验证**：新增 `tests/test_elements_tables.py` 11 项（默认无过渡段、C1 连续性、势能导数=力、表的插值/钳制/
双通道/排序校验/单位报错）；全仓 `pytest` 687 passed / 1 skipped；`verify_vehicle_ref.py` 仍
`VERDICT: EQUIVALENT`。

**没做**：事件检测、元件内部状态（滞回）、空气簧气室物理、Simpack 元件逐条对照。

## 第 70 轮：把"做到哪一步"变成可查的两页（0.4.30）

**为什么做这个**：用户问"整体任务做完了吗"。回答这种问题不能靠记忆，得让文档自己能被检查。

**做了什么**：①`elements.inventory(block)` / `describe_inventory(counts)`，`velch vehicle list`
打印每台车的元件清单；②新增 `docs/ELEMENT_CATALOGUE_2026-10-23.md`（七个元件 ↔ Simpack 对照、
39 个真实力元的槽位判读、**六类明确没搬的东西及原因**）；③新增
`docs/GOAL_STATUS_2026-10-23.md`（五步目标 × 状态 × 证据命令 × 剩余差距）。

**验证**：`tests/test_element_catalogue.py`（目录覆盖全部元件类型、缺项清单在位、车型清单非空、
`vehicle list` 输出含"元件："）；全仓 pytest 全绿；`verify_vehicle_ref.py` 仍 `EQUIVALENT`。

## 第 71 轮（2026-10-24 凌晨）：轴箱反演任务书收口

S1（轴箱体）判据 A 0.23 %、判据 B 轴箱 13.7 Hz / 1.95 g rms；S2（加速度通道）相对误差 0.000e+00；
S3（短波生成器）九带最差 5.25 %；S4 出增益表（96.5 / 1 322 / 3 747 / 175 832 (1/s²)/m，SNR 1.9–4.7）；
**S5 未通过并显式降级**——直线段四带叠加误差 61–213 %，线性 Tikhonov 反演在本设计下不可达。

证据：`docs/S4_BAND_TABLE_2026-10-23.md`、`docs/S5_INVERSION_2026-10-23.md`、
`docs/S5_LINEARITY_2026-10-24.md`、`docs/TASKBOOK_AXLEBOX_INVERSION_2026-10-23.md` §5；
脚本 `scripts/s4_band_probe.py`、`scripts/s5_inversion.py`、`scripts/s5_linearity.py`。
O010（柔轨 + 节点表静平衡）仍开放，未在本次收口中动。

## 第 72 轮：S5 的最终判决——线性反演不适用（附判别实验）

- **判据**：闭环 8.39 %（过）、盲测 87.1 % ≤ 1.5×标定（过）、**带限误差 65.2 %（不过，门槛 30 %）**、分辨表有。
- **判别实验（本轮新增）**：`scripts/s5_dual.py` 用两带**同时**激励测完整复数 2×2（12 个方程解 4 个未知量），
  得 `[[17785, 14], [340, 6718]]`，条件数 2.65。耦合项确实很小，但 **2.0 m 带对角增益比单带低 14 %**，
  反演误差从 −23.5 % 恶化到 −39 %，闭环从 8.39 % 退化到 **14.28 %** → 线性常数矩阵不成立。
- **结论与降级**：任务书 §5d 重写为最终版，主张限定为"两带可分辨 + 单带标定闭环自洽 + 线性 Tikhonov 不适用"；
  下一步只有非线性辨识（分段 `H(A)` 或可微代理）。
- 文档：`docs/S5_DUAL_2026-10-24.md`、`docs/S5_CLOSURE_2026-10-24.md`、`scripts/s5_dual.py`、`scripts/s5_closure.py`。

## 第 73 轮：先让"自己写的表自己能读回来"，再谈观测设计（B026）

上一轮末尾开 S7（观测设计：非共线通道）时，第一次读自己刚跑出的 `history.csv` 就撞了：

```
HistoryError: cannot classify history channel 'axle0_y_acc_m_per_s2'
```

两个都是**静默**缺陷，723 项测试一个都没拦住：

1. **读不回来**：`io/history.py` 的 `classify()` 只认位移/速度/力/力矩/接触，没有 `_acc_m_per_s2` /
   `_acc_rad_per_s2` 规则，而 `read_history` 是按列逐个分类的 —— 一列不认识就整张表读不了。
   既有算例全是加加速度通道**之前**生成的，所以测试从没走到这条路。
2. **编号从 0 开始**：`_column_prefix` 用拓扑里的 0 基索引直出列名，于是同一根轴上
   状态列是 `axle0_y_m`、接触列却是 `axle1_left_normal_n`，而归档 oracle、全部文档与界面标签表
   都是 1 基。按名配对永远差一位，数值本身却完全正常。

修法与证据：

- `Kind` 增 `"acceleration"`，两条后缀规则给 `m/s^2` 与 `rad/s^2`；`channel_names()` 补上加速度名，
  并在 docstring 里写清节点表布局额外会发 `_x_acc_*` 与 `axle<k>_box_<left|right>_*`。
- 轮对/构架列名 `+1`；轴箱体的 `axle` 在 `vehicles/CRH380A_M_axlebox.json` 里统一改成 0 基，
  并由 `topology` 校验"轴箱所在的轴必须是某根轮对的轴"（写错就报错，而不是悄悄偏一位）。
- **顺手补上纵向加速度**：`_acceleration_channels()` 改为按 `body.dof` 遍历（原先是固定的
  `("y","z","roll","pitch","yaw")`，节点表里解出来的 `x` 加速度从来没被发出过），
  加速度列名改为与数字**同源**（`VehicleResult.acceleration_names`），写盘时再与状态列推导结果
  逐项对照，不一致就拒绝落盘（`SimulationFailure`）。
- `tests/test_history_naming.py` 6 项：真跑一个算例 → 整表读回；表头不得含 `axle0`/`bogie0`；
  加速度行与状态列逐项相等；唯一的例外只能是 `_spin_rad`（无轨道输入的簧下自由转动）；
  轴箱轴号与轮对一致。
- 全仓 `pytest` **729 passed, 1 skipped**（`--basetemp F:\velch_tmp\pytest`）。

## 第 74 轮：观测设计——该装哪个通道，以及两个在出结论之前就作废的判据

S7 要回答的问题不是"能不能把矩阵变小"，而是**"这个通道看见的东西，别的通道看不见吗"**。
这一轮的一半产出是方法学：原设计在**产生任何结论之前**就有两处结构性错误，都在数据出来前
撤回了——

1. **判据"加入后条件数下降 ≥30 %"恒成立**：给矩阵添一行不可能让任何奇异值变小
   （`AᵀA ⪯ AᵀA + bbᵀ`），所以条件数对**每一个**候选都会下降，包括完全重复的行。判据作废，
   条件数列只保留作与 S6d 的衔接，并标注为非证据。
2. **两频带的设计不可能回答这个问题**：两带 = 每通道 4 个实数，七条基线行已经张满 ℝ⁴，
   于是任何新行的新息**恒等于 0**。改成六带（0.2–12.8 m，12 个实数）后基线只张到 4 维，
   才有空间让新行"新"。两带那一版跑出来三个候选的 novelty 全是 `0.000`，若照它写结论，
   会得出"什么都不值得装"的假结论。

最终判据（先定后用）：**novelty** = 新行与已有行张成子空间夹角的正弦（增行必然改善条件数，
但"指到新方向"不是必然）；辅以**数值秩**与**相对幅值**。

实测（刚轨、直线、仅垂向不平顺，三个种子 20261024/7/11 结论完全一致）：

| 候选 | 秩 | novelty | 相对幅值 | 判定 |
|---|---|---|---|---|
| 轴箱横向 `_y_acc` | 4 → 5 | **0.374** | 2.9 % | **加了一个可用方向** |
| 轴箱纵向 `_x_acc` | 4 → 5 | 0.229 | 0.2 % | 只加了一层薄方向，基本是重复 |
| 轴箱点头 `_pitch_acc` | 4 → 4 | 0.000 | 0.000 | 这一工况根本没激励它 |

**基线七条垂向通道只张到 12 维里的 4 维**——这就是 S6d 那句"多测点买不到信息"的定量形态：
左右轴箱在对称工况下逐位相同，车体四角在低频上近似共线。这也修正了 S6d 的表述：
"七通道条件数 14.9–30.8"应读作**"七通道里只有 4 个独立方向"**。

限制写在文档里而不是事后解释：单工况、刚性轨、仅垂向激励（点头的"静默"只属于这个激励）、
0.31 的门槛是先定的、novelty 是几何量**不是信噪比**——S5 的结论（常数 H 不存在、
标定误差 65 %）一字未改。

顺带修掉两个文档设施缺陷（都是"检查没覆盖到"的同一种病）：

- `CHANGELOG_DOCS.md` 里存在**两个**生成的文档清单块，而测试只认第一个（第二个是上一轮遗留的
  73 行陈旧副本）；更糟的是块头点名的生成脚本 `.tmp/gen_docs_index.py` 早已不存在，
  所以清单只能手改。现在生成器落在 [scripts/gen_docs_index.py](../scripts/gen_docs_index.py)
  （带 `--check`），并会**删掉任何后续重复块**，重跑不会再次累积。
- 重生成后清单 **122 篇**，`tests/test_docs_index.py` 5 项全绿。

证据：[S7_OBSERVATION_DESIGN_2026-10-24.md](S7_OBSERVATION_DESIGN_2026-10-24.md)、
[scripts/s7_observation_design.py](../scripts/s7_observation_design.py)（三个种子首跑约 4 min，
之后读缓存约 5 s）。

## 第 75 轮：把轴箱横向加速度真正装进观测集，然后量它买到什么（S7b / S7c）

用户要求"增加轴箱横向加速度"。S7 已经算出它是七条垂向通道之外唯一补得上方向的那一条
（novelty 0.374），所以这一轮把它从"分析脚本里的一列"变成**产品里的一条观测**，再用两个实验
分别回答"它让反演更准了吗"和"它到底能看见什么"。

**代码侧（真正装上，不只是脚本）**

- `src/velch/inverse/sensors.py` 新增 `axle_box_acceleration(history, axle, side, axis="z")`：
  直接读求解器**解析输出**的 `axle<k>_box_<left|right>_{x|y|z}_acc_m_per_s2`，不做任何差分
  （对位置通道做二阶差分等于给高频加平滑，而高频正是轴箱加速度存在的理由）。角轴显式拒绝
  （单位是 `rad/s^2`）。缺通道时报出列名并指向 `wheelset_acceleration`。
- `sensor_table()` 改为：同一根轴上**有轴箱体就给三轴测点，没有才退回轮对加速度**——两者从不同时声称，
  否则等于把一次测量数两遍。`tests/test_sensors.py` +5 项（原样读取用 `np.array_equal`、
  横/垂是两个传感器、角轴被拒、缺通道报列名、同轴优先轴箱）。
- `src/velch/ui/store.py` 补齐**加速度中文标签**：`_UNIT_RULES` 原先没有
  `_acc_m_per_s2` / `_acc_rad_per_s2`，B026 新发的加速度列在 ③④ 屏会退回原始标识符。
  现在 `axle1_box_left_y_acc_m_per_s2` → `第1轴左轴箱 横移加速度 [m/s²]`、
  `carbody_roll_acc_rad_per_s2` → `车体 侧滚角加速度 [rad/s²]`，并特别处理 `x`：
  位置里它是"里程"，加速度里它是"纵向"（`里程加速度` 是句错话）。

**S7b：把横向加进"只激励垂向"的实验 → 什么都没变**

| 变体 | 行 | 条件数 | 标定误差 | 闭环 | 复原两带 (mm) |
|---|---|---|---|---|---|
| V（轴箱垂向） | 2 | 2.85 | 65.2 % | 8.39 % | +0.0835 / +0.0788 |
| V+L（加横向） | 4 | 2.84 | **65.1 %** | 8.31 % | +0.0835 / +0.0790 |
| V+W（加轮对垂向） | 4 | 11.95 | 67.4 % | 9.34 % | +0.0838 / **+0.1298** |
| 真值 | | | | | +0.0830 / +0.1030 |

V 变体**逐位复现 S5 发表过的 65.2 % / 8.39 % / 87.1 %**，先立住口径。横向加进去只动 0.1 个百分点，
因为两带=两未知量、垂向两行已经是方阵，加行只能平均噪声，而 65 % 是**偏置**。
反倒量出新事实：加轮对垂向通道把 2 m 带从 −23.5 % 推到 **+26 %**，两个传感器对同一真实值相差约 65 %
——"常数 H 不成立"从此有两个独立来源。

**S7c：换成两方向未知量，横向就能分开，但代价是两个数量级**

单带 2.0 m、`a_v = 0.10 mm` / `a_l = 0.06 mm`、两种方向各自单独激励成列：

| 观测集 | 实方程 | 秩 | 条件数 | 复合误差 | 闭环 | 复原 垂向/轨向 (mm) |
|---|---|---|---|---|---|---|
| V | 2 | **2/4** | — | 51.7 % | 0.78 % | +0.1005 / **+0.0003** |
| L | 2 | **2/4** | — | 48.2 % | 3.59 % | +0.1028 / **+0.0042** |
| V+L | 4 | **4/4** | **286.72** | 40.0 % | 1.25 % | **+0.0985 / +0.0688** |

三条读数：①单独任何一个通道都是**结构上分不开**（2 秩/4），两者都几乎把全部答案塞进垂向槽；
②加了横向变成可解，垂向 −1.5 %、轨向 **+14.7 %**——横向通道确实把轨向从"不可见"变成"可估"；
③但条件数从 2.85 涨到 286.72，复合误差 40 % 仍高于 30 % 门。原因之一是物理的：
**直线对称工况下横向加速度对垂向激励的响应（572.4）比对轨向激励（33.4）强 17 倍**，
它主要是被垂向几何经蠕滑耦合驱动的，不是"轨向专用传感器"。

**一条口径更正（写进文档，不藏）**：`relative()` 比的是复数向量，求解时虚部不被约束为 0，
所以复合误差里含虚部残差。S7b/S5 的 65.2 % 应读作复合口径，而 2 m 带的实幅值偏差是 −23.5 %
（这个数不变）。本轮起两份数字并列报出；要不要把判据改成"实幅值误差"必须**先定再跑**，
不能照着结果改判据。

**补测：286.72 里有 5.7 倍是量纲，剩下 50 才是真重叠**

`scripts/s7c_conditioning.py` 重读上面那批已跑完的运行（不重新仿真，约 10 秒），从各 `.tre` 反推
激励相位重建矩阵，先**逐位复现 286.720** 证明重建没错，然后：

| 度量 | 奇异值 | 条件数 | 复原 垂向/轨向 (mm) | 轨向误差 |
|---|---|---|---|---|
| 原样 | 6483.5 / 6483.5 / 22.6 / 22.6 | 286.72 | +0.0985 / +0.0688 | +14.7 % |
| 每行归一到单位范数 | 1.414 / 1.414 / **0.028** / 0.028 | **50.49** | +0.0989 / **+0.0613** | **+2.2 %** |

行范数是 6458.1 与 573.4（差 11 倍）。最小二乘对"某一行与其数据同乘正数"不变，但**报出来的条件数
会变**——所以 286 这个读数里有 5.7 倍是单位不齐，不是几何。而归一后**答案真的变好**
（轨向 14.7 % → 2.2 %），所以行等比化应当进估计算法，这是最便宜的一步，不动物理、不要新数据。
复合误差只从 40.0 % 降到 35.4 %，说明虚部残差不是缩放问题。

（写这段时踩过一次：反推相位时对全零的垂向列做拟合得到相位 0，横向列被整体转了角度，条件数一度报成
110.49。脚本已改成"取非零的那一列"，并把坑写进 docstring。）

证据：[S7B_LATERAL_2026-10-24.md](S7B_LATERAL_2026-10-24.md)、
[S7C_CROSS_DIRECTION_2026-10-24.md](S7C_CROSS_DIRECTION_2026-10-24.md)、
[scripts/s7b_lateral_blma.py](../scripts/s7b_lateral_blma.py)（约 25 min）、
[scripts/s7c_cross_direction.py](../scripts/s7c_cross_direction.py)（约 3 min）、
[scripts/s7c_conditioning.py](../scripts/s7c_conditioning.py)（约 10 s，重读既有产物）。
`pytest tests -q` **734 passed / 1 skipped**。

## 第 76 轮：柔性轮对的移植契约——SDITT 那边到底有什么、没有什么

用户指出 SDITT 源码在 `G:\研究生\SDITT-RW-FT-250728`。这一轮只做一件事：把"要借的那一层"的
**数据契约**钉死，免得后面按猜测写代码。没有改任何求解器代码。

**决定性发现：这份交付是 RW-FT，不是 FW。** 驱动
`SDITT_CR400_NoStrTIrr_250728_Face.m:303-304` 里 `NM_FW = 31*1` 被注释、`NM_FW = 0` 生效，
包名 `SDITT-RW-FT` 就是这个意思：刚性轮对 + 柔性轨道。柔性轮对的 **14 个 `.m` 全在**
（`Load_ModeShape_FW` / `Load_Rotation_FW` / `Matrix_Vehicle_FW_230409` / `Cal_Vjd_FW_230515` 等），
但**一个数据文件都没有**。

**数据契约（七个输入、两个产物）**：`Load_ModeShape_FW.m:10` 把工作目录 `addpath` 到
`E:\# Flex-Rigid-20200418\# FW_Rotation\ANSYS_FW_SDITT_220608_Mass21\Modes_RigidBeam_Mass21_6DOF_NRC_230506`
（E: 盘在、这个目录不在），读 `NodePos_FW_*.txt`、`ELIST.lis`、Harwell-Boeing 的
`HBFILE_FW_Free_MASS` / `_STIFF`、`Modefile_FW_*_FreqModal.txt`、逐阶 `Mode<k>.txt`、`NLIST_Trend_Lat.lis`，
最后 `:277` **现场生成** `FW_SDITT_230506_Mass21_v2.mat`。第二个产物 `Par_FW_Rotation.mat`
（`Matrix_J/E/L/G` + `Matrix_F_SumAll`，`C = GG + GJ − JG − JJ − E`）由**另一个工程**生成，
本树里只有消费者。四个轮对位置：`Pos_Z = [0.436619, 0.42223, 0.436619, 0.42223]`。

**本机实测缺什么**：2375 个文件里名字含 `FW` 的 14 个全是 `.m`；`Par_FW_Rotation.mat`、
`FW_SDITT_230506_Mass21_v2.mat`、两个 `HBFILE_FW_*`、各阶 `Modefile_FW_*`、`NodePos_FW_*`、
`ELIST.lis` 在 F:/G:/H:/E: 均搜不到；`D:\# Flex-Rigid-20200418`、`E:\# Flex-Rigid-20200418` 不存在。
结论：**能借方法与契约，借不到数字。**

**另一层倒是能借**：`Mat_FT_S8b.mat`（983.63 MB）是 `07(009)` 齿轨道岔的 Abaqus 模态集，
配 `DR_S8b_v*_Crossing.txt` / `_WeldAcc.txt` 逐阶实测阻尼比与 `Mileage_prr_2.txt`；
`Mat_FT_CN18_T4.mat`（18 号道岔）**不在包内**。我们已有 `ModalTrack`/`TrackKernel`（验到 3002 阶），
所以这一层是"换更细的模态集"，不是新能力。

**S8 五步计划与判据**（细节见新文档）：S8-1 模态坐标块 → S8-2 Φᵀ 映射 → S8-3 变形踏面接触几何
→ S8-4 `Ω²C`/`−2ΩG` 进 RHS 与雅可比 → S8-5 整车对照。其中 S8-1/S8-2/S8-4 的框架与模态来源无关，
可以先用合成模态（两阶 300/600 Hz）做出来。

证据：[docs/FLEXIBLE_WHEELSET_PORT_2026-10-24.md](FLEXIBLE_WHEELSET_PORT_2026-10-24.md)。
文档清单重生成 **125 篇**，`--check` 一致。

## 第 77 轮：S8-1 落地——模态核心先自己证一遍，再谈接进求解器

用户决定 `先按 B 的骨架 + A 的接口做`（B = 振型用解析近似、接触层标为不可引用；
A = 文件契约与校验钩子先立好，真 ANSYS 模态集到了只换一张表）。

本轮只做一件事，但做到底：**模态集与它的数学，先作为一个能自己证明自己的模块存在**，
不碰求解器。理由是它可以被一条**不需要振型、也不需要 ANSYS** 的判据钉死 ——
论文实测的频率分叉（420.2 / 499.1 Hz），在 `G` 拼错、符号反了、节径数错一个的时候立刻变红。

新增 `src/velch/wheel_modes.py`：`Mode` / `ModeSet`（`stiffness_diagonal` = `diag(ω²)`、
`damping_diagonal` = `2ζω`、`gyroscopic()` = 每个简并对一个 `[[0,−ND],[ND,0]]`、
`centrifugal()` = `G·G`、`free_frequencies_hz(Ω)` 走伴随矩阵特征值、`pair_splits_hz(Ω)` 闭式）、
版本化契约 `velch-wheel-modes/1`（`to_json`/`save`/`from_json`/`load_modes`，格式不符按名字拒绝）、
`thesis_crh380a_modes()`（论文表 2-3 的 31 阶 + SDITT 的 `DR_FW` 阻尼规则）、
`assert_split_matches_thesis()`（把实测值当靶子，放进库里而不只是测试里）。

**实测**（`tests/test_wheel_modes.py` 14 项）：200 km/h 下 ND2 → **418.57 / 500.83 Hz**
（论文 420.2 / 499.1，差 1.6 / 1.7），ND3 → **1142.61 / 1265.99**（论文 1145.4 / 1263.0，
差 2.8 / 3.0）；无阻尼时特征值解与闭式 `f ∓ ND·n` 一致到 `1e-6`。

**被自己的判据抓到的三个错**：① 表按"每个频率一行"写成 23 行 → `_pairs()` 立刻报"没有简并伙伴"，
正解是成对模态占两行、共 31 行；② 伴随矩阵每个模态出现两次（共轭对共享 |Im|），
`free_frequencies_hz` 返回 62 个值 → 只取 `imag > 0`；③ `mode_table()` 只给简并对左半边标 partner，
一份列表里同一模态一会儿成对一会儿不成对 → 两侧互指。

**一处顺带的更正**：§9.3 原写"1.6 Hz 残差来自 `C` 被截断与 `Ω²` 二阶项"。把 `C` 取成 `G·G` 后，
简并对的 `ω² − Ω²ND²` 与 `2ΩG` 一起给出的特征根**正好**是 `ω ∓ Ω·ND`（`s = −(ω∓μ)²`），
二阶项精确抵消 → 残差**全部属于 `J` 与 `E`**（要振型）。这改变了优先级：`J/E` 是"有振型才谈得上"
的精修，不是必须先补的缺口。

**还没做的**（文档 §10.4 写死，顺序不能反）：模态坐标接进 `Topology`（单位模态质量 +
`ω²`/`2ζω` 作为对地弹簧-阻尼，`LinkSpec` 的单坐标项正好是它）→ 陀螺项需要新的"速度耦合"元件
（现有 `axial`/`torsional` 都是位移型）→ 零模态时 `history.csv` 的 sha256 必须与冻结基线逐位相同。

证据：[docs/FLEXIBLE_WHEELSET_PORT_2026-10-24.md](FLEXIBLE_WHEELSET_PORT_2026-10-24.md) §10。


## 第 78 轮：S8-1 接进求解器——模态块落在轨道块之后，两条原计划被现实改正

上一轮写死的三件"还没做"里，**第一件就错了**，本轮当场改正并落地。

**原计划 ①「把模态坐标接进 `Topology`」作废**。单位模态质量 `1.0` 是归一化，不是 124 kg 真实质量；
做成 `Body` 后 `total_weight = Σ m·g` 会多算 `31×4 = 124 kg`，而重力没有对应项 ——
`translational_action_reaction` 门必挂。那是一个"看起来在算物理、其实在给幻影质量记账"的错。
正解：模态块由 `VehicleDynamics._build_modal_block()` 拥有，`mass` 用 `np.concatenate` 追加，
`Topology` 一行未改。

**落地的四处**：

| 文件 | 改动 |
|---|---|
| `wheel_modes.py` | `ModalBlock`（`K = diag(ω²) + Ω²·G·G`、`C = diag(2ζω) + 2Ω·G`、`f = −(Kq+Cv)`、`V = ½qᵀKq`、`names()`、`free_frequencies_hz()`）与 `ModalAssembly`（连续性校验、常数块求和、`mode_slice`） |
| `vehicle_solver.py` | `self.modal` 在连接器之前构建；`evaluate` 里轨道力与接触反力按 `[dof, dof+len)` 切片，模态力加在偏移处；能量加模态势能；稀疏骨架把整块标实心（静止时反对称陀螺行在 FD 探测里看不见） |
| `vehicle.py` | `_track_size`/`_modal_size` 单一实现；`flexible_wheelset` 块（`table-2-3` 或 `file`，文件 sha256 进 `asset_hashes`）；旧算例重映射后补 `[0.0]*n_modes` |
| `jacobian.py` | `self.track_stop = dof + track.dimension`；四处"尾部就是轨道块"改成切片；`_modal_blocks()` 常数块 |

**顺带修掉一个与 B026 同类的缺口**：`axle1_mode1_q_per_s` 无法分类 —— 状态规则只管 `_q`，
而写入器给每个状态都写速度孪生。**是测试先失败**（`HistoryError: cannot classify history channel
'axle1_mode1_q_per_s'`），不是我先想到。已补 `_q_per_s → "-"/velocity`。

**判据与实测**（`tests/test_modal_assembly.py` 9 项）：刚性算例 `dynamics.modal is None`；
`modal.offset == rigid.dimension`；未激励时前 `body+track` 行 `np.array_equal`、模态行恰为 0；
组装矩阵复现 420.2/499.1 与 1145.4/1263.0；模态雅可比 = 力律导数 `rtol=1e-12`；
能量恒等式中心差分 `atol=1e-6`；示例算例 59 → **183 坐标**、`max|q| = 0.000e+00`、八接触峰值差 **0.17 N**、
两车均 7/7 门。

**第二条原计划也作废**：「零模态时 `history.csv` sha256 逐位相同」在**轨迹层**做不到 ——
状态长度一变，右端浮点求和顺序就变，实测位置差 `1e-10…3e-9 m`（首帧与时间轴完全相同）。
判据拆成两条：**刚性算例逐位不变**（原有 755 项测试与冻结基线负责），
**柔性算例在模态不激励时模态坐标恰为 0、车身与轨道差 < 1e-8 m**。
把"加了 124 个零也要逐位相同"当目标是错的 —— 那是浮点顺序要求，不是物理要求。

**边界（不含糊）**：现在没有任何力映射到 `Φᵀf`，所以整程 `max|q| = 0`。
骨架到位、激励未接 —— 那是 S8-2，需要振型 `Φ`，也就是"要不要 ANSYS"的分界点。

全仓 **764 passed, 1 skipped**。证据：[docs/FLEXIBLE_WHEELSET_PORT_2026-10-24.md](FLEXIBLE_WHEELSET_PORT_2026-10-24.md) §11。

## 第 79 轮：把"相对位移"这条观测真正接进反演，然后被自己的行列量级否掉（S7d）

L5 说文献拿到 0.1–100 m 的长波靠的是**激光位移计测车体↔轴箱相对位移 `dr`**。我们不用新物理就能测它：
车体与轴箱的垂向位移都已在 `history.csv` 里，`dr = z_carbody − z_axlebox`。
所以这一轮把 `dr` 当成第二条观测塞进 S7b 的同一套两带 BLMA（同算例、同 6 个随机相位、同种子 → `V` 必须复现 65.2 %）。

**判据（跑之前定）**：`D` 单独要在 2 m 带上优于 −23.5 %；`V+D` 要 < 30 % 且闭环不高于 8.39 %；盲测 ≤ 1.5×标定；
另按 L5 口径报绝对 RMS。

**结果（判定用 `balanced` 估计器；`raw` 作对照）**：

| 变体 | 条件数 | 标定 | 闭环 | 盲测 | 逐带 |
|---|---|---|---|---|---|
| `V` | 2.85 / 1.09 | **65.2 %** | 8.39 % | 87.1 % | +0.6 % / −23.5 % |
| `D` | 51.57 / 3.89 | 111.5 % → 131.6 % | 92.3 % → 21.1 % | 143 % → 386 % | 不可用 |
| `V+D` | 2.85 / 1.67 | 65.2 % → **78.9 %** | 8.38 % | 117.2 % | +26.6 % / −19.3 % |

**四条判据全未通过**，而且 `V+D` 比 `V` 更差。

**否掉它的数字正好解释了文献为什么能**：`D` 的传递比是 **0.0048 m/m（0.1 m 带）** 与 **0.1190 m/m（2 m 带）**
—— 二系悬挂把 972 Hz 滤到 0.48 %、把 48.6 Hz 滤到 11.9 %。而 Dai 的 `dr` 之所以有用，
是因为 30–70 km/h 下 20–100 m 对应 **0.08–0.9 Hz**，正落在车体浮沉模态附近，那里车体跟着轨面走。
我们的两带在 97.2 m/s 下是 972 Hz 与 48.6 Hz，`dr` 里没有轨面的直流成分。
**所以"相对位移是短波缺的那条腿"这个猜想是错的**，这一轮把它钉死在数字上。

**顺带两条**：① `balanced`（行等比化）把 `D` 的条件数从 51.57 压到 3.89，却让标定误差变差 ——
S7c §6 那条建议要加限定：**均衡化之前先确认该行对该未知量真有增益**；
② 又一次 O010 同族的静平衡失败（`h0.1_5`，`120623.2 N` 一侧脱空），0.1 m 带只有 5/6 个实现，脚本打印了失败。

**下一次（S7e）已被这一轮的机理定死**：波段换到 **20 m / 40 m**（4.86 / 2.43 Hz）、算例 2 s，
预测 `D` 的传递比接近 1.0 m/m、`D` 单独 < 10 %；若不成，"位移通道"整条否掉。

证据：[docs/S7D_DISPLACEMENT_2026-10-24.md](S7D_DISPLACEMENT_2026-10-24.md)、脚本 `scripts/s7d_displacement.py`（20 次运行约 25 分钟）。

## 第 80 轮：长波段（20/40 m）相对位移带信号了，但加速度本来就够（S7e）

S7d 否掉短波段的位移通道后，剩下的疑点是：文献（L5）的 `dr` 用的是 **20–100 m**，我们从未在那个波段测过。
这一轮补上：**20 m / 40 m**（4.86 / 2.43 Hz）、2 s（194 m 行程）、8 个随机相位，
预测 `D` 传递比接近 1.0 m/m 且 `D` 单独 < 10 %。

**第一次尝试是失败的测量**：`V` 标定误差 344 %（S7d 同变体 65.2 %）、`D` 传递比报成 162/294 m/m。
诊断跑（完全不加激励）显示同一窗口的"等效幅值"是 `V` 17 211/60 537、`D` 478/1040 m/m ——
**194 m 真实几何在这些波段的能量是 0.1 mm 探针的 1000 倍**，绝对幅值法在这里测的是几何，不是探针。

**三处修正**：① 八相位回归带截距（`y_k = A·e^{iφ_k} + B`，B 是各次实现共享的几何项）；
② 目标/盲测/闭包改用 `±φ` 差分对（B 精确消掉）；③ 闭包按模长比较（`.real` 曾把 1 % 报成 56 %）。

**结果**：

| 变体 | 条件数 | 标定 | 闭包 | 盲测 | 逐带 | 绝对 RMS |
|---|---|---|---|---|---|---|
| `V` 加速度 | 1.79 | **0.7 %** | 1.0 % | 114.4 % | +1.0 / +0.3 % | 65.5 µm |
| `D` 位移 | 1.66 | 6.8 % | 5.1 % | 118.4 % | −4.1 / +8.1 % | 48.7 µm |
| `V+D` | 1.71 | 3.3 % | 1.9 % | 116.6 % | −1.4 / +4.1 % | 55.9 µm |

**预测成立但结论是否定的**：`D` 传递比 **0.79 / 0.63 m/m**（短波是 0.0048 / 0.1190）——长波段位移确实带信号；
可它**买不到精度**：`D` 6.8 % 不如 `V` 的 0.7 %，因为加速度在这些波段**根本没被衰减**
（实测 589 (m/s²)/m 对"完全跟随"的 931，是六七成量级，而短波只有 1/6330）。
所以"位移补加速度看不见的波段"这条线，短波（S7d）与长波（本轮）**两处都被否**。

**新发现：长波段也没有常数 H**。标定 0.7 %、闭包 1.0 %，但盲测 **114 %** 崩掉，而条件数只有 1.79。
机理是幅值：探针 0.1 mm 与静平衡侵入 65.5 µm 同量级，接触刚度 `∝√δ` 在一个周期里变 1.6 倍以上，
响应关于探针不是奇函数，`±` 差分里含与 A 同阶的偶次项。**这是 S5 那条"不存在常数 H"在长波段的独立复现**，
而且这次系统是良态的（1.79），说明它与病态无关。

**四条边界**：标定只有一个目标相位（0.7 % 是一次抽样）；盲测只有一组幅值（偶次项机制未复核）；
几何干扰是探针的 1000 倍，全部结论依赖差分构造；只测两带、单轴单侧、刚体位移之差。

**下一步**：不再找新观测，改 **按幅值分段的 `H(A)`**（3 段 × 2 带 = 12 实参数，每段 8 次实现），
方向与 L6（SNR 影响有限、误差由模型保真度决定）一致。

证据：[docs/S7E_LONGWAVE_2026-10-24.md](S7E_LONGWAVE_2026-10-24.md)、`scripts/s7e_longwave.py`（列数据缓存在 `F:\velch_tmp\s7e\columns.json`）、`.tmp/s7e_recompute.py`。

## 第 84 轮：S9-1 把变形放进型面，让接触搜索自己去发现（2026-10-25 凌晨）

S8-3 的变形是事后修正（先搜未变形型面，再手改深度与法向），三个量可以互相矛盾。本轮按 L11
（Gao & Dai 的接触线法：先有变形后的踏面，再取竖直距离最小点）把顺序正过来。

| 文件 | 改动 |
|---|---|
| `src/velch/modal_coupling.py` | `TreadRing.profile_projection`（核矩阵 × Φ_z，每环算一次）/ `tread_shift(q, u)`（按横向位置插值，环外钳制）/ `tread_slope(q, u)`（同一张场的斜率） |
| `src/velch/vehicle_solver.py` | 新增 `_deformed_profile(wheel, rail, q)`（零模态返回**原对象**）、`_tilted_geometry`（法向按变形斜率旋转）；删除 `_deform_geometry` 与手改深度路径；`_evaluate_patch` 每个 patch 只算一次变形型面 |
| `tests/test_modal_deformation.py` | 重写为 7 项，钉住"型面精确平移 / `penetration = δ − dz` 到 1e-9 / 力按 `δ^1.5` / 深位移移动接触点 / 法向 `−atan(slope)` / 左轮读镜像横向坐标" |

实测（同一算例，目标位移取在轮心）：

| 目标 | 接触点处 dz | 深度变化 | 力比 | `((δ-dz)/δ)^1.5` |
|---|---|---|---|---|
| +5 µm | −2.75 µm | +2.75 µm | 1.018269 | 1.018270 |
| +20 µm | −11.02 µm | +11.02 µm | 1.073732 | 1.073735 |
| −20 µm | +11.02 µm | −11.02 µm | 0.928037 | 0.928034 |

接触点在 20 µm 量级不动（这条振型在 20 mm 窗内只变 1.6 µm，远小于钢轨曲率），放大到 120 µm
才移动 1.75 mm——测试据此写成"深位移移动接触点"，不编造浅位移下的移动。

一处口径再次确认：`dz` 必须量在**接触点所在的横向位置**（距轮心 4 mm），量在轮心会得到 1.49 而
不是 1.13，上一轮就是因此误判。

全仓 `pytest` **790 passed, 1 skipped**；文档 `FLEXIBLE_WHEELSET_PORT_2026-10-24.md` 新增 §15。

## 第 85 轮：刚柔对比第一次给出的是一段起振瞬态，坐稳之后才只剩 1.2 %（S9-2 / S9-3）

S9-2 要求给"刚性 vs 柔性"的轮轨力对照。第一次跑出来的是直线 23.18 %、辙叉 87.24 %，看着像
柔性轮对改变了物理；把八个接触的法向力**逐帧求和**才发现稳态没变（480.86 vs 480.80 kN，整备
重量 477.30 kN），变的只有瞬时最大值（484.97 → 590.77 kN）。原因是模态坐标从零起步：踏面还没
被压进去，前几十毫秒是轮对按自己的 76.8 Hz 往下坐，而 0.05 s 的辙叉窗**整段都在里面**。

处置不是调容差，是把静平衡补齐：

| 文件 | 改动 |
|---|---|
| `src/velch/vehicle_solver.py` | 新增 `_settle_modal_coordinates(dynamics, q, v, rounds=12)`：`force[modal] = Q − K q` ⇒ `K⁻¹Q = q + K⁻¹force[modal]`，一次代换一次不动点迭代，收敛率 = 柔度×接触刚度 ≈ 0.5；在 `_integrate_vehicle` 里与 `_static_vertical_equilibrium` **交替两轮**，只在 `equilibrate_vertical` 打开时执行 |
| `src/velch/modal_coupling.py` | 新增 `ModalContact.has(axle)` |
| `src/velch/vehicle_solver.py` | 型面变形、法向倾斜、力投影三处都先 `has()` 再算（部分轴柔性会崩，见下） |
| `tests/test_modal_assembly.py` | +2 项：坐稳后 t=0 的模态残差 < 1e-3 倍且位移非零；刚性算例原对象返回 |
| `scripts/s9_compare.py` / `scripts/s9_acceleration.py` | 刚柔对照 + 加速度谱（读已落盘 history，不再仿真） |

结果：

| 窗口 | 刚性 | 柔性（坐稳后） | 差 | 墙钟 |
|---|---|---|---|---|
| 直线 0.4 s | 60.62 kN × 8，侵入 66.152 µm | 61.36 / 60.89 kN，侵入 70.079 µm | **1.21 %**（原 23.18 %） | 5.8 → 113.9 s（原 215.6 s） |
| 辙叉 0.05 s | 208.86 / 171.09 kN，侵入 155.058 µm | 164.44 / 163.93 kN，侵入 145.272 µm | 78.66 %（原 87.24 %） | 2.4 → 37.3 s |

辙叉那 78.66 % 现在有归属：`max |q_modal| = 2.5 mm`，是 200 kN 静柔度（70 µm）的 36 倍，即
冲击把弹性模态振起来了（论文 ND0 阻尼比 1e-3，Q ≈ 500），不是静变形，也不是初值。

S9-3 的加速度谱（Hann、去均值、单边幅值）：直线窗柔性版 300–400 Hz 能量是刚性的 **44 倍**
（0.00025 vs 0.00001 m/s²），但与通道 rms 6.8 m/s² 差 **4.5 个数量级**，所以在平滑直线上看不见，
"加了柔性轮对就能看见 345/378 Hz"不成立；辙叉窗只有 101 个样本、分辨率 19.8 Hz，刚性的 5 自由度
轮对也读出 10.61 m/s²，那是冲击泄漏，**该表不作证据**——要检验论文的 345 / 378 Hz 必须换 ≥0.5 s
窗口。

两个自造缺陷：① 只声明部分轴柔性时三处直接索引模态块 → `ModeError: no modal block for axle 1; built axles are [0]`，已加 `has()` 守卫；② `table-2-3` 那套只有频率没有振型，`_build_modal_contact` 返回 `None`，所以任何"模态该动"的测试必须加载 `vehicles/modes/CRH3C_wheelset_fe.json` —— 第一版单元测试正是被这条抓住的（`displacement == 0`）。

全仓 `pytest` **792 passed, 1 skipped**；文档 `FLEXIBLE_WHEELSET_PORT_2026-10-24.md` 新增 §16。

---

## 第 89 轮：给轮对加纵向自由度，让轴箱纵向通道第一次有物理来源（S9-7）

S9-6 之后 `axle1_box_left_x_acc_m_per_s2` 的谱峰是 0.000 m/s² —— 因为轮对**没有纵向坐标**，
`x` 由走行速度给定。本轮把它变成可解坐标，并量它到底看到什么。

| 位置 | 改动 |
|---|---|
| `src/velch/vehicle_solver.py` | `self._wheel_axes` 按名字解析下标（取代八处 `wh + k`）；`station_m(rail, t, q)` 成为"轮子在轨道哪里"的**唯一**实现，接触评估与作用-反力门共用 |
| 同上 | `x` 里程含 `q[x]`；`travel = v0 + v[x]` 进蠕滑率；列名 **`axle1_dx_m`**（`axle<k>_x_m` 已是绝对里程，不可重用）；`_acceleration_name("axle1_dx_m") = "axle1_dx_acc_m_per_s2"` |
| `vehicles/CRH380A_M_axlebox_x.json` | 新车型：15 刚体 / **90 坐标** / 76 元件，8 根 `bearing_a{1..4}{L,R}_x`（1e8 N/m） |
| `tests/test_longitudinal_wheelset.py` | 6 项：坐标存在且 `x` 在 `y` 前、`dx_m` 不与里程列冲突且无重复表头、加速度名往返、`station_m` 随 `q[x]` 平移且随 `t` 前进、静止时该行力为零而位移后不为零、无纵向坐标的布局逐位不受影响 |
| `scripts/s9g_longitudinal.py` | 新脚本：50 mm 波长的垂向或横向波磨，80 km/h，20 kHz |

实测（`numerically_checked`，谱峰精确落在 444.4 Hz）：

| 激励 | x 增益 | z 增益 | y 增益 (m/s²)/m |
|---|---|---|---|
| 垂向 30 µm | **0.04** | **26 455** | 4 009 |
| 横向 30 µm | **936** | 597 | 382 |

机理：垂向不平顺在恒定滚动半径下不改变蠕滑率，故 `F_x = f11·ν` 不变 —— **垂向波磨对纵向通道
物理盲**（0.04 是 z 的 1.5e-6）；横向不平顺把接触点沿型面横移、滚动半径变，纵向蠕滑力被激励，
且是三个通道里最强的。于是两个短波通道互补：**深度看垂向，轨向/多边形看纵向**。

冻结基线：`test_oracle_frozen` 3 passed；86 坐标车型的垂向增益 26 459 vs 90 坐标 26 455（差 0.02 %）。

还欠：解析雅可比没有 ∂/∂x（inexact Newton 省略）；没有多边形/偏心算例；86 与 90 两种车型只在
这一个工况上比过。另记一笔**无效测量**：先用 `channels: ["lateral"]` 配一个只填垂向列的 `.tre`，
两次结果逐位相同 —— "量到一个看起来像零的零"，脚本已改为按被测分量自写 `.tre`。

文档：`docs/LONGITUDINAL_WHEELSET_2026-10-25.md`。

## 第 90 轮：补上结论 2 的另一半（滚动半径 → 纵向通道），350 km/h 深度复测，并交出总说明

### 改了代码

| 文件 | 改动 |
|---|---|
| `src/velch/vehicle.py` | 新增 `WheelPolygon(order, depth_m, phase_rad)`：`radius_offset_m(spin) = depth·cos(order·spin + phase)`、`wavelength_m`、`frequency_hz`；`VehicleCase.wheel_polygon`，算例里用顶层 `wheel_polygon` 块声明 |
| `src/velch/vehicle_solver.py` | 新增 `_out_of_round_shift()`，在 `_evaluate_patch` 里把轮对剖面整体下移该偏移（`R = -z`，半径小了 z 就大）；**并把纵向切向力真正加进状态**：`if "x" in wheel_axes: force[x] += longitudinal_force_n`。此前这一项从未累加，因为 x 是给定的，"轴箱纵向通道恒为零"不是物理而是漏加 |
| `tests/test_wheel_polygon.py` | 5 项：几何定义、余弦相位、整体均值为零（所以静平衡可以忽略它）、算例解析、以及"半径小 30 µm ⇒ 轮-frame 接触点下移 30 µm 而侵入不变" |

### 量到的（同一 350 km/h、20 kHz、30 µm）

| 激励 | 轴箱 x 增益 | 轴箱 z 增益 |
|---|---|---|
| 垂向不平顺（80 km/h） | 0.04 | 26 455 |
| **多边形 order 10（359.8 Hz）** | **82.5 刚性 / 172.0 柔性** | 27 593 / 34 045 |

结论：垂向起伏对纵向通道几乎全盲（1.5e-6），滚动半径变化能把它点亮（0.3 %）。两个通道各自对应"深度"与"半径"。

### 350 km/h 短波深度复测（与生成的 .tre 比）

| 波长 | 激励频率 | 反演深度 | 偏差 | 采样 |
|---|---|---|---|---|
| 50 mm | 1 944.2 Hz | 36.96 µm | **+23.2 %** | 5 点/周期（1e-4 步长） |
| 100 mm | 972.2 Hz | 34.53 µm | +15.1 % | 10 点/周期 |

偏差随频率上升：1 944 Hz 在 1e-4 s 的求解步长下只有 5 个采样点，因此 +23.2 % 不能直接读作精度，需要 2e-5 s 才能定死。

### 新文档

- `docs/SOFTWARE_AND_INVERSION_2026-10-25.md`：① 软件怎么建的（四层结构、状态向量只在一处定长度、五块按需打开的能力、四个创新点及其可执行判据、车辆库与外部数据的分工）；② 长波与短波反演（三波段三机理、`f_n` 常数增益、差分测量消几何、Tikhonov 与闭合、四类精度判据、多边形与纵向通道）；③ 复算命令；④ 现在还做不到的五件事。

### 一条限制，写在文档里而不是藏着

x 自由的车型跑**垂直**不平顺会漂：自由车体没有纵向边界，不平衡蠕滑力会让它整体加速，最终滚到轮缘触发 `graph slope limit at axle2_right/right, x=28.3055772 m`。正解是给车体一个"列车其余部分"的纵向惯性边界，尚未做；因此 350 km/h 深度实验改用不带 x 的 `CRH380A_M_axlebox`。

## 第 91 轮：给纵向自由度一条边界，把纵向力变成开关

### 为什么

上一轮把纵向切向力接进状态之后，竖直不平顺的算例跑到 `x≈28.31 m` 就撞 `graph slope limit`：
x 自由的车体是一个**自由体**，任何不平衡的纵向力都让它整体加速，而这一项还经力臂进摇头行，
于是接触点一路走到型面陡处。两处修正：

| 改动 | 位置 | 内容 |
|---|---|---|
| 纵向边界 | `vehicles/CRH380A_M_axlebox_x.json` | 新增接地弹簧-阻尼 `train_x`（车体 → 地，1e9 N/m、1e6 N·s/m），代表"列车其余部分"的惯性；`axial_spec` 本来就支持 `to_body=None`，无需改代码 |
| 开关 | `src/velch/model.py` `RunSettings.longitudinal_force`（默认 False）+ `vehicle_solver._evaluate_patch` | 只有 case 显式打开时才把 `longitudinal_force_n` 加进 x 行 |

### 量到的（350 km/h、20 kHz、30 µm）

| 情形 | 轴箱 x 增益 | 轴箱 z 增益 |
|---|---|---|
| 垂向不平顺，开关关 | **0.0** | 26 454 |
| 多边形 order 10，开关开，有 `train_x` | **71.4 刚性 / 167.9 柔性** | 28 853 / 34 917 |
| 多边形，开关开，无 `train_x`（上一轮） | 82.5 / 172.0 | 27 593 / 34 045 |

读法：垂向激励对纵向通道仍然全盲（≤1.5e-6）；滚动半径变化点亮它，量级 0.25 % 的垂向；
接地边界把结果压低 13 %，说明"整体惯性"确实参与。垂向那一条现在能跑完，不再撞 slope limit。

## 第 92 轮：短波的 +23.2 % 不是欠采样；多边形通道在脱离接触前才线性

### 一、2e-5 s 求解步长复核（否决"欠采样"这个解释）

1 944 Hz 在原来的 1e-4 s 步长下只有 5 点/周期。把 `SOLVER_STEP_S` 降到 2e-5（26 点/周期）重跑 50 mm 一条：

| 量 | 1e-4 s | 2e-5 s |
|---|---|---|
| 反演深度 | 36.96 µm | **36.96 µm** |
| 逐窗散布 | 1.31 µm | 1.31 µm |
| 增益 (m/s²)/m | 30 057 | **30 057** |

逐位相同 → 那个 +23.2 % 是**物理传递差异**，不是数值。顺带把口径改准：`1/ω_n²` 只在同一车速下近似成立
（80 km/h 下 25 mm 与 50 mm 差 1.1 %），跨车速会涨 13.6 %（26 459 → 30 057），
所以短波反演精度应报 **10 %–25 %** 并注明标定车速。

### 二、多边形（滚动半径）通道的倍频程扫描

| 深度 | x 增益 | z 增益 | x/z |
|---|---|---|---|
| 15 µm | 130.4 | 28 403 | 0.00459 |
| 30 µm | 74.8 | 26 029 | 0.00287 |
| 60 µm | 20.5 | 19 658 | 0.00104 |

非线性（x 散布 146 %），原因是**每转一圈脱离接触**：静平衡侵入 65.8 µm，60 µm 的峰-峰 120 µm 已经超过 2×65.8 µm。
线性的边界是"深度 ≲ 侵入的一半"，越过它就要分段标定——与长波那条"没有常数 H"的结论同源。

新增 `scripts/s9j_radius_longitudinal.py`（3 次运行约 67 s 可复算，判据写在模块 docstring 里：
x 增益在 ±10 % 内随深度成正比、x/z 保在 2e-3…4e-3）。

## 第 108 轮：把模型也装进包里，而不是只装程序

上一版证明了"包里的随包柔性算例能跑"，但用户真正要的是**带着模型走**。这一轮把三个代表性算例
连同它们引用的资产导出成可移植目录，并让 `data_root()` 能在包里找到它。

| 变更 | 位置 | 判据 |
|---|---|---|
| 模型导出器 | 新增 `packaging/portable_models.py` | 内容哈希去重；改写成相对名；逐份 `load_vehicle_case` |
| 随包语料发现 | `data_root._bundled_corpus()` + `BUNDLED_CORPUS` | 环境变量/标记文件优先，其次四个包内候选 |
| 打包收集 | `packaging/Velch.spec` 加 `portable` | 解压后 `_internal/portable/validation/crh380a_m/` |
| 干净机器第 3 步 | `packaging/clean_room_test.py::step_bundled_corpus` | `selfcheck` 报 3 个算例 + 辙叉算例跑通 |

实测：298 个资产 / 12.1 MB；干净机器 **ACCEPT · 6 步 · 失败 0**；
zip 98.5 MB（+3.4 MB，压缩比把 12.1 MB 的资产压到约三分之一）。

## 第 107 轮：换一台电脑能不能跑，现在有一条自动验收

审查发现的关键事实不是"少补一个路径"，而是**三套根各说各话**：算例资产只认"相对算例文件"、
车辆库认"仓库/安装目录/_internal"、语料认环境变量与标记文件。于是出现"包能开、算例能跑、
柔性轮对跑不起来"的半可用状态。

| 变更 | 位置 | 为什么 |
|---|---|---|
| 资产解析一层 | 新增 `src/velch/assets.py` | 四种写法一个入口；`lib:` 复用 `vehicle_db.vehicle_dir()`，不新造第二个根 |
| 四处引用点改走它 | `vehicle.py`（型面 / `.tre` / `modal_file` / `flexible_wheelset.file`） | `base = case.parent` 这个隐含假设从此只在一处 |
| 随包柔性算例 | `examples/portable/case_flexible.json` | 唯一能被"干净机器"验证的柔性轮对入口 |
| 干净机器验收 | 新增 `packaging/clean_room_test.py` | 白名单环境 + 重命名路径 + 逐字节相同，才是"拷过去能跑" |
| 模态轨道切片 | `track_models.py` 的三处 `q[self.offset:]` | 柔性轮对模态块落在轨道块之后，切片会越界 |
| 语料根两种写法 | `data_root._with_validation()` + 提示词 + 示例 marker | 提示词让人填上一层，而程序要的是含 `crh380a_m` 的那层 |

证据：`packaging/clean_room_test.py` → ACCEPT · 5 步（5 车型 / selftest / 明文路径跑通 /
中文含空格路径跑通 / `history.csv` 逐字节相同）；`pytest` 819 passed；
`examples/portable/case_flexible.json` 实跑 `numerically_checked`、七门 7/7。

## 第 106 轮：车辆库真的进包了，而且是从 `_internal` 里找出来的

两处缺陷，都是"看起来像没做、其实是没接上"：

| 缺陷 | 症状 | 处置 |
|---|---|---|
| 模型没打包 | `packaging/Velch.spec` 只收集 `examples/` 与 `docs/`，打包版 `vehicle list` 是空的 | 收集列表加 `vehicles/`（5 台车 + `index.json` + `modes/CRH3C_wheelset_fe.json` 1.85 MB） |
| 打包了也找不到 | PyInstaller 6 把 `datas` 放进 `_internal/`，而 `vehicle_db._root()` 只查 `<安装目录>/vehicles` | 两个位置都查，与 `selfcheck.docs_roots()` 同一套做法；`VELCH_VEHICLE_DIR` 仍优先 |

证据：
- `tests/test_vehicle_ship.py`（新，4 项）——两种安装布局各一条、环境变量优先一条、模态集确实在库里一条；
- 冻结版 `velch-cli.exe vehicle list` → `车辆库：…\_internal\vehicles`，5 台车（35 / 38 / 38 / 86 / 90 自由度）；
- `vehicle validate CRH380A_M_axlebox` → `合法（字段、正负、左右对称、自由度剖面、出处齐全）`；
- `packaging/smoke_test.py --readonly-acl` → ACCEPT · 8 步 · 失败 0 · 跳过 0；
- 全仓 `pytest` 813 passed, 1 skipped；`physics_invariants.py` → UNCHANGED；包 zip 95.1 MB。

## 第 105 轮：按带拆开，判据应当按带写

`scripts/s9aa_band_split.py` 用已有的三组相位结果核对 §15 的归因（单带反演的误差就是该带标定误差）：

| 相位 | 两带聚合 | 只 20 m | 只 40 m |
|---|---|---|---|
| 1.0065 | 1.9 % | **0.1 %** | 2.5 % |
| 3.1009 | 0.4 % | **0.0 %** | 0.6 % |
| 5.1953 | 12.4 % | **1.0 %** | 15.9 % |

**20 m 带 0.0–1.0 %、三相位全稳；40 m 带 0.6–15.9 %，全部摆幅都在这里。** 所以判据不能写成"长波标定 ≤3 %"这种两带聚合的数，必须写成按带：20 m 带 ≤1 %，40 m 带在 0.1 mm 幅值下只报量级、需 0.3–0.5 mm 幅值或整数周期记录才能定量。

证据：`docs/BAND_CAPABILITY_2026-10-26.md` 第 15.1 节、`F:\velch_tmp\s9i\band_split.json`。

## 第 104 轮：长波也吃相位，1.945 % 是三次里最好的一次

§8 的 1.945 % 只有一个目标相位。用同一组 H 列、只换目标相位重放三次（`scripts/s9y_longwave_phases.py`，6 次运行 × 约 1 000 s）：

| 相位 (rad) | 标定误差 | 20 m 带 | 40 m 带 |
|---|---|---|---|
| 1.0065（原发表） | 1.9 % | +0.1 % | −2.5 % |
| 3.1009 | **0.4 %** | −0.0 % | −0.6 % |
| 5.1953 | **12.4 %** | −1.0 % | −15.9 % |

**均值 4.9 %，极差 12.0 个百分点**，所以"长波 ≤3 %"在 3 个相位里 2 个成立、1 个不成立。

机理不是窗泄漏：`scripts/s9z_leakage_check.py` 在窗内做单频复数最小二乘，20 m 带幅值三次只差 **0.6 %**、残差/幅值稳定 0.22；40 m 带**残差是幅值的 2.2–2.5 倍**，幅值随相位掉 13 %，正好等于标定误差的摆幅。真正原因：**0.1 mm 幅值的 40 m 分量在这个 194 m 记录里信噪比 < 1**，它贡献的那部分是噪声抽样。

修订后的门槛：**20 m 带 ≤1 %（三相位都成立）；40 m 带在 0.1 mm 幅值下不可定量，需提到 0.3–0.5 mm 幅值或拉长到整数个 40 m 周期（20.6 s，单次约 1.7 h）**。

证据：`docs/BAND_CAPABILITY_2026-10-26.md` 第 15 节、`F:\velch_tmp\s9i\phases.json`、`F:\velch_tmp\s9i\leakage.json`。

## 第 103 轮：偏置的样本外检验——两带拟合、第三带检验，四个带 3/4 → 4/4

第 102 轮把短波误差分成偏置与散布。偏置只有在样本外仍是常数时才值得标定，所以 `scripts/s9x_bias_calibration.py` 只用种子 1、2 拟合每个带一个乘性常数，再用于**从未参与拟合**的种子 3：

| 带 (m) | 真值 | 种子 1+2 | 常数 | 种子 3 | 标定前 | 标定后 |
|---|---|---|---|---|---|---|
| 0.05–0.1 | 11.000 | 9.381 | 1.173 | 9.152 | −1.60 dB | **−0.21 dB** |
| 0.2–0.4 | 8.500 | 9.189 | 0.925 | 9.307 | +0.79 dB | **+0.11 dB** |
| 0.8–1.6 | 12.000 | 9.187 | 1.306 | 10.087 | −1.51 dB | **+0.81 dB** |
| 3.2–6.4 | 9.000 | 8.086 | 1.113 | 6.724 | −2.53 dB | **−1.60 dB** |
| 1.6–3.2 | 3.000 | 4.508 | 0.665 | 3.340 | +0.93 dB | −2.60 dB |

真值 ≥8 µm 的四带：**未标定 3/4 → 标定后 4/4** 在 2 dB 内。三条限制同时写下来：

1. 这是**原理证明**而非"已标定"——两个种子拟合、一个种子检验，样本量太小；
2. 常数必须**按车型与速度重取**（同一 `k/m` 在 80 与 350 km/h 相差 13.6 %）；
3. 1.6–3.2 m 标定后反而更差（+0.93 → −2.60 dB），因为它的常数是从 3.90 与 5.12 µm 的散点上取的，属"用噪声拟合噪声"，所以这一带只报分辨率底、不做标定。

证据：`docs/BAND_CAPABILITY_2026-10-26.md` 第 14 节、`F:\velch_tmp\s9u\bias_calibration.json`、`scripts/s9x_bias_calibration.py`。

## 第 109 轮：只读审查的七个缺陷——两处静默错数、一处 .tre 假警报

代码审查工程师做了一轮只读审查（HEAD `a9f43c8`），报 13 条，其中 7 条落实为修复。全部细节见
`docs/AUDIT_FIXES_2026-10-26.md`。

**先纠正我自己的误判**：我报的"`.tre` 完全不生效"不是缺陷。施加链路完好（`ShiftedSeries`
在 40.5125 m 处给 +30.0 µm），真正原因是**几何错配**——`x_start=38 m` 时四轴扫过 28.0–33.6 与
45.5–53.6 m，而波磨带在 40–41 m，没有任何车轮走到它。改 `x_start=30` 立刻出现
`max|ΔF| = 7.56e4 N`。为防再犯，装配完 `irregularity` 后做一次里程区间求交，空交时发
`RuntimeWarning` 并在记录里写 `reach`（四轴区间、激励带、`overlaps`）。

**两处静默错数**：

- **B028** `src/velch/track_models.py` 三处把竖向轨道坐标写死成 `36 + 2*i`
  （`internal_force` / `potential_j` / `support_reaction`）。只有 35 坐标的内联车型才对；
  节点表（38 / 86 坐标）下竖向支撑、位能、功率**全部为零**，横向仍正确，所以不崩、只算错。
  现在一律 `self.offset + 2*i (+1)`；`offset=35` 时逐位不变。
  它之所以一直没被看见，是因为 **O010 先一步挡住了**（节点表在柔性轨道上静平衡本就不收敛）；
  O010 一修好，它就会立刻变成静默错数。
- **B031** `src/velch/uncertainty.py` `fold_non_negative` 里的 `sqrt(x)**2` 是恒等式，
  被截断分量的方差一点没折 → 报告成"均值 0、σ 不变"，即**确定等于 0**。改成半正态
  `(1 − 2/π)·σ²`。

**其余五条**：B029 v1 路径 `solver.py:73` 取未包装的 `rail.profiles` → `.tre` 静默失效；
B030 接触几何 LRU 键缺横向指纹 → lateral/gauge/roll 通道被吞；
B032 `portable_models.build()` 无防护 `rmtree`（`--target` 手误可删掉语料）；
B033 生成器把同一份场赋给每个通道（横/竖 corr = 1.0）；B034 `generate()` 默认
`step = shortest` 自相矛盾、无参调用必抛。

另：`assets.py` 的 `lib:`/`case:`/`data:` 前缀补了包含性校验，`lib:../..` 不再越出数据根。

**验证**：`tests/test_audit_fixes.py`（9 项）+ `tests/test_uncertainty.py`（10 项）全绿；
全仓 **838 passed, 1 skipped in 117.21s**。冻结基线未动（唯一被冻结基线走到的分支是
`offset=35`，与旧常量逐位相同）。

## 第 102 轮：收尾——带平均算子、三种子、D4 有界，以及 200 km/h 的价码

- 带平均算子把叠加误差从 **35.4 % 降到 16.0 %**（Pearson 0.978），单种子反演 **6/8**；
- 三种子重测把主张修正为 **5/8**，并把"偏置"（0.05–0.1 m 与 0.8–1.6 m 三次都低 15–21 %、散布 1.3 %/6.7 %）与"散布"（真值 ≥8.5 µm 为 1.3–13.5 %，≤3 µm 为 18–141 %）分开；6.4–12.5 m 两次解到 0，判不可反演；
- D4 量化：长波差分首末比 1.001/0.974/1.008/1.008（≤2.6 %），短波有信号区 1.06–1.19，残余只在 0.8–1.6 m 前 0.5 s（估计器从 0.40 s 起算）；末窗 <1e-3 的组标 `n/a`，避免"除以零"被读成抵消失败；
- 200 km/h 尝试：测站表扩到 400 m，单段 2 s 运行实测 **660 s**（80 km/h 为 110 s；0.05 m 带在 200 km/h 是 1111 Hz，精度限制的步长小得多），9 对差分需 ≈3.3 h，09:00 前跑不完，已停并记价。

今晚最终能力：长波 20–40 m 标定 **1.945 %** / 闭环 **0.664 %**；短波 0.05–0.4 m 与 3.2–6.4 m 在 2 dB 内（散布 1.3–13.5 %）；0.8–1.6 m 在边界；1.6–3.2 m 与 6.4–12.5 m 不可定量；0.025–0.05 m 单频投影 80 km/h +9.7 %、350 km/h +4.9 %。

证据：`docs/TASKBOOK_INVERSION_NIGHT_2026-10-26.md` 第 6 节、`scripts/s9s_bandaverage_operator.py`、`scripts/s9u_seed_spread.py`、`scripts/s9v_cancellation.py`、`scripts/s9w_speed_bands.py`、`F:\velch_tmp\s9w\out_b00_plus\manifest.json`。

## 第 101 轮：把“差分抵消了多少”量出来，D4 从怀疑变成有界

评审 D4 说 ±A 差分只能抵消 12–600 倍（13 Hz 极限环相位差约 8°）。那个极限环已被 **B027** 消除，所以这条要重测。新脚本 `scripts/s9v_cancellation.py` 不需要新仿真——每组 ± 对都在磁盘上，把差分切窗比较首末即可：

| 组 | 首窗 | 末窗 | 首/末 |
|---|---|---|---|
| 长波 col20 / col40 / target / replay | 0.0799 / 0.0146 / 0.0644 / 0.0645 | 0.0798 / 0.0150 / 0.0639 / 0.0640 | **1.001 / 0.974 / 1.008 / 1.008** |
| 短波 b03 / b05 / b06 / test | 0.0037 / 0.0369 / 0.0054 / 0.1489 | 0.0031 / 0.0341 / 0.0099 / 0.1404 | 1.192 / 1.082 / 0.541 / **1.061** |
| 短波 b04（0.8–1.6） | 0.0686 | 0.0346 | **1.981** |

- 长波差分全记录起伏 **≤ 2.6 %**，D4 对长波的怀疑消除（也解释了修好测站表后长波立刻落到 1.9 % / 0.66 %）；
- 短波有信号的区 1.06–1.19，唯一 2 倍余额出现在 b04 的**前 0.5 s**，而估计器从 **0.40 s** 起算，已挡在外面；
- 0.05–0.4 m 三组的末窗落在 1e-5，比值是“除以零”，脚本对 `tail < 1e-3` 标 `n/a`——这条口径要写下来，否则会被读成“抵消失败 26 倍”。

D4 至此有界：长波 ≤ 2.6 %、短波 ≤ 19 %，残余集中在前段且不进估计窗口。

证据：`docs/BAND_CAPABILITY_2026-10-26.md` 第 13 节、`scripts/s9v_cancellation.py`。

## 第 100 轮：三个随机种子把“6/8”修正成“5/8”，并把偏置与散布分开

第 99 轮的带平均算子在**一条**测试随机轨道上给出 6/8 带 ≤ 2 dB。一次实现分不清“方法的性质”和“这一次的相位”，所以用三个种子重跑测试轨道（同谱形、不同相位、同一算子），`scripts/s9u_seed_spread.py`（3 对差分，每对约 420 s，全部 `numerically_checked`）。

| 带 (m) | 真值 µm | 种子 1 | 种子 2 | 种子 3 | 均值 dB | 散布 |
|---|---|---|---|---|---|---|
| 0.05–0.1 | 11.000 | 9.306 | 9.456 | 9.152 | −1.45 ✔ | 1.3 % |
| 0.1–0.2 | 2.250 | 2.287 | 2.128 | 1.945 | −0.51 ✔ | 6.6 % |
| 0.2–0.4 | 8.500 | 10.276 | 8.102 | 9.307 | +0.72 ✔ | 9.6 % |
| 0.4–0.8 | 2.750 | 3.072 | 1.831 | 2.069 | −1.47 ✔ | 23.1 % |
| 0.8–1.6 | 12.000 | 9.764 | 8.611 | 10.087 | −2.04 ✘ | 6.7 % |
| 1.6–3.2 | 3.000 | 3.896 | 5.120 | 3.340 | +2.75 ✘ | 18.0 % |
| 3.2–6.4 | 9.000 | 9.070 | 7.102 | 6.724 | −1.43 ✔ | 13.5 % |
| 6.4–12.5 | 2.000 | 0.000 | 0.000 | 2.962 | −6.10 ✘ | 141 % |

叠加误差 16.0 / 23.7 / 17.9 %。三条结论：

1. **三种子均值 5/8**（单种子 6/8）。差别全在 0.8–1.6 m：单次 −1.79 dB 过线，均值 −2.04 dB 差 0.04 dB 出线。对外只能说"六个带里五个"。
2. **散布分层**：真值 ≥ 8.5 µm 的带散布 1.3–13.5 %；真值 ≤ 3 µm 的带散布 18–141 %。又一次是信息量决定精度。
3. **偏置 ≠ 散布**：0.05–0.1 m 与 0.8–1.6 m 三次都偏低 15–21 % 而散布只有 1.3 % / 6.7 %，属可用一个标定系数吸收的偏置；6.4–12.5 m 两次解到 0，按不可反演处理。

最终主张：长波 20–40 m 定量（标定 1.9 %、闭环 0.66 %）；短波 0.05–0.4 m 与 3.2–6.4 m 定量（散布 1.3–9.6 %）；0.8–1.6 m 在边界；1.6–3.2 m 与 6.4–12.5 m 不可定量。

证据：`docs/BAND_CAPABILITY_2026-10-26.md` 第 12 节、`F:\velch_tmp\s9u\seed_spread.json`、`scripts/s9u_seed_spread.py`。

## 第 99 轮：换成带平均探针，叠加误差 16 %、反演 6/8 过 2 dB

第 98 轮发现带中心单音系统性低估带平均 1.15–1.92 倍，这一轮把探针换成**带平均随机相位宽带**（`scripts/s9s_bandaverage_operator.py`，每带一条、只保留被探倍频程，5 µm rms，8 个探针 + 测试对）。

- 叠加误差 **35.4 % → 16.0 %**，Pearson **0.978**；measured/predicted 从“八带全部 1.15–1.92”变成 0.85/1.02/1.20/1.02/0.82/1.19/1.03/0.30，系统性偏差消失；
- 这一组探针第一次看到**真实的相邻带耦合**（0.4–0.8 对 0.2–0.4 是对角的 16 %），单音探针看不到；
- 反演（`s9t_band_average_analysis.py`，另加非负约束）：**对角 5/8、全矩阵 6/8、非负 6/8** 在 2 dB 内；未过的两带分别是 1.6–3.2（真值 3.00 µm，落在 3–4 µm 底噪上）与 6.4–12.5（无约束解为负）。

这是第一个能同时解释宽带记录（叠加 16 %）并在 6/8 带上给出定量幅值的算子；与第 5 节的对角方法同级，但那一条每次只知道一个带。

证据：`docs/BAND_CAPABILITY_2026-10-26.md` 第 11 节、`F:\velch_tmp\s9s\operator.json`、`F:\velch_tmp\s9s\analysis.json`。

## 第 98 轮：带算子重测——耦合塔了，剩下的误差是“一个音不等于一个带”

B027 修完后，用干净工作目录重测 8×8 带算子（`scripts/s9m_fresh_operator.py`，旧缓存不带协议指纹，见 D7）：

- 非对角元从每行 280–5 900 塔到 **最大 40.3**（对角 273–146 759），反过来说明修前那个“共同低频足迹”就是 13 Hz 模态；
- 叠加误差 **51.0 % → 35.4 %**，Pearson 0.939；
- 但对角 2/8、全矩阵 3/8 过 2 dB，因为 `measured/predicted` 八个带**全部在 1.15–1.92**，即带中心单音系统性低估带平均。

对照结论：**带平均标定**（`s9l`，随机相位宽带）**6/8 过 2 dB**；**带中心单音**（2/8、3/8）只能用来测耦合结构。这一条把“为什么两种方法结果不一样”说清楚了，也给出下一步：带平均标定 + 可见带解耦。

证据：`docs/BAND_CAPABILITY_2026-10-26.md` 第 9–10 节、`F:\velch_tmp\s9m_fixed\matrix.json`。

## 第 97 轮：长波重测——标定 1.9 %、闭环 0.66 %，两条门槛都过

审查意见 D1 指出 `s9_inversion.py` 没有站位表守卫：`SPEED = 97.2222`、`DURATION_S = 2.0`、`x_start = 13.5` 的行程到 **217.9 m**，而这个算例的钢轨站位只到 **150 m**——`s9i/out_target_plus` 在 **t = 1.3015 s** 永久失去接触、`axle1_z_m = −2.474 m`，分析窗口里 **31 %** 是自由落体。所以上一轮报的"长波 3.8 % / 闭环 1.20 %"是无效记录上的数。

这一轮把两件事修掉再重跑：

1. `flexible_base()` 把末站位**克隆到 400 m**（算例是等截面直线，克隆是延长几何而不是编造几何），并在仍然不够时直接 `SystemExit: run leaves the rail station table: reach …`；
2. `--columns` 重测四个探针列，`columns.json` 里带上 `bands / amplitude / speed / duration`，`load_columns()` 校验这四项（D11 的缓存指纹问题）；
3. 顺带修掉 B027（轴箱缺转动约束，13.094 Hz 四重根 ζ = 0），见 `docs/AXLEBOX_RESTRAINT_2026-10-26.md`。

重跑结果（12 次运行、9 737 s，全部 `numerically_checked`）：

| 变体 | 条件数 | 标定 | 逐带 | 反演 (mm) | 闭环 |
|---|---|---|---|---|---|
| **V** | 1.37 | **1.9 %** | +0.1 % / −2.5 % | 0.08305 / 0.10043 | **0.66 %** |
| D | 1.16 | 2.6 % | −2.0 % / −2.9 % | 0.08132 / 0.10003 | — |
| V+D | 1.25 | 2.5 % | −1.5 % / −2.9 % | 0.08177 / 0.09999 | — |

真值 0.0830 / 0.1030 mm。H 的对角（V）：20 m 探针 **957.80**、40 m 探针 **234.01** (m/s²)/m；D：1.1314 / 1.0388 m/m。

两点必须一起看：**H 的量级比无效记录那一次大了一倍多**（583.69 → 957.80），主要来自记录合法化——自由落体把差分响应压低了一半；而 **D 通道在长波上第一次可用**（2.6 %），与 S7e 的 0.79/0.63 m/m 传递比一致，但 V+D 并不比 V 更好，说明两条观测在长波上高度相关。

证据落在 `docs/BAND_CAPABILITY_2026-10-26.md` 第 8 节与 `F:\velch_tmp\s9i\inversion.json`。

## 第 96 轮：350 km/h 的短波深度误差从 +23.2 % 降到 +4.9 %——同一处装配缺陷

B027 修完后，把 350 km/h / 20 kHz / 50 mm 那个算例原样重跑（`scripts/s9i_highspeed_shortwave.py`，`CRH380A_M_axlebox`，`numerically_checked`，407.5 s，12 001 样本）：

| | 修前 | 修后 |
|---|---|---|
| 反演深度 | 36.96 µm | **31.47 µm** |
| 真值 | 30.00 µm | 30.00 µm |
| 误差 | **+23.2 %** | **+4.9 %** |
| 逐窗散布 | 1.31 µm | **0.43 µm** |
| 常量 `(2π f_n)²` | 24 398 | 24 398（不变） |

逐窗读数 30.19 / 31.55 / 31.70 / 31.60 / 31.59 / 31.64 / 31.61 / 31.58 / 31.65 / 31.60 µm——修前是 35.1–38.8 µm 的**系统性偏高**，现在是紧贴 30 µm 上方的一条平线。

这一条把因果钉死了：+23.2 % 不是欠采样（2e-5 s 求解步长给出逐位相同的 36.96 µm，第 92 轮已证），也不是插值（2.5 mm 步长对 50 mm 基波只改 1.6 %），而是**轴箱那个 ζ = 0 的 13 Hz 模态把接触状态和通道方差一起抬起来**，投影到 1 944 Hz 上就变成固定的偏高。修掉装配缺陷，偏差从 23 % 掉到 5 %，不需要任何标定系数。

同一轮里 `s9m` 的 8×8 带算子第一次跑出来的表仍是修前的（脚本会从 `matrix.json` 续跑，我把缓存当成结果读了一次）——已删缓存重跑，表以重跑为准。

## 第 95 轮：修掉三处测量错误后，短波 8 带里 6 带达标（修前 2 带）

审查给出的 D1/D3/D5/D6/D8 不是五个独立问题，而是**一条链**：轴箱缺转动约束造出一个 ζ = 0 的 13 Hz 模态，它把轴箱通道灌满 9 m/s² 的假信号；为了让这个假信号"看起来像传递函数"，后面的每一步都在补偿它——速度取错、站位表跑出界、探针用峰值而回归用 rms、矩阵转置着求逆、底线测了不减。

B027（见 `docs/AXLEBOX_RESTRAINT_2026-10-26.md`）之后，同一套差分协议重测：

| 波长带 (m) | G (m/s²)/m | 真值 (µm) | 复原 (µm) | 误差 | dB | 零激励对照 |
|---|---|---|---|---|---|---|
| 0.05–0.1 | 79 680 | 11.00 | 10.31 | −6.3 % | **−0.56 ✔** | 0.00e+00 |
| 0.1–0.2 | 252 200 | 2.25 | 2.49 | +10.7 % | **+0.88 ✔** | 0.00e+00 |
| 0.2–0.4 | 61 310 | 8.50 | 10.63 | +25.0 % | **+1.94 ✔** | 0.00e+00 |
| 0.4–0.8 | 107 000 | 2.75 | 4.43 | +60.9 % | +4.13 ✘ | 0.00e+00 |
| 0.8–1.6 | 76 810 | 12.00 | 9.71 | −19.1 % | **−1.84 ✔** | 0.00e+00 |
| 1.6–3.2 | 5 715 | 3.00 | 4.85 | +61.6 % | +4.17 ✘ | 0.00e+00 |
| 3.2–6.4 | 1 473 | 9.00 | 9.84 | +9.4 % | **+0.78 ✔** | 0.00e+00 |
| 6.4–12.5 | 599.8 | 2.00 | 1.63 | −18.7 % | **−1.80 ✔** | 0.00e+00 |

**6/8 落在预登记的 2 dB 判据内**（修前 2/8），零激励对照每带**严格 0.00e+00**。没过的是真值最小的两带（2.75 / 3.00 µm），复原值都停在 **4.4 / 4.9 µm**——残余底线约 **3–4 µm 等效深度**，来源是单边 Hertz 接触与蠕滑饱和的跨带泄漏（与"不存在常数 H"同源），不再是那条 13 Hz 模态。

协议侧同时修掉：`s9k.build_case` 保留内联车辆并写入正确速度、加"是否跑出站位表"硬报错（`ValueError: run would leave the rail station table`，D8）；`s9_inversion.flexible_base()` 把末站克隆到 400 m，仍不够则退出（D1），列缓存改为记录 `bands/amplitude/speed/duration` 指纹（D11），并新增 `--columns` 让它自己测列（D1 之后旧缓存整份作废）；`s9m` 的归一化改成除以输入 **rms**（D5）。

新文档 `docs/BAND_CAPABILITY_2026-10-26.md`（含"能说明什么/不能说明什么"两节）。`docs/RANDOM_SPECTRUM_INVERSION_2026-10-25.md` 的旧表按此作废。

## 第 94 轮：轴箱缺了一根转动约束，于是 13 Hz 的无阻尼模态把每个短波测量都压住了（B027）

审查 D3 说的是"轴箱通道里有一个 13.0 Hz、9.3 m/s²、永不衰减的分量"。追下去不是激励、不是轨道、不是接触：是**装配缺了一项约束**。

诊断链（每步都可复算）：

| 步 | 结果 |
|---|---|
| 零不平顺 6 s，逐 0.25 s 窗取 10–17 Hz 峰值 | 9.181 m/s²（t=0.12）→ 9.074（t=5.87），**剩 98.9 %**；接触占空比 1.0000 |
| 通道分解（末半窗） | 轴箱 z rms **6.7589**；**轮对 0.0016**；构架 0.0073；车体 0.0002 —— 只有轴箱自己在跳 |
| `s9p` 线性化特征值 | **13.094 / 13.094 / 13.095 / 13.095 Hz，ζ = +0.0000**（四重简并），同频段其它模态 ζ 0.011–0.185 |
| 动能参与度 | 八个 `axlebox*.z` 各 \|u\| 3.036e-3，占**总动能 97.6 %** |
| 力元普查 | 只有 `bearing_a*_z`（1e8，c = 0）与 `primary_*_z`（1.176e6，c = 1e4），两者伸长量都是 `(轮对.z − 轮对.roll) − (轴箱.z − 轴箱.roll)` 的同号组合 → **"上移多少就转多少"方向上刚度为 0** |
| 给 `bearing_*_z` 加阻尼 | 0 / 2e3 / 2e4 / 2e5 N·s/m 四档，13.094 Hz 的 ζ **全是 0.0000**（该方向两端速度差本来就是 0） |

根因：Simpack 用 `joint.type = 2`（转臂关节）连轴箱与构架，那个关节有转动约束；我们的节点表只有平移衬套（`arm_*_x` 13.7e6、`arm_*_y` 5.49e6）加一根 yaw 弹簧，**绕横轴的转动约束完全没有**。

修法：八根 `box_roll_{axle}{L,R}`（`axis: roll`，轴箱 ↔ 该轴所属构架，**k = 1.4e6 N·m/rad**＝`k_y·b²`＝5.49e6×0.25，c = 2.0e3），同时写进两个车辆文件与**算例自带的内联拓扑**——第二个坑：`case_straight_axlebox.json` 自带 76 元件拓扑，只改 `vehicles/*.json` 时 `velch vehicle validate` 通过而算例毫无变化。

| 指标 | 修前 | 修后 |
|---|---|---|
| 12.5–13.7 Hz 最低 ζ | 0.0000（13.094 Hz 四重） | **0.0042**（12.620/12.621 成对） |
| 零不平顺 10–17 Hz 峰值 | 9.181 → 9.074 m/s²（剩 98.9 %） | **0.020 → 0.000（剩 0.0 %）** |
| 50 mm 短波 / 80 km/h 的轴箱 z 增益 | 26 459 (m/s²)/m | **33 256 (m/s²)/m**（柔性车 30 868 → **75 815**） |
| 同一算例刚性 x 通道 | 0 | 0（对竖向仍然全盲，符合结论 2） |

最后一行是要如实说的代价：`(2πf_n)² = 24 398` 这个解析常数与修前实测只差 8 %，修后差 **36 %**——修前那个"吻合"里有一半是未约束轴箱的额外柔度凑出来的。所以短波增益必须**按车标定**，不能拿公式当结论。

`tests/test_axlebox_rotational_restraint.py` 4 项，其中一条**把八根元件删掉**再线性化，断言同一窗口 ζ < 1e-3——让测试能像缺陷那样失败。新文档 `docs/AXLEBOX_RESTRAINT_2026-10-26.md`；`docs/BUGS.md` 增 B027。

## 第 93 轮：随机谱一次反演——两次失败、一次部分成功，以及一个必须先说的假精度

用户提出：生成随机不平顺谱 → 激励 → 从轴箱加速度反演出"一条随机谱" → 与生成谱整体对照看精度。
做了三次（`scripts/s9k_random_spectrum.py`、`scripts/s9l_differential_bands.py`，新文档
`docs/RANDOM_SPECTRUM_INVERSION_2026-10-25.md`）。

| 次 | 做法 | 结果 |
|---|---|---|
| ① | 校准轨 A → 测试轨 B（同谱异种子） | **假精度**：6/8 带误差 0.0 %，因为两轨逐带幅值相同、且激励淹没在起振本底里（SNR≈0 dB），反演恒等于校准幅值 |
| ② | 异形测试谱 + 逐带比值 | **失败**：反演列逐行等于校准列；`german_low` 0/0 个带越过本底门，`flat` 只有 0.05–0.1 m 带越过（+83 %） |
| ③ | 差分对 `(a(+A) − a(−A))/2` | **零对照 0.00e+00**（本底精确抵消）；2/8 带 ≤2 dB；真值 ≥8.5 µm 的带 −16…+82 %，≤3 µm 的带全部挤在 4–16 µm |

结论：**单次宽带随机激励不能整体反演**——存在约 10–16 µm 等效深度的逐带串扰底（接触非线性的带间泄漏，
与"没有常数 H"同源）；真实 `german_low` 在 0.05–6.4 m 各带只有 0.01–6 µm，几乎全部在底之下。
此前窄带结果（0.05–0.1 m 的 10–25 %、20/40 m 的 0.7–3.8 %）不受影响，因为一次只激励一个带。
要把"整体"做成，必须分带窄带激励、逐带标定传递与串扰底，再合成整条谱。

## 第 112 轮：修车第一刀——O010 归因更正，静平衡与状态迁移的三处结构性缺陷

**结论先说：O010 不是"节点表车型"的问题，已关闭。** 五项受控对照（内联 35 / node 38 / 内联参数 + node 拓扑 /
内联布局 + node 参数 / axlebox 86）**五组全部收敛**，残差 6.9e-09…2.8e-08 N。真正的两个机制：

| 编号 | 实质 | 后果 |
|---|---|---|
| B035 | `remap_state` 只搬**车辆块** | 整条状态向量被喂进去时轨道块整段丢失 → 每根轨残留一个接触斑的静载 59 662 N，读起来像"车压在一侧" |
| B036 | 均摊值用 `weight_n / len(case.rails)`（12 根轨 vs 8 个接触斑） | 上限只比正确解高 **2.8 %**，左右不对称再大 3 % 正确解就被判成坏分支 |
| B037 | 机械能门只算车体 + 构架 + 轮对的重力势 | 86/90 布局的能量门漏 8 × 48.2 kg，与力循环对不上 |

改动：

- `src/velch/topology.py`：新增 `migrate_initial_state(supplied, source, target, *, tracks, modal_size=0)`
  （车辆块按名、轨道块原样、模态块置零），`remap_state` 加长度守卫——截断从"静默"变成"响亮失败"并指向它。
- `src/velch/vehicle.py`：抽出 `vehicle_parameters(block)`（内联与车辆文件共用一处解释），loader 改调迁移函数。
- `src/velch/vehicle_solver.py`：静平衡均摊改 `weight_n / (2 × 轮对数)`；判据要求"承载斑数 = 轮数"；提前
  break 窗口收到 1.25×、硬拒绝仍 1.6×；失败文案改为"N 个轮子里有几个承载"（原本文案把左右倾覆说成垂向不均摊）。
  能量门遍历所有含 `z` 的刚体。

验证：

- `python -X utf8 F:\velch_tmp\probe_o010_seat.py` → 内联 35 / node 38 / axlebox 86 **三布局全部 OK**（51 / 54 / 102 坐标），
  此前 38 与 86 在柔性轨道上必失败。
- `tests/test_initial_state_migration.py` **5 项**（整条向量被 `remap_state` 拒绝、轨道块原样、新坐标置零、
  模态块补零、长度不合报错）。
- `tests/test_oracle_frozen.py` + `test_topology.py` + `test_jacobian.py` → **11 项全绿**，冻结静载门
  59 680.5769 N / 65.47 µm 未动。

记录：`docs/BUGS.md` O010 归因更正（closed）+ B035 / B036 / B037。

下一步（同一目标"先把车修好，再做真实曲线"）：S1 轨道参考位移（`TrackKernel.local_state` 返回 `q + ref`、
弹簧力用 `q − ref`，`ref ≡ 0` 时逐位不变），S3 曲线力与速度场（离心力的竖向分量、`(1 − κ y)` 进纵向蠕滑）。

## 第 113 轮：把曲线的"几何"和"力"分开，并量出几何单独用不够

- 新增 `run.curve_geometry`（默认关）：打开后轨道核拿到设计中心线 `y(s)=s^2/(2R)`、`dy/ds=s/R`，
  超高进入两轨高差。`q` 仍只装弹性位移，势能/内力/雅可比不变。
- 实测（R=350 m、h=60 mm、100 km/h、0.05 s、86 坐标、解析雅可比+BDF）：只有体力时
  `graph slope limit at axle1_right/right:main, x=42.687753 m`；打开几何对齐后改成
  `vertical preload equilibrium failed ... 2 of 8 wheels carry load ... 264504.2 N`。
- 结论：几何对齐是必要条件、不是充分条件——静平衡目前只有垂向未知量（A1），车体不能横移/偏航，
  满足不了前后轴各 143 mm 的反向偏移。`curve_geometry` 因此保留为"分段直轨"路线的对照实现、默认关闭；
  要落地的是 S2（静平衡加横向/侧滚未知量）与 S3（曲率进蠕滑 `(1-κy)`/`Δv_x=∓vκb`、离心竖向分量）。
- 新增 `tests/test_curve_alignment.py` 5 项（含超高两轨高差恰为 `curve_cant_m`、弹性位移叠加）；
  新增 `docs/CURVE_GEOMETRY_2026-10-26.md`；全仓测试 866 passed / 1 skipped。

## 第 114 轮：柔性轨道的曲线里程本来就在，但静平衡还坐不住

- 核对 `case_diverging_R1100.json`：`path` 16 664 点 / 30.000–116.590 m / `y_m` 0→1.979 m，正好是
  `(s−50.578)²/(2×1100.75)`；钢轨站位 19 001 站、5 mm 间距、`local_compliant`。曲线里程不需要新建。
- 实测：自带暖启动 69 m 与冷启动 69 m 都失败（7/8 轮着轨、最重 118 538.9 N = 2× 均分）；55 m 通过；
  30 m 失败（前轴在站位表起点之外）。⇒ 卡点是静平衡只有垂向未知量（A1），与第 2 节同因。
- **B038（我自己上一轮引入的回归）**：均分改成"按接触斑"并要求每根声明的轨都承载，使多轨算例永远无法
  通过。改为按车轮归组（`_wheel_of`/`_load_per_wheel`），判据按车轮合力；新增
  `tests/test_seat_per_wheel.py` 5 项；`test_oracle_frozen` 仍 59 680.577 N。
- 下一步 S2：静平衡加横向/侧滚未知量（有曲率或超高时才启用），再重测上表；S3 再把 κ 放进蠕滑。

## 第 115 轮：冻住时间历程基线，并把速度做成值对象

审查的 A0/A1。`scripts/freeze_baseline.py` 新增：跑两个短算例，把 `history.csv` 的 sha256 写进 `docs/baselines/time_history.json`（`straight_rigid` 3.5 s / `06928c9db944796d`，`straight_flexible` 130.4 s / `ab81290f5924c3a5`，都 `numerically_checked`），`--check` 重跑比对、漂移退 2；JSON 里写明「同机同库」与「时长被缩短」两条限制。

`src/velch/speed.py` 新增 `Leg` / `SpeedSchedule`：`v_at(t)`、`x_at(t)`、`duration_s`、`distance_m`、`speeds`、`is_constant`、`constant_speed_m_s`、`describe()`；常速走**闭式** `x_start + v t`（累加会让里程差 1 ulp，进而改变采样站位，这条是 A1 验收的要点）；`Leg` 必须恰好给时长或距离之一。`tests/test_speed_schedule.py` 8 项（含「段内严格线性」这条可精确验证的性质，替代会误报的一阶中点积分）。

尚未接线（下一轮）：`RunSettings.speed_profile`、18 处 `travel_speed_m_s` 的替换、`jacobian.py:336` 的第二份里程公式、转速一致性控制器与第 8 门 `spin_tracking`。

文档：`docs/VEHICLE_SPEED_PROFILE_2026-10-27.md`。

## 第 116 轮：速度剖面接进算例，常速逐字节等价、多段先拒绝

`RunSettings.speed_profile` + `VehicleCase.speed_schedule` 落地：`SpeedSchedule.from_spec` 解析 `{"constant": {"speed_kmh": 80}}` 或 `{"legs": [...]}`，单位由键名给出（不给裸数字），长度二选一。

两处关键：
- 常速剖面是**唯一事实源**：`travel_speed_m_s=99` + `constant: 2.0 m/s` 与「只有 2.0 m/s」的算例 `history.csv` **逐字节相同**。第一版失败在覆盖时机——剖面在函数末尾才生效，而轮对初始自转在函数中段已按旧速度算好；改成读取之后立即覆盖，并把 `case_sha256` 改为提前算的磁盘字节哈希。
- 多段剖面**解析并随算例携带，但在 `simulate_vehicle` 明确拒绝**（消息写出段数与「先加 spin_tracking 门」），因为蠕滑参考速度还是单值，`v` 一变就会被 `saturate_creep_force` 的 `hypot` 吃成假纵向需求。

测试：`tests/test_speed_schedule.py` 11 项、`tests/test_speed_profile_case.py` 2 项（含逐字节等价，6.5 s）。

文档：`docs/VEHICLE_SPEED_PROFILE_2026-10-27.md` 新增第 5 节。

## 第 117 轮：力路径改走速度调度，基线仍逐位不变

`station_m`、`jacobian.py` 的第二份里程公式、蠕滑参考速度（3 处）、等效直线曲线的离心项，全部改成读 `dynamics.speed_at(t_s)` / `dynamics.x_at(t_s)`。新增 `speed_schedule` / `speed_at` / `x_at` 三个入口，常速剖面是纯直通（`_direction` 是 ±1.0，乘法只改符号位），所以 `freeze_baseline.py --check` 仍是 **UNCHANGED**（两个算例 sha256 与上一轮相同）。

测试 +2：`x_at` 与 `x_start + v*t` 逐位相等（含负速度），以及「字段 99 m/s + 剖面 2 m/s → 里程按 2 m/s」——后者是防止力路径里再出现直接读字段的地方。

文档：`docs/VEHICLE_SPEED_PROFILE_2026-10-27.md` 新增第 6 节（四个位置的原写法/现写法/为什么不能留两处）。

## 第 118 轮：轮对转速跟着速度，多段剖面放开

- `VehicleDynamics.spin_control`：一阶伺服把自转驱向 `v(t)/r`，增益取惯量（时间常数恒为 2 ms），2→4 m/s 阶跃峰值力矩 176.7 kN·m；`run.spin_control` 可显式开启，非匀速剖面自动开启，常速剖面不开。
- 第 8 门 `spin_tracking`：判据取**每条腿结束时**的相对滑移 ≤1 %——阶跃点本身是 2.000 m/s，无法跟随，如实报告但不入门。实测腿末 **1.39e-4**；常速剖面不带该门，仍是 7 门。
- `simulate_vehicle` 不再拒绝多段剖面（拒绝的理由已消失），`SpeedSchedule.leg_end_times_s` 提供腿边界。
- 测试 `tests/test_spin_control.py` 2 项；基线 UNCHANGED；**897 passed, 1 skipped**。
- 文档：`docs/VEHICLE_SPEED_PROFILE_2026-10-27.md` 第 7 节。

## 第 126 轮：几何路线上的超高改为明确拒绝；三组对照把"缺轨侧旋转"从唯一原因降为之一

- `_curve_placement` 遇到 `|curve_cant_m| > 0` 直接抛 `SimulationFailure`，消息指出轨面未旋转并给出两条出路（改用体力路线，或令 `cant = 0`）。理由：与其让一个接触表示不了的高差伪装成龙门失败，不如显式拒绝。
- `cant = 0` 下三组对照：只加横向偏移 → `x=70 m` 失败；只加航向 → `x=52.5 m` 失败；两者都加 → `x=70 m` 失败。因此"缺轨侧旋转"不是唯一缺口。
- 下一步是量而不是猜：在 `evaluate` 内对同一轴位打印 `local_state` 的 `y`、`placement(index, x_m)[0]`、接触搜索实际用的 `rail_y_m`，验证三者一致。
- 验证：`tests/test_curve_seat.py` 8 passed / 1 xfailed；冻结基线 UNCHANGED。

## 第 125 轮：放置逐轴一致（上轮猜测错），超高被做成台阶而非倾斜

- 逐轴对比证明放置没错：轨道 dy 与车轮 dy 在 +10/+7.5/−7.5/−10 m 四个里程**完全相等**（45.455 / 25.568 mm），因为放置本来就是 `(rail_index, x_m)` 与按刚体各自里程算的。
- 真正的错：`_curve_placement` 的 `dz = ±rise` 是**垂直平移**，轨型面没有转 θ；车体按 θ 滚之后与"平移未转"的轨面相遇，接触法向偏离竖直 → 斜率门在第一步退出（失败点全在右/外轨：x=67.5 / 70 / 52.5 m）。
- 反号对照：θ 取负仍全败，说明不是符号问题而是表示问题；θ 保留正号（物理方向对），缺的是轨侧旋转。
- 待做：`find_graph_contact/_strip_contact` 增加 `rail_roll_rad`，`local_state` 的 placement 从三元组扩到四元组 `(dy, dz, dz_dy, dy_ds)`。在此之前 `curve_geometry=true` 记为"表示不完备"，可交付口径用体力路线。
- 验证：11 passed / 1 xfailed；冻结基线 UNCHANGED。

## 第 124 轮：滚转车轮下包络改单值，曲线失败点前移；R=350@100 km/h 的验收在物理上不成立

- **修一个真正的闸门**：`contact.py` 的 `wheel_y = wheel_y_m + c·local_y − s·local_z` 要求严格递增，判据等价于 `|dz/dy| < 1/tan(roll)`；轮缘斜率几十，超高角 4.08° 时 `1/tan = 14`，于是**所有几何一致的曲线**（轨道+车辆都上曲线）在第一步抛 `wheel roll made the lower envelope non-monotonic in lateral y`。新增 `_single_valued_envelope()`：按 y 排序、同一 y 取最低点；`roll = 0` 时原样返回，故逐位不变（baseline UNCHANGED）。
- **拆开两个半场**：`run.curve_placement`（默认 None = 跟随 `curve_geometry`），可单独测量"车辆放上设计线"。
- 实测三个几何一致算例：包络错误消失，失败点移到 |s| 最大的两根轴（x = 50 / 70 m）——轨道按某里程搬了 45 mm、车轮按另一里程放了 45 mm，不同步即贴轮缘。下一步：每个接触体在自己的里程上取放置。
- **口径更正**：R=350 m @ 100 km/h 的平衡超高是 `h_th = 1.5·27.78²/(9.81·350) = 0.337 m`，超过模型自带的 0.20 m 上限、也超过实际线路 0.15 m 的最大超高 → 该工况必然是欠超高，不能要求"每轮 1.00×"。物理一致的写法是 **66.7 km/h @ 150 mm**（平衡）与 **100 km/h @ 150 mm**（欠超高，由限值门判定）。
- 验证：905 passed / 1 skipped / 1 xfailed；冻结基线 UNCHANGED。

## 第 123 轮：车辆按几何摆上曲线（S4 第一半），解析几何路线被接触搜索挡住

- 新增 `_place_on_alignment()` / `_body_offset_m()`：每个刚体按自己里程加 `y = s²/(2R)` 与 `yaw = atan(s/R)`；35 坐标布局没有 `x` 时由 `axle_offsets_m` 推里程（轮对取轴偏移、构架取两轴中点、车体取中心）。
- 实测放置：前轴 +10 m → y 45.45 mm / yaw **+9.0907 mrad**；前后轴航向差 **18.18 mrad = 20 m / 1100 m**，正是上一轮刚体偏置扫不到的分布。
- 但 `curve_geometry = true`（轨道也搬到曲线上并滚转）四个超高全部失败：0 与 0.107 → `ValueError: wheel roll made the lower envelope non-monotonic in lateral y`（`contact.py:106`）；0.02 / 0.05 → `graph slope limit`。
- 结论：放置不是瓶颈，卡在接触搜索对"滚转后包络"的表示；而"只用几何"本来就在专家列的 8 条错答案里，正确路线仍是随动坐标系 + 力/速度场。
- `tests/test_curve_seat.py`：7 passed + **1 strict xfail**（`test_the_analytic_geometry_route_would_run_if_the_contact_search_allowed_it`），几何路线一旦能跑，这个 xfail 会变红。

## 第 122 轮：第三条算例——道岔上的常速剖面也逐位相同

- 新增 `scripts/s12_profile_equivalence.py`：同一算例跑两遍（字段声明速度 vs 常速剖面），比 `history.csv` sha256。
- 实测三条全部 **IDENTICAL**：`case_A_final_law` 0.015 s → `2c6db969…`；`case_frog_N_strip05` 0.015 s → `bb85a8ee…`；同算例 0.05 s → `5042269f…`；`VERDICT: EQUIVALENT`。
- 两处形状约束记进脚本注释：`speed_profile` 必须是 `{"constant": {"speed_m_s": …}}`（带 `unit` 键抛 `SpeedScheduleError`）；派生到临时目录的算例必须把型面引用绝对化（否则 `AssetRefError` 按自身目录解析不到 `bodies/…csv`）。
- 至此目标第 3 项（车辆速度剖面）的"3 个算例 sha256 全等"判据满足。

## 第 121 轮：yaw 不是座椅该解的量（三种做法都实测过）

- `case_diverging_R1100.json` 的曲率只在站位表里：原点位表 → 悬架分支（`118538.9 N` = 2×）；显式给 R=1100/超高 0.107 → 座通过但第一步 `graph slope limit at x=79 m`。
- 把 **yaw 加进座未知量**：座"通过"（八轮 0.5–1.6×），积分却在 `x=52.5 m` 挂 —— 解出满足载荷但姿态错的分支。
- **刚体 yaw 偏置扫 0/±2/±5/±9.1/±14 mrad，九个值全败**，失败轴在 4/1/4/2/2 之间换。R=1100 下 20 m 足迹切线差 **18 mrad**，刚体偏置只能平移分布、不能产生分布。
- 结论：yaw 属于 S4 随动坐标系的**放置**问题，不是座椅未知量；`tests/test_curve_seat.py` 新增第 6 项钉住"曲线座不得改动 yaw 行"。
- 顺带把 `Velch/.gitattributes` 真正入库（前一轮 renormalize 时它只存在于工作区，规则没有进仓库）——行尾策略现在可继承。

## 第 120 轮：曲线先问对静平衡，再把曲率放进蠕滑

直向路径逐位不动（`freeze_baseline --check` → UNCHANGED），两处改动都在曲线分支里：

1. **静平衡的未知量在曲线时扩到 y 与 roll**（`vehicle_solver.py`）：原先只有 z，右端有 `m v^2/R` 却没有横向坐标可以平衡，于是轮胎只能被推到轮缘——`graph slope limit at axle1_left, x=41.24 m` 与 `2 of 8 wheels carry load, 264504.2 N` 都是这个病。配套加了 0 / ±2 mm 三个横向种子。
2. **曲率进纵向蠕滑**（`contact.py`）：`slip_x = travel + omega*lever_z - kappa*travel*lever_y`。曲线上同一轮对两个接触点走过的弧长不同，这是轮对能转向的物理来源；缺它就没有滚动半径差，只能硬顶轮缘。

实测（`case_A_final_law` 内联 35 坐标 → R=1100 m / 超高 0.107 m / 100 km/h / 0.01 s）：`numerically_checked`、**七门全真**、八轮 59 652–59 708 N 对均分 59 662 N，**每轮 1.00×，全部落在 [0.5, 1.6]**。0.107 m 正是该半径 100 km/h 的理论超高 `1.5 v^2/(g R)`，不是调出来的。

**斜率门没有放宽**：同半径、超高 0 仍然 `graph slope limit`——未平衡的侧向力只能靠轮缘，这正是该门要识别的工况。

证据：`tests/test_curve_seat.py` 5 项（直向 kappa=0、曲线 kappa=1/R、蠕滑项 `curved - straight == -kappa v b` 相对误差 1e-12、配平曲线八轮 1.00× 且七门全真、不平衡曲线仍报斜率门）；`docs/CURVE_SEAT_AND_CREEP_2026-10-27.md`；文档索引 148 篇。

## 第 119 轮：里程列改走调度，三段剖面闭合 0.000

- `save_vehicle_result` 写在 `history.csv` 里的里程列原先是 `x_start + travel_speed_m_s * t`，多段剖面下会写出一条不属于该几何的轨迹；现改为 `travel_mileage_m(case, t)`（与力路径同一个函数），常速仍逐位相同。
- 新脚本 `scripts/s11_mileage_closure.py`：80/60/40 km/h 三段、0.05 s、101 帧 → 里程列与解析距离**闭合 0.000e+00**（阈值 0.2 %），`spin_tracking` 相对滑移 **1.02e-4**，`numerically_checked`。
- 口径记录：梯形积分在 101 帧上只得 0.85833 m（−0.32 %），因为帧不落在腿上；参考值只能取解析距离。
- 测试 `tests/test_mileage_closure.py` 1 项。

## 第 127 轮：静平衡里的接触守卫改为"拒绝这一步"，并量清几何曲线为什么坐不住

- `src/velch/vehicle_solver.py`：`_static_vertical_equilibrium` 的 `residual()` 捕获 `SimulationFailure`
  并返回 `_SEAT_BARRIER_RESIDUAL = 1.0`（≈1e8 N 势垒），新增 `VehicleDynamics.seat_barrier_hits`。
  此前一个**试算点**触发 `graph slope limit` 就会从 `least_squares` 里逃出来，报错描述的是试算点而非模型。
- 实测（R=1100、无超高、100 km/h、`curve_geometry=true`）：`x_start` 40/50/60/70 m、两种时长，
  **每次坐实触发 148–150 次**；修复后报出真话 `vertical preload equilibrium failed`（`gtol`）。
- 三个量的对照（§14.1）：车轮 `y`/`yaw` 与轨道 `y` 逐轴一致（45.455 / 25.568 mm，`yaw = s/R`），
  左右轨横向偏移相同 —— 放置不是失败点。
- 结论（§14.4）：几何一致曲线仍坐不住，因为该路线显式拒绝超高（第 126 轮），
  而 R=1100/100 km/h 需要 0.107 m 平衡超高；下一步是**轨面滚转**，不是放宽容差。
- 测试：`tests/test_curve_seat.py` 新增势垒用例（`seat_barrier_hits > 0`）与"不平衡曲线坐不住"用例；
  `tests/test_curve_alignment.py` 的超高用例改为断言拒绝与体力路线保真。`15 passed, 1 xfailed`。

## 第 128 轮：超高是转动而不是抬轨，转动之后仍需要倾斜车架

- `src/velch/irregularity.py`：`RolledSeries` / `roll_rails`，绕轨自身中心线转断面，`dz_ds` 不变，0 角纯直通。
- `src/velch/vehicle.py`：`angle = asin(cant/gauge)` 接到装配处；107 mm / 1.493 m → 0.0717 rad。
- `src/velch/vehicle_solver.py`：几何路线对非零超高改为显式拒绝，文案说明"需要倾斜车架"，并指向 `curve_geometry = false`。
- 实测：断面已转但几何路线仍坐不住（每个种子都失败），力路线同算例 `numerically_checked`；原因是平衡超高靠重力在倾斜平面内的分量抵消 `m v²/R`，本路线重力固定在世界 z，车轮需自扛约 34 kN。
- 测试：新增 `tests/test_rail_roll.py`（5 项）；三个曲线测试文件合跑 **20 passed, 1 xfailed**。
- 复算：见 `docs/CURVE_SEAT_AND_CREEP_2026-10-27.md` §15。

## 第 129 轮：看不见的谐波留在先验，而不是被钉成"确定为零"

- `src/velch/inverse/harmonics.py`：`invert_corrugation` 的 `floor_gain` 默认改为"最强阶增益的 2 %"（`None` 触发），低于地板的阶不进方程、留先验并列入 `silent_orders`；防止 `sigma = noise/gain` 把噪声变成"确定为零"。
- 测试：`tests/test_harmonics.py` 新增 `test_a_gain_nobody_can_see_stays_at_the_prior_by_default`（11 passed）。
- 复核：`scripts/s9l_differential_bands.py` 的 "‑A 静默通过" 已在第 114 轮改为两半都必须 `numerically_checked`。
- 文档：`docs/HARMONIC_LADDER_INVERSION_2026-10-26.md` 新增 §7。

## 第 130 轮：超高按轨道平面发布（转 + 抬 + 车架侧滚），几何路线仍坐不住

- `src/velch/vehicle_solver.py`：`_curve_placement` 删除超高拒绝，改为 `rise = ½·gauge·sinφ`，与 `roll_rails` 的断面旋转、`_place_on_alignment` 的车架侧滚共用同一个 φ；107 mm / 1.493 m → φ = 0.0717 rad、rise = 0.0535 m。
- 实测三种发布方式（只抬 / 只转 / 转+抬+侧滚）在 R = 1100 m、100 km/h 下**全部无法坐住**；力路线同算例可跑完。结论：失败点不在超高发布，下一步先查曲线体力项是否与几何路线重复计入。
- 测试：`tests/test_curve_seat.py` 的该用例改为断言"仍然坐不住"并写清三种发布方式的实测；`tests/test_curve_alignment.py` 删掉重复用例（同样的失败已在 seat 覆盖）；三个曲线测试文件合跑 **17 passed, 1 xfailed**。
- 判据未放宽（slope guard、侵入限值、搜索窗、接触刚度均未动）。

## 第 131 轮：曲线体力项按路线分叉，无超高的几何曲线第一次能跑

- `src/velch/vehicle_solver.py`：`evaluate` 的等效直线曲线体力项改为 `if curve and not _placement_enabled(run)`，几何路线不再与"抬高 + 侧滚 + 断面旋转"重复计入。
- 实测：R = 1100 m、cant = 0、100 km/h、内联 35 坐标 **坐住并跑起来**，8 个接触斑，七门中六门通过，唯一失败 `translational_action_reaction`（该门参考量还没含向心合力，属门定义问题）。
- 有超高的几何曲线仍坐不住；逐行残差最大项在 y/roll 行（−43.2 kN / −38.8 kN / −35.1 kN / −32.9 kN / −29.4 kN）。
- 新诊断：`_place_on_alignment` 之后直接求值，四个轮对 y 行各带 **+1.95 MN**，说明逐体 `s²/2R`＋`s/R` 的放置不是力自由状态。
- 否掉两个假设：超高符号翻转会让整车只压一侧（1.31×，另一侧全 0），比原符号更差，已回退；三档横向种子（0/−2/−5 mm）残差 68.2/74.2/43.2 kN，均远高于 0.1 N。
- 测试：`tests/test_curve_seat.py` 的 barrier 用例把 slope guard 压到 0.02 以强制触发（并允许"坐住"这一新结果），单测 1 passed。

## 第 129 轮：曲线几何进入采样层（`CurveSeries`），并量出下一处真障碍

- 新增 `irregularity.CurveSeries`：把 `y(s) = s²/(2R)` 与半轨距超高加到**被采样的轨面**上，刚性/柔性/模态轨道共用一条弯曲轨面；`dz_ds` 不随横向平移改变（第一版把它加了 `offset/R`，等于额外倾转轨面 1°，十四个种子全部失败）。
- 八根轨全部包装（`bodies` 与 `contact_bodies` 都要看）；只包一侧时轨距被拉宽 0.18 m，与 O008 的单侧横向导入是同一个错误。
- 实测：R=1100 m、x_start=60 m 下轨面横向位移 61/70/80 m 为 +0.455 / +45.455 / +181.818 mm，高度变化恒为 0；车辆侧逐轴 `y = +45.455 / +25.568 mm`、`yaw = ±0.009091 / ±0.006818`，两者一致。
- 静平衡仍未闭合：10/30/60/100 km/h 四档同样停在 `gtol termination condition is satisfied`，放置态最大力 `wheelset1.z = 1.46e8 N`、`wheelset1.roll = −9.5e7 N`，指向接触搜索在弯曲轨面上的取样前提。几何曲线因此**不宣称可用**，力路由仍是唯一可跑的曲线。
- 测试 `tests/test_curve_series.py` 6 项（弧矢、无超高时高度不变、超高内外轨符号、覆盖转发、source 标记、与 `RolledSeries` 复合）。

## 第 130 轮：18 号道岔把车放到自己的设计线上（80 km/h 侧向限速）

- `_gauge_centre` + `_align_to_track_frame`：从被采样的轨面读该里程的轨距中心与切线，逐刚体写入 `y`/`yaw`；只在 `|tangent| > 1e-4` 时动手，直线基线因此 `UNCHANGED`。
- 实测 69 m：轨距中心 **+0.159525 m**、切线 **+0.015833 rad**，与解析弧矢 0.154 m / 0.0167 rad 一致。
- 取样口径：道岔同一里程有基本轨/尖轨/翼轨三面，「前两根轨取均值」给出 −0.599 m；改成按 `template_id` 每侧取一根才对。
- 侧向 80 km/h 仍未跑通：对齐后静平衡停在 `xtol termination condition is satisfied`（力路由与几何路由相同），下一步打印道岔算例的残差行。
- 否定结果：`contact_grid` 的横向轴改成绝对 `rail_y` 会打坏直线冻结基线（`ftol`），已回退并把否证写进注释。

## 第 131 轮：给不收敛的曲线静平衡做残差探针，量出右轨根本没被搜索到

用户口径：18 号道岔、R = 1100 m、侧向 80 km/h。第 130 轮已经把车辆放到道岔自己的设计线上（69 m 处 +0.159525 m / +0.015833 rad，与解析 0.154 m / 0.0167 rad 吻合），但静平衡仍停在 `xtol`。

本轮新增 `scripts/s12_curved_seat_residual.py`：记录静平衡里的每一次 `evaluate`，打印最后一帧的最大残差行、接触斑、每斑法向力与侵入量。三个配置的实测：

| 起始状态 | evaluate | 障碍命 | 有载斑 | 侵入量 | 法向力 |
|---|---|---|---|---|---|
| 未对齐（y=0，轨已横移 45 mm） | 1214 | 207 | 3，全左轨 | 5.55 / 5.76 / 2.89 mm | 13.6 / 13.8 / 2.9 MN |
| 未对齐 + yaw 进未知量 | 2318 | 292 | 4，全左轨 | 6.18 / 5.46 / 4.40 / 2.94 mm | 14.8 / 13.2 / 2.1 / 2.9 MN |
| 已对齐（+45.5 mm / 0.0091 rad） | 8082 | 317 | 4，全左轨 | 16.0 / 14.6 / 16.0 / 17.1 mm | 69.1 / 27.4 / 23.3 / 67.7 MN |

三条结论：① **右轨一次也没有接触斑**，三个配置都是——不是解错，是搜索没返回右轨接触；② 加 yaw 不解决（它物理上必须，但不是病因），所以 yaw 只在几何路由（`curve_geometry` / `align_to_track`）进入未知量并保留实测注释，力路由仍保持 y+roll（它的平衡曲线原本就是八轮等载 59 652–59 708 N，加 yaw 反而打坏）；③ 对齐后侵入更深（17 mm / 69 MN），说明不收敛不是横向错位，而是竖向被压在接触搜索边缘上。

下一轮的靶点因此具体化：`contact_grid._build_rail_grid` 用 `rail_sample.profile.y_m` 建横向轴，而 `CurveSeries` 正是把该 `y_m` 横移了 45 mm；全局改成绝对 `rail_y` 会打坏直线冻结基线（已否证），修正必须限定在“被横移过的序列”上。

证据：`scripts/s12_curved_seat_residual.py`；`tests/test_curve_seat.py` 的 yaw 分支守卫；`tests/test_curve_seat.py` + `test_curve_alignment.py` + `test_curve_series.py` **18 passed, 1 xfailed**；`docs/CURVE_SEAT_AND_CREEP_2026-10-27.md` §21。

## 第 132 轮：三个探针排掉三个候选，把曲线失败推进到「第一次接触求值就错」

- `scripts/s12b_grid_frame.py`：网格假设作废——本算例走条带路径，`_build_rail_grid` 一次都没被调用（附「必须改 `contact_search` 上的绑定」这个坑）。
- `scripts/s12c_gauge_centre.py`：60/70/80 m 的轨距中心 +0 / +0.045455 / +0.181818 m，与 `CurveSeries` 横移后的左轨均值逐位对应；对齐把 `wheelset1/4` 放到 +0.045455 m、`wheelset2/3` +0.025568 m。几何与对齐都对。
- `scripts/s12d_z_only_seat.py`：只解四个轮对 z 时，**对齐状态的第一次 `evaluate` 就是左轨 150 690 kN、右轨 0**；随后载荷单调下降，说明起点差约 12 mm（按 65 µm ↔ 59.7 kN 的 Hertz 反推）。所以不是静平衡搜索的问题，是第一次接触求值就已经把左轨压进去、右轨根本没找到接触。

下一轮：在同一状态上只取一对轨，打印条带切片的 `rail_y` 区间、轮面 y 区间与最深切片。

证据：三个探针脚本；`docs/CURVE_SEAT_AND_CREEP_2026-10-27.md` §22。

## 第 133 轮：曲线加在轨面上与车辆侧不在同一框架——车不动时左轨就连 78.8 MN

`scripts/s12e_alignment_parts.py` 把对齐拆成三个成分，在同一个对齐状态上逐个量（R = 1100 m、cant 0、80 km/h、x_start 60 m、内联 35 坐标）：

| 轨面 | 车辆状态 | axle1_left | axle1_right |
|---|---|---|---|
| 直线 | 任意 | 0.0 kN | 0.0 kN |
| 曲线 | 对齐（y +45.5 mm / yaw +0.0095） | **150 690.0 kN** | 0.0 kN |
| 曲线 | 只 yaw | 78 785.2 kN | 0.0 kN |
| 曲线 | 只 y | 150 689.6 kN | 0.0 kN |
| 曲线 | **直车状态（y=0, yaw=0）** | **78 786.2 kN** | 0.0 kN |

结论：病因是 `CurveSeries` 把曲线加在 `profile.y_m` 上，与车辆侧坐标约定不同框架——横移 45.5 mm 的轨面与横移 45.5 mm 的车没有抵消而是**叠加**（78 786 → 150 690 kN）。下一轮先判定 `profile.y_m` 是绝对还是轨局部坐标（§22 表里它带 −0.753337，倾向绝对），再把横移写到 `rail_y_m`（`contact_search.py:202` 里真正与轮面比较的量）或改回只移动车辆。

证据：`scripts/s12e_alignment_parts.py`；`docs/CURVE_SEAT_AND_CREEP_2026-10-27.md` §23。

## 第 134 轮：`align_to_track` 一直是个 no-op；轨面横移默认关闭，曲线回到诚实边界

- **真缺陷**：`vehicle_solver` 里用 `getattr(case.run, "align_to_track", False)` 读开关，但 `RunSettings` 从来没有这个字段，于是它恒为 False——前几轮所有「align_to_track」实际生效的都是 `curve_geometry`。本轮在 `RunSettings` 里正式加上该字段（默认 False），并写明用途。
- `CurveSeries` 改为显式 opt-in（`curve_geometry` **且** `curve_rail_surface`），默认关闭，注释记录 §23 的 78 786 / 150 690 kN。
- 只做对齐、不做轨面横移的 80 km/h 侧向过岔**仍不收敛**（`xtol`，0.01 s 与 0.05 s 都是），如实记录。
- 下一步二选一：(a) 曲率全放车辆侧（横移+偏航+`v·κ` 与 `(1−κy)` 进蠕滑），(b) 先把 `profile.y_m` 的坐标系变成显式约定再谈轨面横移。两者都先量后改。

证据：`src/velch/model.py`（新字段）、`src/velch/vehicle.py`（opt-in 门）、`docs/CURVE_SEAT_AND_CREEP_2026-10-27.md` §24。

## 第 135 轮：把实测检出率按段级校准重算——50 % 而不是 83 %

- `scripts/s10_measured_corrugation.py` 的 `score()` 早已改成段级口径（`_pseudo_segment_maxima` 铺 1585 个等长伪段，
  阈值取它们的 95 百分位，再给二项零假设），但**从未用新口径重跑过一次**，所以文档里仍是旧的 5/6。
- 本轮重跑 `F:\ai道岔状态反演辨识\75kmh数据\Run_75kmh_E1toE2.mat`：声音通道阈值 13.73 dB、
  段内 12.80 / 段外 6.42（+6.38）、AUC 0.880、**3/6（50 %）**；振动通道同样 **3/6**；
  零假设下期望 0.30 次、**P(X≥3)=0.002**、9 个未归属超阈峰。
- 判读：信号真实（p=0.002）但**远低于 95 % 目标**；旧 5/6 作废，因为它把窗口级阈值配到段内最大值上
  （有效段级虚警 46–76 %）。`docs/MEASURED_VALIDATION_2026-10-26.md` 新增第 7 节记录这次重算与四条判读。
- 顺带核对：`scripts/s9l_differential_bands.py:87-93` 与 `src/velch/inverse/harmonics.py:248-287` 的两处口径缺陷
  **已经在代码里修好**（前者要求 ±A 两半都 `numerically_checked`，后者把 `floor_gain` 默认成 `1e-3·max|g|`），
  所以目标第 2 项现在只剩「s10 用新口径重跑并落数」，本轮已完成。

## 第 136 轮：把曲线的四条死路写成决策记录，免得第四次重走

- 新增 `docs/CURVE_APPROACH_DECISIONS_2026-10-27.md`：力路由（能坐住但只对平衡超高）、轨面横移
  （78 786 / 150 690 kN 两次实测否掉）、超高当抬升（旋转断面仍不解平衡，因为重力没有随框架倾）、
  `align_to_track` 曾是不存在字段（现已补上）四条，每条都带可直接复查的数字与脚本。
- 第五节写明唯一没被否的路线：曲率放车辆侧（站表已弯、`(1−κy)` 与 `Δv_x=∓vκb` 已在并有 rel=1e-12 测试），
  缺的是"车架随轨道平面倾斜"这个姿态自由度，下一轮要量而不是猜。
- 第 21 轮的实测重算（段级虚警 3/6，P=0.002）记在第 135 轮。

## 第 137 轮：几何路由的“跑不了”其实是配置自相矛盾（1e6 kN 的第一次求值）

- `F:\velch_tmp\round23_first_loads.py` 打出三种配置在 R=1100 / 100 km/h / x_start 60 m 下的**第一次** `evaluate`：
  力路由（cant 0.107）八斑全 0，随后坐成 59.65–59.71 kN；几何路由（cant 0.107）右轨 161 289 / 936 715 / 971 169 /
  174 810 kN；几何路由（cant 0）左轨 54 764 / 70 379 / 134 822 / 152 453 kN。
- 1e6 kN 量级不是物理载荷，是“每个求值点都在荒谬穿透量上”的标志；根因是第 20 轮把轨面横移默认关掉之后，
  `curve_geometry` 变成「车横移 45.5 mm、轨面不动」这种自相矛盾的配置。
- 因此“曲线跑不了”这一结论只对这个配置成立。下一轮的正确改法是**在加载时拒绝该组合**，并让两者共享同一框架，
  而不是继续调收敛。`docs/CURVE_APPROACH_DECISIONS_2026-10-27.md` 新增第七节。

## 第 138 轮：车辆侧与轨面侧同进同出，`curve_geometry` 不再能单独移动车辆

- `src/velch/vehicle.py`：`surface = bool(run_block.get("curve_rail_surface")) or bool(run_block.get("curve_geometry"))`，
  于是 `curve_geometry` 一定同时把轨面套上 `CurveSeries`。理由写进注释：车按 s²/2R 移 45.5 mm 而轨面不动，
  第 23 轮实测第一次求值给出 161 289 / 936 715 / 971 169 / 174 810 kN（一侧）与 0（另一侧），那是荒谬穿透而非载荷。
- 新增 `tests/test_curve_series.py::test_curve_geometry_alone_now_curves_the_rail_as_well` 钉住这条耦合
  （顺带给该文件补 `import json`）。
- 曲线相关测试 **19 passed / 1 xfailed**；冻结物理与直线基线未动。
- 仍未解决：同进同出之后 R=1100/cant=0.107 的几何路由依然坐不住（第 19 轮量到 150 690 kN），
  所以下一步是让两者共享同一坐标框架，而不是继续调收敛。

## 第 139 轮：曲线的横移被数了两次——修掉重复计入

- 第 25 轮量出框架关系：`TrackKernel.local_state` 已经返回 `rail_y_m = s²/(2R)`（x=70 m 处 +0.045455 m），
  而 `CurveSeries` 又给 `profile.y_m` 加了同样的 +45.455 mm，于是左轨冠部从「直轨 −0.753337」变成
  **−0.669296**（应为 −0.707882），右轨 +0.850824（应为 +0.798810）——多算了 45.5 mm；
  车轮与冠部的横向距离因此是 32–79 mm 而不是直线工况的 6.8 mm。
- 修法：**删掉 `CurveSeries` 的接线**，轨面只由 kernel 的 placement 负责；`curve_rail_surface` 这个伴随
  开关一并去掉（它从来不是 `RunSettings` 字段，所以只可能被读成“未设置”，耦合因此一直是单边的）。
  注释里写明这次的四个数字与「轨面只在 kernel 一处」这条结论。
- 验证：移除后同一探测左冠部 **−0.714751**（= −0.753337 + 45.455 mm + 冠部位置），曲线相关测试
  **18 passed / 1 xfailed**；`import velch.vehicle` 正常。
- 未做（下一轮）：**没有重跑静平衡**，所以「几何路由现在能坐住」这句话还**不能说**。要量的是 R=1100 / cant=0 /
  100 km/h 的 `simulate_vehicle`。

## 第 140 轮：去掉重复计入之后，几何路由依然坐不住（结论与下一步都写清）

- 第 25 轮删掉 `CurveSeries` 的接线后重跑静平衡（`F:\velch_tmp\round26_seat.py`，R=1100 m、100 km/h、x_start 60 m、0.01 s）：
  - **A 力路由** cant=0.107 → `numerically_checked`，**七门全过**（唯一能跑的那条，仍然是它）；
  - **B 几何路由** cant=0 + `align_to_track` → `vertical preload equilibrium failed: no seed converged; gtol`；
  - **C 几何路由** cant=0 不对齐 → 同样的失败。
  所以「去掉重复计入」**没有**让几何路由坐住，这一步只是把一个确定的代码错误消掉，不改变结论。
- 重新量第一次求值（`F:\velch_tmp\round23_first_loads.py`）：几何路由 cant=0 仍是左轨 54 764 / 70 379 / 134 822 / 152 453 kN、
  右轨 0；cant=0.107 是右轨 161 289 / 936 715 / 971 169 / 174 810 kN、左轨 0 —— **与第 23 轮逐位相同**。
  这点很重要：说明这些巨值不是「轨面被数两次」造成的，而是另一件事。
- 反解量级：`F = C·δ^1.5`、`C = 1.1267e11`，`9.7e8 N` 对应 **δ ≈ 4.2 mm**，不是 65 µm。4 mm 的有效穿透 + 完全单侧，
  指向**侧向接触/轮缘根**而不是正常轨顶接触（正常 δ≈65 µm 给 59.7 kN）。下一轮要量的是接触点位置
  （`geometry.lever_y_m` 与车轮/轨面最近的 y 区间），而不是继续调种子。
- 交付：无代码改动（本轮是测量与记录），`docs/CHANGELOG_DOCS.md` 本条；文档索引 149 篇不变。

## 第 141 轮：接触点位置量出来了——轮缘在轨距面上咬了 27 mm

`F:\velch_tmp\round27_contact.py`（R=1100 m、cant=0、100 km/h、x_start 60 m、`initial_state` 已移除）：

```
直线（名义高度或下沉 65 um）  八斑 pen 0.00 um，lever_y +/-0.75277，0.00 kN
R1100 几何路由，对齐          左斑 pen 27 020.72 / 21 023.79 um，lever_y -0.69404 / -0.70150
                              右斑 pen 0.00 um
R1100 几何路由，不对齐        与“对齐”逐位相同
```

三条判读：

1. **penetration 27.02 mm ≈ 轮缘深度（28 mm）**，lever_y 从 −0.75277 移到 −0.69404（**向内侧 58.7 mm**）——
   这是**轮缘压到轨距面（flange root）**的特征，不是轨顶接触。27 mm 与 65 µm 差 400 倍，载荷自然到 1e6 kN 量级。
2. **“对齐”与“不对齐”逐位相同**，说明 `_align_to_track_frame` 在这一配置上**没有产生任何效果**（又一次成为
   no-op）。同时说明轨面确实被 kernel 的 placement 移了 +45.455 mm，而车轮没有跟着移，
   两者相差约 31.7 mm —— 正好把轮缘送进轨距面。
3. 因此“几何路由坐不住”的真实机理是：**曲线只移动了轨面，没有移动车辆**；`_align_to_track_frame` 本该补上这一半，
   但它没有生效。下一轮要打印 `_align_to_track_frame` 的返回值，确认是 `_gauge_centre` 返回 0（`template_id` 过滤）
   还是写入的索引与接触读取的索引不同 —— 这是量而不是猜。
- 本轮无代码改动；文档索引 149 篇不变。

## 第 142 轮：对齐终于生效了（13 个分量），曲线仍然坐不住

上一轮发现 `_align_to_track_frame` 对配置“逐位无影响”。本轮把这个 no-op 一路查到根：

1. `_gauge_centre` 只读 `sample.profile.y_m`，而**几何路由的曲线偏移在 track kernel 的 placement 里**，
   `profile.y_m` 是相对断面坐标（对称断面均值恒为 0）——所以它每次返回 `+0.000000 m, slope +0.000000`。
   这就是“对齐无效”的原因，不是写入索引错。
2. 修法：`_gauge_centre(case, s_m, dynamics=None, speed_m_s=0.0)`，在得到相对均值后加上
   `dynamics.track.local_state(zeros, zeros, index, x_m, speed)[0]`（与接触读取同一个 frame），
   并把 `dynamics`/`speed` 从 `_align_to_track_frame` 的两个调用点透传。
3. 实测（R=1100、cant=0、x_start 60 m、35 坐标）：对齐向量**13/35 个分量非零** ——
   `q[0]=q[15]=+0.045455`（前后轴）、`q[5]=q[10]=+0.025568`（中间轴）、
   `q[4]=+0.009545 / q[9]=+0.007273 / q[14]=-0.006364 / q[19]=-0.008636`（各轴 yaw）、
   `q[20]=q[25]=+0.034801`（构架 y）、`q[34]=+0.000455`（车体 y）。与 placement 的 +45.455/25.568 完全对上。
4. **但对齐到位后曲线仍然坐不住**：`aligned geometry cant 0`、`unaligned geometry cant 0` 都是
   `no seed converged; gtol`；而 **`align_to_track=True` 配力路由反而从“能坐”变成 `xtol`** ——
   力路由的轨面不动，把车横移 45 mm 等于把车挪到钢轨旁边。
5. 因此 `_align_to_track_frame` 的开关改为**只认 `curve_geometry`**（力路由不允许对齐），并在注释里写明这条实测。
   曲线四个测试文件 12 passed / 1 xfailed。
- 结论更新：第 27 轮把失败归因于“车辆没跟着移”**只对了一半**——移了以后仍然失败，说明还有第二个原因；
  下一轮要量的是“对齐后八个接触斑的 pen 与 lever_y 各是多少”（上一轮的表是未修 `_gauge_centre` 之前的状态）。

## 第 143 轮：对齐之后接触在哪、残留多大——三个数把失败钉成了“残留不收敛”

第 28 轮修好 `_gauge_centre` 后，本轮把两个状态逐行量出来（R=1100 m、cant=0、100 km/h、x_start 60 m、35 坐标）：

| 状态 | 八个接触斑 | 最大残留行 |
|---|---|---|
| **对齐后的起点** | 8 个斑几何都在，**pen 全 0.00 µm、力全 0 kN**（车轮悬在 65 µm 净空里） | 四个 `wheelsetN.z` 各 −119 323.9 N（合计 477.3 kN ≈ 整车重 477.4 kN） |
| 未放置的零状态 | 左斑 pen 27 020.72 / 21 023.79 µm、152.5 MN | `wheelset1.z` +152 333 358 N |

三条结论：

1. **第 27 轮的 27 mm 是“没做 placement 的零状态”造成的**（探针直接 `evaluate(zeros)`），不是算例本身的几何错；
   对齐状态下八个斑都在正确的净空里，pen = 0，所以要坐下去只需下沉约 65 µm。
2. 因此曲线坐不住的表述应当改成：**载荷全在 `wheelsetN.z` 上（各 119.3 kN），接触一个都没接上，静平衡最小二乘在
   y/roll 自由的情况下停在 `xtol`（对齐）/`gtol`（未对齐），残差降不到 0.1 N 判据以下。** 直线同一算例是 1e-7 N。
3. 试过一次把 yaw 从静平衡未知量里拿掉（第 17 轮曾量到“加 yaw 更差”）：消息从 `gtol` 变 `xtol`，**仍然坐不住**，
   所以 yaw 不是主因，已回退，结论如实记录。

下一轮要量的是**收敛点的残差向量**（哪几行没降到 0.1 N 以下、各自多大），而不是再猜哪个变量该进未知量。

## 第 144 轮：曲线静平衡是**秩亏**，而且“横向静平衡”在零速下本来就不存在

本轮量了残差向量与雅可比，把失败定性到两个层次：

1. **雅可比秩亏**：对齐起点、未知量取 z+y+roll（21 个）、方程 21 个时，
   数值雅可比 `cond = 3.76e12`，奇异值从 1.014e2 一路降到 **2.7e-11**。
   所有种子都停在 `|r| = 2.39`（240 kN）的驻点上，`gtol`/`xtol` 都试过。
2. **残差对 z 不敏感**：对齐起点把四个轮对同时下沉 0 / 65 / 130 µm，
   `|r|` 恒为 **2.386479e0**；到 500 µm 才涨到 1.4e1（接触过压）。说明起点处接触刚度**没有进入方程**。
3. **只解垂向则一切正常**：把未知量限制为 7 个 z（含两构架与车体），从同一对齐态出发，
   `least_squares` 收敛到 **|r| = 1.07e-12**，八个斑 **pen 全 65.47 µm**、
   载荷 **58.7 / 60.4 / 59.0 / 58.7 / 59.0 / 60.4 / 60.6 / 60.6 kN**（均分 59.66 kN）。**这就是曲线能坐的那个解。**
4. **物理判断**（这也是为什么“横向静平衡”不该被要求）：零速下蠕滑力为零，轨顶接触的横向分量≈0，
   所以横向力没有平衡项——曲线上车辆的横向状态是**运行中的平衡**，不是静态平衡。
   第 30 轮据此试过“去掉 y/roll/yaw 只解 z”和“先垂向预解再全量解”两种改法，
   在真实的 `_static_vertical_equilibrium` 里都仍报 `no seed converged; xtol`，
   与探针结果（1.07e-12）矛盾——**两者差异还没查清，所以三处试验性改动全部回退**（`git checkout`），
   不留下说不清的行为改变。下一轮要查的是这个矛盾：探针与 seat 的
   `indices`/`seeds`/验收判据（`error_n > 0.1`）到底哪里不同。

## 第 145 轮：曲线的静平衡通了——把横向未知量从 seat 里拿掉

第 30 轮量到两件事：未知量取 z+y+roll 时雅可比 `cond 3.76e12`、所有种子停在 `|r| = 2.39`（240 kN）；
而只解 7 个垂向坐标时收敛到 `1.07e-12`、八斑全 65.47 µm、载荷 58.7–60.6 kN。本轮把后者落进真代码。

**改动**（`src/velch/vehicle_solver.py`，`_static_vertical_equilibrium`）：曲线时**不再**把 y/yaw/roll 加进未知量，
并把理由写在代码里：零速下蠕滑力为零、轨顶接触无横向分量，那些行没有解，加进去只会让方程秩亏。
曲线的横向状态是**运行中的平衡**——placement 给定、轨迹发展、seat 只决定车轮坐多深。

**实测（R=1100 m、cant=0、100 km/h、x_start 60 m、35 坐标、0.01 s）**

| 配置 | 结果 | 门 |
|---|---|---|
| 几何路由 + 对齐 | **跑通** | 7 门，唯一失败 `translational_action_reaction` |
| 几何路由 + 不对齐 | **跑通** | 同上 |
| 力路由 + 对齐 | `numerically_checked` | 7/7 全过 |

**这是曲线第一次跑起来**：第 26 轮起的「坐不住」结束了；现在剩下的是**曲线工况的作用-反力门不平**——
几何路由把车辆放到弧线上、轨面也移了，但反力账本没有随曲率记入，这是下一轮的具体目标（不是放宽容差）。

两个测试按新行为改写：`test_an_unbalanced_curve_cannot_be_seated_at_all` 改成断言「能跑、但
`translational_action_reaction` 失败」；`test_only_the_geometry_route_puts_yaw_among_the_seat_unknowns`
改成 `test_the_seat_puts_no_lateral_coordinate_among_its_unknowns`，钉住这条分支**不存在**。
`freeze_baseline.py --check` → **UNCHANGED**（直线 `06928c9db944796d`、柔轨 `ab81290f5924c3a5`）。

## 第 146 轮：曲线的第七门也过了——力只在「真的施加了它」的路由上记账

第 31 轮曲线跑通但只差 `translational_action_reaction`。本轮查明：那一门把 `m v²/R`（100 km/h、R=1100 时
**34.2 kN**）加进横向账本，条件是「有 `curve_radius_m` 就加」；而**几何路由根本不施加这个力**（车辆被 placement
放到弧线上，`evaluate` 里不加法向力），于是账本凭空多出 34.2 kN——**只在这一门、只为这一个原因失败**。

修法一行：`if curve_radius and not _placement_enabled(run):`，并把理由写进注释（含 34.2 kN 实测）。

**实测（0.01 s，R=1100 m、cant=0、100 km/h、x_start 60 m、35 坐标）**

| 配置 | 状态 | 门 |
|---|---|---|
| 几何路由 + 对齐 | **numerically_checked** | **7/7 全过** |
| 几何路由 + 不对齐 | **numerically_checked** | **7/7 全过** |
| 力路由 + 对齐 | **numerically_checked** | **7/7 全过** |

**这是第一次几何曲线工况给出 quotable 结果**（此前 7 轮分别是：坐不住 → 秩亏 → 车辆未对齐 → 帧不一致 →
剩一门）。测试也按新事实改写：`test_an_unbalanced_curve_cannot_be_seated_at_all` →
`test_a_geometric_curve_runs_and_passes_every_gate`，断言**全门通过**，并在 docstring 里写清这两轮各自修了什么。

直线/柔轨冻结基线不受影响（只有在 `curve_radius_m` 且 placement 开启时才走新分支）。

## 第 147 轮：R=350 不是「过不去」，是「没有超高可给」——两条读数各归其位

第 32 轮之后几何路由首次 quotable，于是把架构审查要求的验收点真跑了一遍（0.01 s，x_start 60 m，35 坐标）：

| 工况 | 所需横向力 / 接触角 | 状态 | 八轮载荷 | 最大侵入 |
|---|---|---|---|---|
| R=350，cant 0，**80 km/h** | 68.6 kN / 8.18° | **numerically_checked 7/7** | 57.3–75.6 kN（0.96–1.27× 均分） | 74.9 µm |
| R=350，cant 0，100 km/h | 107.3 kN / 12.67° | **numerically_checked 7/7** | 56.8–166.9 kN（0.95–2.80×） | 177.7 µm |
| R=1100，cant 0，100 km/h | 34.1 kN / 4.09° | **numerically_checked 7/7** | 58.7–63.5 kN（0.98–1.06×） | 69.7 µm |

三条读数，一条结论：**`graph slope limit` 不再被触发**，R=350 的失败不再是几何问题。80 km/h 那行**完全满足验收判据**
（8/8 着地、每轮 ∈[0.5,1.6]×均分）；100 km/h 那行载荷到 **2.80×**，而它的平衡超高是
`h_th = 1.5·27.78²/(9.81·350) = 0.337 m`——**超过模型的 0.20 m 合理上限，也超过实际线路最大超高**。
所以正确表述不是「R=350 过不去」，而是**「R=350 在 100 km/h 下没有超高可给，载荷转移就是它应有的物理」**：
前外轮 166.9 kN、后外轮 104.4 kN，七门全真、侵入 177.7 µm（限值 500 µm 以内）。

两条读数都写成测试（`test_a_350_metre_curve_at_its_eighty_limit_sits_within_the_band`、
`test_an_uncompensated_350_metre_curve_runs_but_transfers_load`），这样以后谁改坏了载荷分配或谁把斜率守卫调回去，
测试立刻红。

### 33d 顺带查明：力路由的曲线**不做载荷转移**，不能当作曲线结果引用

写测试时把 `geometry` 默认值（`False`）用错了，于是同一 R=350/100 km/h 走了力路由，读数 **1.0039×**（几乎均分），
而几何路由是 **2.80×**。这不是笔误，是物理：

- 力路由把 `m v²/R`（107.3 kN）作为体力加到每个含 y 的刚体上，但车仍在**游间**里，钢轨没有提供反力；
- 0.01 s 内横向加速度 2.2 m/s² 只走 **0.11 mm**，够不到轮缘，所以垂直载荷根本不转移；
- 而 `translational_action_reaction` 把施加的力按构造记入账本，于是**七门照样全真**。

结论：**曲线结果只能引几何路由**；力路由的 7/7 不能当曲线证据（第 6 轮那次「力路由八轮均分 59 652–59 708 N」
正是同一个现象）。两条读数都钉成测试：
`test_a_350_metre_curve_at_its_eighty_limit_sits_within_the_band`（0.96–1.27×）、
`test_an_uncompensated_350_metre_curve_runs_but_transfers_load`（2.80×）、
`test_the_force_route_carries_no_load_transfer_and_must_not_be_quoted_as_a_curve`（力路由 <1.05× 而几何路由 >2.0×）。

## 第 148 轮：超高上几何路由——两种符号都试过，都是「4/8 轮着地、另一侧全脱空」

上一轮之后几何路由已能 quotable（R=1100/350、cant 0 全部 7/7）。本轮试把**超高**也做进去，两条改动都做了：

1. `_curve_placement` 恢复外轨抬高（`rise = 0.5·gauge·sin(theta)`，前一轮为保证可坐把它置零了）；
2. `evaluate` 里重力按坡面分解（`cos` 竖向 + `sin` 横向，`self._plane_angle_rad = asin(cant/gauge)`）。

**实测（0.01 s、35 坐标、几何路由、x_start 60 m）**

| 工况 | cant | 结果 |
|---|---|---|
| R=1100，100 km/h | 0 | **7/7**，份额 0.985–1.064，侵入 69.7 µm |
| R=1100，100 km/h | +0.107（平衡超高） | `4 of 8 wheels carry load`，最重 **124.8 kN**（≈2×） |
| R=1100，100 km/h | **−0.107** | `4 of 8 wheels carry load`，最重 **119.0 kN** |
| R=1100，80 km/h | ±0.107 | 同上（119.0 / 124.8 kN） |
| R=350，80 km/h | ±0.100 | 同上（119.1 / 126.4 kN） |

**两种符号给出同一种失败**，所以不是「外轨抬高与车体侧滚方向相反」这类符号错：抬高确实生效（`±53.5 mm`），
但车体侧滚没有跟着生效——118–126 kN ≈ 2×均分正是「车站在一根轨上」。这是第 20/21 轮「flag 接上了但没生效」
的同一类问题（`align_to_track` 字段缺失、`curve_rail_surface` 不是字段、`_gauge_centre` 读错帧），
**第四次**出现在同一条链上。

处置：**两条改动整体回退**（`git checkout src/velch/vehicle_solver.py`），不把「一半生效」的状态留在树里；
探测脚本收进 `scripts/s12g_cant_balance.py`，下一轮直接从「车体侧滚为何没生效」入手（先打印
`_place_on_alignment` 返回的 roll 分量与 `_static_vertical_equilibrium` 的初始 q，再谈物理解释）。

曲线结论不变：**cant=0 的几何曲线已可引用**（R=350/80 km/h 满足 [0.5,1.6]×，R=350/100 km/h 与 R=1100 全 7/7）；
**超高曲线仍不可引用**，原因已缩到一处。

## 第 149 轮：超高的最后一道量——轨面与车轮被「反着」倾斜

第 148 轮把超高整体回退。本轮先回答「车体侧滚到底有没有进静态平衡」，答案：**进了**。

`scripts/s12h_cant_frames.py`（`_place_on_alignment` 的返回 + 静态平衡入口快照）实测：

```
bodies with a roll coordinate:  wheelset1..4 / bogie1..2 / carbody 全部 roll = +0.071729 rad
seat start: 非零 21 项，roll 全为 +0.071729（与 placement 一致）
```

即 `asin(0.107 / 1.493) = 0.0717 rad = 4.11°` 确实写进了 seat 的初始状态。所以第 148 轮「侧滚没生效」的判断**是错的**，
我又错了第二次（第一次是认为 `_gauge_centre` 读相对坐标没问题）。

真正的问题在**方向约定**：把轨面抬高的量打出来（x = 70 m）：

| rail | z（带 ±rise） |
|---|---|
| `axle1_left` … `axle4_left` | **+0.05350** |
| `axle1_right` … `axle4_right` | **−0.05350** |

而车体 roll = **+0.0717 rad**，在「+roll 抬 +y 侧」的约定下把**右**轮抬 +53.5 mm。两者**反着**。
于是把 `outer` 从 right 改成 left 再试——`4 of 8 wheels carry load, heaviest 124.8 kN` **一模一样**；
再把 `curve_frame_tilt` 关掉（只抬轨面、不倾车体）——**还是一模一样**。

三条读数合起来说明：**不是符号选错，而是「抬高轨面」与「侧滚车体」这两条通道在接点处没有共同的符号基准**，
而 `rises_only` 与 `full_tilt` 读数相同又说明**抬高本身没有改变接点的相对高度**（否则两者必然不同）。
这只有在「`dz` 进了 `local_state` 但没进接触点高度」时才成立——即 rise 只改变了轨面采样，而轮轨间隙仍按未抬高的基准算。

因此本轮处置：**再次整体回退**（`src/velch/vehicle_solver.py`、`src/velch/model.py` 回到 HEAD），
不保留 `curve_frame_tilt` 这个只在坏路径上有意义的开关；探测脚本收进 `scripts/s12h_cant_frames.py`。

下一轮的第一件事因此明确成一条可测的命题：**打印单个车轮接点在 +roll 下的 z 与同里程轨面的 z**，
两者必须在 1e-3 m 内相等；做不到就说明 rise 没有进 `geometry`，而不是再换符号。
曲线能力边界不变：**cant=0 的几何曲线可引用**（R=350/80 km/h 带内、其余 7/7），**超高曲线不可引用**。

## 第 150 轮：抬高与侧滚**都**进得了接触点，剩下的只可能是 `_absolute_arrays` 内部的一个符号

第 149 轮的推断（「rise 没进接触点」）也被代码否掉了。两处调用链逐一核对：

- `src/velch/vehicle_solver.py:626-627`：`rail_y, rail_z, rail_vy, rail_vz = self.track.local_state(q, v, rail_index, x, speed)`，
  `src/velch/vehicle_solver.py:651` 把 `rail_z_m=rail_z` 交给接触搜索；`src/velch/contact_search.py:203` 再把它与断面坐标相加
  （`rail_z = rail_z_m + rail_sample.profile.z_m`）。**所以 ±rise 确实进了轨面高度**。
- `src/velch/vehicle_solver.py:648-650`：`wheel_z_m = cfg.wheel_center_height_m + q[z]`、`wheel_roll_rad = q[roll]`、
  `wheel_lateral_offset_m = ±0.7465`。**所以车体侧滚也确实进了接触点**。

两条都在，因此第 149 轮那三个「读数一模一样」的配置需要重新解释：它们不是『rise 丢了』，而是
**`_absolute_arrays` 里车轮那一侧的 roll 旋转方向与轨面抬高的方向约定相反**——两种 `outer` 选择各自把
一侧配成「+53.5 对 −53.5」（107 mm 错位），于是两种配置给出**同量级、同形态**的 `4 of 8 / 124.8 kN`，
看起来像「没变化」。这解释了为什么换符号不改变读数。

下一轮的唯一实验因此非常具体：在 `src/velch/contact_search.py::_absolute_arrays` 前后各打印一次
`wheel_y/wheel_z/rail_y/rail_z`（同一 y 处），量出车轮接点与轨面在 +roll 下的**高度差**；
- 若差 ≈ 107 mm → 旋转方向约定相反，改 `_absolute_arrays` 里 roll 的符号（并同时核对直向是否逐位不变）；
- 若差 ≈ 0 → 说明错位来自别处，回到 `_gauge_centre`/placement 再查。

本轮没有改代码（两处都已确认在位），只记录这两条路径与修正后的推断；曲线边界不变：
**cant=0 可引用**（R=350/80 km/h 带内、其余 7/7），**超高不可引用**。

## 第 151 轮：`_absolute_arrays` 确实随 roll 倾斜（单侧 ±51.5 mm），所以问题不在「有没有倾斜」

`scripts/s12i_wheel_rail_tilt.py` 直接调用 `_absolute_arrays`，固定车轮中心 0.43 m、轨面基准 0，
只改 `wheel_roll_rad`，量「轨面 z − 车轮 z」的最小/最大值（R=1100，cant −0.107 的算例，x = 70 m）：

| roll | 车轮中心处 z | 最小间隙 | 最大间隙 |
|---|---|---|---|
| 0 | **−5.526 mm** | +25.027 mm | +54.326 mm |
| **+0.071729** | **−54.036 mm** | +74.044 mm | +108.690 mm |
| **−0.071729** | **+44.072 mm** | **−29.290 mm** | +26.135 mm |

（绝对间隙的数值无意义——探测里车轮中心与轨面基准是我随手给的；有意义的是**随 roll 的变化量**。）

**结论：roll 把车轮接点高度改变了 ±49–51.5 mm 每侧，峰峰 103 mm ≈ 2·b·sinθ。** 也就是说
`_absolute_arrays` **确实**按 roll 倾斜车轮，量级与 107 mm 的轨面高差同一数量级。

于是第 150 轮剩下的那个假设（「旋转方向约定相反」）既不能被证实也不能被否证——因为**两种 `outer` 配对都必须
成功一种**，而实测两种都失败。新的最小可疑点因此从「符号」移到「轨面侧到底有没有跟着转」：
`roll_rails` 只在 `vehicle.py` 里 cant≠0 时接线，而本轮探测拿到的 `rail_sample` 是否来自 `RolledSeries`，
第 150 轮的续查就是打印 `type(rail.bodies[0].series)`。

本轮不改代码（探测脚本入库，`scripts/s12i_wheel_rail_tilt.py`）；曲线边界不变：**cant=0 可引用**，**超高不可引用**。

---

## 第 152 轮：超高被加了两次，一处 `abs()` 一处随 cant 变号

- 新探测 `scripts/s12j_cant_double_count.py`（固定基准，打印每轨 `rail_z_m`/`wheel_z_m`/侵入/力）在 R=1100 m、100 km/h、几何路由量到 cant **+0.107 → 右轨 +104.008 mm**（≈2×53.5）、cant **−0.107 → −0.285 mm**（≈0），即超高被加两次、负号相消。
- 两处来源：`src/velch/vehicle_solver.py:318` 的 placement `rise = abs(...)`（符号被 `abs()` 抹掉，永远抬右轨）与 `src/velch/irregularity.py:472-477` 的轨面旋转（符号跟随 cant）。
- 本轮不改这条路径（探测时临时打开的 `rise` 已 `git checkout` 复原），cant 在几何路由仍标不可引用；`docs/CURVE_SEAT_AND_CREEP_2026-10-27.md` §152 记录修法 A/B 与验收读数。

## 第 153 轮：超高只加一次了，车仍坐在一侧

- 按 §152 的两种修法各试一次：只留轨面旋转 → 右轨 `rail_z` **+49.976 mm**、侵入 24.953 mm；只留带符号 level difference → **+50.645 mm**、侵入 26.095 mm。两者都把 §152 的 +104.008 mm 消掉，证明重复是唯一被消掉的东西。
- 两种修法下车的状态相同：**4/8 轮着地**、左轨四根无接触、右轨各压 25–26 mm。结论：左右抬升与车轮 roll 不是同一约定（一侧相加一侧相减），需要同时打印两轨 `rail_z_m` 与四轮 `wheel_z_m` 才能定符号。
- 两处改动均未提交（`git checkout` 复原）；新增探测 `scripts/s12k_cant_single_owner.py`；cant 在几何路由仍不可引用。

## 第 154 轮：轨面两侧已经正确，差在车轮变换里的半个 b·sinφ

- 新探测 `scripts/s12l_both_rails.py` 同时打印两条轨的 `max z_m` 与四个轮心的 `y/z/roll`：左轨 **−53.721 mm**、右轨 **+54.799 mm**（差 108.520 = 2×54.26，与 `b·sinφ = 53.5` 吻合），四轮 `z = 0`、`roll = +0.071729`。
- 结论：轨面超高这半边已经正确（`RolledSeries` 以轨道中心为轴），placement 的 level difference 确实不该再加；剩余的 26 mm 是车轮变换里 `z` 抬升只拿到一半，下一轮用 `_absolute_arrays` 的 `wheel_z.min()` 与解析值对照定位。
- cant 在几何路由仍不可引用；`docs/CURVE_SEAT_AND_CREEP_2026-10-27.md` §154 记录表与下一步。

## 第 155 轮：车轮倾斜项正确，差的 23 mm 是轮缘而不是高度

- 新探测 `scripts/s12m_wheel_tilt_arrays.py`：左右跨各调 `_absolute_arrays`，两轮都恰好比「轮心 − R ± b·sinφ」低 **22.982 mm**（= 轮缘），两轮踏面差 **107.000 mm**，两轨顶差 **108.520 mm**，只剩 **1.52 mm**。
- 结论：`local_y·sin(theta)` 项完全正确，§154 的 26 mm 不是高度失配，而是**接触落在轮缘根**（`wheel_z.min()` 在轮缘上）。
- 下一轮：打印 `find_strip_contact` 的 `wheel_y` 区间与 `lever_y`，判定是否落在踏面；若是轮缘根，按踏面带宽限定候选，不动高度。

## 第 156 轮：轨顶内缘 35 mm 的接触，来自轨与轮绕不同点旋转的 31 mm

- 新探测 `scripts/s12n_contact_band.py`：四轴抬到 `wheel_center_height_m` 后只量搜索选中位置，左轨 `lever_y −714.322 mm`（轨带 −785.4…−713.2 的内缘），右轨 `+787.344 mm`（轨带 +713.2…+785.4），即接触比轨顶中心**内移约 35 mm**。
- 算式给出量级：轨绕轨道中心转 → 轨顶横向只动 `z·sinθ ≈ 5 mm`；轮绕轴心转 → 踏面接触点横向动 `R·sinθ = 30.8 mm`；差 **≈31 mm**。
- 下一轮：`RolledSeries` 改为绕自身轨顶旋转，轨顶横向不动、只改法向倾角；验收 `lever_y` 距轨带中心 ≤10 mm 且 cant=0 逐位不变。

## 第 157 轮：超高在几何路由改成拒绝——滚一个面表达不了超高

- `src/velch/vehicle.py` 的 cant 分支由 `roll_rails` 改为抛出带数字的 `ValueError`：`R sin(phi) = 30.8 mm`（φ = +0.07167 rad、1.493 m 轨距）说明滚轨面无法同时满足 `z·sinφ = 5 mm` 的轨顶横移。
- `tests/test_curve_seat.py`：旧测试替换为 `test_cant_on_the_geometry_route_is_refused_because_of_the_wheel_transform`（断言新文案）；顺带修掉按行号截断误删三条 R=350 测试的事故，`def test_` 计数 13。
- 全套 **920 passed / 1 skipped / 1 xfailed**；`docs/CURVE_SEAT_AND_CREEP_2026-10-27.md` §157。

## 第 158 轮：水平差 + 重力分量 + roll 入未知量，试过并回退，但定位到下一步

- 试了架构评审给的正解三件：轨面只做水平差（`RaisedSeries`）、重力在倾斜系分解（`sin 0.071606 / cos 0.997433`）、cant 非零时 roll 进静平衡未知量。
- 读数：cant=0 回归 `1.071e-07 N` / 8 斑 / 58.7–60.6 kN 不受影响；cant=0.107 只做水平差 → **4/8 轮着地**；再加 roll → `no seed converged; gtol`；手抬 z 到 `wheel_center_height_m` 且 roll ±0.0717 时，已升到 **+53.50 mm** 的左轨上接触仍是 **0.000 mm / 0.00 kN**、`max|force| 2.023e+06 N`。
- 判定：抬升没有到达接触几何（`RaisedSeries` 生效于 `series.sample`，`_absolute_arrays` 看到的仍是未抬基准）。三处改动已 `git checkout` 回退，仓库保持几何路由超高的**显式拒绝**。

## 第 159 轮：按里程重采样，深度第一次落进物理区间（1.5 µm → 9.7 µm）

- 新 `scripts/s17_order_tracking.py`：5 mm 空间网格重采样（`np.interp`，站停的重复里程先去重）、Hann
  空间谱找主波长、`k = 2π/λ` 的相干拟合给幅值，再除以 L3 的算子换算深度；`--sections` 按论文六区段分别投影。
- 主波长 **26.68 / 29.54 mm**（中位 28.11），与 H 假定的 27.5 mm、论文的 24.4–30.4 mm 一致——第一次用独立方法交叉验证 H。
- 全程深度 7.4 / 5.1 µm；**按区段** 12 个值中位 **9.7 µm**（3.0–37.4），落在物理区间内；固定频率只给 1.5 µm。
- 两个自造错已记：合成测试只覆盖 17.2 m（6000 点 @4 kHz），以及非整周期（627.09 个）拟合把幅值压到 0.757（−5.3 %）；改整周期后空间域恢复到 1e-6。
- 新 `tests/test_order_tracking.py` 5 项：主波长、变速度下空间幅值（并断言同频时间域拟合 < 50 %）、异波长不可见、重复里程去重、网格落到整步长。全套命令：`pytest tests/test_order_tracking.py`。
- L5 仍 `not_met`（3/6 检出、定位 ~30 m）；对外只能宣称检出与定位，不能宣称剖面反演。

## 第 160 轮：算子按速度标定，增益降 32 %，但探针设计误差同样大

- 新 `scripts/s18_speed_table.py`；`s16_operator.model_gain` 参数化（`speed_kmh` / `patch_start_m` / `periods`，默认值等于原行为）。
- 五档增益：40 km/h **2.757e4** → 80 km/h **2.087e4**，(m/s²)/m，**单调降 32 %**；同一速度换探针设计（790 周期 vs 240 周期）差 **−23 %**。
- 按段速度重算深度：中位 **12.6 µm**（单一速度 9.6 µm，比值 1.31）；区间 6.7–49.1 µm。判据仍是数量级，系统不确定度 ±30 %。
- 两个自造错：把运行起点与波磨起点绑在一起 → 增益小 **180 倍**；`Vi_Speed` 本身是 km/h，我又乘 3.6 → "274 km/h 的区段"。
- 新 `tests/test_speed_table.py` 4 项：表内插值、表点精确、表外取端点并置 `extrapolated`、增益随速度单调降且降幅 >20 %。
- L5 仍 `not_met`（3/6 检出、定位 ~30 m）；深度只作数量级引用。

## 第 167 轮：速度分离实验——这份记录只有一个稳态速度（2026-10-27）

- 新增 `scripts/s23_speed_separation.py`：按速度分箱做 FDD，再用 `f = a + b·v` 与 `order_slope = f/v` 比较，把峰分成“频率锁定（车辆）”与“波长锁定（轨道）”。判据是 `abs(slope) < 0.3·order_slope`。
- 实测：整程 145 s 里 1–70 km/h 全是**加速段**（各箱速度标准差 2.27–4.63 km/h > 2.0 门槛），**唯一稳态是 75–85 km/h 共 67.5 s**。因此“换速度看频率是否平移”的对照**在这份数据上不存在**，脚本以非零码退出并打印原因。
- 结论：第 166 轮那两组重复脊（57–60、88–92 Hz）只能停在“可重复、未归属”；车辆模态与轨道周期性在该记录里信息上不可分。要标定模型，必须有**同一区段的第二个稳态速度**。
- 修掉一个自己的判别式错误：原门槛 `0.15·order_slope·mean_speed` 在 57 Hz/65 km/h 下等于 8.8 Hz/km/h，把所有峰都判成频率锁定；改为与 `order_slope` 直接比较。
- `docs/OMA_MEASURED_2026-10-27.md` §9。

## 第 166 轮：FDD 补做——谱脊可重复，但还不能归给车辆（2026-10-27）

- 新增 `src/velch/inverse/spectral.py`：频域分解（Brincker 等），`spectral_matrix` 用 Welch 互谱拼 `S(f)` 后逐频点 `eigh`，输出未归一化的第一奇异值谱与奇异向量；`find_peaks` 以下四分位为底、忽略数值零线。
- `tests/test_spectral.py` 5 项全绿（解析 2 自由度 22.0/57.6 Hz 恢复、单音秩一形状比 0.5、奇异值有序、四类拒绝、证据字段）。
- 实测 6 个区段 + 整程：**57–60 Hz 与 88–92 Hz 两组谱脊在 4–6 个区段重复**（Cov-SSI 做不到这一点），但**与模型的 12.0/24.9/133.3 Hz 一个都不重合**；且 0.6 m 枕距在 75 km/h 下给出 34.7 Hz 及谐波 69.4/104 Hz，本记录只有单一速度，**无法区分轨道周期性与车辆模态**。
- 两处自己的错：谱矩阵按频点迹归一化会把峰值对比抹平（第一奇异值处处≈0.9），已改为不归一化；纯音算例里 1e-13 的数值零线会“零除零”赢下显著性，已加 `max·1e-9` 绝对底。
- 结论：FDD 可继续用，但要用它标定模型，必须先有一段**不同速度**的数据；`measurement_validation_status` 仍为 `not_evaluated`。
- 新增 `scripts/s22_fdd_measured.py`；`docs/OMA_MEASURED_2026-10-27.md` §8。

## 第 165 轮：运行模态识别接到实测——算法通过，实测不收敛（2026-10-27）

- 新增 `src/velch/inverse/oma.py`：Cov-SSI（平均相关信号 → 协方差 → 块 Toeplitz → SVD → 状态矩阵极点）+ 奇异熵增量定阶 + 阶次间稳定判据 + 模糊 C 均值剔除伪模态 + **簇内自洽与 |ζ|≤0.5 两条物理过滤**。按 Lv 等的 SSI-FCM 论文实现。
- `tests/test_oma.py` 6 项全绿：合成 2 自由度链（解析模态 22.0 / 57.6 Hz）恢复到 3 % 以内、单音 37 Hz、SEI 阶次、归一化、四类拒绝、证据字段。
- 实测 `Run_75kmh_E1toE2.mat`（145 s @ 4 kHz，2 通道）：S2 给 134.4/135.0/150.7/189.0 Hz，S3 给 69.7/100.2 Hz，S5 给 65.9/165.0 Hz，整程给 67.4/166.8 Hz（12 个稳定极点 / 154，SEI 阶次 5，MAC 代理 0.06）——**区段之间不重复**，只有一个 134.43 Hz 与模型轮盘 133.34 Hz 吻合（+0.8 %），但三套互不相容的答案使这条吻合不可引用。
- 两处自己的错：`Vi_Speed` 是 km/h（当 m/s 读会把 75 km/h 显示成 279 km/h）；区段样本阈值 20 000 过严（真实区段 13 686–26 121）。
- 结论：两通道轴箱记录在 5–200 Hz、4 s 级区段下不足以支撑稳定模态识别；下一步 FDD/EFDD、加入 `Vi_Lat` 作第三通道、只在平顺段识别，三者都不成则如实登记。
- 新增 `docs/OMA_MEASURED_2026-10-27.md`；`scripts/s21_oma_measured.py`。

## 第 168 轮：第二个稳态速度到手，波长锁定验证了，深度一致性没通过

用户提供 `Run_50kmh_E1toE2.mat`（40 km/h 在下载中），于是"只有一个稳态速度"这条限制解除，重开速度分离。

- 新增 `scripts/s23b_two_speeds.py`：两条记录各自取 ±4 km/h 稳态窗、4096 点块（1.02 s、0.98 Hz）、
  按同一组预注册区段 S1–S6 求平均谱、找峰、按 `f = v/λ` 换算后比对，并换算 27.5 mm 处的深度。
- 量到的可比性：75.73 km/h / 76.4 s 稳态 与 **50.50 km/h / 162.4 s 稳态**，两条都覆盖 S1–S6；
  50 km/h 记录的稳态占 83 %，比 75 km/h 那条干净得多。
- **设计频率按速度缩放被直接测到**：27.5 mm ↔ 764.9 Hz（75.73 km/h）与 510.1 Hz（50.50 km/h），
  比值 0.6669 = 两速度之比。
- **但峰集对不上**：18 行里 3 行是波长锁定候选、1 行是车辆模态、14 行无匹配；其中 S3 的"1.26 Hz 差"
  是拿 754 Hz 附近的噪声对出来的，50 km/h 记录里根本没有 1026 Hz 的峰。**所以不能写成"三个区段确认是
  波磨"**。
- **深度一致性失败**：24.2 µm（75.73 km/h）对 3.1 µm（50.50 km/h），比值 0.13。三种解释（本底淹没 /
  算子随速度变 / 两条记录的里程覆盖差 200 m）留待 40 km/h 记录到手后三点连线分开。
- 结论降级：`docs/OMA_MEASURED_2026-10-27.md` 新增 §10，明确"短波定值与速度无关"这条主张从"已验证"
  降回"只在 80 km/h 附近验证过"，并在 §10.4 写明三条候选解释与分辨方法。
- 顺手修的两处：匹配器阈值与分辨率的关系没写清（0.98 Hz 分辨率下 2.5 Hz 阈值过宽，已注明只能当候选）；
  通道平均（谱按两个轴箱通道平均而不是分别找峰），并在注释里写明原因。

## 第 169 轮：四条速度记录到手，波长缩放成立，但 27.5 mm 上没有可分辨的峰

用户补齐数据目录（40/50/60/75 四个速度，40 与 60 为反向），于是"深度随速度不一致"这条异象可以定案。

- 新增 `scripts/s23c_four_speeds.py`：自动扫描 `Run_*kmh_*.mat`，四条记录各取 ±4 km/h 稳态窗、
  4096 点块、同一组区段，输出"命中矩阵 + 深度表 + 判定"。
- 四个稳态速度：**40.83 / 50.50 / 61.03 / 75.73 km/h**，都覆盖 S1–S6。
- **波长缩放的必要条件成立**：27.5 mm 的设计频率 412.5 / 510.1 / 616.5 / 764.9 Hz，相邻比 1.237 /
  1.209 / 1.241 与速度比逐位一致。
- **充分条件不成立**：24 个区段-速度里，27.5 mm 命中 3 个、60 mm 命中 4 个、20 mm 与 40 mm 各 0 个；
  命中的也不是同一批区段。
- **于是"深度"表测的是本底**：27.5 mm 深度中位数 5.2 µm、最小 0.3、最大 85.5，极差 337 倍。
  上一轮"深度差 7.7 倍"的三种解释收敛为一种——**那条波长上没有峰**。
- 能力边界更新：27.5 mm 在本数据集**不具备定量反演条件**；60 mm 是唯一多速度候选；检出 3/6 站得住，
  定量一条都不站。`docs/OMA_MEASURED_2026-10-27.md` 新增 §11（含命中矩阵与深度表）。

## 第 170 轮：60 mm + 2.05 s 块也不可定量，实测侧能力声明成文

- 新增 `scripts/s23d_candidate_wavelength.py`（波长与块长作为参数，复用 `s23b` 的稳态窗与区段），
  回答"换个波长、把分辨率翻倍，能不能把 27.5 mm 那条线救出来"。
- 实测 60 mm / 8192 点（2.05 s、0.49 Hz）：命中 **3/22**，且**只在 S1**；S1 三个速度的深度
  8.9 / 27.0 / 12.1 µm，**差 3.0 倍**。整体深度散布 0.2–134.9 µm（797 倍）。
- 判定：**不可定量**，而且原因不是波长选择、不是分辨率，而是区段太短、只有 S1 同时有峰、无廓形真值。
- 新文档 `docs/MEASUREMENT_CAPABILITY_2026-10-27.md`：把"能声称 / 不能声称 / 归类 / 需要什么新数据"
  四栏写成验收级声明（含 L0 台账、检出 3/6、波长缩放必要条件、四速度命中矩阵、五条不能声称的判据失败位置）。
- `docs/OMA_MEASURED_2026-10-27.md` 新增 §12 记录两个旋钮的实测与结论。

## 第 171 轮：几何路由的超高补上重力倾角后仍不足以闭合，写成 ADR 并保留拒绝

- 试了最后一块拼图：把重力放进倾斜坐标系（`force[y] += m g sin(phi)`、`force[z] -= m g (1 - cos(phi))`），
  同时恢复被写死成 `rise = 0.0` 的外轨抬高。`cant0` 的几何曲线仍 `numerically_checked` 7/7（改动对无超高
  工况惰性），而 `cant = 0.107 m` 的工况仍在加载阶段被 `vehicle.py:503` 拒绝。两处改动在现有配置下是死代码，
  已回退。
- 写清算术：外轨抬高 `±b sin phi = ±53.5 mm` 与轮对 roll 的 `±b sin phi` 必须成对且同号，缺一边就是
  `2 b sin phi = 107 mm` 错位（与第 38 轮实测 103 mm 一致）；重力倾角只解决横向力那一半，**不解决竖向错位**。
  竖向错位要静平衡同时解 z 与 roll，而 0 速度下横向方程无平衡解（第 30 轮 cond 3.76e12）。
- 新增 `docs/CURVE_CANT_DECISION_2026-10-27.md`：ADR 形式记录"几何路由继续拒绝"+ 力路由可用（59 652–59 708 N）
  + 正路是"运行态坐车"（先无超高坐 8/8，再在时程中把坡面抬进去）+ 禁止的四条捷径。

## 第 172 轮：曲线切线从运行起点挪到它的真实位置（B039 关闭）

- `_curve_placement` 与 `_place_on_alignment` 原先都用 `s = x_m - x_start`，把 `y = s²/(2R)` 的顶点钉在
  运行起点。R=1100 m、切线 50.578 m、`x_start` 30 m 时，切线**之前**也给出 `s < 0`，把车辆放到一条镜像弧上：
  后轴 −425.1 mm、前轴 −50.8 mm、车体 −192.5 mm（正确值都是 0）。
- 新增 `_arc_parameter_m(run, mileage_m)`：`max(mileage - tangent, 0)`，切线取 `run.curve_origin_m`，
  `None` 时退回 `x_start_m`（既有算例逐位不变）。**轨面侧与车辆侧共用同一个函数**，避免两侧对"弧从哪开始"分歧；
  切线处一阶连续（`dy/ds` 两侧都为 0）。
- `RunSettings.curve_origin_m` 新增；加载时拒绝两种组合：无 `curve_radius_m` 的 `origin`（否则静默无效）、
  `origin` + `cant`（带超高的几何路由本身被拒绝，组合只会造出"配了但不起作用"的工况）。
- `tests/test_curve_origin.py` 5 项：切线前/处/后 10 m 的弧参数、`None` 的旧含义、两侧一致且直股段严格为零、
  两条拒绝。
- 实测（`x_start` 30 m、R=1100、100 km/h、0.02 s）：不给 origin / origin=30 / **origin=50.578** 三个变体
  都 `numerically_checked`、7/7。第三个变体即"从直股进入曲线"，以前不存在。
- `docs/CURVE_SEAT_AND_CREEP_2026-10-27.md` 新增 §26（含一阶误差表与三个变体）。

## 第 173 轮（未决）：同一条 R=1100 m 曲线，起点 30 m 能坐、60 m 不能

B039（第 172 轮）落地后，回测同一条几何曲线在不同起点上的静态平衡，结果不一致：

| 算例 | 起点 | 结果 | 门 |
|---|---|---|---|
| R=1100、cant=0、100 km/h、0.02 s | 30 m | `numerically_checked` | 7/7 |
| 同上 | **60 m** | **坐不住** `unbalanced branch - 4 of 8 wheels carry load … heaviest 127821.9 N`（均分 59 662 N） | — |

已排除的两条：

1. **不是 `align_to_track` 与 `curve_geometry` 重复平移**：`curved_geom`（只开 `curve_geometry`）与
   `curved_both`（两者都开）报**同一个数**（127 821.9 N，四位相同），所以不是两倍 45 mm 叠加；
2. **不是几何没到位**：在 60 m 起点、前轴里程 70 m 处，轨面侧横向偏移实测 **+0.045455 m**、
   横向速度 **+0.252525 m/s**（= v·s/R），与 `s²/(2R)`、`s/R` 的设计值一致；`_seat` 结束后
   placement 已按设计恢复（on / enabled）。

**因此未决的是**：`_seat` 内部把 placement 关掉之后，接触搜索看到的到底是直轨还是弯轨——需要沿用
第 17 轮那个"记录 `evaluate` 每一次调用"的探针（`scripts/s12_curved_seat_residual.py`），在 `_seat`
**内部**打印每块斑的里程与 `rail y`，而不是在调用前后打印（本轮探针打在了恢复之后，因此看不到）。
探针已入库：`scripts/s72_curve_creep_terms.py`（三条路由对照）、`scripts/s72_seat_frames.py`（起点内外帧）、
`scripts/s72_curve_origin_variants.py`（三个切线变体）。

这一条不改变 B039 的结论——切线位置本身已由 5 项测试与三个变体证明；它只说明"起点离弧顶远到一定程度"
时还有第二个问题，而第 172 轮的三个变体起点都在 30 m（离弧顶 20.6 m 以内）。

## 第 174 轮：撤回第 173 轮那条"未决"——原因是我自己的探针绕过了 `_seat`

第 173 轮记下"同一条 R=1100 m 曲线，起点 30 m 能坐、60 m 不能"，并把它列为未决。这一轮查清了，
**它不是软件的问题，是探针的问题**。

### 174.1 实际发生的事

`scripts/s72_curve_creep_terms.py` 直接调了 `_static_vertical_equilibrium(...)`（模块函数），而没有走
`_seat(...)`。`_seat` 的关键动作正是**在求解期间把曲线 placement 关掉**（`dynamics.placement_enabled = False`
+ `dynamics.track.placement = None`），因为零速下弯轨没有横向平衡（第 31 轮：cond 3.76e12、最小奇异值 2.7e-11、
每个种子残差 2.39 = 240 kN）。绕过它，等于让静平衡去解一条"钢轨在弧上、车辆在直线上"的系统——
结果就是那个指纹：**4/8 轮着地、最重 127 821.9 N（均分 59 662 N）**，与第 17、22 轮用弯轨求解时一模一样。

### 174.2 这一轮的实测（`F:\velch_tmp\round73_seat_frame.py`）

记录 `_seat` **内部**每一次 `evaluate` 调用看到的帧：

| 起点 | 结果 | 首次调用处的轨面帧 |
|---|---|---|
| 30 m | 静平衡残差 **1.11e-07 N** | `x_start 30`、里程 40.00、`rail y +0.000000`、`vy +0.000000`、`placement off`、`enabled False`、`ProfileSeries` |
| 60 m | 静平衡残差 **4.18e-08 N** | `x_start 60`、里程 70.00、`rail y +0.000000`、`vy +0.000000`、`placement off`、`enabled False`、`ProfileSeries` |

两处都是**直轨帧**，两次都坐得住。所以"起点 60 m 坐不住"这件事**不存在**；第 173 轮那张表里的
`127 821.9 N` 是我的探针造成的。

### 174.3 顺手把这个错误变成不可再犯

`_static_vertical_equilibrium` 现在在入口处**拒绝**在 placement 打开时运行：

```
the vertical seat cannot run with the curve placement on: the rails would be on the arc while the
vehicle is on the straight line, and the seat settles on one side (measured 4 of 8 wheels,
127 821.9 N against a 59 662 N share). Call _seat(), which switches the placement off around the solve
```

这样下一次有人（包括我）直接调这个函数去测曲线，会拿到明确的报错而不是一个看起来像"软件缺陷"的数字。
测试加在 `tests/test_curve_seat.py`：直调必须抛这条；走 `_seat` 必须正常。

## 第 175 轮：实测反演的判定页与机读产物（L0–L5）

- 跑通 `scripts/s24_verdict.py`（此前只有模块与脚本，从未在实测数据上执行），产出
  `reports/inversion_measured_2026-10-28/` 六件：`verdict.json`、`bands.csv`、`windows.csv`、
  `speed_table.json`、`operator.json`、`order_tracking.json`。
- 判定：**L0 passed**（579 740 样本 / 2 通道 / 4 kHz / 3 798–6 303 m / 稳态 1 档 67.5 s）、
  **L1 passed**（双通道滞后 2.25 ms，判据 25 ms）、**L2 failed**（该记录只有一个稳态速度，
  按速度的标定表只在 70.8 km/h 建过）、**L3 passed（有限）**（算子 2.743e+04 (m/s²)/m；
  峰可重复但幅值无可比真值）、**L4 skipped**（地板与覆盖率只在合成记录上验过）、
  **L5 failed**（3/6 段，判据 6/6；段级虚警 5 %，二项 p = 0.0022）。
- `measurement_validation_status = detection_only`、`physics_validation_status` 不变；并列出四项
  「不能声称」的话与四条缺什么（按代价排序），其中「40/50/60/75 四份记录只有 75 那份建了表」是 L2 的
  真实缺口，不是数据不存在。
- 新增 `docs/INVERSION_VERDICT_2026-10-28.md`（结论两行、逐层表、四项不能声称、缺什么、与 95 % 的关系）。

## 第 176 轮：L2 从「一个速度」到「四个速度」（波长散布 11.3 %）

- `scripts/s14_speed_table.py` 对 `F:\ai道岔状态反演辨识\75kmh数据` 下**全部四份**记录各建一行表：
  39.9 / 49.2 / 58.0 / 70.8 km/h → 线频 398.4 / 451.8 / 565.2 / 713.2 Hz、中位波长 28.1 / 29.9 / 26.7 / 27.5 mm、
  落 18–40 mm 的比例 93.6 / 90.2 / 68.3 / 64.7 %、突出度 28.2 / 23.7 / 23.0 / 23.1 dB；脚本判 `PASS`。
- 两件事同时成立：**线频随速度缩放**（1.79× vs 速度比 1.77×）、**波长不随速度变**（散布 **11.3 %**，判据 15 %）。
  这是「常数波长」假设的正面证据，也是「表按速度分键、不内插」这条规则能用的前提。
- `scripts/s24_verdict.py` 的 L2 由硬编码 `FAILED` 改为读四速度表判定：`speeds_with_steady_data = 4`、
  `wavelength_spread = 0.113`、`criterion_spread = 0.15` → **passed**。判定变为
  L0/L1/**L2**/L3 passed、L4 skipped、L5 failed（3/6）；`measurement_validation_status` 仍为 `detection_only`。
- 重新生成并入库 `reports/inversion_measured_2026-10-28/`（`verdict.json`、`bands.csv`、`windows.csv`、
  `speed_table.json` 四件已刷新）；`docs/INVERSION_VERDICT_2026-10-28.md` 增 §2b（四速度表）并改 L2 行与「缺什么」表。

## 第 177 轮：四次过车 × 六个区段 —— 单次 3–4/6，融合 6/6（声通道）

- 对四份记录各跑一次检测（伪区段校准、段级虚警 5 %），把「漏的是哪一段」摊开：
  - **声通道**：单次 3/6、4/6、3/6、3/6，**融合 6/6**，**S4 四次全中**；
  - **振动通道**：单次 2–3/6，**融合 4/6**，**S2 与 S6 四次全漏**（最好一档 19.6 / 25.2 dB 仍低于各自阈值）。
- 命中的速度组合不随方向聚集（S1 于 50/60 km/h、S3 于 40/75、S5 只于 75）→ **漏检不是方向问题**。
- L5 的 6/6 现在有两种口径且必须分开写：**单次未达成**；**多过车融合已达成**（声通道）。定位误差 0 m
  仍是因为没有断面真值可核。
- 新增 `docs/MEASURED_MULTIPASS_2026-10-28.md` 与
  `reports/inversion_measured_2026-10-28/multipass_sections.json`。

## 第 178 轮：manifest 现在自己声明 measurement_validation_status，且只有验收层能抬高它

- `manifest.json` 的 `summary` 新增 `"measurement_validation_status": "not_evaluated"`，与
  `physics_validation_status` 并列；写死在这一处、并在注释里写明**只有 `velch.inverse.verdict` 能返回更强的值**，
  因为只有那一层真的拿实测记录做了比较。一次仿真本身永远不能声称自己的数字被实测验证过。
- 顺手清掉 `verdict.measurement_validation_status` 里把 `L5_acceptance` 绑两次、两个名字同一层的写法
  （行为不变，读起来不再像"检测层"和"验收层"是两条证据）。
- 新增 `tests/test_measurement_status.py`（5 项）：manifest 默认值 + 真实跑一次 0.005 s 算例取 manifest；
  **源码扫描**——除 `src/velch/inverse/verdict.py` 外任何模块都不得出现 `detection_only` /
  `consistent_with_recorded_section` 字面量；失败验收只授权"仅检出"、无 `detected` 时退回 `not_evaluated`；
  通过验收必须有 `consistent_with_recorded_section` 证据；每个取值都有含义。
- 测试里两个坑：`LayerResult` 拒绝"通过但没有数字"和"失败但不说原因"，所以构造判决对象必须带 metrics/notes；
  把示例算例复制到临时目录会丢失型面的相对根（`AssetRefError: cannot resolve profile 'wheel_lower.csv'`），
  必须把 `.csv/.txt/.prr` 引用改写成绝对路径。

## 第 179 轮：曲率项不能写成 `(1−κy)` 因子——那是把同一个量算两遍

- 试过把纵向蠕滑写成 `slip_x = (1 − κ·lever_y)·(v + ω·lever_z) − κ·v·lever_y`，理由看起来是"轨在横向
  y 处弧长按 `(1−κy)` 缩短"。推导一行就否掉：**外侧接触点与内侧的弧长差本身就是 `Δv = κ v b`**，而
  这一项已经以 `−κ·v·lever_y` 的形式在表达式里；再乘一个因子等于把同一个量加第二遍。零自转时两种写法的
  差值恰好是 `−κ v b`，即**翻倍**。
- 因此 `src/velch/contact.py` 保持原式，新增
  `tests/test_curve_seat.py::test_the_arc_length_factor_would_double_count_the_curvature_term`
  把这件事钉住：实测 `curved − straight` 等于 `−κ v b`（rel 1e-12），并显式断言它**不等于**它的两倍——
  将来谁再"补"这个因子，测试立刻红。
- 验证：`tests/test_curve_seat.py` + `tests/test_curve_alignment.py` **14 passed / 1 xfailed**；
  `scripts/freeze_baseline.py --check` → **UNCHANGED**（`straight_rigid 06928c9db944796d`、
  `straight_flexible ab81290f5924c3a5`）。

## 第 180 轮：超高的三件已在位，静平衡能坐住，但运行会陷 26.4 mm——因此仍然拒绝，数字换了

- 上一轮我怀疑「外轨抬高」那半又被钉成 0（`rise = abs(0.5·gauge·sin(theta))` 后面紧跟 `rise = 0.0`，
  第 38 轮还原时的残留）。恢复之后，几何路由的超高三件齐了：**外轨抬高 `b sinφ`**、
  **轨面绕自身轴滚 φ**（`roll_rails`）、**车架随坡面倾 φ**（`_place_on_alignment`）。
- 实测（R=1100 m、cant=0.107 m、100 km/h、0.01 s、`curve_geometry + align_to_track`）：
  - **静平衡第一次坐住**：残差 **4.181e-08 N**，八个接触各 **59.7 kN**（与 cant=0 的 59.7 kN 一致）；
  - 但 0.01 s 运行报 `numerical_gate_failed`，唯一失败门 `penetration_within_case_limit`，
    **最大侵入 26.4 mm**——正好是轮缘深度，说明加超高的轮轨变换仍把车轮送到轨距面上。
- 因此 `curve_cant_m` 在几何路由**继续拒绝**，但拒绝理由从"未实现"换成了量到的
  **26.4 mm（= 轮缘深度）**，并保留"力路由可用（七门、八轮 59 652–59 708 N）"作为正路。
- 这条把 `docs/CURVE_CANT_DECISION_2026-10-27.md` 的结论从"没试"推进到"试了、坐住、跑不住"，
  下一个要查的是加超高后 `penetration_m` 在**哪一帧哪一轨**变成 26.4 mm。

## 第 181 轮：26.4 mm 定位到「四条右轨、第 0 帧」，并指向座与放置的先后顺序

- 读 `F:\velch_tmp\round79_cant107_out\history.csv`（2 帧、8 个穿透列）：
  **`axle1_right / axle2_right / axle3_right / axle4_right` 在 t = 0 全部是 26 415.6 µm**，左侧四条为 0。
  四条同值、只在右侧、且在第一帧 → 这是**静态配对误差**，不是动态振荡。
- 数值上 26.4 mm ≈ 53.5 mm（外轨抬高 `b sinφ`）− 27.1 mm，即**抬高收到了一半效果**；而第 180 轮那次
  `_seat` 探针在同一算例下**坐住**（残差 4.181e-08 N、八轮 59.7 kN）。同一份算例、同一个座，探针成功、
  运行第 0 帧就穿 26.4 mm——差别只有一处：**放置（`_place_on_alignment`）在座之后才施加**
  （上一轮为修"对齐把车挪到直股外 45 mm"而把顺序改成"先座后对齐"）。对弧线这是对的，对**超高**则错：
  倾斜必须在**座里**参与，否则车是按水平面坐好、再被整体转 φ 的。
- 下一轮的唯一实验：让 `_seat` 在超高速径上**带倾角求解**（座内 `roll` 初值取 φ，placement 保持开启），
  再看第 0 帧穿透是否归零；若归零且七门全过，则几何路由的超高可以发布，否则按 §180 继续拒绝并保留
  26.4 mm 这个证据。

## 第 182 轮：滚动初值下的静态侧向平衡也不收敛——曲股侧向状态是「运行平衡」

- 目的：验收门第 4 项要求把静平衡未知量从「只有 z」扩到 y/yaw/roll。此前只量过**零速**（秩亏
  `cond 3.76e12`、σ_min 2.7e-11、所有种子停在 240 kN）。这一轮把轮对自转设成 `omega = v/r = 51.6796 rad/s`、
  让 `creep_attack_velocity = travel * yaw` 与 `slip_x` 的曲率项真正起作用，再解 36 个未知量
  （每个体 y/z/roll/yaw + 8 根弹性轨垂向行），三个种子。
- 结果（否定）：最好一次 `|r|max = 6.5699e+04 N`（`xtol`）、`cond 5.441e+07`、**只有 2/8 轮承力**
  （`axle3_right 131807.9 N = 2.209×`、`axle4_right 138987.3 N = 2.330×`，四个左轮全 0）；
  最大残留行是 `wheelset4.roll 65698.9`、`wheelset3.roll 56894.3`、`bogie2.roll 56284.7`。
  下沉 1/2 mm 的两个种子更差（全行撞 1.0 势垒，guard 命中 76 次）。
- 对齐的两个变体 `none` 与只给横移的 `shift` 给出**逐位相同**的结果（同一 5.7637e+04、同样 2/8、
  134591.9–139094.6 N）→ 两者都落到同一支外轨贴靠解，对齐不是差别所在。
- 判读：曲线上车辆的侧向状态由运动闭合（滚动半径差给偏航力矩、冲角给横向蠕滑力），压成静态根必落贴靠支。
  与 Elkins & Gostling（VSD 1977）一致；也与「同一算例时程跑 7/7、八轮承载」互为对照——**轨迹找得到、座找不到**。
  因此**不再扩张静态座的未知量**，座只决定车轮坐多深。
- 顺带登记一个待定缺陷（未改代码）：`_align_to_track_frame` 把 `yaw` 写成**绝对航向** `arctan(dy/ds)`，
  而 `contact.py:732` 把同一坐标当**冲角**用；本条曲线上两者差 0.0158 rad，即 `travel*yaw = 0.352 m/s`
  的虚假横向蠕变（约 0.9° 冲角）。下一轮用「同状态比较 yaw=0 与 yaw=切线角时的横向合力是否等于
  `m v²/R = 21.4 kN`」这个可判定的实验来定它。
- 新增 [`docs/CURVE_QUASISTATIC_SEAT_2026-10-28.md`](CURVE_QUASISTATIC_SEAT_2026-10-28.md) 与
  `scripts/s26_quasistatic_seat.py`（约 17 s 可复算）。冻结物理未动。

## 第 183 轮：B040 —— 路线的横向「搬运速率」被当成横向蠕滑，曲股第一帧就饱和

- 触发：曲股波磨算例（`s27_curve_corrugation.py`，R=1100 m / 80 km/h）在 `x=81.289777 m` 处报
  `graph slope limit at axle1_right/right:main`。这个 `x` 是**钢轨站位里程**（含 1 位轴 +10 m 偏置），
  所以车辆只走了 **2.29 m**（t ≈ 0.103 s）。
- 实测（`scripts/s29b_seat_slip.py`，座位后第一帧，除自转外状态速度全为零）：`slip_lateral`
  为 **+0.5737 / +0.5232 / +0.2205 / +0.1700 m/s**，`sum(Fy) = −36 939 N` —— 方向与曲线所需
  `+21 842 N` 相反，量级 1.7 倍。蠕滑饱和速度量级只有 0.01–0.1 m/s，所以接触从第一帧起就是饱和的。
- 根因：`vehicle_solver.py` 把 `path.lateral_velocity_m_s = v·dy/ds`（79 m 处 `1/0.0257`、22.22 m/s
  下 0.571 m/s）加进 `wheel_v_y_m_s`。**顺着曲线走的车辆对钢轨没有横向相对速度**（`dq[y]/dt = 0`）；
  `v·dy/ds` 是参考系在笛卡尔坐标里的搬运速率，不是材料滑移。位置上的 `lateral_extra = path.at(x)`
  是对的（车轮必须被搬到设计线上），速度上的那一项是错的。
- 修法：`wheel_v_y_m_s=float(v[axes["y"]])`（去掉 `+ lateral_rate`）；`PathTrack.lateral_velocity_m_s`
  的 docstring 改成它真实的含义并写明不得进蠕滑；新增 `tests/test_path_transport.py` 两项
  （搬运速率随里程增长、量级 0.61 m/s；以及一个源码级守卫，钉住接触调用不再加这一项）。
- 效果（实测）：`slip_lateral` 四项全部 **0.00000**、`sum(Fy)` **+292.5 N**；斜率守卫触发点从
  `x=81.289777 m` 推到 `x=83.525026 m`，即行程 **2.29 m → 4.53 m**（t 0.103 s → 0.204 s）。
  直向算例 `dy/ds = 0`，两个冻结基线 `UNCHANGED`。
- **没修好**：曲股仍然过不去。0.30 s 跑 784.7 s 后仍在同一守卫停下，右轨 `2.69–2.91×` 过载、
  `axle1_right`/`axle2_right` 无接触依旧 —— 那是几何问题（B041，见下一条），不是蠕滑问题。
- 新增 [`docs/CURVE_PATH_RATE_DEFECT_2026-10-28.md`](CURVE_PATH_RATE_DEFECT_2026-10-28.md)、
  `scripts/s28_curve_contact_table.py`、`scripts/s29_path_rate.py`、`scripts/s29b_seat_slip.py`、
  `tests/test_path_transport.py`。

## 第 184 轮：B041 —— 曲股右轨的站位表不是一条一致的轨道几何

- 事实：两侧站位表来自两个不同模型（左 `Profile_Mileage_JBG.prr`（CRH380A）19 001 站 / 5 mm；
  右 `jbg-20200418-R.prr`（SDITT）16 664 站 / 5.2 mm），各自给 `y_offset_m`。左轨严格跟着
  设计线 `s'²/(2·1100.75)`（吻合 1e-4）；右轨相对左轨的偏离在 **1.4438 … 1.5876 m** 之间漂移，
  即轨距 1.4438–1.5876 m，而车轮是按 1.493 m 放的。
- 后果：79–94 m 处右轮内移 63–95 mm，落在轨距角/轮缘根上 —— 第一帧 `axle3_right 160.5 kN = 2.69×`
  （侵入 120.6 µm），`axle1_right` / `axle2_right` 无接触，而左轨四轮 0.97×。两侧冠高还差
  72–134 µm，垂直座没有 roll 自由度，只能靠不等侵入吸收。
- 三种重建方案都失败（`scripts/s30_fix_diverging_gauge.py` + `s30b` + `s30d` + `s30e`）：
  右 = 左 + **1.493**（车轮轨距）→ 第一帧 `axle1_right` y=+1.08229 给 3143 µm、`|n_y/n_z| = 1.274`，
  斜率守卫在 t=0 抛出、`gtol` 停住；右 = 左 + **1.50649**（45 m 处已知能坐住的关系）→ 座位"收敛"
  但 `axle1_right 1 879 096 N = 31.5×`、`axle2_right 758 335 N = 12.7×`、`sum N = 6.33×` 重量；原样 →
  2.69× 与两个右轮无接触。
- 原因已定位到断面本身：两个断面的**冠部不在其中位**（左冠比中位靠外 6.8 mm、右冠靠外 6.7 mm），
  实测**冠距恒为 1.5071 m，而车轮冠距是 1.4930 m**（两个车轮断面最大半径都在 local y ≈ 0），
  一直差 14.1 mm。正确的重建必须**逐站位**把冠钉在车轮冠上：
  `right_offset = left_offset + 1.4930 + (左冠偏移) − (右冠偏移) ≈ 1.4795 m`（在原样、1.493、1.50649
  三个候选之外）。验收门已先写死（四轴位冠距 1.4930±0.5 mm、8/8 承力 ∈[0.625,1.6]×、第一帧
  `|n_y/n_z| < 0.3`、80 km/h 跑 ≥0.30 s 且越过 79.6–83.6 m 补片、直线与两个冻结基线 `UNCHANGED`）。
- 新增 [`docs/CURVE_RAIL_GEOMETRY_2026-10-28.md`](CURVE_RAIL_GEOMETRY_2026-10-28.md)、
  `scripts/s30_fix_diverging_gauge.py`、`scripts/s30b_seat_after_gauge.py`、
  `scripts/s30c_crown_heights.py`、`scripts/s30d_seat_diagnose.py`、`scripts/s30e_guard_geometry.py`。

## 第 185 轮：对称轨道上的曲线静平衡是精确的，几何路线却没有向心力的来源

- B041 的第四次重建（右 = 左 + 1.5065 m，即冠距口径的正确符号）仍然失败：第一帧
  `axle1_right 1 879 207.6 N = 31.498×`、`axle2_right 758 137.1 N = 12.707×`、`axle4_right` 无接触、
  `sum N = 3 021 912.8 N = 6.331×` 重量，`slip_lat` 全为 +0.00000（B040 生效）。所以修右轨这条路
  走不通：**右侧断面本身沿里程在变**，它不是一条轨。
- 换路：`case_A_final_law`（刚性、左右同源、轨距正好 1.493 m）+ `curve_radius_m = 1100` +
  `curve_geometry` + `align_to_track`，80 km/h，从 30 m 起，35 坐标。脚本
  [`scripts/s31_curve_smoke.py`](../scripts/s31_curve_smoke.py)。
- **坐实精确**：静平衡残差 **1.109e-07 N**，八轮 **0.988–1.013×** 均分、侵入全部 **65.47 µm**、
  `|n_y/n_z| = 0.025`、合计 **1.000× 整车重**，左右逐位镜像。0.02 s 运行 `numerically_checked`、
  **门 7/7**、最大侵入 73.27 µm、八斑峰值 62.0–69.9 kN。**曲线静平衡在对称轨道上可解**——
  上一轮"曲股坐不住"的读数属于 B041 的数据缺陷，不是曲线物理。
- **但跑不过 1 m**：0.30 s 失败 `graph slope limit at axle1_left/left:main, x=41.04259 m`（`x` 含
  +10 m 轴偏移 ⇒ 行程 1.04 m、t ≈ 0.047 s）。用 `scripts/s31c_yaw_attack.py` 把对齐后的 `yaw`
  清零（接触几何是 (y,z) 条带搜索、不读 yaw）重跑 → `x=40.7585517 m`（0.76 m），**更早失败**，
  所以漂移不是第 182 轮登记的偏航双重含义驱动的；该口径问题降级为"仍未定"，不是曲线阻塞点。
- **真因**：向心力 `m v²/R` 只加在力路线上（`if curve_radius and not _placement_enabled(run)`），
  几何路线把车摆到弧线上却**不给任何法向力**，车按惯性走直线、轨按弧线弯走，相对横移按
  `s/R = 9.09 mrad`（9 mm/m）长大，最后只能压在轮缘上。R = 1100 m、80 km/h 需要 **21 842.4 N**。
  而反过来，力路线**不能**把曲率放进蠕滑：`curvature_1_per_m` 的开关注释记录着
  `flags on but placement off` 时 **4 of 8 wheels、128 901 N = 2×** 的实测——静平衡的未知量里没有能
  平衡 `∓v κ b` 摇头力矩的自由度（只有 z；y/roll/yaw 都试过，零速下 rank-deficient，cond 3.76e12）。
- 结论：**两条路线各缺一半**，随动坐标系需要的不是"再把曲率打开"，而是让静平衡能吸收这个力矩。
  波磨反演协议 [`scripts/s31b_curve_corrugation.py`](../scripts/s31b_curve_corrugation.py) 已按判据写死
  （单侧内轨、四个对数分层波长、峰峰归一化、0 / 0.1 / 0.3 mm、最小档标定去预测大档、
  "零档响应的 6 倍以上才算被激励"、"0.3 mm 复原峰峰 ±2 dB"），但它必须先有一个能跑满 0.34 s 的曲线算例。
- 新增 [`docs/CURVE_ROUTE_COMPARISON_2026-10-28.md`](CURVE_ROUTE_COMPARISON_2026-10-28.md)、
  `scripts/s31_curve_smoke.py`、`scripts/s31b_curve_corrugation.py`、`scripts/s31c_yaw_attack.py`。

## 第 186 轮：曲率进蠕滑不再按路线门控、轮对 yaw 进座、对齐补上速度（B042/B043）

- 目标第 1/120 轮（goal 第 4 项主线）。四处改动，每一处都带实测依据：
  1. `curvature_1_per_m` 不再按 `placement_enabled` 门控——曲率是**轨道**属性（一根轴的两接触点走不同弧长，
     `±vκb`），门控它等于让两条路由各拥有随动坐标系的一半；
  2. 曲线时把轮对 `yaw` 加进 `_static_vertical_equilibrium` 的未知量（`y`/roll 仍不进：零态轨顶接触无横向
     分量 → cond 3.76e12、σ_min 2.7e-11、种子停在 240 kN；`yaw` 的行由蠕滑律 `travel*yaw` 提供刚度，
     不秩亏）；
  3. **B042**：`_align_to_track_frame` 不再把设计线切线写进 `yaw`，写 **0** —— 状态 `yaw` 被蠕滑律读作
     **攻角**（`creep_attack_velocity_m_s = travel * q[yaw]`），写切线等于注入 `travel*arctan(slope)`：
     30 m 处 0.352 m/s、81.6 m 处 0.6707 m/s；
  4. **B043**：新增 `_align_velocity_to_track`，在 `_integrate_vehicle` 里紧跟对齐之后调用，给每个刚体装上
     设计线自己的横向速度，取自 `local_state` 的第三返回值（解析 `speed*dy_ds`）。第一版用 `_gauge_centre`
     的 1 m 差分斜率，得 0.2121 m/s 而轨面真值 0.2020 m/s（二次曲线上前向差分滞后半米，+5 %），
     这股外向蠕滑此后一直在还账。
- **力路由得到最干净的曲线座**（`case_A_final_law` + R=1100、无摆置、80 km/h、0.02 s、35 坐标）：
  残差 **4.179e-08 N**，八斑全部 **59 680.6 N = 1.000×**（即冻结静载门那个数，误差 0），
  `slip_lat +0.0000`，合计 1.000× 整车重；运行 `numerically_checked`、**7/7**、峰值 59 748–59 916 N。
- **几何路由仍然拿不住**，但失败点从 1.04 m 挪到 **1.20 m**（`x=41.1989149 m`，t ≈ 0.054 s）。失败瞬间状态：
  前轴轨面已横移 **57.4 mm** 而车轮只到 **47.8 mm**（落后 9.6 mm），触发接触 slope **1.0423**、
  侵入 **413 µm**（轮缘压轨顶）。
- **把账算清**：踏面在 65.47 µm 侵入下 `n_y/n_z = ±0.0250` ⇒ 每斑 1.49 kN、八斑 **11.9 kN**，而 R=1100/80 km/h
  需要 **21 842.4 N**，缺口 **9.9 kN**。补它必须爬到斜率 ≈ 0.2，爬到 1.0 就是轮缘——这就是 guard 在 1.04 退出的
  物理含义。**无超高时轨顶接触撑不住这条曲线**，不是容差问题；也解释了为什么站表里本来就是弯的 18 号道岔
  （曲线是静态几何、没有 `rail_vy`）能 7/7，而人为摆出来的同半径曲线跑不到 0.06 s。
- 新增 [`docs/CURVE_ALIGNMENT_VELOCITY_2026-10-28.md`](CURVE_ALIGNMENT_VELOCITY_2026-10-28.md)、
  `scripts/s31d_curve_guard.py`、`tests/test_curve_velocity.py`（3 项：初速等于摆置自身导数、
  对齐不写方位进攻角坐标、力路线不加初速）。曲线相关测试 22 passed / 1 xfailed。
- 下一步（判据已写死）：把曲线**写进站表**（两侧同源、轨距 1.493、5 mm 站位，`y = s'^2/(2R)`），
  `curve_geometry = false`、座在直股段，另加"允许按站表对齐"的开关；判据 R=1100/80 km/h 跑满 ≥0.34 s、
  八轮 ∈[0.625,1.6]×、`|n_y/n_z| < 0.3`、直向与两条冻结基线逐位不变。

## 第 187 轮：站表路线加回帧的横向加速度——曲线量级第一次出现，但 0.60 s 仍在往外跑

- 起点：上一轮量清了两条路各缺一半（摆置路线要 21.8 kN 而轨顶只给 11.9 kN；站表路线侧向需求为零、
  `slip_lat` 逐位 0.0000）。这一轮保留站表 + `path` 的几何，把**这一帧自己的横向加速度**以虚设力加回去：
  `scripts/s32_curved_station_table.py --curvature-force` 只设 `run.curve_radius_m = 1100` 而
  `curve_geometry` 保持关闭 —— `evaluate` 据此加 `m v²/R`，曲率进蠕滑的 `±vκb` 上一轮已不再门控。
- **0.34 s：物理量级第一次出现**（`case_A_final_law` 的同源轨、R=1100 m、80 km/h、35 坐标）：
  座残差 1.022e-07 N、八轮 0.988–1.013×、侵入 65.47–65.50 µm、`slip_lat −0.0112…−0.0115 m/s`；
  运行 `numerically_checked`、1701 帧、**七门 7/7**、最大侵入 120.51 µm、峰值 1.03–1.37×。
  最后一帧 **`sum Fy −17 062.8 N` = 需求 21 842.4 N 的 78.1 %**、左右 **250 055 / 225 007 N**
  （转移 **+25 048 N = 5.2 % 轴重**，左轨更重 = 外轨）、轮对横移 **+7.35…+7.70 mm**、
  攻角 **−1.775…−2.028 mrad**。站表路线在"横向合力"这一列原来是 0。
- **0.60 s：不收敛，如实记账**：运行仍 `numerically_checked`、3001 帧、七门 7/7，但最大侵入到
  **276.26 µm**、峰值到 **2.04×**（`axle2_right 121 719 N`）；最后一帧 `sum Fy −32 997.1 N`
  （**151 %** 需求）、转移涨到 **+66 811 N**、`axle2_right` 侵入 **198.81 µm**、`lever_y +0.91327`
  （轮对中心 +0.753、轨顶带仅 ±0.036）——车轮已爬到**轨距角/肩部**；攻角 1.9 → 3.7 mrad，
  而按 `k_yaw = 1.96e6 N·m/rad` 与蠕滑摇头力矩 ≈1.0 kN·m 估的平衡攻角是 **0.5 mrad** 量级。
- 两个候选原因（都写进文档）：① 该车一次悬挂 **`c_y_n_s_m = 0`、`c_yaw_nm_s_rad = 0`**，横向与摇头
  两个模式唯一的耗散来自接触蠕滑；② `creep_stiffness_lateral_n = 5.0e5 N` 比真实 f22（5–8 MN）低一个
  数量级 —— **但这一条不能动**，那正是硬约束禁止的"提高接触刚度把失败变绿"。
- 新增 [`docs/CURVE_COROTATING_FRAME_2026-10-28.md`](CURVE_COROTATING_FRAME_2026-10-28.md)、
  `scripts/s32_curved_station_table.py`（站表曲线 + `path` + `--curvature-force` + 末帧逐轨表）。
- 下一轮判据先写死：0.34/0.60 s 两窗 `|sum Fy /(m v²/R)| ∈ [0.9,1.1]`、转移在 0.34→0.60 s 变化 <20 %、
  八轮 ∈[0.625,1.6]×、`|lever_y − ±0.753| < 10 mm`、七门 7/7、`κ=0` 逐位不变、冻结基线 `UNCHANGED`；
  做不到就如实降级为检出/定位。

## 第 188 轮：阻尼候选被实测排除；毛病在这张表的两条轨冠距 1.50667 m（应为 1.4930）

- `scripts/s32_curved_station_table.py` 新增 `--primary-damping C_Y C_YAW`（只改合成算例，基线保留 0，
  并把取值写进 `purpose_detail` 与文件名）。取 20 kN·s/m 与 20 kN·m·s/rad（真实转臂节点/横向减振器量级）
  跑 0.34 s 与 0.60 s：`sum Fy` 由 −32 997.1 N 变 **−37 689.5 N（172.6 % 需求）**、转移 66.8 → 52.5 kN、
  右轨侵入 198.81 → 187.76 µm、`lever_y` 仍到 +0.9666。**加阻尼不改变走向 ⇒ "没有阻尼"不是原因**。
- `scripts/s30c_crown_heights.py --case scratch/s32/case_curved_R1100_t30.json` 量到两张表的
  **冠距 1.50667 m 全程恒定、两侧冠高相等（dz = 0.00 µm）**，而车轮冠距是 **1.4930 m** —— 差 **13.67 mm**。
  根因与 B041 同族：`y_offset_m = ∓0.753` 钉的是**型面中点**，这套型面的冠部在自身中点外约 6.8 mm。
- 后果机理（写进文档 §7）：车轮落在轨冠内侧 6.8 mm 的斜面上，法向自带 ±0.0250 的向外分量；直线工况
  两侧互相抵消（`sum Fy` 逐位 0.0000），加曲线载荷后右四轨 `Fy` 合计 **−51.0 kN**、左四轨 **+13.3 kN**，
  净 **−37.7 kN 与虚设力同向** ⇒ "越压越出去"。
- 下一轮：建表按**冠部**对齐（`y_offset += 各自型面的冠部偏移`，目标冠距 1.4930 m，`s30c` 一行验收），
  再跑 0.34/0.60 s 对上一轮已写死的判据。这是数据修正，不是放宽容差、不是加大搜索窗、不是提高接触刚度。
- **更正（同轮）**：把表改成"冠距 1.4930 m"之后静平衡**不收敛**（`no seed converged; gtol`），
  因此 1.50667 m 的冠距不是缺陷而是**标定用的参考构型**（冻结 oracle 的 59 680.5769 N / 65.47 µm 就是在
  "车轮落在轨冠内侧 6.8 mm"这个位置量出来的，那条 ±0.0250 的法向倾角是它的组成部分）。
  脚本已 `git checkout` 回退、不留开关；剩余唯一候选改为"摇头平衡条件"，下一轮量需求力矩与可用蠕滑力矩。

## 第 189 轮：摇头平衡量到闭合，并否掉"把蠕滑系数标定上去"这条修法

- 新增 `scripts/s33_yaw_balance.py`：坐在曲线站表上带自转做**一次** `evaluate`，逐接触打
  `N / slip_x / Fx / slip_lat / Fy / lever_y / lever_z`，逐轮对打力偶 `−Σ(lever_y·Fx)`、`yaw` 与 `k_yaw·yaw`。
- 实测：**力偶 = `k_yaw·yaw` 逐个吻合到 1 %**（−0.98/−0.98、−1.00/−1.00、−1.02/−1.02、−1.02/−1.02 kN·m，
  yaw 0.50–0.52 mrad）。链条逐项闭合：`κvb = 0.0151 m/s` → `Fx = f11·Δv/v = 680 N` → 力偶 1.02 kN·m
  → `yaw = 1.02/1.96 = 0.52 mrad`；攻角只给 `f22·(vψ)/v = 260 N`，轨冠倾斜给 `N·n_y/n_z = 1 492 N`，
  单轮合计 1.75 kN（实测 1.75/1.76），每轮对净 0.53 kN 对需求 5 460 N —— **差 10 倍**。
- **否证**：`--creep-scale 10`（`f11 1e7`、`f22 5e6`，真实量级）后失稳**更早**（`x=22.0499317 m`，
  车体只走 2.05 m、t≈0.09 s，对照 4.53 m）⇒ 横向力不是不够而是**方向不对**，
  调大蠕滑增益只会让同向的错力来得更快。**"去标定 f22"这条路在动手前被实测关掉。**
- 新线索：轮对型面（282 点，y ∈ [−69.30, +70.07] mm）最大 z 落在**自己的横向边界**上、从那里 1 mm
  掉 4.11 mm（斜率 1.4，是轮缘/倒角侧而非 0.025 的踏面锥度），而八个接触的 `lever_z` **完全相同**
  （−0.42982 m）⇒ 接触落在等半径平段，横向移动不产生滚动半径差、轮对**无回正机制**。
  下一轮查型面装载（`y_sign`/`z_sign` 与前 70 mm 裁剪的语义），属几何装载问题。
- 文档 `docs/CURVE_YAW_BALANCE_2026-10-28.md`（九节，含第 2 节实测表、第 3 节闭合表、第 7 节否证、
  第 8 节锥度线索）。脚本 `s32` 新增 `--creep-scale`（只改合成算例，冻结算例不动）。

## 第 190 轮：锥度在（否掉我上一轮的猜想），但 21.8 kN 只能靠"单边承载 + 0.14 mm 侵入"换到

- 新增 `scripts/s34_wheel_taper.py`：从坐好的曲线站表出发，把整车整体横移 `dy`（垂向坐标不重解），
  逐接触读 `lever_z / N / Fy`，给出侧向力—位移特性表。
- **锥度在**：`lever_z` 左右反向变化约 **50 µm/mm**（2 mm 横移 → 96 µm 滚动半径差，锥度 0.048）。
  第 189 轮"接触落在等半径平段、没有回正机制"的推断**被实测否掉**（那是按型面最高点落在边界上推的）。
- 侧向特性回正且硬：中心附近 `dFy/dy ≈ 6 kN/mm`；21 842 N 需求对应约 **2.5 mm** 横移，
  但该点 `left N 793.5 kN / right 0`（单边承载 1.6 倍整车重）、侵入 **142.6 µm**。
- 结论：21.8 kN 在这个接触律下只能以"单边承载 + 0.14 mm 侵入"的形态出现 ⇒ 0.34 s 之后必然走向
  轨距角，不能作为可引用的曲线通过结果。**符号口径（哪侧是外轨、虚设力朝哪）本轮不判定**，
  表里只引用幅值与斜率，方向待独立测试。
- 文档 `docs/CURVE_YAW_BALANCE_2026-10-28.md` §10–§11。

## 第 191 轮：直向 + 随机抽速的波磨反演跑通并判定 —— 带限幅值命中 4/8，显式降级

- 新增 `scripts/s35_straight_random_speed.py`：直向路线（`case_A_final_law` 派生）、速度从
  **70–90 km/h** 用种子 20261028 抽出 **70.32 km/h**（这是短波算子按速度标定的唯一有效带，
  带外即外推）；四波长 0.10–0.30 m 混合、补片 42.5–45.5 m 只加左轨、幅值 0/0.1/0.2/0.3 mm 峰峰。
- 四个水平全部 `numerically_checked` **7/7**（最大侵入 65.47 / 138.26 / 168.80 / 236.33 µm）。
- **窗内该轮离轨帧比例 0.0 %**（四个水平），排除"轮子飞起造成非线性"这一解释。
- 响应与幅值不成比例且**逐带方向相反**：0.1004 m 增益 3.610 → 0.454（掉 8 倍）、
  0.1379 m 1.136 → 0.959、0.2073 m 0.302 → 0.457、0.2293 m 0.231 → 0.362。
- 判定：0.1 mm 标定 → 0.2 mm **3/4** 带 ≤2 dB、→ 0.3 mm **1/4**，合计 **4/8 = 50 %**；
  再用 0.1 与 0.3 的增益对数内插预测 0.2 mm，**1/4** —— 分段 `H(A)` 也被否掉。
  故第 6 门直向半边**显式降级**：可检出、可给量级，不可报 ±2 dB 带限幅值。
- 文档 `docs/STRAIGHT_RANDOM_SPEED_2026-10-28.md`（8 节，含排除表与下一步判据）。

## 第 192 轮：逐带幅值扫描 —— 非线性是逐带的，85–94 Hz 线性（1.007×）142–195 Hz 不是（5.3–7.6×）

- 新增 `scripts/s36b_contact_migration.py`：把同一根轨抬高/降低 ±150 µm 后重算接触，
  **`lever_y` 完全不动**（d lever_y/dz = 0.0000 m/m，跨度 0.0 µm），侵入量与抬高量 1:1
  （−150 µm → 0、+150 µm → 215.4 µm）。零偏移处与求解器 `evaluate` 的差是 12 µm / 19 nm。
  ⇒ **"接触点随波峰迁移"这条假设被否掉**。
- 预载实验设计被否（记入文档）：单侧抬高 85 µm 会让只解 z 的静平衡落到"站在一边"分支
  （2 837.5 N … 116 523.7 N）；两侧同时抬高则重新解回 65.47 µm。预载不是自由变量。
- 新增 `scripts/s36_single_component_sweep.py`（一次一个波长 × 三档幅值，12 次 0.30 s 运行，
  全部 `numerically_checked` 7/7）：增益跨度 **0.1004 m 7.558× / 0.1379 m 5.333× /
  0.2073 m 1.064× / 0.2293 m 1.007×**。
- 机理（观测到的相关性）：线性两带的平均侵入稳定在 62–72 µm，非线性两带升到 90–134 µm
  （静止 65.47 µm）——高频带里车轮跟不上波峰，被持续压住，`δ^1.5` 上侧被压缩。
- 逐带判定（0.1 mm 标定 → 预测 0.2/0.3 mm）：**2/4 带达标**（0.2073 m +0.06/+0.54 dB、
  0.2293 m +0.03/+0.06 dB），另两带 −5.35…−17.57 dB。合计 4/8，与混合激励的 4/8 相同，
  说明变的是**归因**：`s35` 里低频带的偏差来自高频带的**带间泄漏**，不是它们本身非线性。
- 协议规则（可执行）：定量只在"自身增益平"的带上给；混合激励必须先窄带分离再逐带投影。
- 顺手抓到自己脚本的一个坑：未窗化的记录经 `ShiftedSeries` 会在补片外被**钳位成端点常数**，
  0.2 mm 的单音因此把整车压到一侧、静平衡被判据拒绝；改成 `scaled_track(..., fade_m)` 后正常。
  这个坑第 182 轮记过一次，本轮在自己的新脚本里复发。
- 文档 `docs/SINGLE_BAND_SWEEP_2026-10-28.md`（6 节）。

## 第 193 轮：随机相位带限记录逐带反演 3/8 —— 限制从"非线性"换成"带内传递变化"

- 新增 `scripts/s37_random_spectrum_bands.py`：四个等对数带（0.1000–0.1316 / 0.1316–0.1732 /
  0.1732–0.2280 / 0.2280–0.3000 m），每带 24 个随机相位谐波、归一化到 **8 µm rms**；
  **标定种子 20261029（一次只开一个带），测试种子 20261030 / 20261031（四带同开）**，
  标定从不看测试波形。判据每带 ≤2 dB，报带命中率。
- 结果 **3/8**（`verdict: DEGRADED`）：0.1732–0.2280 m +0.74 / −0.76 dB，0.1000–0.1316 m
  −3.03 / +1.88 dB，0.1316–0.1732 m +2.44 / +3.73 dB，0.2280–0.3000 m **+2.44 / +2.29 dB**。
- **六次运行的平均侵入量 63.0–65.5 µm，全部在 65.47 µm 附近的允许区间内**，所以本轮失败
  **不是**第 192 轮那条 `δ^1.5` 非线性。
- 机理：第 192 轮的逐音增益在 85.2 → 94.2 Hz 之间就升 **29 %**（频率只变 10.5 %），一个三分之一
  倍频程带的带内传递足以变化几十个百分点；"带 rms ÷ 单一增益"只在两条记录谱形相同时无偏，
  两条随机实现谱形不同就带出同向偏置（+2.3…+2.4 dB）与散布（−3.03…+1.88 dB）。
- 下一步协议（判据先写）：**频率分辨反演** `r(f)=a(f)/H(f)`，判据仍为每带 ≤2 dB、同一批 8 次预测，
  且**不许换一个更有利的带**（带的划分已预注册）。
- 修掉自己一个度量缺陷：`band_rms` 归一化少了 `1/n`（正弦读成 17.5 倍）。因标定与复原同用该估算子、
  比例抵消，第 2 节数字不受影响；已改为 Hann 加窗 PSD 口径，两个正弦验证到 2.121 / 2.120（理论 2.1213）。
  宽带内容上该估算子仍低约 2 倍，写进 docstring，凡引用只用比值。
- 文档 `docs/RANDOM_SPECTRUM_BANDS_2026-10-28.md`（8 节）。

## 第 194 轮：频率分辨反演 6/8，标量 6/8 —— 真值口径比估算子更重要

- 新增 `scripts/s38_spectral_bands.py`：逐频点 `r(f) = a(f)/H(f)`，`H` 由标定运行做 H1 估计；
  **输入谱可复算** —— `applied_input()` 用 `window_factor` 重建前轴脚下真实激励，
  所以 `H` 是"响应/真实激励"而不是"响应/名义幅值"；标量估算子在**同一批频点**上重算，两个命中数可配对比较。
- 结果 **频率分辨 6/8，标量 6/8**（同一批 8 次预测）：频谱方法在本轮**没有带来改善**，
  而且在 0.2280–0.3000 m 上两个估算子同时失败、偏差几乎相同（+2.17 vs +2.37 dB）——共享输入实现的指纹。
- 真正结论：一条随机带限记录在**窗内只有 3–8 个频点**时，它自身该带 rms 与标称值可以差 **3.7 dB**
  （种子 20261030 带 3：12.20 µm vs 8.00 µm）。第 193 轮把名义 8.00 µm 当分母，把这部分**实现方差**
  算进了"传递误差"；所以 193 轮那句"带内传递变化导致偏置"**只对了一部分**，另一半是实现方差。
- 对判据的修正建议（写进文档）：第 6 门"带限幅值 ±2 dB"必须写明真值口径 ——
  **主判据用"该记录在该带的实际 rms"**（可复算、与轨道等级无关），另报"相对名义谱偏差"作工程指标。
- 频率分辨未改善的原因已量清：3–8 个频点 + 单次实现的 H1，输入能量低的频点放大噪声。下一轮 A 路 =
  逐频点**单音**标定（无噪声 `H`），24 次运行；判据 ≥7/8 且偏差符号不再随种子翻转。
- 文档 `docs/SPECTRAL_BANDS_2026-10-28.md`（7 节）。

## 第 195 轮：单音标定 3/8 —— 不是传递测不准，是多音不满足叠加

- 新增 `scripts/s39_tone_calibrated.py`：用**纯音逐点**标定 `H`（确定性输入、无实现噪声），
  其余全不动（同四带、同种子、同 2 dB 判据、同频点、真值取该记录自身带 rms）。25 次运行全部
  `numerically_checked`。判据运行前写死：≥7/8 且偏差符号不随种子翻转。
- 结果 **3/8**（第 194 轮 6/8）：8 个误差**全为负**（−1.44…−5.95 dB），符号不翻转 ⇒ 系统性"复原偏小"。
- 直接量到成因：`|H_tone| / |H_record|` 逐带中位 **1.555 / 1.142 / 1.676 / 1.776**
  （+3.84 / +1.15 / +4.49 / +4.99 dB），与复原偏差**逐项对应**、符号相反、量级一致。
- 振幅效应测掉：129.87 Hz 上纯音峰值 2.5 → 20 µm（8 倍），`|H|` 只变 **+0.17 %**
  （581 713 → 582 827），而**同一频点记录的 `H` 是 542 222（低 6.7 %）** ⇒ 差距不是振幅。
- 结论（写进文档）：**同一振幅水平下，多谐波记录每频点响应比纯音低 1–5 dB** ⇒ 线性叠加不成立，
  把"物理传递"当除数原理上不对；能用的算子是**用同类谱型记录标定的经验增益**，
  它把多音相互作用一并吸收（这就是第 194 轮 6/8 成立的原因）。
  这是"不存在常数 H"的第三个独立证据，而且是在**单一振幅**下复现的。
- 更正第 194 轮的说法："频谱方法输在 H1 噪声"只对一半 —— H1 噪声确实存在，但消除后结果**更差**，
  所以限制因素是**叠加假设**本身。
- 判据影响：第 6 门"±2 dB 带命中率"必须**同时声明标定谱类**；交付时 6/8（同类标定）与
  3/8（单音标定）**并列**报告。
- 文档 `docs/TONE_CALIBRATION_2026-10-28.md`（8 节）。

## 第 196 轮：带幅值必须带"标定谱类"，从约定变成构造约束

- `src/velch/inverse/verdict.py` 新增 `CALIBRATION_CLASS_FIELDS`、`AMPLITUDE_CLAIM_KEYS`、
  `calibration_class(...)` 与 `LayerResult` 构造期守卫：**状态 `passed` 且 `metrics` 出现带幅值声明键
  时，`calibration_class` 必须四字段齐全**，否则抛 `VerdictError`，文案引用第 195 轮的 1.2–5.0 dB。
  规则**单向** —— `failed` 的层允许不带谱类报数（降级路径不是声明，堵死只会逼人绕过）。
- 新增 `scripts/s40_band_verdict.py`：读第 194 轮（同类，6/8）与第 195 轮（单音，3/8）写出的两个 JSON，
  **不手抄数字**，组出带谱类的 `Verdict` 并落 `reports/inversion_synthetic_2026-10-28/verdict.json`
  + `bands.csv`（16 行 = 2 种子 × 4 带 × 2 估计子）。
  层状态：L0 passed、L1 skipped（单通道）、L2 passed、L3 passed（`band_hit_rate` 0.75 + 谱类）、
  L4 skipped（只有两个种子）、L5 failed（6/8 未达 8/8）；派生
  **`measurement_validation_status = not_evaluated`** —— 合成自洽性检验不对实测做声明，这是正确结果。
- 谱类实测值（不是设定值）：每带 rms **8.000 / 7.999 / 7.997 / 7.999 µm**；整条记录 rms
  **16.578 / 15.487 µm**（**8 µm 是每带不是整条**，前几轮措辞在此明确）；峰值 37.771 / 47.170 µm；
  峰值因数 **2.278 / 3.046**（归种子决定，**不属于谱类常量**，故谱类里存的是标定记录的实测值）。
- 新增 `tests/test_verdict_calibration_class.py` **9 项**（缺谱类被拒且文案点名缺哪几个字段、
  完整谱类可写入 JSON、部分谱类被拒、`failed` 层不受限、四类非法谱类值被拒、派生状态未被破坏）。
- 可复算性补丁：`reports/` 被 `.gitignore` 忽略、两个源 JSON 原本只在 `../scratch`，因此
  `reports/inversion_synthetic_2026-10-28/inputs/` 保留副本（`git add -f` 入库），`s40` 优先读 scratch、
  读不到读该副本；把 scratch 挪走后重跑输出逐项相同（已实测）。
- 文档 `docs/BAND_CLAIM_CLASS_2026-10-28.md`（6 节）。

## 第 197 轮：L4 从 skipped 变成实测留出覆盖率；实测判决不再只活在这台机器上

* `scripts/s41_coverage.py`：四个速度档是同一条轨道的四次独立测量，主导波磨波长属于轨道而不是某一趟，
  因此留出一趟就是真正的样本外检验。**判据在看结果之前写进 docstring**：区间取"一个新观测的预测区间"
  `mu ± k·s·sqrt(1+1/n_train)`（`mu`/`s` 只来自三个训练折，`s` 用 `ddof=1`），且必须
  **1σ 覆盖 ≥ 0.50、2σ 覆盖 = 1.00、任何折 |z| < 3**。
* 折表（估计量 `median_wavelength_in_band_mm`）：28.062（z **+0.71**）、28.427（**+1.31**）、
  26.265（**−1.31**）、26.630（**−0.71**）mm；**1σ 覆盖 0.50（正好压线）、2σ 1.00、max|z| 1.31 → PASSED**；
  二项尾概率 **P(X≤2)=0.379** —— 四折只能"证伪"、不能"证明标定"，故正确读法是"未被证伪，且 2σ 条款成立"。
* 敏感性判定估计量：同一批折在 `median_wavelength_mm`（全窗）上 **2σ 只有 0.75、max|z| = 3.06 → FAILED**。
  说明全窗中位数有一次 3.06σ 的胖尾（最强线偶尔落在波磨带外），**带内中位数才是可引用的速度无关观测量**。
* 第二个不确定度来源：同谱类两条记录之间每带误差差 **1.96 / 1.78 / 0.54 / 1.78 dB**，四带中三带 ≳1.8 dB，
  与整个 ±2 dB 预算同量级 ⇒ 要作 ±2 dB 声明必须跨多记录平均，而本数据集没有这么多记录（散布不是覆盖率，已注明）。
* 判决更新：`reports/inversion_measured_2026-10-28/verdict.json` 的 **L4 skipped → passed**（其余五层状态不变，
  L5 仍 failed 3/6），派生 **`measurement_validation_status` 仍为 `detection_only`**（加一层不确定度不授权幅值声明）。
* 可复算性问题（上一轮只补了合成侧）：`reports/` 被 git 忽略，实测产物从未入库，而 `s24_verdict.py` 从
  `F:\velch_tmp` 读四个输入 —— 干净检出后每层都会退回 `skipped`。现在 `reports/inversion_measured_2026-10-28/inputs/`
  存四个输入 + `detection.json`，`s24` **优先读入库副本、其次读 scratch**；证据字符串因此指向仓库内文件。
  **实测**：删掉 scratch 的 `coverage.json` 后重跑，`verdict.json` **逐字节相同**（sha256 `ae79a756…`）。
* 合成侧补上缺失的 `windows.csv`（8 行：种子 × 带；窗 **0.127985–0.281568 s**、42.5–45.5 m、保留 bin
  7/5/4/3、能量占比 0.99），两条路线的 `verdict.json + bands.csv + windows.csv` 至此齐全。
* 新增 `tests/test_coverage.py` **7 项**（预测区间宽度含"新观测"的 +1、`s` 用 `ddof=1`、z 的符号与两端的对称性、
  远折必挂 2σ、四折覆盖只能落在四分之一、退化训练集给 inf 而不是"零宽区间算覆盖"、判据三个条件缺一不可）。
* 文档 `docs/COVERAGE_HELDOUT_2026-10-28.md`（8 节）。

## 第 198 轮：五个随机抽样速度上跑同一套协议 —— 直向幅值能力只有"一个带"宽

* `scripts/s42_speed_sweep.py`：把第 194 轮整套协议（四个对数带、每带 24 谐波 8 µm rms、标定种子 20261029、
  测试种子 1030/1031、同一通道/补片/窗、判据 2 dB 对各自带内 rms）在**五个抽样速度**上重跑；速度由
  `default_rng(20261032).uniform(70, 90, 5)` **预注册抽取**（78.68 / 79.47 / 82.16 / 88.02 / 88.16 km/h），
  且**判为可定量需要 ≥7/8**（比第 194 轮自己的 6/8 更高，不是放宽）。实现直接调用 `s38_spectral_bands.main`
  并改其 `SPEED_KMH`，因此标定/窗/投影**只有一份实现**；先用 80 km/h 验证过补丁确实进到算例
  （`travel_speed_m_s = 22.222`）与窗（0.1125–0.2475 s）。
* 结果：**0/5 个速度达到 7/8**；各速度 hit 为 **5/8、6/8、6/8、6/8、6/8**；合计 **29/40（72.5 %）**。
  标量估计器同批为 6/8、6/8、6/8、3/8、3/8。
* **失败集中在一个带上**：0.1000–0.1316 **8/10**、0.1316–0.1732 **6/10**、0.1732–0.2280 **5/10**、
  0.2280–0.3000 **10/10**（该带十次全在 +1.19…+1.78 dB 内）。中间两带的偏差**全是正的 +2.0…+2.8 dB**，
  即**过复原**而不是丢失。
* 因此第 194 轮那句"6/8 进 2 dB"是**最好的一次**，不是典型值：五个抽样速度最高只到 6/8。正确表述改成
  **按带、按速度**：最宽带在所有抽样速度上可定量；中间两带在任何抽样速度上都不可定量且系统性高估。
* **否掉一个机制假设**：原以为高速下窗变短（0.2816 s → 0.2045 s）会减少保留 bin 数（更粗 FFT）。
  实测 bin 数为 **70.32 km/h 时 7/5/4/3，88.16 km/h 时 7/5/4/4** —— 基本不变，因为带边界按当地速度换成 Hz
  （∝v）而窗长 ∝1/v，乘积不变。故"格点变粗"被实测否掉，如实记录而不是删掉。
* 仍存的两个候选（本轮**没有分辨**）：同一空间带在高速下落到更高频段（0.1732–0.2280 m 从 379–483 Hz 移到
  477–608 Hz），而第 192 轮已实测**带内传递不平坦**（85.19→94.23 Hz 增益升 29 %）；以及每条记录自身的
  rms/峰值因数差异。要分辨需要在**同速度、更长补片**上重做（窗更长、谱类不变）。
* 两条本轮限制：抽到的 88.02 与 88.16 km/h 几乎重合（八条预测中六条相差 ≤0.03 dB），**有效速度数是 4**；
  抽样落在声明区间上半天（78.68–88.16），70–78 km/h 除第 194 轮那一个点外没有数据，>90 km/h 属外推（禁）。
* 新增 `tests/test_speed_sweep.py` **5 项**（抽取可复现且落在声明区间并按 0.01 取整、判据卡在 7/8 而非任意 hit 数、
  `summarise` 读两个种子共 8 条预测、per-band 计数跨所有速度累加、四个常量被钉住）。
* 文档 `docs/SPEED_SWEEP_2026-10-28.md`（8 节）；产物 `reports/inversion_synthetic_2026-10-28/speed_sweep.json`
  （含每条预测与预注册判据）。

## 第 199 轮（2026-10-28）曲线缺口是物理边界还是算法不够：把横向力能力量出来

* 用户问「曲线跑不了会不会是算法不够好」。把问题改写成可直接量的形式：**八轮仍在轨顶、载荷仍在验收带内时，
  接触最多能提供多少横向力**？需求 `m v²/R = 21 842.4 N`（R = 1100 m、80 km/h、48 654 kg）。
* 新增 `scripts/s43_running_equilibrium.py`：`--curvature-force` 的站位表工况（既有线路几何、又有体力项，
  且 `_placement_enabled` 为假所以不会被放置两次）；`solve_frame_equilibrium`（y/roll/yaw 入未知量，
  9 个种子，中心差分雅可比，SVD 取 cond）；`capability_sweep`（指定轮对横移 −4…+4 mm 与冲角 0/1/2 mrad，
  每个几何重解竖向行，读接触自己的净横向力）；`table` 打印每轨 `N / 比 / pen / lever_y / n_y:n_z / slip_lat / Fy`。
* **框架平衡不存在**：今天的座残差 1.022e-07 N、八轨 0.988–1.013×、`sum N` 1.000×，但**它不解的横向行最大 15 683.1 N**；
  把 y/roll/yaw 一起放开后 9 个种子全部 `xtol`，最好 `|r|max 8.4124e+03 N`（cond 1.505e+04），
  `sum Fy −1 391.3 N`（−6.4 % 需求），轮对 `y −0.822…−2.938 mm`、`yaw 0.455…0.832 mrad` → `NOT FOUND`。
* **验收带内的横向力上限 = 8 169.6 N = 需求的 37.4 %**（冲角 +2 mrad、横移 +0.5 mm、每轮 0.750–1.251、侵入 76.98 µm）；
  带内能出现的横移只有 −0.5 / 0 / +0.5 mm 三个点。
* **需求只在整侧卸载时出现**：+4 mm / +2 mrad 给 −22 276.4 N（102 %），但比值 **0.000–2.002**、
  因 `sum N` 仍为 1.000× 重量故 `4×0 + 4×2.002`，即四个轮子完全离轨、另四个承担两倍。
* 物理对照：真实载荷转移 `ΔP = F·h/b = 21 842.4×1.5/0.7465 ≈ 43.9 kN` → 0.63×…1.37×（**在带内**）；
  模型要到需求必须 ±59.66 kN，**是物理值的 2.7 倍**。带内单位载荷横向产出 1.7 %，需求要 4.6 %。
* 因此这一轮能说：曲线缺口**不是反演算法**（反演尚未开始）、**也不是**"把 `f22` 调大"（`--creep-scale 10` 更早失败），
  而是"无超高 R=1100 m / 80 km/h 上，‘八轮着地且在带内’与‘提供 21.8 kN’互斥"。
  **不能**说：接触平面倾角为什么固定在 ±0.0250——这必须用"不同横移下 `n_y/n_z` 与 `lever_y` 的演化"独立测量，
  若该斜率能把带内上限抬到 ≥1.0× 需求，则"带内不可能"被推翻，要改的是接触几何而不只是超高。
* 新增 `tests/test_curve_lateral_capability.py` **5 项**（需求值、座留下的横向残差、带内上限落在 30–45 %、
  到需求的点必须整侧卸载且另一侧 ≈2.00×、带内横移窗口 ≤1 mm），读取归档
  `reports/curve_capability_2026-10-28/capability.json`；结论一旦变化测试会红，不允许静默继承。
* 文档 `docs/CURVE_LATERAL_CAPABILITY_2026-10-28.md`（7 节，含预注册的下一步三行判据）。

## 第 200 轮（2026-10-28）倾角对横移不响应：横向力被"冻结的 2.5 %"封在 11.9 kN

* 接着第 199 轮 §5 留下的判据做独立测量：`scripts/s44_tilt_sensitivity.py`（横移 −3…+3 mm、0.25 mm 步长，
  每个几何重解竖向行保持一个车重，读 `n_y/n_z`、`lever_y`、净横向力；±2.25 mm 以外一侧失接触）。
* **倾角对横移完全不响应**：`d(n_y/n_z)/dy = +0.000 1/m`（拟合值 6.9e-16），`d(lever_y)/dy = 0.00000 m/m`；
  倾角只取 0.02182 / 0.02238 / 0.02326 / 0.02328 / 0.02463 / 0.02498 / 0.02547 这几个离散值，
  接触点在横向**跳格**。
* 由此得到比"带内 8.17 kN"更强的**结构上限**：`Fy ≤ W·tan τ = 477 295.7 × 0.02498 = 11 922 N`，
  而需求 21 842.4 N；要 21.8 kN 需要 `ΔN = 872 kN > W`，物理上不可能。
* 蠕滑通道同时量化：`slip_lat ≈ 11 mm/s` → `f22·slip/v ≈ 248 N/接触`；2 mrad 冲角 → `≈1 kN/接触`，
  八个接触约 8 kN——两条通道加起来仍不到需求的一半。
* 结论（三处独立数字支持）：**无超高时曲线只能靠轮缘，而轮缘被 `maximum_abs_contact_slope = 1.0` 挡住；
  正路是超高**（18 号道岔与真实曲线都有 107 mm 超高 = `h_th = 1.5v²/(gR)`）。缺的物理是"倾角随横移演化"，
  不是求解器精度。
* 文档 `docs/CURVE_LATERAL_CAPABILITY_2026-10-28.md` 新增 §6b（表）、§6c（结论）；归档
  `reports/curve_capability_2026-10-28/tilt_sensitivity.json`；`tests/test_curve_lateral_capability.py` 扩到 **8 项**。
* **第 200 轮补记（§6d/§6e）**：把座好的状态逐项拆开，得到两条新事实：
  ① 净横向力几乎**全部来自蠕滑**（`Ft·t_y` 左右同号 +247.3/+249.6 → 净 +497 N），法向项左右反号、
  净和只剩 +36.8 N，所以"倾角承担 54 %"只在单接触口径成立；
  ② `slip_lat = travel × q[yaw]` 被钉住（直接调 `evaluate_contact` 得 0.00000000，`evaluate` 内给
  −0.01115896，差值恰为 `22.222 × 0.000502`），**不是伪蠕滑，是座自己解的冲角**。
  由此给出系数关系 `F_lat ~ f11·f22·κ·b²·v/k_yaw ≈ 2.9 kN`（实测净 2.1 kN），
  并解释"两个系数一起乘 10 更早失败"（`f11` 也乘 10 → `yaw` 到 5 mrad → 转过量压轮缘）；
  按 Kalker 量级（`f11 ≈ 3.5e6 N`、`f22 ≈ 2.5e6 N`）该式给 ~70 kN 并被 `μN` 截住——
  预注册的下一个实验（需授权）是把两个系数各自回到 Kalker 量级、保留饱和模型。

## 第 201 轮（2026-10-28）两点接触：按 L12 补齐接触算法，并量清它对曲线是惰性的

- **改了什么**（三处结构性改动）：`contact_search.masked_sample_around(...)`（把主斑带压到 10 m
  以下再走同一条搜索——挖井而不是删除，保住 `np.interp` 的单调横坐标；空窗返回**同一对象**，
  这是"单斑逐位不变"的构造性保证）；`RunSettings` 新增 `contact_two_point=True`、
  `contact_two_point_exclusion_m=0.012`、`contact_two_point_min_slope=0.25`（三个都在
  `__post_init__` 校验）；`VehicleDynamics` 里主斑的 ~23 个搜索参数收进一个字典
  （`_contact_search_kwargs`），力律抽成 `_contact_response`，新增 `_second_contact`。
- **守卫按物理重推而不是放松**：陡法向不再立刻抛错，而是收集起来，只有当该接触**没有任何缓斑**
  时才抛，报文一字不差（`graph slope limit at …x=… m`）。依据是实测：轮缘根分担载荷时
  `n_y/n_z = 0.7216/0.6923`（斜率 1.04）是正常物理。
- **默认值是被测出来的**：开、排除窗 8 mm → **动了冻结 oracle**（`−0.00042` vs `−0.000463`）；
  量病因发现 `case_A_plain` 就座态每根轨裂成两斑——**41 400.5 N @ −0.75277（154.86 µm）**
  + **18 298.0 N @ −0.74471（89.85 µm）**，相距 **8.06 mm**，是**一个**赫兹斑被型面双曲率
  看成两个极值（胎面/轮缘相距约 55 mm）；只放距离（12 mm）仍裂（8×2，合并 59 698.462 N，
  竖向 −0.4496 mm）；再加坡度门后才**逐位**回到 59 680.5769 N / −0.4628 mm / 残差 1.88e-08。
- **测试 5 项**（`tests/test_two_point_contact.py`）：掩蔽机制（单调、长度、窗内压深 >5 m、
  窗外逐位、空窗同一对象）；关掉仍等于静止锚；**开与关 `assert_array_equal`**（状态与逐轨法向力，
  每轨 1 斑）；两个判据都在承重（出厂 1 斑 vs 排除窗 4 mm + 坡度 0.002 → 2 斑）；只剩一个陡斑时
  仍然抛守卫（横移 12 mm）。
- **对曲线的影响：惰性**。`--curvature-force --duration 0.34` 与上一轮**逐项相同**——
  就座 8/8（0.988–1.000×）、1701 帧 7/7、最大侵入 **120.51 µm**、末帧 `sum Fy −17 062.7 N`（−78.1 %）、
  转移 **+25 048 N**。原因可算：轮缘根在胎面以下约 **23 mm**，而全程最大侵入 0.12 mm（0.34 s）
  到 0.28 mm（0.60 s），差两个数量级 ⇒ 两点接触在这条曲线上永远不触发，**它不是缺的那条腿**。
- **顺带否掉一条猜测**：既然守卫由轮缘触发，"放宽守卫"看似能救曲线；实测守卫是在轮缘**已经顶上**
  之后才响的，放开它只是让那次非法接触进状态——这也正是项目规则禁止的做法，本轮没做。
- **仍待授权**：把 `f11`/`f22` 放回 Kalker 尺度（`3.5e6`/`2.5e6` N）并保留 `μN` 饱和，判据
  8/8 在带内、`sum Fy ≥ 0.9×` 需求、0.34 s 内 7/7 门；若仍不过，曲线项按"系数标定不足以救曲线"降级。
- 文档 `docs/TWO_POINT_CONTACT_2026-10-28.md`（七节，含三次测量的过程表与复算命令）。

## 第 202 轮（2026-10-28）离心力的符号：−78 % 变成 +69 %，并把"力不够"改写成"方向错"

- **两个带标记的诊断开关**（都不改冻结算例）：`s32_curved_station_table.py --creep-kalker`
  （L13 的 Kalker 尺度 `f11 = 3.5e6 N`、`f22 = 2.5e6 N`，写进 `purpose_detail` 与文件名 `_kalker`）、
  `--curve-sign ±1`；`RunSettings` 新增 `curve_lateral_sign: float = 1.0`（只接受 ±1），乘进右端的
  `m v²/R` 体力项与作用-反力门的 `curve_lateral_n` 台账，默认 `+1` ⇒ **既有算例逐位不变**
  （`freeze_baseline --check` = `UNCHANGED`，曲线测试 19 passed / 1 xfailed）。
- **四组实测**（R = 1100 m、80 km/h、0.34 s，只改符号与蠕滑尺度）：

  | 配置 | 结果 | 最大侵入 | 峰值 | 末帧 `sum Fy` |
  |---|---|---|---|---|
  | `+1`、原蠕滑 | 7/7 | 120.51 µm | 1.03–1.37× | **−17 062.7 N（−78.1 %）** |
  | `+1` + Kalker | `graph slope limit at axle2_right/right:main, x=42.3838731 m`（4.88 m，t ≈ 0.15 s） | — | — | — |
  | **`−1`、原蠕滑** | **7/7** | **102.79 µm** | **0.99–1.35×** | **+15 086.9 N（+69.1 %）** |
  | `−1` + Kalker | 7/7 | 381.56 µm | 1.06–1.48× | +14 280.1 N（+65.4 %） |

- **读法**：① 符号翻转把净横向力**方向**改对（−78.1 % → +69.1 %）；② 符号比系数重要——
  Kalker 尺度在错符号下**更早**失败（4.88 m），在正确符号下反而不如原系数（65.4 % vs 69.1 %，
  侵入 382 µm vs 103 µm），与此前 `--creep-scale 10` 更早失败（2.05 m vs 4.53 m）互证；
  ③ 符号可以由**几何**判定：本工况线形 `y = s²/(2R)` 向 +y 转弯 ⇒ 曲率中心在 +y、惯性力指 −y，
  而力路由的"外侧 = +y"把 `m v²/R` 加到 +y，在站表曲线上正好反了；
  `_curve_placement` 的 docstring 里"曲率中心在 −y 侧"与它自己的公式不自洽。
- **仍未过验收**：末帧 69.1 % < 90 %，且 0.60 s 时**过冲到 +157.2 %**（右侧卸载到 0.609×、0.666×，
  低于 0.625 下限）⇒ 没有稳定平衡，曲线项**保持降级**。
- **新登记、必须先查清（B045）**：曲线上大横移时右侧接触的 `lever_y` 达到 `+0.899`（0.34 s）与
  `+1.007`（0.60 s），而右轨在 37.6 m 处的站表偏移约 +0.779 m、轨头半宽 0.036 m ⇒ 可信区间
  0.743–0.815 m。**超出 84–228 mm 的接触点不可能在轨顶上**；在查清"它落在哪个表面"之前，
  不得引用这些帧的 8/8 与载荷比。判据已写进文档：`|lever_y|` 必须落在该里程的轨头区间内。
- 文档 `docs/CURVE_LATERAL_SIGN_2026-10-28.md`（六节：诊断开关、四次实测、为什么藏了这么久、
  当前状态含 B045、下一轮判据、复算命令）。

## 第 203 轮（2026-10-28）线形成为唯一事实源：曲率、离心力与超高从同一个对象导出

- 新模块 `src/velch/alignment.py`：`Alignment`（`curvature_1_per_m` 带符号、站表曲率、`curvature_at`、
  `lateral_force_n`、`has_line`、`legacy_equivalent_straight`）与 `alignment_for(case)`。约定只写一次：
  `κ > 0` ⇒ 中心在 +y ⇒ 惯性力 `−m v² κ`；外侧（−y）抬高 ⇒ 重力分量 `+m g sinθ`。
  参照量是 `contact.slip_x` 的 `−κ v lever_y`（它本来就是对的）。
- **离心力改为从线形导出**：`evaluate` 的体力项改为 `self.alignment.lateral_force_n(...)`（逐刚体按**自身里程**取曲率）；
  `curve_radius_m` 而无线形的旧算例走 `legacy_equivalent_straight`，算式与浮点次序原样保留 ⇒ 归档数字不动。
- **作用-反力门改为读"实际施加值"**：`evaluate` 记录 `curve_lateral_applied_n`，门读它。第一版门自己重算了
  一次，把曲率取在**里程 0**（线形从 30 m 才开始，那里是直线段）⇒ 台账读到 `0.000 N`，门误报失败；
  这与"同一件事写两遍"是同一类缺陷，已用注释写清。
- **超高手性修正（B046，当前惰性）**：几何路由原来把**内侧**轨抬高（实测 `axle*_right +54.799 mm`、
  `axle*_left −53.721 mm`，而 κ>0 时外侧是 −y），且车体侧滚 `+theta` 也向内侧倾。改为 `outer = "right" not in id`
  与 `roll −= theta`。几何路由仍在加载期拒绝 `curve_cant_m ≠ 0`，所以本轮没有任何数的改变。
- **实测**（R=1100 m、80 km/h、`--curvature-force`、符号由线形给出、无 `--curve-sign` 标志）：
  `seat 1.022e-07 N`、0.34 s **1701 帧 7/7 门**、最大侵入 **78.40 µm**（此前错符号 120.51 µm、
  手翻符号 102.79 µm）、峰值 0.99–1.36×、末帧 `sum Fy +11 691.2 N（+53.5 %）`、转移 `+30 152 N`。
  仍未达到 `|sum Fy| ≥ 0.9 × 需求` ⇒ **曲线项继续降级**；0.60 s 的判据是"不随时间增长"，正在复算。
- 物理层审查成文：`docs/ALIGNMENT_CONVENTIONS_2026-10-28.md`（九节：约定、B044、蠕滑同源、B046、
  力路由与线形路由的超高不能混用、无稳态的四组证据、Kalker 尺度下单斑力够用、七项确认无需改动、判据与复算）。
- 测试 `tests/test_alignment_conventions.py` **7 项**（线形曲率符号、惯性力背离中心、超高指向抬高轨、
  旧半径算式逐位相等、直线为零、按算例内容选线形、含 NaN 的站表被拒绝）。

### 第 204 轮：摇头刚度与 Kalker 蠕滑都不能让曲线稳定

第 203 轮把离心力符号改为由设计线形给出后，0.34 s 净横向力从 −78.1 % 变成 +53.5 %（侵入
120.51 → 78.40 µm），但 0.60 s 仍是 +135.3 %、峰值 1.90×。判据先定为
`|sum Fy(0.60 s)| / |sum Fy(0.34 s)| <= 1.2`，测三种配置：`k_yaw` ×2、×5 与 Kalker 蠕滑
（f11 3.5e6 / f22 2.5e6）。

实测比值：基准 2.53、×2 得 2.32、×5 得 2.47、Kalker 2.19 —— **一个都不稳定**。`k_yaw` 加到
5 倍只把 0.34 s 的净横向力动了 1.6 %（11 691.2 → 11 883.8 N），所以"摇头角是主因"被否掉；
Kalker 尺度是迄今最接近的一次（0.34 s 86.8 %、峰值 1.06–1.58× 全在带内），但 0.60 s 冲到
190.1 %、侵入 383→478 µm，越压越深。六次运行七门全过、没有一次撞斜率守卫 ⇒ 不是数值故障。

曲线项继续降级，理由收窄成一张逐项排除表（两点接触、蠕滑尺度、符号、摇头刚度、横向阻尼、
积分/搜索全部排除），剩下唯一未被否掉的是轮轨几何本身：带内横向力上限 8 169.6 N = 需求的
37.4 %，要拿 21.8 kN 必须外移 2.5 mm、而那里一侧承担 1.6 倍整车重量。

新增 `scripts/s45_yaw_stability.py`（只读日志的分析器）、`reports/curve_yaw_stability_2026-10-28/`、
`docs/CURVE_YAW_STABILITY_2026-10-28.md`、`tests/test_yaw_stability.py` 3 项；`s32` 新增
`--primary-yaw`。

### 第 205 轮：倾斜坐标系（超高）把需要的接触横向力压到带内，但稳态仍未建立

先说"倾斜坐标系"的实现口径：超高在本模型里的最小正确形式是**两轨高差 + 重力沿坡面分量**，
**轨道和车辆都不单独滚转**——只滚轨面，轨顶横移 `z·sinφ ≈ 5 mm`；只滚车轮，踏面接触点内移
`R·sinφ = 30.8 mm`；两者一起滚等于整个系统刚体旋转、接触几何不变。`s32` 新增 `--cant` 只做前两件。

特征值试验（`scripts/s46_hunting_stability.py`，座实状态线性化，8 个配置）：确实存在一个
**7.17 Hz 的轮对摇头/横移模态**，冻结蠕滑 `Re = +0.0009 1/s`、Kalker `+0.0211 1/s`（时间常数 47 s，
0.60 s 内只放大 1.013 倍）；一旦给摇头阻尼，`Re` 归零，剩下的最大实部是 **0.00 Hz 的刚性模态**。
所以 53 % → 190 % 的增长**不是颤振**，是"外力不平衡 + 横向无静态回复项"的刚性漂移。

超高把收支改过来：R=1100 m、80 km/h 下平衡超高约 68.6 mm，`cant=0.060 m` 把**需要接触提供的**
横向力从 21 842.4 N 压到 **2 662 N**（带内上限 8 169.6 N 的 32.6 %）。实测：

| cant | 需要接触力 | 0.34 s | 0.60 s | 0.60 s 峰值 | 1.0 s 峰值 |
|---|---|---|---|---|---|
| 0 | +21 842.4 N | +11 691.2（53 %） | +29 544.4（135 %） | 0.99–1.90× | — |
| 0.107（100 km/h 平衡，过超高） | +12 376 N | −9 211.2（74 %） | −18 868.3（152 %） | 1.03–1.75× | — |
| **0.060（≈80 km/h 平衡）** | **+2 662 N** | +351.9（13 %） | +4 093.5（154 %） | **0.99–1.39×** | **1.10–1.99×** |

`cant=0.060` 的 0.34/0.60 s 是曲线第一次八轮全在 [0.625,1.6] 带内；但 1.0 s 的
`transfer +152 849 N`、`axle1_left 1.99×` 说明载荷转移没停——**0.60 s 的带内是过渡过程的一瞬，
不能当稳态发布**。曲线项继续降级，但降级理由已经从"缺哪一项"变成"缺横向静态回复"。

新增 `scripts/s46_hunting_stability.py`、`docs/CURVE_TILTED_FRAME_2026-10-28.md`、
`tests/test_hunting_stability.py` 4 项、`s32 --cant`。

### 第 206 轮：横向回复刚度——不是"没有回复"，而是硬了 927 倍（B047）

第 205 轮把 1.0 s 的越界归因于"整车横向没有静态回复项"。那是一个**假设**，本轮把它写成预注册判据
再量：`RESTORING BLIND`（`k_force < 0.2·k_grav`）/ `RESTORING PRESENT`（0.5–2×）/ `RESTORING STIFF`（>2×）。

`scripts/s48_lateral_restoring.py` 在座实状态上把整车横移 −2…+2 mm，每个点只重解竖向行
（所以 `ΣN ≡ 1.000×` 车重），读 `ΣFy`、`M_yaw`、左右载荷差与两轮滚动半径差：

| 偏移 | ΣFy (N) | 转移 (N) | r_L−r_R (µm) |
|---|---|---|---|
| −2.0 mm | +12 472.5 | +453 284.2 | +95.6 |
| −0.5 mm | +4 471.4 | +122 028.5 | +15.7 |
| **0** | **+2 090.7** | **+2 581.6** | 0.0 |
| +0.5 mm | −296.7 | −116 894.8 | −15.7 |
| +2.0 mm | −8 688.8 | −450 562.5 | −95.6 |

`k_force = +5 404.5 kN/m`、`k_yaw = +145.8 kN·m/m`、**`k_transfer = 239 712 kN/m = 240 kN/mm`**、
`λ_eff = +0.0210`（1:48）、`k_grav = W/4·λ/r = 5.83 kN/m` ⇒ **`k_force/k_grav = 927`，落在
`RESTORING STIFF`：回复存在、符号正确，但机制错了三个数量级**。细扫（±0.6 mm、0.1 mm 步）
`k_force +4 926.5`、`k_transfer +233 666`，转移随偏移连续单调、无跳变，所以不是接触分支跳变的假象。

它一次解释了三件事：① 第 204 轮的带内上限 8 169.6 N 就是 `0.0210·W = 10 023 N` 的 **81 %**
（两个独立测量互相解释）；② 第 205 轮 1.0 s 的 `+152 849 N` 转移只对应 **0.64 mm** 走位——
车没有跑掉，它走了不到一毫米就把一侧卸空；③ 需求 2 662 N 在 **−0.15 mm** 处即满足
（−0.2 mm：2 978.7 N、转移 40.9 kN、份额约 1.09×），所以带内稳态存在，但容许窗口只有 **±0.9 mm**。

**B047 登记**：横向定位由 65.47 µm 的 Hertz 压入深度配一个冻结的 1:48 接触角决定（240 kN/mm），
真实轮对由锥度 + 蠕滑定位（5.83 kN/m，软 927 倍）。它是第 203 轮"倾角冻结"的直接后果：
倾角不动 ⇒ 横向力只能借法向力再分配 ⇒ 刚度必然是 Hertz 量级。修法与 B045 同根。

新增 `scripts/s48_lateral_restoring.py`、`docs/CURVE_LATERAL_RESTORING_2026-10-28.md`、
`tests/test_lateral_restoring.py` 4 项（上限即转移界、超高把需求压到界内、927 倍、0.64 mm 走位）。

### 第 207 轮：降低值能当反演真值，但真值不在断面数据里

用户提出用**尖轨/心轨降低值**做零对照验证（零不平顺算例 → 反演 → 看能否还原设计降低值）。
这条思路成立，而且比 `.tre` 探针更硬：真值来自设计，不是我们写进去的波磨。本轮先把
"真值到底在不在数据里"量清楚（`scripts/s49_design_lowering.py`）。

两套设计集都在 `G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728\WRProfile-07(009)-1_18`：
`07(009)-*`（站位 40–153 mm）与 `CN18-*`（12.5–250 mm），五族断面（`zjg` 直尖轨、`qjg` 曲尖轨、
`qjbg` 曲基本轨、`zgyg` 翼轨、`cxg` 心轨）加一张「里程 → 断面文件」表，表尾还带角色切换
（`zjg_zgyg` 在 105 m 处指向 `zgyg-...-cxg-71.3.txt`）。

但**降低值不在断面里**：四族断面冠部与平轨之差只有 **−0.019 … +0.000 mm**（1001 点、y 步长
0.072 mm 的量级，是离散化噪声）。`CN18` 更直接——尖轨尖端 `CN18-jg-0` 是一片 **4.0 mm 宽的薄片**
（y −37.196…−33.209 mm），冠部 **+23.000 mm**，与基本轨 `CN18-qjbg-R` 的 **+23.000 mm** 完全齐平。

所以降低值是**装配时给薄片加的竖向偏移**，属设计表/铺设图，不在这批断面文件里。这带来一条
必须写清的分界：若降低值由我们按设计表写入算例，则它验证的是"转移链 + 估计器"（与 `.tre` 真值
同类）；若要它成为独立于我们输入的真值，必须先拿到那张设计表，而当前断面**恰好不含它**——
这一点对验证有利。

顺带查实一件更硬的事：`case_diverging_R1100.json` 的 19 001 个站位全部指向**同一个平轨断面**，
只有 `y_offset_m` 在变，所以**没有尖轨、没有心轨、没有翼轨，也没有任何竖向道岔几何**
（此前测到 `dz/ds ≡ 0` 不是 NaN 缺陷，是几何本来如此）。因此"反演降低值"目前连被反演的对象
都不存在，P1 的第一步是建几何，不是反演。

新增 `scripts/s49_design_lowering.py`、`docs/LOWERING_VALUE_TRUTH_2026-10-29.md`（含预注册判据：
定位 ≤ 5 m、幅值 ±2 dB、尖轨尖端与心轨鼻端不得互换、零对照落回本底、`freeze_baseline` UNCHANGED）。

### 第 208 轮：降低值的真值在轨道梁设计表里，并且它是一个锐利的载荷转移点

第 207 轮说「降低值不在数据里」，只对了一半，必须更正：**不在断面文件里，但在轨道梁初始
几何表里**（`Cal_RailBeam_230518.m`）。尖轨表 `InpPar.RailBeam.Pos_Z.R2_zjg` 是生效代码，
长心轨 `Pos_Z.R3` 是注释掉但有数。

| 特征 | 07(009) | CN18 |
|---|---|---|
| 尖轨尖端降低值 | 23.0 mm @ 50.000 m | **16.0 mm @ 50.485 m** |
| 尖轨归零里程 | 57.304 m | **55.913 m**（坡道长 5.428 m） |
| 长心轨尖端 | 16.0 mm @ 103.200 m | 理论 2.0 mm @ 104.379 m |
| 长心轨归零 | **104.425 m** | 105.153 m 仍 0.1 mm |
| 实测件（超差） | — | 尖轨 15.81/6.28/4.65/1.86/**1.76** mm；心轨 3.8/2.7/1.5 mm |

物理含义：16 mm 是冻结算例静侵入 65.47 µm 的 **244 倍**，所以降低值没降到 65 µm 以下时
**尖轨一点力都不承**；降到零的那一刻才开始承载。设计因此给出一个锐利的、由设计确定的
**载荷转移点**（CN18 尖轨 55.913 m、07(009) 心轨 104.425 m），而不是一条模糊的斜坡。
并且理论件与实测件**可区分**：实测件末端 residual 1.76 mm ⇒ **根本不转移**，中间站位
还差 1.9/1.85 mm（4.4→6.28、2.8→4.65）。这就是 P1 的实验。

频率也合适：5.428 m 坡道在 80 km/h 是 **4.09 Hz**（160 km/h 8.19、350 km/h 17.91），
属长波段——加速度反演最强处（20 m 带 0.0–1.0 %、闭环 1.20 %），幅值又是毫米级。

表示方式的差异写清了：SDITT 把降低值实现成 `RailBeam_Motion.Pos_Z/Vel_Z` 的竖向运动
（`Multi_Con_250812.m:805/810`），我们改用逐站 `z_offset` 的准静态几何（法向接触等价，
不含轨道梁柔性与惯性响应），并在文档里标明。

新增 `scripts/s50_design_lowering.py`（编码四张表 + 单调性校验 + 载荷转移点 + 频率换算）、
`docs/TURNOUT_LOWERING_DESIGN_2026-10-29.md`、`reports/turnout_lowering_2026-10-29/lowering.json`。
P1 判据据本轮真值收紧：转移点定位 **±3 m**（原 ±5 m）、中间站位幅值 **±2 dB**、
理论件与实测件的「转移 / 不转移」必须复现。仍缺的是算例几何（第 207 轮实测：
现有道岔算例只有一个平轨断面，无尖轨/心轨、无竖向几何）。

### 第 209 轮：降低值表的里程映射被测出来，不是假设的

P1 全靠一条映射（表里「距 FSR」= `里程 − 50 m`，且点名断面就站在该里程）。本轮测了它
（`tests/test_design_lowering.py` 5 项）：五个设计点的站表里程偏差 **≤ 0.004 m**；
设计宽度对实测横向带宽之差 **4.11 / 4.08 / 3.69 / 4.08 / 4.06 mm**（均值 4.07，即断面画出的
头两侧各约 2 mm 圆角）；五个断面冠部全部 23.000 mm。于是第 1 节的绝对里程可以直接进算例。

同轮把「锐利载荷转移」写成断言：CN18 尖轨 55.913 m、07(009) 尖轨 57.304 m、
07(009) 长心轨 104.425 m；且**实测件永不转移**（末端 residual 1.76 mm > 65.47 µm 静侵入）。

### 第 210 轮：图纸通道被许可阻断，记录清楚并给出两条解封路径

用户指出 07(009) 特征断面图纸目录（6 张 DWG）。本想作为降低值表的第三来源，实测三条路都不通：
`accoreconsole` 的 `_.SAVEAS`/`_.DXFOUT` 都挂在授权错误上（exit 124，无产出）；直接扫 DWG 二进制
找 GBK/UTF-16 的「降低」0 命中（R2018 后对象数据分段压缩）。解封方式：图形界面另存 DXF 2013
或打印 PDF（`ezdxf 1.4.5`/`pypdf 6.10.2` 已就绪），或直接抄表。P1 不依赖此步。

### 第 211 轮：P1 第一步——案例站表里没有降低值，但机制已就位

`scripts/s51_case_lowering.py` 从算例自己的站表读冠高：左轨 40–118 m 恒为 **+0.000 mm**、断面文件恒为
`Profile_Mileage_JBG.prr`；右轨 +0.072 mm（70 m 处 +0.134），断面文件随里程在基本轨/曲基本轨/曲尖轨/心轨之间切换。
站表条目实测无竖直偏移键，所以**设计降低值不在几何里**——切换的是“谁承担车轮”，不是“谁低多少”。

机制其实已有：`load_profile` 的 `z_offset_m` 在四个加载器里都透传，本轮补上 `simpack_case.py` 的冠高诊断函数。
实测把左模板全设 `z_offset_m=-0.005`，左四轨冠高恰好 −5.000 mm、右轨一位不动。
`tests/test_station_z_offset.py` 2 项钉住（冠高恰好动 5 mm；另一侧逐位不变）。下一步是“尖轨段双体”算例：
降低值只有在两条轨并存时才可观。

### 第 213 轮（2026-10-29）把降低值装进算例：双体尖轨区

* 新增 `scripts/s52_switch_two_body.py`：把发散侧站表改成**双体**（`right:stock` 16664 站 + `right:blade` 1996 站），
  基本轨体把 `qjg` 断面换回基本轨断面（保留各站自己的横向偏移），尖轨体按设计表逐站 `z_offset_m = -降低值`，
  并以 `s_lo_m`/`s_hi_m` 限在 60.95–70.92 m。装载走的既有 `rail_templates[i]["bodies"]` 路径，未改求解器。
* 校核：把两族断面各自的冠部数字化基准拟合掉（−0.061 mm）后，`(stock − blade) − 基准` 与设计表逐点差 **0.000 mm**。
  说明：该残差是构造性的，验证的是注入算术与站表落地，**不是**设计表本身——设计表是 P1 的真值。
* 新增 `tests/test_switch_two_body.py`（4 项，corpus 标记）：设计表数值、双体与区间有界、尖端低 22.5–23.5 mm 且远端归零并单调、
  基本轨体不再含 `qjg` 断面。
* 新增 `docs/SWITCH_TWO_BODY_2026-10-29.md`（5 节）：为什么双体是唯一合法表示、映射口径、校核表、边界、复算。
* 边界：**没有跑时程**——P1 的零不平顺运行要穿过 60.95–70.92 m，须在 50 m 附近起步，那里正是 B047/B045 未清的区间；
  尖轨形面仍是整体竖向偏移，没有做变截面。

### 第 214 轮（2026-10-29）双体尖轨区第一次通过 0.05 s

* 新增 `scripts/s53_switch_passage.py`：在双体算例上跑 0.05 s（座位 45 m、80 km/h、BDF + 解析雅可比）。
  实测 **101 帧、七门 7/7、最大穿透 124.83 µm、前轴 62.00 → 63.11 m**，即进入尖轨区 1.11 m 而车仍在走行面上；
  算例报 **12 个接触体**（8 根轨 + 右侧尖轨体），证明双体进了求解器。
* `docs/SWITCH_TWO_BODY_2026-10-29.md` 新增第 6 节（实测、能说/不能说、复算命令），并记录脚本里逐接触打印的
  API 错误（`contacts[-1]` 是单层字典）已在跑完后修正。
* 边界：0.05 s 只走 1.11 m，尖轨真正抬起承力要到约 68.5 m 之后；要量到那里需 ≥0.6 s，会穿过 B045/B047 区间，
  本轮不闯。

### 第 215 轮（2026-10-29）0.60 s 过不去：尖轨窄断面给不出纵向斜率

* 实测：`--duration 0.60` 在 `contact_search.py:685` 抛 `ProfileError: longitudinal profile derivative is
  undefined at the contact point`。定位：尖轨抬到与基本轨齐平（尖端后 7.304 m ≈ 68.9 m）后成为**候选接触体**，
  而它原带的是自己的 `qjg` 断面——窄条（尖端 4.0 mm 宽），相邻两站连共同横向覆盖都不足，纵向斜率无定义。
* 修法：尖轨体改用**基本轨断面 + 自己的横向偏移 + 设计降低值的竖向偏移**（降低值是高度差，与窄断面形状无关）。
  重建后 66.93 / 68.92 / 70.92 m 三处 gap 与设计表逐点差 0.000 mm，冠部基准差由 −0.061 mm 归零。
* 代价登记：尖轨真承力之后的接触几何不再是真尖轨头部（变截面未做），本轮能读的是"降低值何时被吃掉"。
* `docs/SWITCH_TWO_BODY_2026-10-29.md` 新增 §7–§9（故障、性质、修法、复算）。

### 第 216 轮（2026-10-29）修好窄断面之后 0.32 s 通过：前轴越过尖轨全高

* 尖轨体改用基本轨断面后，`--duration 0.32` 实测 **641 帧、七门 7/7、最大穿透 124.83 µm、前轴 62.00 → 69.11 m**，
  已越过"尖轨抬到全高"的 68.92 m ——降低值被吃掉的全过程都在这次运行里，且无门失败。
* 末帧：`axle1_right 47.38 kN (0.79×)`、`axle2_right 50.11 kN (0.84×)`、`axle3/4` 两侧 59.62–59.74 kN。
* 两条限制写进文档：**B045 仍在**（`axle1/2_right` 的 `lever_y` +0.910/+0.876 m，落在轨头外 95–160 mm，故这两轴读数
  不可引用）；打印按轨 id 合并了两体，**看不到尖轨/基本轨分担**。

### 第 220 轮（2026-10-29）：直向横向漂移的根因是 B047，不是座椅偏置

- `scripts/s72_straight_stock_baseline.py` 新增 `lateral.csv` 与 `lateral_start/last/drift` 汇总
  （此前只写 summary，漂移速率量不到）。
- 实测 40 → 50 m、0.45 s：四根轮对横向**起点全为 +0.0000 mm**，0.45 s 后漂移
  **−37.7657 / −21.3213 / +0.1107 / +0.5043 mm**（前转向架走、后转向架几乎不动）。
- 横向刚度实测（坐好后平移 `wheelset1` ±1/±2/±3 mm）：ΣFy 从 +705.2 kN 到 −564.3 kN，
  斜率 ≈ **−235 kN/mm**（物理值 0.2–0.3 kN/mm，差 ~900 倍，正是已登记的 **B047 927 倍**）；
  **±1 mm 就有一侧完全失去接触**，说明横向位移被映射成深度尺度变化。
- 诊断：把蠕滑改成 Kalker 量级（3.5e6/2.5e6）后撞门**更早**（54.331 m vs 67.030 m），
  证明蠕滑刚度不是病因，只是放大 B047 的后果。新增 `s73 --creep-kalker`（诊断专用、写进 `purpose_detail`）。
- 结论：尖轨区与心轨区的降低值反演都要等 B047 定位清楚。下一步判据：`dΣFy/dy` 落到 0.05–0.5 kN/mm、
  ±3 mm 内不出现单侧掉接触，再到 0.45 s 要求漂移 < 1 mm。
- 文档：`docs/STRAIGHT_LATERAL_B047_2026-10-29.md`。冻结物理、七门、DOP853 逐位等价不受影响。

## 第 219 轮（2026-10-29）：直向刚性算例的四个缺陷，以及 0.45 s / 7 门的第一次干净运行

- 新增 `scripts/s72_straight_stock_baseline.py`（对任意刚性道岔算例跑基线并打印逐轨份额）与
  `scripts/s73_straight_pair.py`（把左右两侧拼成**同一根直向**，保留尖轨体）。
- 四个缺陷逐一实测：① 原算例是侧向道岔（40 m 处轨距中心偏 0.475 m）→ 4/8；② 左右断面族不同源
  （横向跨度 1.4994 vs 1.5376 m）→ 拼接点 `ProfileError: adjacent profiles have no lateral overlap`、
  刀尖区 `graph slope limit`（`pen 3143.53 µm、lever_y +0.71535、slope 1.274`）；③ 左右轨顶高差 72 µm
  → 载荷 1.29×/0.71×；④ `s73` 缓存键只含文件名 → 镜像后的左断面取到未镜像的轨顶偏移，右轨顶被放到
  +0.76713 m（应 +0.75325，差 13.88 mm = 2×6.94 mm）。缓存键改为 `(file, y_sign, z_sign, format)`。
- 修完后的第一次干净运行（40 → 50 m，0.45 s，80 km/h）：35 坐标、8 轨、静平衡残差 1.492e-08 N、
  **七门 7/7**、八轮末帧 **0.979–1.051×**、单斑峰值 65.458–65.720 kN、里程 10.000 m。
- 未解决：80 / 95 / 105 m 起跑均在静平衡报 `xtol`（几何与 40 m 相同，未定位）；尖轨区斜率门未重测；
  心轨区 103.28–116.44 m 需从 40 m 跑 3.0 s 才到。
- 文档：`docs/STRAIGHT_PAIR_2026-10-29.md`。冻结物理、七门、DOP853 逐位等价不受影响。

## 第 218 轮（2026-10-29）：降低值旋钮可用，两条刚性路线卡在同一处站表拼接

- `z_offset_m` 是「受伤断面」的合法入口（`profiles.py:120` 逐点相加，`vehicle.py:394` 从站点读取），
  新增 `tests/test_lowering_offset.py` 三项：+22.6 mm 逐点可加（atol 1e-12）、不动横向坐标、
  不给偏置时与显式 0 逐位相同。守卫理由：键名写错会被静默忽略，症状是读数不变（仓库已有四次同类事故）。
- 读出算例真实结构：`rail_templates` → `stations{s_m, profile}`；left 19001 站 30.0–125.0 m，
  right 16664 站 30.0–116.59 m 并带 `event_branches`——心轨区 103.28–116.44 m 确实在算例里。
- 两条刚性路线各撞一处、同一家族：起点 30 m 跑到刀尖区 53.7 m 报 `graph slope limit`
  （`pen 3143.53 µm、lever_y +0.71535、slope 1.274`）；起点 95 m（轴在 105/102.5/87.5/85 m）
  在静平衡阶段报 `ProfileError: adjacent profiles have no lateral overlap`。
  两者都是「不同来源、不同横向跨度的断面被拼在一根站表上」，修法是补齐共同横向区间 + 显式过渡插值，
  判据为 `dz_ds` 在 100–118 m 全程有限、起点 95 m 静平衡残差 < 1e-5 N、八轮 0.625–1.6× 均载。
- 已站住的：柔性路线上尖轨 23.0 mm / 心轨 23.0 mm（真值 22.6，−1.8 %），`+0.268 mm` 剖面偏置
  → `+0.268 mm` 载荷等效（1.01 %）。
- 文档：`docs/LOWERING_KNOB_2026-10-29.md`。冻结基线、七门、DOP853 逐位等价不受影响。

## 第 217 轮（2026-10-29）B045 撤回：判据拿了另一段里程的轨头宽

* 新增 `scripts/s54_contact_locus.py`（只读几何，不跑仿真）：按**每根轴自己的里程**采样对应轨的轨头带，
  与 `lever_y` 比较。实测 8 个接触**全部在轨头内**：69.11 m 处右轨头 +0.8949…+0.9321 m（`lever_y` +0.91038）、
  49.11 m 处 +0.7371…+0.7743 m（+0.75252）。
* 结论：`lever_y` 是**绝对横坐标**，第 216 轮用直线段的 0.743–0.815 m 当判据属误报；**B045 撤回**，
  那次 0.32 s 运行是可信的八轮读数，前两轴 0.79×/0.84× 就是曲线载荷转移。
* 新判据写死：`lever_y` 必须与**同里程、同轨**的轨头带比较。

### 第 218 轮（2026-10-29）P1 第一组数字：尖轨承力起始里程误差 5 mm

* 新增默认关闭的观测钩子 `velch.vehicle_solver.BODY_CONTACT_HOOK`（每轨每次求值回调 `(t, rail_id, ((body_id, N), …))`），
  用来读两体分担；`tests/test_body_contact_hook.py` 3 项钉住"默认为 None""不挂钩子行为不变""各体之和 = 合并响应"。
* 新增 `scripts/s55_blade_onset.py`：按设计降低值斜率预注册判据 **68.16 ± 0.20 m**，实测尖轨首次承力
  **68.152 m（误差 −0.005 m，PASS）**，此前 67.79 m 恒为 0，接触后 0.5 m 内抬到约 24 kN（≈0.4× 均分）。
* 681 帧、七门 7/7。边界：仅前轴右侧；尖轨变截面未做，接触斑形状不可引用。

### 第 219 轮（2026-10-29）撤回第 218 轮的判据通过：尖轨起始点依赖进场路径

* 同一算例换进场点复测，保持判据 68.16 ± 0.20 m：52 m 进场 → 68.152 m（0.065 kN）；62 m（至 68.67 m）、
  66.5 m @100 km/h（至 70.40 m）、66.5 m @80 km/h（至 68.94 m）**全部无接触**。
* 结论：`§11` 的 −5 mm 只在一条进场轨迹上成立，**不能算判据通过**；真正判据需含轮对横移 `q[y]`（二维判据）。
* 预注册下一步：把 q[y] 代入二维判据做零假设检验；不通过则必须先做**尖轨变截面**。

### 第 220 轮（2026-10-29）二维判据实测：零横移 68.80 m，几何式偏早 0.64 m

* 新增 `scripts/s57_blade_gap_vs_lateral.py`：不积分轨迹，把 axle1 放到指定里程、`wheelset1` 横移 −2…+2 mm，
  读尖轨体法向力，得到 (里程, 横移) 二维边界表。
* 实测：零横移 **68.80 m（1.70 kN）**；+0.5 mm 68.60；+1.0 mm 68.40（1.90 kN）；+2.0 mm 68.40（16.32 kN）；
  负横移始终为 0。几何式给的 68.158 m **偏早 0.64 m**（对应轮面高差 ≈0.32 mm）。
* 68.20 m 处即使 +2.0 mm 仍为 0，所以轨迹上的 68.152 m 首触**是动态闭合，不是几何接触**；第 218 轮的
  "PASS" 至此被两处独立测量否掉。P1 判据改为含 `q[y]`、竖向速度与轨下沉的三项式，几何项已标定。

### 第 221 轮（2026-10-29）尖轨改用真实设计断面：几何 0.000 mm，分担比仍不可引用

* `scripts/s52_switch_two_body.py` 新增 `--real-sections`（不再把尖轨断面复制成基本轨）与
  `--blade-datum-mm`（两族断面 z 采样极点差 **−0.061 mm**，不抵消会让尖轨高 0.060 mm）。
* 先在 B041 轨距修正算例（`--gauge 1.50649`）上建表：8 个站位 `(gap − datum) − design` 全部 **0.000 mm**，
  60.95 m 处 23.000 mm，68.92 m 处 −0.000 mm —— 软件第一次拥有真实下压几何。
* 第 215 轮那个 `ProfileError` 的真因是断面缺横向基准，不是"切片太窄"；`--real-sections` 用
  `y_offset_m` 统一左缘后，窄切片可正常求导。
* 载入：51 坐标 / 8 轨 / **10 体**，静平衡 `8.282e-08 N`；0.10 s（80 km/h、`align_to_track`、座 45）
  **7/7 门全过**，t ≥ 0.01 s 各轮 56–93 kN。
* **但第 0 帧** `axle1_right` 报 **1879.34 kN（31.5×）**、另一条右轨 758.49 kN，从 t = 0.01 s 起才回到物理量级
  → 首帧状态与几何不同步，**尖轨分担比与首触里程暂不可引用**；第 218/220 轮的 68.152 / 68.80 m 建立在
  断面被替代的算例上，正式判定待首帧修好后在真实断面上重测。
* 文档 `docs/SWITCH_TWO_BODY_2026-10-29.md` §15。冻结物理与基线未动。

### 第 222 轮（2026-10-29）第 0 帧缺陷定位：对齐对站表道岔从不生效

* 根因：`_align_to_track_frame` 的门是 `_placement_enabled(run)`，而道岔的 `curve_radius_m` 为空 → 门恒假，
  `align_to_track` 整段 no-op。实测座后 `wheelset1 y = 0.000 mm`，而中心线在 55 / 65 / 66 m 处为
  **+0.0221 / +0.0947 / +0.1083 m**。
* 首帧 1879 kN 由此解释：车轮在 +0.7465 m，设计线已在 +0.0947 m → 压在轨距面而非轨顶。
* 试把门放宽为"采样中心线位移 > 1 mm"：静平衡仍 `8.175e-08 N`，积分**第一步**即
  `graph slope limit at axle1_right/right:stock, x=65.0084398 m` → **只做横向平移不够**：同构架两轴
  相距 10 m，设计线相差 **72.6 mm**，而站表把曲线编码成"断面横移、断面不转"。
* 改动已回退，工作区不留未验证行为；下一步单一实验：对齐态下打印 65.008 m 的 `wheel_y` / 轨冠 y /
  `n_y/n_z`，判定是放置不足还是断面未随切线旋转。文档 `docs/SWITCH_TWO_BODY_2026-10-29.md` §16。

### 第 223 轮（2026-10-29）轮轨横向基准差 13.8 mm：此前"跑通"是在轨距角上跑

* 实测冠距 **1.52059 m** 对轮平面距 **1.49300 m** → 每侧轨冠在轮平面外侧 **13.8 mm**（冠距处处常数；
  55 m 处 1.54659，是断面族切换留下的 +26 mm 跳变）。
* 对齐后车轮中心 +0.841220 m vs 右轨冠 +0.854861 m → **内移 13.6 mm**；第 0 帧
  `axle1_right` 两体 **28 255 / 28 013 kN**、侵入 13 157 / 12 560 µm、`n_y/n_z` **+0.279 / +0.248**
  → 轨距角接触，不是轨顶。第 0 帧 1879 kN 与 B045「`lever_y` 越出轨头」是同一件事。
* 把冠距修到 1.49366（`--gauge 1.47956`）：几何仍 0.000 mm，但静平衡 **`gtol` 不收敛** ——
  说明此前 7/7 的收敛依赖的正是轨距角那个陡峭支撑。
* 结论：横向基准与静平衡未知量必须一起改。下一步：冠距 1.493 算例上把未知量扩到 **z + 轮对 roll**，
  判据残差 < 1e-5 N、8 轮着地、0.625–1.6×、`lever_y` 在轨头内。文档 §17。

### 第 224 轮（2026-10-29）轨距只在三段正确：50–62 m 鼓出 26–62 mm，静平衡无法重建

* 逐站冠距（冠基准修正后）：35 / 45 / 47.5 / 50 / 65 m 均为 **1.4937**（轮平面 1.4930），但 **55 m 1.5197（+26 mm）、
  60 m 1.5557（+62 mm）** —— 这一段是站表从基本轨切到成型尖轨断面的走廊，两族断面各自带横向基准。
* 新增 `scripts/s61_crown_seat.py`：未知量 **z + 各轮对 roll（19 个）**，从**对齐后**状态出发、斜面试探记势垒；
  三个种子全部 **|r| = 1.000e+00（势垒）**，最好解仍在 `axle3_left/left:main, x=47.5 m` 触 `graph slope limit`。
* 结论：**不是缺一个未知量，而是站表还没有统一轨距/基准**。P1 的下一步是把 50–62 m 的鼓形消掉
  （每条轨全部站位按**冠**对齐到 1.4930，且不引入台阶），判据：35–75 m 每 0.5 m 冠距 ±0.5 mm、
  `dz_ds`/`dy` 无跳变、冻结基线与直向算例逐位不变。文档 §18。

### 第 225 轮 · 降低值反演：尖轨能定位不可定量，心轨降低值本来就在几何里

* **尖轨（两体区，真实图纸断面，设计 23 mm @ 尖端 → 0 @ 7.304 m）**：把设计降低值整体乘 k，
  测首触里程（`scripts/s55_blade_onset.py`，判据 k=1 为 68.16 m ± 0.20 m）：
  k=0.80 → **68.046 m**、k=1.00 → **68.152 m**、k=1.20 → **68.114 m**，误差 −0.112 / −0.070 / −0.043 m，
  三次都在判据带内。但 k 变 ±20 % 只让首触里程动 **0.05–0.11 m**（每 10 % ≈ 0.05 m），
  而 2 ms 输出步长在 22.22 m/s 下就是 **0.044 m** —— **一个输出步长 ≈ 10 % 的降低值**；
  且 68.25 m 处尖轨分担只从 41.94 变到 42.75 kN（**< 2 %**），68.69 m 处为 42.73 / 42.79 / 42.76 kN。
  机理：尖轨落座后分担比由**刚度分配**决定，与它低了多少无关。
  所以**零点位置可反演（±0.1 m），幅值不可辨识（只能给量级）**。
* **心轨（103.200–104.600 m）**：算例**自身站表**已带设计降低值。新增
  `scripts/s63_frog_body.py --read-back` 逐站对比 46 站：**最大偏差 0.205 mm、rms 0.072 mm**
  （103.280 m 冠面 −13.696 mm vs 设计 −13.5；104.425 m −0.003 vs 0.000）→
  第 208 轮"降低值不在断面里"只对**尖轨区**成立，不适用于辙叉区；
  再叠一个按设计降低的心轨体就是**同一量加两遍**（`build()` 仅留作该结论的证据）。
* 文档 `docs/LOWERING_INVERSION_2026-10-29.md`（两部件对照表 + 四条边界 + 复算命令）。

### 第 226 轮 · 断面级数值对照：心轨 0.268 mm 最大、尖轨降低值整段缺失

* 按用户要求给出**逐断面**的数值对照（同一里程的设计降低值 vs 反演/读回值），三个来源都用同一基准
  （基本轨冠面 +0.072 mm）：
  * **心轨**（几何读回，5 个设计断面）：103.280 → 设计 13.500 / 读回 **13.768**（差 **+0.268**）；
    103.500 → 6.743 / 6.531（−0.212）；104.000 → 2.007 / 2.086（+0.079）；104.200 → 1.043 / 1.062（+0.019）；
    104.425 → 0.000 / 0.075（+0.075）。**均值 +0.046 mm、最大 0.268 mm**；46 站 rms **0.072 mm**。
  * **尖轨**（算例几何 vs 设计表）：算例在 50.6–60.9 m **没有尖轨断面**（那一带是曲基本轨 `qjbg`），
    所以差值等于设计降低值本身：51.075 → −**11.634**；52.575 → −4.495；54.575 → −1.854；56.575 → −0.496；
    58.500/59.500 → 0.000；60.962 → −0.061（qjg-72 高出基本轨 62 µm 的那一步）。
  * **尖轨动态反演**：反演值 = **23 mm × (1 − 0.03 ± 0.26) = 22.3 ± 6.0 mm**，设计 23 mm 落在区间内
    ——即“能反演但区间宽度 26 % ”，不能作定量结论。
* **修正**：本文件第一版把 k=1.00 的误差写成 −0.070 m（对错参考里程 68.222 m），三个 k 共用
  68.157 m 参考后是 **−0.005 m**；首触里程三个值只铺开 0.106 m 且**非单调**，反而**加强**
  “幅值不可辨识”的结论。

### 第 221 轮 — B047 的机制不在律、不在蠕滑量级，在横向基准

同一个对称就位的直向成对算例，`strip_integral` 与冻结点接触律在 0.20 s 内给出 **−5.295 / −5.261 mm**（差 0.03 mm），所以不是条带积分的问题。拉到 0.60 s：冻结蠕滑 **−71.201 mm**（trend −118.7 mm/s，wheelset2 −46.505）、**七门仍 7/7**；Kalker 量级 **0.29 s 撞门**（`x=56.463171 m`，走了 6.46 m）。两条读数把结论固定为：单调漂移而非界振荡、七门看不见横向走位、放大蠕滑只会更快。

靶点因此落在横向基准：`z_loaded = z_raw − 0.4411`，滚动圆在 `z_raw = +0.0111`，而左右两侧被安置在比踏面深 3.6 mm 的轮缘根上，左右滚动半径不等 → 恒定差动纵蠕滑 → 恒定摇头力矩 → 恒定横向速度。

新增 `scripts/s76_normal_law.py`、`scripts/s76b_lateral_hold.py`、`scripts/s77_kalker_drift.py`；`docs/STRAIGHT_LATERAL_B047_2026-10-29.md` 增 §三（含先写死的三条判据）。冻结物理未动。

### 第 222 轮 — 先把道岔廓形认清楚：命名、组合断面、以及从图纸读出的降低值

两个来源文件夹里一个 `.prr` 就是一个断面，文件名即断面名（拼音首字母）：`JBG` 基本轨、`JG_XX` 尖轨（基本轨+尖轨组合）、`XG_XX` 心轨、`YG_XX` 翼轨、`YG_DD_XG_DD` 组合、`R/L<里程>` 单根轨；侧向另有 `CB…CF / DB…DE / JB…JF / Z / ZS`。组合断面被画成一条连续上表面，中间是 V 形轮缘槽，z 向下为正。

从两个 crown 的高差直接读出设计降低值：直向 `JG_CC_1 +14.000 → DD 8.489 → EE 3.429 → FF 1.401 → GG 0.308 → JJ 0.124 → KK 0.000 mm`；侧向 `JB 14.040 → JC 3.078 → JD 0.522 → JE 0.015 mm`。**最大降低值是 14.000 mm，不是此前假定的 23 mm**，这成为 P1 的独立真值（图纸几何，不是我们写进去的不平顺）。侧向 `CB…CF` 那恒定的 **11.968 mm 是轮缘槽深**，与降低值不是一件事。

限制：侧向断面只有 **247 点**（直向 1999），0.42 mm 一点，接触曲率精度受限，必须写成已知误差源。

新增 `scripts/s78_profile_atlas.py`、`docs/TURNOUT_PROFILE_ATLAS_2026-10-30.md`。冻结物理未动。

### 第 223 轮 — 组合断面怎么进模型：文献给的三条路，以及我们该走哪一条

查了 L14（新增）：① 基本轨与尖轨之间存在**竖向相对运动**且改变接触力学（CN60-1100-1:18 为对象）；② 转换区的**反向横向接触力是运动学现象**；③ 变截面曲梁是另一条路（Abaqus 直向模型即如此）。结论：按 V 形槽把组合断面**劈成两条各自独立的轨体**，降低值取两 crown 高差（14.000 → 0 mm），不写 z 偏移表；不得把两根轨并成一根来绕过接触转移。
### 第 224 轮 — 学会 SDITT 怎么用这套道岔轨道：三条独立轨线，降低值长在断面里

`Bezier_InterpProfile_210620.m` 读三张里程表（曲基本轨 76 站 / 直尖轨+直翼轨 161 站 / 长心轨 68 站，侧向另有曲尖轨+曲翼轨 75 站），每条线在「里程 × 横向」两个方向 Bezier 插值成 `Profile_Bezier`，接触**按线独立**求、取最深 ⇒ 轮载转移自然发生。断面是单根轨（1001 点，两列，z 向下为正、轨顶 0），后缀即宽度 mm。

实测降低值在断面里：`zjg-3` 顶面 ≈ +15 mm、`zjg-30` ≈ +1.2、`zjg-72` ≈ 0，与图纸 14.000 mm 同源；`qjbg-72` 横向原点在 +36…+108 mm，每条线各有原点。结论：直接用里程表做站表、断面直接读、**不再写 z 偏移表**。
### 第 225 轮 — 断面文件是 z 向下为正：图要反转纵轴（用户指出的"倒立"）

`.prr` 与同名 `.txt` 内容逐点相同（1001 点，corr=1.000000），约定是 **z 向下为正、轨顶在 0、断面下缘 +23 mm**。第 224 轮的图没反转纵轴，轨头被画成开口向上的 U，看起来倒立——已修正为 `set_ylim(30, -20)`。数值结论不变（`min(z)` = 最高点，降低值 14.94 → 1.16 → −0.09 mm），但"画断面必须反转纵轴"写成口径。
### 第 226 轮 — 用"最平的一段"证明断面方向，并给出新文件名的图

不依赖任何外部约定：**走行面是轮廓里最平的部分**。`zjg-72` 有 **86 点**近水平段落在 `z ≈ −0.06 mm`，`zjg-30` 的 3 点水平段在 `+1.16 mm`，`zjg-3` 的 2 点在 `+14.94 mm` ⇒ `z` 向下为正、轨顶在 0，两处降低值成立。另记：整个语料里最高的断面就是 **23.14 mm**（只有轨头），所以图里永远看不到轨腰与轨底。新增 `scripts/s80_orientation_check.py`（可复算判据）与 `scratch/s80_orientation_verified.png`（新文件名，避开浏览器缓存）。
### 第 227 轮 — 照 SDITT 读三条轨线：降低值在断面里，起点预注册为 57.019 / 104.395 m

解析 `07(009)-Mileage` 的三张表（76 / 161 / 68 行，按 stem 索引 697 个断面，0 缺失），读出冠高：基本轨全程 −0.07 mm；尖轨从 +14.94 mm（50.578 m）爬到齐平 **57.019 m**；长心轨从 +13.70 mm（103.280 m）爬到 **104.395 m**。与旧算例"图纸表 + 侵入阈值"推出的 68.15 m 差 11.1 m，原因量化（图纸 23 mm@0 宽度 vs 几何 14.94 mm@3 mm 宽度）并留待零不平顺运行裁决。新增 `scripts/s81_sditt_lines.py`、`docs/SDITT_LINES_READER_2026-10-30.md`。
### 第 228 轮 — 载荷转移图：能不能反演，先看转移是否良定义

按冠高逐 0.25 m 扫 45–125 m：基本轨承力到 **58.50 m** 交给尖轨，尖轨/基本轨在 59.75–98.25 m 交替（冠高差 ≤0.02 mm，由轮子横向位置裁决），**107.25–116.75 m** 由长心轨承力。降低值是 14.94 mm/6.4 m（≈1:450）与 13.70 mm/1.1 m（≈1:80）的台阶，约为 65 µm 静侵入的 230 倍 ⇒ 转移是离散事件、可反演量是两个**里程**（定位问题，不是幅值问题）。同时更正 2026-10-29 那条"降低值不在断面里"的判定（那是 z 方向读反）。新增 `scripts/s82_transfer_map.py`。
### 第 229 轮 — 三条线算例装成：51 坐标、右轨 3 个 body、降低值全在几何

`scripts/s83_three_line_case.py` 用 `07(009)-Mileage` 三张表组出右轨三体（基本轨 76 站 / 尖轨+翼轨 160 站 / 心轨 68 站），51 坐标、body 数 `[1,1,1,1,3,3,3,3]`、无 z 偏移表。量出并修掉左右冠距差 **13.2 mm**（+733.45 vs −759.89 → 显式 ±746.50）。仍卡：左轨（另一源、30 mm 头、`y_sign −1`）在 40 m 触发 `graph slope limit`，下一步量左右镜像方向与冠偏移。新增 `docs/THREE_LINE_CASE_2026-10-30.md`。
### 第 230 轮 — 道岔数据库落地：一套 18 号、293 个断面、3 张权威表

`scripts/s84_turnout_database.py` 从 `G:` 的 7 张里程表里定下 3 张权威表（另 4 张记录被取代原因），复制 **293 个断面 / 7.9 MB** 与车轮断面到 `vehicles/turnouts/CN60-1100-1_18/`，逐文件记 sha256，缺失 0——算例不再依赖 `G:`。`scripts/s85_db_case.py` 生成并加载基线直向算例：**51 坐标、8 rail、右轨 3 body**；左右用同一断面镜像、每站抵消自身冠位，左冠 −746.60 mm、尖轨冠 −1.68 mm（55.5 m）、心轨冠 +0.10 mm（110 m），与里程表一致。**座椅仍失败**（`ftol`），下一步按 §5 打印同一里程各 body 的接触。新增 `docs/TURNOUT_DB_2026-10-30.md`。
### 第 231 轮 — 带 body 的轨会丢掉基本轨：修复后仍未收敛，病因缩到接触搜索

`rail_templates[].bodies` 一旦存在，加载器便不再把 `stations` 当基本轨，右轨只剩尖轨与心轨，40 m 处右轨**零接触**。已把基本轨写成显式 body（`['stock','blade','frog']`）。修后左右冠位 ∓746.6/±746.5 mm、冠高 +0.07 mm 全部对齐，但座椅三颗种子仍停在 `max|r| = 6.819e-01`（68 185 N），六行竖向残差相同 → 接触力恒为 0；轮对沉到 −20 mm 仍 0.00 kN，而旧算例 0.2 mm 就有 66.89 kN。差异已缩到两处：断面 1001 点（`.txt`）对 1999 点（`.prr`）、轨面 z 上界 +0.072 对 0.000 mm。
### 第 232 轮 — 坐不住的两个真原因：丢基本轨、车轮断面带钢轨偏置

其一，`rail_templates[].bodies` 一旦存在，加载器不再把 `stations` 当基本轨，右轨只剩尖轨与心轨（40 m 处右轨零接触）。其二，`wheels[i].profile` 复用了钢轨的 `station_profile()`，被减掉钢轨冠位 −0.6772 m，再叠加 ±0.7465 的轮位偏置，踏面落到 −1.49 m 而轨冠在 −0.7465 m，**相距 0.68 m**，所以沉 20 mm 也是 0.00 kN。两处都改在 `scripts/s85_db_case.py`，注释里带全部实测。修后接触出现但斜率门触发；把轨冠相对轮心做成参数扫描：0 mm 触发门、7 mm 3 982.79 kN、10 mm 1 087.41 kN、13.7 mm 1.98 kN、20 mm 0.00 kN —— **3.7 mm 跨越三个数量级**，说明压上去的是轨肩而不是轨顶圆弧。旧的可跑算例其轨冠恰在轮心外 13.7 mm，正是本库接触消失的值，两者必有一个基准错了。
### 第 233 轮 — 座椅解决（轨冠在轮心外 13.0 mm），直向 401 帧七门全过并落盘

把轨冠相对轮心的偏置做成参数逐点跑真座椅：12.0 / 12.8 / 13.4 / 13.7 mm 四处都收敛（残差 3e-08…1.2e-07 N），八轮份额全 **1.000**、总力恒 **477.4 kN**——窗口平坦 ≥1.7 mm，说明这是几何而非调参：1:40 轨顶 + LMA 踏面的接触点本就在轨冠内侧约 13 mm。**"13.2 mm 基准错误"的结论撤回**，旧算例的 13.7 mm 是对的。`scripts/s86_run_baseline.py --route straight --duration 0.20` 跑出 **401 帧、七门 7/7**，数据落 `../scratch/s86/straight_0.20s/`。曲向**拒绝运行**：直向算例每站引用同一份基本轨断面，横向是直的，曲股横向在逐里程断面与 `qjg_cgyg` 表里，尚未入库。
### 第 227 轮 — 18 号道岔库补齐曲向：直向/曲向共用一套断面与一套基准

`scripts/s85_db_case.py` 新增 `--route diverging`：右线每站位移 `y = (s − 50.578)²/(2 × 1100.75)`，`run` 写 `curve_radius_m` / `curve_origin_m`；`scripts/s86_run_baseline.py` 改为按路线取算例、不再拒绝曲向。实跑：直向 401 帧七门 7/7（轮对 y 恒 0），曲向 401 帧七门 7/7（轮对 y 到 +5.3…+5.9 mm，前轴末位置 54.4 m、导曲线给 6.6 mm，同量级）。数据落 `../scratch/s86/{straight_0p20,diverging_0.20s}`。

### 第 234 轮 — 接触钉扎：候选 1、2 被否证，候选 3 的探针接线错误

横移扫描给出 `d(lever_y)/d(shift) = −1.0000 m/m`（接触点与车轮 1:1 同走）⇒ 基准错位不成立；`s92` 显示接触在车轮踏面内（距轮心 −6.27 mm），没钉在轨面特征上 ⇒ 候选 2 不成立，但顺带发现"轨面 z 最小点"是一个 −0.1 mm 的**角**而非冠，此前所有用 `argmin(z)` 当轨冠的推算需改用接触点拟合曲率（该处 299.6 mm）。窗口 1→10 mm 与带宽 0.25→0.10 mm 三组读数逐位相同，说明 `dataclasses.replace(case, contact=…)` 未传进求解器使用的 law——**候选 3 尚未被检验**，下一轮先证明覆盖生效。实测增益 25.0 µm/mm 仍是 300 mm 冠理论值 6.7 µm/mm 的 3.7 倍（先前的 1666.7 是我式子写错）。

### 第 235 轮 — 用 SDITT 的接触实现反查：我们漏了 ε·δ 的虚拟贯入量

读 `SDITT-RW-FT-250728`：`NF_STRIPES_230623.m` 用 `h_0 = ε·δ`（`ε = n²/r/(1+(n/m)²)`) 做虚拟贯入量，`m/n/r` 是接触点处的横向曲率半径与滚动圆半径；接触斑来自"全部局部极小 + 1 mm 去重"（`Multi_Con_250812.m:309-354`），法向刚度来自 `Par_Con.m` 的 Hertz 表 `BGmn`。据此重算：Hertz 在 65.47 µm/59.68 kN 处应为 **1 367 kN/mm**，我们的 strip 态（197.6 µm）应 453 kN/mm，而实测 `dN/dδ = 9.74/0.0250 = 0.39 kN/mm`——**软 1 100 倍**。结论：载荷由多条带分摊，横向增益由"条带接合范围"决定，不是轨冠曲率；"3.7 倍"那个比较用错了框架。

### 第 236 轮 — B048：直向算例的 20 mm 等效半径把横向做硬了 12 倍

`case_A_plain.json` 声明 `effective_radius_m = 0.02`，而断面拟合给出 `R_wheel 1273.65 mm / R_rail 295.27 mm`、`R* = 0.5501 m`。换成按曲率的 `local_circular`：贯入 197.62 → **65.47 µm**（正是冻结 oracle）、法向力同为 59.681 kN、横移 1/2/4 mm 卸载到 32.6 / 7.7 / **0 kN**。结论：竖向标定**不需要**那个 20 mm 覆盖；横向的症结是注册（轮心到轨冠 6.8 mm），不是法向律。另更正上一轮"软 1100 倍"为单位错误（实测 389.6 kN/mm vs 模型 453 kN/mm，差 14 %）；并确认 `find_strip_contact` 不在生产路径上（只有 `find_graph_contact`），因此"候选 3 窗口"结构上测不到。

### 第 237 轮 — 20 mm 等效半径退役（B048，选项 A）

`stiffness_policy` 默认改为 `local_circular`（三处签名），`_settle_modal_coordinates` 的
`rounds` 12→20（让步因子 0.755/次）。实测：力 59 680.57685863 N 不变、贯入 197.62 → **65.4661 µm**
（正是文档 oracle）、`R* = 0.55010 m`、轮对高 132 µm。五个测试文件同步（`ORACLE_VERTICAL_M`
改为 `-3.3057783604e-04`；模态力律改写为按实测 C 与实测深度，因为 C 现在随接触位置变）。基线
重新冻结：`straight_rigid 295809cb24c8e24b`、`straight_flexible 7b1daef7e80664ac`。
未解决：横向注册（1 mm 卸载 45 %）、B045。
