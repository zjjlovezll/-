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

- `.tmp/gen_docs_index.py` 在 `
<!-- DOCS:ALL:BEGIN -->
## 完整文档清单（由 `.tmp/gen_docs_index.py` 生成，测试会检查是否过期）

| 文件 | 首行标题 |
|---|---|
| [A1_STRIP_WINDOW_2026-10-22.md](A1_STRIP_WINDOW_2026-10-22.md) | A1：条带接触窗（bounded strip patch） |
| [A2_C_DELTA_DEGENERACY_2026-10-22.md](A2_C_DELTA_DEGENERACY_2026-10-22.md) | A2 C–δ 简并排查（2026-10-22） |
| [A3_MULTIPATCH_2026-10-22.md](A3_MULTIPATCH_2026-10-22.md) | A3 同步多斑 + 局部弹性分配 —— 实测：**前提不成立，局部分配已经存在** |
| [AGENT_TOOL_LAYER_2026-10-22.md](AGENT_TOOL_LAYER_2026-10-22.md) | Velch AI 调用层设计（Agent Tool Layer，2026-10-22） |
| [AI_INTERFACE_ARCHITECTURE_2026-10-22.md](AI_INTERFACE_ARCHITECTURE_2026-10-22.md) | Velch 软件分层与 AI 接口架构（设计草案） |
| [ARCHITECTURE_2026-10-21.md](ARCHITECTURE_2026-10-21.md) | Velch 架构收口与 Simpack 2021x 对标（2026-10-21） |
| [ASSESSMENT_2026-10-20.md](ASSESSMENT_2026-10-20.md) | 标准评价指标（assess）：把仿真输出变成可判读的结论 |
| [B2_EVENT_INTEGRATION_2026-10-22.md](B2_EVENT_INTEGRATION_2026-10-22.md) | B2 事件化积分 / 峰值分辨率（2026-10-22） |
| [B3_TABLE_AMORTIZATION_2026-10-22.md](B3_TABLE_AMORTIZATION_2026-10-22.md) | B3 接触表按反演批次摊销（2026-10-22） |
| [B4_DESCRIPTOR_2026-10-22.md](B4_DESCRIPTOR_2026-10-22.md) | B4 接触状态描述子降维 —— 实测**负结果** |
| [B5_JACOBIAN_EVENTS_2026-10-22.md](B5_JACOBIAN_EVENTS_2026-10-22.md) | B5 雅可比作事件检测（2026-10-22） |
| [bench_toolchain_design.md](bench_toolchain_design.md) | Velch 性能基准与剖析工具链（v1 最小可用设计） |
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
| [CRH380A_M_REAL_SIMPACK_VALIDATION_2026-10-19.md](CRH380A_M_REAL_SIMPACK_VALIDATION_2026-10-19.md) | CRH380A_M 刚性模型真实 Simpack 验证记录（2026-10-19） |
| [CRH380A_M_VALIDATION_2026-10-19.md](CRH380A_M_VALIDATION_2026-10-19.md) | CRH380A_M 刚性模型作为 Velch 验证算例的检查记录 |
| [DAMPING_CALIBRATION_2026-10-21.md](DAMPING_CALIBRATION_2026-10-21.md) | 接触阻尼定标：无效（负结果） |
| [DEVELOPMENT_GATES.md](DEVELOPMENT_GATES.md) | Velch 后续开发与验收门 |
| [DIVERGING_ROUTE_2026-10-21.md](DIVERGING_ROUTE_2026-10-21.md) | 曲向（diverging route）装配 — 阶段 1 记录（2026-10-21） |
| [EVIDENCE_MAP.md](EVIDENCE_MAP.md) | 证据地图：这一版凭什么可以说「可以发布」 |
| [FROG_WINDOW_BREAKTHROUGH_2026-10-21.md](FROG_WINDOW_BREAKTHROUGH_2026-10-21.md) | 辙叉窗突破：脱空归零，宽带频谱塌回 Simpack 量级 |
| [INNOVATION_SPRINT_2026-10-22.md](INNOVATION_SPRINT_2026-10-22.md) | 创新冲刺 2026-10-22（B1 步长上限 → A1 接触窗 → B4 描述子降维 → …） |
| [INVERSION_DEMO_2026-10-20.md](INVERSION_DEMO_2026-10-20.md) | 合成反演：可辨识性门 + 高斯‑牛顿（2026-10-20） |
| [LAYERED_TRACK_2026-10-20.md](LAYERED_TRACK_2026-10-20.md) | 分层轨道（layered track）：钢轨 / 扣件 / 轨枕 / 板下胶垫 / 轨道板 |
| [MEASURED_VALIDATION_2026-10-21.md](MEASURED_VALIDATION_2026-10-21.md) | 实测数据接入验证（2026-10-21） |
| [OBSERVATION_LAYER_2026-10-20.md](OBSERVATION_LAYER_2026-10-20.md) | 观测量层：仿真对仿真 + 实测对模型（2026-10-20） |
| [ONBOARDING_2026-10-21.md](ONBOARDING_2026-10-21.md) | 新增车体 / 新增道岔的接入指南 |
| [OPEN_SOURCE_WHEEL_RAIL_CONTACT_SURVEY_2026-10-19.md](OPEN_SOURCE_WHEEL_RAIL_CONTACT_SURVEY_2026-10-19.md) | 开源轮轨接触算法调查（2026-10-19） |
| [PACKAGING_2026-10-22.md](PACKAGING_2026-10-22.md) | 打包与安装包（Windows） |
| [PARALLEL_AND_SIMPACK_RWP.md](PARALLEL_AND_SIMPACK_RWP.md) | 多核并行、Simpack RWP 机制与 CONTACT 接入 |
| [PHYSICS_INVARIANTS.md](PHYSICS_INVARIANTS.md) | 物理不变量复算门 |
| [RACK_CASE_DATA_CONTRACT_2026-10-21.md](RACK_CASE_DATA_CONTRACT_2026-10-21.md) | 齿轨过岔算例：数据契约（2026-10-21） |
| [RAIL_CANT_2026-10-20.md](RAIL_CANT_2026-10-20.md) | 轨底坡 1:40：把"整体倾斜"换成"绕轨顶中心旋转" |
| [RELEASE_NOTES_0.4.1.md](RELEASE_NOTES_0.4.1.md) | Velch 0.4.1 · 发布说明（2026-10-22） |
| [RELEASE_NOTES_0.4.10.md](RELEASE_NOTES_0.4.10.md) | Velch 0.4.10 发布说明（2026-10-23） |
| [RELEASE_NOTES_0.4.11.md](RELEASE_NOTES_0.4.11.md) | Velch 0.4.11 发布说明（2026-10-23） |
| [RELEASE_NOTES_0.4.12.md](RELEASE_NOTES_0.4.12.md) | Velch 0.4.12 发布说明 |
| [RELEASE_NOTES_0.4.13.md](RELEASE_NOTES_0.4.13.md) | Velch 0.4.13 发布说明 |
| [RELEASE_NOTES_0.4.14.md](RELEASE_NOTES_0.4.14.md) | Velch 0.4.14 发布说明 |
| [RELEASE_NOTES_0.4.15.md](RELEASE_NOTES_0.4.15.md) | Velch 0.4.15 发布说明 |
| [RELEASE_NOTES_0.4.16.md](RELEASE_NOTES_0.4.16.md) | Velch 0.4.16 发布说明 |
| [RELEASE_NOTES_0.4.2.md](RELEASE_NOTES_0.4.2.md) | Velch 0.4.2（2026-10-22 夜间） |
| [RELEASE_NOTES_0.4.3.md](RELEASE_NOTES_0.4.3.md) | Velch 0.4.3 发布说明（2026-10-22 夜） |
| [RELEASE_NOTES_0.4.4.md](RELEASE_NOTES_0.4.4.md) | Velch 0.4.4 发布说明（2026-10-23 凌晨） |
| [RELEASE_NOTES_0.4.5.md](RELEASE_NOTES_0.4.5.md) | Velch 0.4.5 发布说明 |
| [RELEASE_NOTES_0.4.9.md](RELEASE_NOTES_0.4.9.md) | Velch 0.4.9 发布说明（2026-10-23） |
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
| [SAME_MODEL_COMPARISON_2026-10-22.md](SAME_MODEL_COMPARISON_2026-10-22.md) | 同模型效率对比：为什么不能直接吃 SDITT 的 6204 阶，以及怎么才算公平 |
| [SDITT_TRACK_TIMING_2026-10-22.md](SDITT_TRACK_TIMING_2026-10-22.md) | 采用 SDITT 柔性轨道参数时的耗时与对比（2026-10-22） |
| [SELFCHECK_2026-10-23.md](SELFCHECK_2026-10-23.md) | 第一次运行先跑自检（`velch selfcheck`） |
| [SIMPACK_COMPARE_2026-10-23.md](SIMPACK_COMPARE_2026-10-23.md) | Simpack 与 Velch 的定量对照（前轮对，23.5–138.5 m） |
| [SIMPACK_IMPORT_2026-10-22.md](SIMPACK_IMPORT_2026-10-22.md) | 从 Simpack 模型算一个算例（2026-10-22） |
| [SOFTWARE_ARCHITECTURE_V0_4.md](SOFTWARE_ARCHITECTURE_V0_4.md) | Velch 0.4 软件架构与模型边界 |
| [SPECTRUM_SOURCE_2026-10-21.md](SPECTRUM_SOURCE_2026-10-21.md) | 153.85 Hz 是什么：速度标定实验 |
| [SPEED_2026-10-20.md](SPEED_2026-10-20.md) | 提速：先量再改（2026-10-20） |
| [STAGE2_MODAL_2026-10-21.md](STAGE2_MODAL_2026-10-21.md) | 阶段②：钢轨模态扩阶（60 → 320 阶）对接触力频谱的影响 |
| [STAGE3_EFFICIENCY_2026-10-21.md](STAGE3_EFFICIENCY_2026-10-21.md) | 阶段③：与 SDITT 的效率对标 |
| [STAGE_B_SURROGATE_2026-10-21.md](STAGE_B_SURROGATE_2026-10-21.md) | B 阶段：可微代理与保险丝 2026-10-21 |
| [UI_CHINESE_LABELS_2026-10-22.md](UI_CHINESE_LABELS_2026-10-22.md) | 界面中文命名规则（Velch UI） |
| [UI_READABILITY_2026-10-22.md](UI_READABILITY_2026-10-22.md) | 界面可读性：字号缩放与不截断 |
| [UNIFIED_SCALE_AND_SOFTWARE_READINESS_2026-10-22.md](UNIFIED_SCALE_AND_SOFTWARE_READINESS_2026-10-22.md) | 统一口径复核 + 代码体检（2026-10-22） |
| [VEHICLE_V2_DESIGN_AND_EVIDENCE.md](VEHICLE_V2_DESIGN_AND_EVIDENCE.md) | Velch v0.2：车辆—轮对—道岔轨道耦合的证据与实现 |
<!-- DOCS:ALL:END -->` 之间生成
  "文件 → 首行标题"表（73 行，机械取自每篇自己的标题，不改写内容）；
- 新增 `tests/test_docs_index.py`（5 项）：清单块存在且 ≥60 行、**每篇 `docs/*.md` 都被索引提到**、
  索引里每个 `.md` 链接都能解析到真实文件、**生成块与当前标题一致（漂移守卫）**、
  **当前 `__version__` 必须有对应的 `RELEASE_NOTES_<ver>.md` 且已登记**。

最后那条正是"文档与版本一致"的可执行版本：以前版本号改了、发布说明漏写，没人会发现。

顺带记一个判断错误：最初还写了"发布说明在索引里必须按 semver 排序"，跑起来立刻失败——索引表是按
**书写顺序**追加的，不是 semver 顺序。排序在这个位置没有意义，已替换为"当前版本必须有说明"。
`pytest` **539 passed, 1 skipped**。

<!-- DOCS:ALL:BEGIN -->
## 完整文档清单（由 `.tmp/gen_docs_index.py` 生成，测试会检查是否过期）

| 文件 | 首行标题 |
|---|---|
| [A1_STRIP_WINDOW_2026-10-22.md](A1_STRIP_WINDOW_2026-10-22.md) | A1：条带接触窗（bounded strip patch） |
| [A2_C_DELTA_DEGENERACY_2026-10-22.md](A2_C_DELTA_DEGENERACY_2026-10-22.md) | A2 C–δ 简并排查（2026-10-22） |
| [A3_MULTIPATCH_2026-10-22.md](A3_MULTIPATCH_2026-10-22.md) | A3 同步多斑 + 局部弹性分配 —— 实测：**前提不成立，局部分配已经存在** |
| [AGENT_TOOL_LAYER_2026-10-22.md](AGENT_TOOL_LAYER_2026-10-22.md) | Velch AI 调用层设计（Agent Tool Layer，2026-10-22） |
| [AI_INTERFACE_ARCHITECTURE_2026-10-22.md](AI_INTERFACE_ARCHITECTURE_2026-10-22.md) | Velch 软件分层与 AI 接口架构（设计草案） |
| [ARCHITECTURE_2026-10-21.md](ARCHITECTURE_2026-10-21.md) | Velch 架构收口与 Simpack 2021x 对标（2026-10-21） |
| [ASSESSMENT_2026-10-20.md](ASSESSMENT_2026-10-20.md) | 标准评价指标（assess）：把仿真输出变成可判读的结论 |
| [B2_EVENT_INTEGRATION_2026-10-22.md](B2_EVENT_INTEGRATION_2026-10-22.md) | B2 事件化积分 / 峰值分辨率（2026-10-22） |
| [B3_TABLE_AMORTIZATION_2026-10-22.md](B3_TABLE_AMORTIZATION_2026-10-22.md) | B3 接触表按反演批次摊销（2026-10-22） |
| [B4_DESCRIPTOR_2026-10-22.md](B4_DESCRIPTOR_2026-10-22.md) | B4 接触状态描述子降维 —— 实测**负结果** |
| [B5_JACOBIAN_EVENTS_2026-10-22.md](B5_JACOBIAN_EVENTS_2026-10-22.md) | B5 雅可比作事件检测（2026-10-22） |
| [bench_toolchain_design.md](bench_toolchain_design.md) | Velch 性能基准与剖析工具链（v1 最小可用设计） |
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
| [CRH380A_M_REAL_SIMPACK_VALIDATION_2026-10-19.md](CRH380A_M_REAL_SIMPACK_VALIDATION_2026-10-19.md) | CRH380A_M 刚性模型真实 Simpack 验证记录（2026-10-19） |
| [CRH380A_M_VALIDATION_2026-10-19.md](CRH380A_M_VALIDATION_2026-10-19.md) | CRH380A_M 刚性模型作为 Velch 验证算例的检查记录 |
| [DAMPING_CALIBRATION_2026-10-21.md](DAMPING_CALIBRATION_2026-10-21.md) | 接触阻尼定标：无效（负结果） |
| [DEVELOPMENT_GATES.md](DEVELOPMENT_GATES.md) | Velch 后续开发与验收门 |
| [DIVERGING_ROUTE_2026-10-21.md](DIVERGING_ROUTE_2026-10-21.md) | 曲向（diverging route）装配 — 阶段 1 记录（2026-10-21） |
| [FROG_WINDOW_BREAKTHROUGH_2026-10-21.md](FROG_WINDOW_BREAKTHROUGH_2026-10-21.md) | 辙叉窗突破：脱空归零，宽带频谱塌回 Simpack 量级 |
| [INNOVATION_SPRINT_2026-10-22.md](INNOVATION_SPRINT_2026-10-22.md) | 创新冲刺 2026-10-22（B1 步长上限 → A1 接触窗 → B4 描述子降维 → …） |
| [INVERSION_DEMO_2026-10-20.md](INVERSION_DEMO_2026-10-20.md) | 合成反演：可辨识性门 + 高斯‑牛顿（2026-10-20） |
| [LAYERED_TRACK_2026-10-20.md](LAYERED_TRACK_2026-10-20.md) | 分层轨道（layered track）：钢轨 / 扣件 / 轨枕 / 板下胶垫 / 轨道板 |
| [MEASURED_VALIDATION_2026-10-21.md](MEASURED_VALIDATION_2026-10-21.md) | 实测数据接入验证（2026-10-21） |
| [OBSERVATION_LAYER_2026-10-20.md](OBSERVATION_LAYER_2026-10-20.md) | 观测量层：仿真对仿真 + 实测对模型（2026-10-20） |
| [ONBOARDING_2026-10-21.md](ONBOARDING_2026-10-21.md) | 新增车体 / 新增道岔的接入指南 |
| [OPEN_SOURCE_WHEEL_RAIL_CONTACT_SURVEY_2026-10-19.md](OPEN_SOURCE_WHEEL_RAIL_CONTACT_SURVEY_2026-10-19.md) | 开源轮轨接触算法调查（2026-10-19） |
| [PACKAGING_2026-10-22.md](PACKAGING_2026-10-22.md) | 打包与安装包（Windows） |
| [PARALLEL_AND_SIMPACK_RWP.md](PARALLEL_AND_SIMPACK_RWP.md) | 多核并行、Simpack RWP 机制与 CONTACT 接入 |
| [RACK_CASE_DATA_CONTRACT_2026-10-21.md](RACK_CASE_DATA_CONTRACT_2026-10-21.md) | 齿轨过岔算例：数据契约（2026-10-21） |
| [RAIL_CANT_2026-10-20.md](RAIL_CANT_2026-10-20.md) | 轨底坡 1:40：把"整体倾斜"换成"绕轨顶中心旋转" |
| [RELEASE_NOTES_0.4.1.md](RELEASE_NOTES_0.4.1.md) | Velch 0.4.1 · 发布说明（2026-10-22） |
| [RELEASE_NOTES_0.4.10.md](RELEASE_NOTES_0.4.10.md) | Velch 0.4.10 发布说明（2026-10-23） |
| [RELEASE_NOTES_0.4.11.md](RELEASE_NOTES_0.4.11.md) | Velch 0.4.11 发布说明（2026-10-23） |
| [RELEASE_NOTES_0.4.2.md](RELEASE_NOTES_0.4.2.md) | Velch 0.4.2（2026-10-22 夜间） |
| [RELEASE_NOTES_0.4.3.md](RELEASE_NOTES_0.4.3.md) | Velch 0.4.3 发布说明（2026-10-22 夜） |
| [RELEASE_NOTES_0.4.4.md](RELEASE_NOTES_0.4.4.md) | Velch 0.4.4 发布说明（2026-10-23 凌晨） |
| [RELEASE_NOTES_0.4.5.md](RELEASE_NOTES_0.4.5.md) | Velch 0.4.5 发布说明 |
| [RELEASE_NOTES_0.4.9.md](RELEASE_NOTES_0.4.9.md) | Velch 0.4.9 发布说明（2026-10-23） |
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
| [SAME_MODEL_COMPARISON_2026-10-22.md](SAME_MODEL_COMPARISON_2026-10-22.md) | 同模型效率对比：为什么不能直接吃 SDITT 的 6204 阶，以及怎么才算公平 |
| [SDITT_TRACK_TIMING_2026-10-22.md](SDITT_TRACK_TIMING_2026-10-22.md) | 采用 SDITT 柔性轨道参数时的耗时与对比（2026-10-22） |
| [SIMPACK_COMPARE_2026-10-23.md](SIMPACK_COMPARE_2026-10-23.md) | Simpack 与 Velch 的定量对照（前轮对，23.5–138.5 m） |
| [SIMPACK_IMPORT_2026-10-22.md](SIMPACK_IMPORT_2026-10-22.md) | 从 Simpack 模型算一个算例（2026-10-22） |
| [SOFTWARE_ARCHITECTURE_V0_4.md](SOFTWARE_ARCHITECTURE_V0_4.md) | Velch 0.4 软件架构与模型边界 |
| [SPECTRUM_SOURCE_2026-10-21.md](SPECTRUM_SOURCE_2026-10-21.md) | 153.85 Hz 是什么：速度标定实验 |
| [SPEED_2026-10-20.md](SPEED_2026-10-20.md) | 提速：先量再改（2026-10-20） |
| [STAGE2_MODAL_2026-10-21.md](STAGE2_MODAL_2026-10-21.md) | 阶段②：钢轨模态扩阶（60 → 320 阶）对接触力频谱的影响 |
| [STAGE3_EFFICIENCY_2026-10-21.md](STAGE3_EFFICIENCY_2026-10-21.md) | 阶段③：与 SDITT 的效率对标 |
| [STAGE_B_SURROGATE_2026-10-21.md](STAGE_B_SURROGATE_2026-10-21.md) | B 阶段：可微代理与保险丝 2026-10-21 |
| [UI_CHINESE_LABELS_2026-10-22.md](UI_CHINESE_LABELS_2026-10-22.md) | 界面中文命名规则（Velch UI） |
| [UI_READABILITY_2026-10-22.md](UI_READABILITY_2026-10-22.md) | 界面可读性：字号缩放与不截断 |
| [UNIFIED_SCALE_AND_SOFTWARE_READINESS_2026-10-22.md](UNIFIED_SCALE_AND_SOFTWARE_READINESS_2026-10-22.md) | 统一口径复核 + 代码体检（2026-10-22） |
| [VEHICLE_V2_DESIGN_AND_EVIDENCE.md](VEHICLE_V2_DESIGN_AND_EVIDENCE.md) | Velch v0.2：车辆—轮对—道岔轨道耦合的证据与实现 |
<!-- DOCS:ALL:END -->

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
