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
| 测试 | 361 passed（2026-10-22 17:40 实测，含 16 条架构规则 + 20 条 agent 契约 + 8 条三维几何；会随并行会话增加，验收只认 0 failed） | — |

基线组合：条带积分法向律 + 钢轨垂向自由度 + 柔性扣件 5e7/4e4 + 接触阻尼 3e7 且
`damping_force_cap_ratio=0.5`。

## 文档清单

| 文档 | 回答什么问题 | 仍成立？ |
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
| `docs/AI_INTERFACE_ARCHITECTURE_2026-10-22.md` | **AI 怎么调用这套软件**（架构）：L0–L4 分层与依赖方向、进程内 `VelchService` 只做编排 + 算的一律 subprocess（import 0.078 s vs 0.489 s 实测）、MCP stdio 是对 AI 的正式形态而 HTTP 等消费者、`gate_failed` 不是 error、幂等键与四道可回退、Phase 0–6 分期与每期下限 | ✅ 新增。Phase 0 已落地，Phase 1 被本切片绕过（registry 是 stdlib 叶子，不必外移） |
| `docs/AGENT_TOOL_LAYER_2026-10-22.md` | **AI 具体能调哪些工具**（契约）：20 个工具 6 域的设计、三层白名单与通配 `[]` 这颗雷、`solver_patch` 第二命名空间、错误码闭集与 `gate_failed` 例外、ledger 只追加成链、成本模型与路由（<60 s 同步 / ≥60 s 后台 / 预算先拒）、三条"自动化下必崩"的实证；**§8 是设计 vs 代码对照（12 个工具已实现、未做的逐条列出、`physics_changed` 认"采样≠物理"、auto_accept 四步）** | ✅ 新增。§1 的 20 个工具里 12 个已实现，其余见 §8.3 |

| `docs/DAMPING_CALIBRATION_2026-10-21.md` | 接触阻尼定标（负结果） | ❌ **已作废（限定量级）**：扫点 ζ ≤ 5e-4；`S2_REMAINING_PATHS` §4.0 在生产量级 1e6→3e7 上测得 rms −44%，结论相反 |
| `docs/ARCHITECTURE_2026-10-21.md` | **架构收口与 Simpack 2021x 对标**：14 行能力矩阵（接触几何/多点接触/法向律/切向律/阻尼/积分器/轨道结构/车辆自由度/执行机构/观测量/反演/UQ/批处理/UI，每行给出 Velch 文件:行号 × Simpack 取证 × 差距性质）、实测 import 图与 4 条真实违规（`io`→`inverse` 类型级反向依赖、`case/spec.py:27`、`vehicle_solver.py:23`、`contact.py:32`）、上帝模块与 6 步拆分顺序、四道结构性缺口（①模态每轨一套 ②钢轨离散化 ③轴箱体 ④轨底应变桥路）的接口+DOF 布局+验收门、UI/CLI 边界与稳定接口清单、三个月四轴路线 | ✅ 新增。行号基准 2026-10-21 11:40 工作树；用 `python -X utf8 _cite_check.py` 重解析、`_arch_scan.py` 重算依赖图 |
| `tests/test_architecture_rules.py` | 架构适应度函数（16 项 AST 静态断言）：前向不得 import `inverse`、`inverse` 不得 import 前向、`contact*` 不得 import 调用者、`case/*` 只许 import `velch.vehicle`、`io.history` 必须是叶子、`vehicle_solver` 只许从 v1 借 `SimulationFailure`、UI 不得 import 前向栈、import 时图无环、`io.measured → inverse` 不得是运行时边 | ✅ 16 passed；失败信息直接打印违规边（含 `kind ∈ runtime/deferred/typing`） |

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
