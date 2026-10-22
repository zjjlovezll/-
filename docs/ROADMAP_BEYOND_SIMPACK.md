# Velch 路线图：借鉴 Simpack 并超越它（2026-10-20 起）

> 原则：**不做 Simpack 的克隆**。Simpack 的三件内核（接触几何表 GT、隐式 BDF、通用多体约束）
> 是 1990 年代为“通用”付的代价。我们用**解析几何 + 半 Hertz 条带 + 可微 GPU 求解 + 伴随反演**
> 跳过那一代做法，并在它结构上做不到的三件事上取胜：参数梯度、工况批量、后验区间。

## 0. 起点（已实测，作为全过程的 oracle）

| 指标 | 当前值 |
|---|---|
| 平直段静载（8 接触） | 59 680.577 N，2401 采样零波动 |
| 静平衡侵入 | 65.5 µm（Simpack 66.2 µm，−1.1%） |
| 接触刚度中位 `C = N/δ^1.5` | 1.1267e11（Simpack 1.1174e11，+0.8%） |
| 整程轮对垂向行程 | 0.593 mm（Simpack 0.594，−0.2%） |
| 辙叉窗右轨峰值 | 158.04 kN（Simpack 127.84，+24%） |
| 辙叉窗轮对垂向行程 | 192 µm（Simpack ≈1 µm，200×） |
| 辙叉窗力主频 | 194 Hz（Simpack 39 Hz） |
| 脱空采样 | 0（Simpack 0） |
| 单核实时倍率 | 约 0.005–0.01×（Simpack 70.9×） |

冻结方式：`Velch\validation\crh380a_m\out_final_full1p2s\`、`out_A_final_law\` 的
`manifest.json` + `history.csv`，以及 `validation\turnout18_ref\CONTACT_ALGORITHM_FINAL_2026-10-20.md`。
**任何阶段的结果都必须与它逐点比对**（默认 1e-6 相对，几何类 1 µm 绝对）。

## 1. 四个阶段总览

| 阶段 | 主题 | 关键交付 | 验收门 |
|---|---|---|---|
| **S1** | 解析接触几何 | C² 型面 + 扫掠面极值求解 + 精确曲率 → `R*`、斑宽 | 辙叉窗 194 Hz 振铃消失；峰值 ≤140 kN；轮对行程 ≤10 µm；单核墙钟 ≤1/5；静载与静平衡侵入不变 |
| **S2** | 可微求解器 | PyTorch RHS、隐式积分、`jacrev` 精确 Jacobian、半光滑接触 | 实时倍率 ≥20×（单核）；Jacobian 与有限差分相对误差 <1e-6；1.2 s 工况复现 S1 |
| **S3** | GPU 批量 | 工况维 + 样本维向量化 | ≥200× 实时；100 工况 5 min 内 |
| **S4** | 反演与 UQ | 伴随梯度 + 后验 | 合成数据反演误差 <5%；比“有限差分+优化器”快 ≥50× |

S1 是纯 CPU、纯 numpy，不引入新依赖；S2 起引入 torch（本机已装，RTX 5050 8 GB）。

## 2. S1 —— 解析接触几何（先做，因为它同时解决精度和速度）

### 2.1 为什么要换掉现在的几何管线

现在：`ProfileSeries` 存离散点列 → 站间**线性插值** → 0.05 mm 网格重采样 → 网格上 `argmax`。
三个已知缺陷（都被实测过）：

1. 站间斜率跳变（实测坡度跳变 10.1 mm/m，5 mm 重采样后 44.5 mm/m）；
2. 网格 `argmax` 给出的是采样点，不是极值点（0.05 mm 网格 → 侵入量误差可达 µm 级）；
3. 曲率靠网格差分，`R*` 抖动 → `C` 的 p10 比参考软 15%。

### 2.2 表示

- **型面**：每段断面用**三次 B 样条**（`bc_type="clamped"`）拟合测点，C² 连续，解析给出
  `z(y)`、`z'(y)`、`z''(y)`、曲率 `κ(y)`。节点数取测点数的 1/4–1/2，拟合残差门 ≤2 µm（轨）/≤5 µm（轮）。
  - 注：文献的**圆弧样条**（曲率分段常量、切线连续）是等价方案，内存更省；先做 B 样条，
    若 S3 的显存成为瓶颈再换（两者接口一致）。
- **沿里程**：断面参数（节点值）沿 `s` 再取一次 C² 样条 → **扫掠面 `S(s,y)` 的解析表示**，
  站间不再是线性插值，`∂S/∂s` 连续。
- **接触求解**：把 `g(y) = z_rail(s,y) − z_wheel(y)` 写成样条差，求 `g` 的所有局部极值
  （`g'(y)=0` 的根，Brent + 分段扫描），取 `max(0, g)` 的最大者为接触点，**同时**给出
  该点的 `κ_w`、`κ_r`、`g''`。一次求解 O(局部段数)，无表、无网格。

### 2.3 三步落地（每步独立可验收）

| 步 | 内容 | 验收 |
|---|---|---|
| S1-a | `contact_geometry.py`：`BSplineProfile`（z/dz/d2z/kappa）+ 拟合器 | 26 个辙叉站位 + 平直站位的拟合残差 ≤2 µm；与密集点列采样差 ≤1 µm |
| S1-b | `swept_contact()`：极值求解 + 斑宽估计（`a = √(2R*δ)`） | 与现行 `find_graph_contact` 在同一状态上差：侵入 ≤1 µm、横位 ≤0.05 mm |
| S1-c | 接入 `contact.py`（新 `geometry_policy="spline"`），跑 0.05 s 辙叉窗 | 峰值 ≤140 kN、轮对行程 ≤10 µm、无脱空、静载不变 |

### 2.4 依赖与风险

- 依赖：仅 `numpy`/`scipy`（已在用）。
- 风险：B 样条在轨头顶角的尖点会振铃（Gibbs）。对策：轨头圆角在拟合前就用现在已验证的
  形态学算子（`limit_curvature`，r=6 mm）处理，把尖点变成有限曲率——这一步已有代码。
- 回退：`geometry_policy="grid"` 保留现有路径，随时可切回。

## 3. S2 —— 可微求解器（PyTorch）

- `velch/dyn/torch_rhs.py`：把 `VehicleDynamics.evaluate` 的力装配写成一个纯函数
  `rhs(t, q, v, params) -> (dFdq_ready)`，全部 torch 张量；`params` 里放**待辨识量**
  （支撑刚度、磨耗、间隙、摩擦系数）。
- 积分：`torchdiffeq` 风格的手写 BDF2/Radau 或直接用 `torch.func` 的隐式求根
  （`torch.func.root` 不存在，用 `torch.autograd.functional` 的隐式微分或定点迭代 + `jacrev`）。
- 接触：半光滑化 `δ ← softplus(δ, β)`，随步长自适应；配事件检测（接触生灭）避免 smearing。
- 双精度优先（CUDA 上 float64 慢但必需；关键量级是 1e-6）。
- 验收：Jacobian vs 有限差分 <1e-6；复现 S1 轨迹（1e-6）。

## 4. S3 —— GPU 批量

- 维度：`[case, axle, patch, sample]`。RHS 张量化后 `vmap` 掉 case 维。
- 目标：100 个参数组合（支撑刚度 10 × 磨耗 10）5 min 内完成。
- 显存：单工况状态 70 维 × 2401 采样 × float64 ≈ 1.3 MB，100 工况 ≈ 130 MB，8 GB 够。

## 5. S4 —— 伴随反演与不确定度

- 目标量：`θ = {轨下支撑刚度 k_s, 扣件失效指标, 心轨/翼轨磨耗 Δz, 轨距偏差 Δy, μ}`。
- 观测量：轮轨力、轮对加速度、轨腰应变（后续）。
- 方法：`L(θ) = Σ ||y_obs − y(θ)||²_W`；`dL/dθ` 由可微正向 + 伴随一次拿到；
  L-BFGS 或 Gauss–Newton；后验用 Laplace 近似（Hessian 由 `jacrev(jacrev)` 或 GGN）。
- 验收：合成数据（已知 θ*）反演误差 <5%；与有限差分基线比 ≥50×。

## 6. 里程碑与工作量

| 周 | 内容 |
|---|---|
| 1 | S1-a 型面样条与拟合器 + 单元测试 |
| 2 | S1-b 扫掠面极值接触 + 与 oracle 的逐点对照 |
| 3 | S1-c 接入求解器，跑辙叉窗与整程，出 S1 验收表 |
| 4–5 | S2 张量化 RHS（先 numpy 向量化，再 torch），Jacobian 校验 |
| 6–7 | S2 隐式积分 + 半光滑接触 + 复现 S1 |
| 8–9 | S3 GPU 批量 + 100 工况验收 |
| 10–12 | S4 伴随 + UQ + 合成反演 |

## 7. 明确不做的事

- 不实现通用多体约束引擎（我们的拓扑固定为 35 DOF 四轴车辆 + 轨道模态，够用）。
- 不追求 Simpack 那样的通用前后处理 GUI；用脚本 + manifest + 报告。
- 不在 S1–S3 阶段碰轨下结构；它属于反演的前置物理（单独一条线）。
- 不再调接触力律常数（已实测排除十种做法）。

## 8. 引用

- [A geometric approach to wheel–rail contact accounting for non-prismatic rails in turnouts (VSD 2025)](https://www.tandfonline.com/doi/full/10.1080/00423114.2025.2589328)
- [半 Hertzian（Sichani/Enblom），KTH 预印本](http://kth.diva-portal.org/smash/get/diva2:953605/FULLTEXT01.pdf)、[道岔专用半 Hertz](https://hal.science/hal-01216416v1/document)
- [Pascal & Soua, 多 Hertz 共形接触（虚拟侵入）](https://www.tandfonline.com/doi/abs/10.1080/00423114.2016.1161201)
- [Fast and Reliable Gradients for Deformables Across Frictional Contact Regimes](https://browse-export.arxiv.org/pdf/2603.16478)
- [Discontinuous variational time integrators for complex multibody collisions (NME)](https://onlinelibrary.wiley.com/doi/abs/10.1002/nme.4764)
- [Coupling surrogate neural networks and classical numerical solvers for non-smooth dynamics with contact](https://hal.science/hal-05385069v1/file/rr_coupling_v1.pdf)
- [A differentiable Boussinesq framework for forward and inverse 3D elastic contact](https://www.sciencedirect.com/science/article/abs/pii/S0955799726003243)
- [Stochastic Galerkin for vehicle–track dynamics with parametric uncertainties](https://ascelibrary.org/doi/10.1061/9780784481257.059)

---

## 状态更新（2026-10-20 晚）

| 阶段 | 状态 | 结论 |
|---|---|---|
| S1-a 解析几何 | **完成** | contact_geometry.py；侵入与 grid 差 0.08 µm，R* 差 6.35%（S1_CHECKPOINT_2026-10-20.md） |
| S1-c 几何策略 | **完成（空结果）** | 亚节点细化把接触点变连续，但 150–250 Hz 份额 73.9%→72.5%、峰值 188.9→195.9 kN → 振铃是**物理的**点接触共振（S1C_GEOMETRY_POLICY_2026-10-20.md） |
| S1-d 分布接触 | **完成（部分有效）** | 条带积分 峰值 -9.4% (188.9 to 171.1 kN)、脱空 14 to 10；主频 158.4 Hz 不动，频率不由接触律决定（S1D_STRIP_CONTACT_2026-10-20.md） |
| S1-e 轨下离散支撑 | **下一目标** | 600 mm 岔枕 -> 162 Hz，落在实测主频窗 138-178 Hz 内；唯一能改频率的建模项 |
n.dref 阻尼过渡；验收 150–250 Hz 份额 <20%、峰值 ≤140 kN |
| S2 可微求解器 | 待做 | 目标：伴随反演；先解析 Jacobian |
| S3 GPU 批量 | 待做 | 目标：单核之外再拿 10–50× |
| S4 反演 + UQ | 待做 | 状态：轨下支撑刚度、心轨/翼轨磨耗下沉、轨距/加宽、扣件失效 |

当前与 Simpack 的差距只剩两点，且都已定量：**194 Hz 振铃带来的 +30 kN 峰值**
（158 vs 128 kN）与**质量模型差 412.5 kg**。

## 状态（2026-10-21 更新，取代上表）

| 项 | 状态 | 证据 |
|---|---|---|
| L1 曲率/斜率预表 | **完成** | `grid_stencil`：几何 107.6 → 83.1 µs，RHS 累计 1582 → 990 µs（−37.5%），回归逐位一致 |
| L2 (s,y) 接触表 | **跳过** | `profiles.py:290` 已对剖面做标量混合 + 站间缓存，表中没有可省的工作 |
| L3 多斑批量化 | **取消** | 多斑尚未成立（单一轨头内就是伪次峰），无可批量对象 |
| 接触阻尼定标 | **完成** | c=3e7 + cap 0.5：571 Hz 振铃消失，主频 57.14 Hz 对 Simpack 57.97 |
| 轨下结构 S1-g | **完成（负结果）** | 加轨道板更平滑（30-60 Hz 4.09 → 2.39 kN rms），不追该频带 |
| S1-f 钢轨梁模态 | **负结果** | 整根轨浮沉模态恒 131.9 Hz，给不出 30-60 Hz |
| S2 可微求解器 | 待做 | 目标：解析 Jacobian → 隐式积分 |
| S3 GPU 批量 | 待做 | 目标：单核之外再拿 10–20× |
| S4 反演 + UQ | 部分 | `inverse/` 已有可辨识性、观测量层、合成反演；实测数据接入已打通常规口径 |

整程当前状态：7/7 门、0 脱空、峰值 89.7 kN（Simpack 134.97）、最小力 37.20（27.67）、
主频 57.14（57.97）、rms 9.13（23.30）、行程 0.641（0.5944）。**差距只剩"我们更平滑"**。

## 状态更新（2026-10-21 夜间第 14 轮）

| 阶段 | 状态 | 实测证据 |
|---|---|---|
| S1 解析接触几何 | **完成**（含分布接触） | 条带积分律 `N=(π/4)E*Σmax(δ,0)Δy` 落地；辙叉窗 188.85 → 171.10 kN、脱空 14 → 10 |
| S1 支撑/轨道 | **完成**（分层轨道任意层数） | `kind="layered"`：L=0 等价 local_compliant（106.90 vs 106.76 kN）、L=1 两层、L=2 加轨道板；柔性扣件 + 钢轨垂向自由度把整程做到 **89.7 kN / 0 脱空 / 7 门全过** |
| S1-g 轨道板连续化 | **负结果，已停** | 加第三层后 30–60 Hz 带 +41% 但峰值/脱空无改善 |
| S2 隐式积分 | **部分**：窗口 1.86×，整程受阻 | 0.05 s 窗口 32.4 → 17.4 s、0.2 s 跨换体 1.50×，物理逐位一致；整车 1.2 s 两种 BDF 均在 t≈0.61 s 报 non-finite（已排除“记忆污染”，指向 `N∝δ^1.5` 在 δ→0 的非光滑） |
| S3 GPU 批量 | 未开始 | 多进程 `--jobs 8` 已实测 8.58× 近线性，可作为 GPU 之前的基线 |
| S4 伴随反演 | 未开始 | 合成反演（高斯‑牛顿 4 次迭代、`rail_k_z` 恢复 +0.01%）已跑通，可辨识性门已落地 |

**下一道门（S2 收尾）**：接触状态事件检测——在 δ→0 之前插入事件点，让积分器不穿越非光滑面；
此门不通则整程继续用 DOP853，只把 BDF 的 1.86× 限定在窗口级实验里，不写进对外结论。
