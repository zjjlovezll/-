# S3 样本批量：theta 敏感度第一测（2026-10-21）

## 生成器与跑通
`validation/crh380a_m/make_sample_fleet.py`：从 `case_inverse_window.json`（20 ms 辙叉窗、51 自由度、
条带积分 + 钢轨垂向自由度）派生四个只改扣件参数的同族算例；四例均 `numerically_checked`、7 门全过。

| 算例 | k_z (N/m) | c_z (N·s/m) | 右轨峰值 kN | 有接触采样 |
|---|---|---|---|---|
| fleet_00_k0.85c0.85 | 4.25e7 | 3.40e4 | 151.6 | 101/101 |
| fleet_01_k1.00c1.00 | 5.00e7 | 4.00e4 | 151.4 | 101/101 |
| fleet_02_k1.15c1.15 | 5.75e7 | 4.60e4 | 151.2 | 101/101 |
| fleet_03_k0.90c1.10 | 4.50e7 | 4.40e4 | 151.5 | 101/101 |

## 结论（负结果，重要）
扣件刚度/阻尼在 ±15 % 内变化，**峰值力只变 0.4 kN（约 0.26 %）**；单调性也不成立
（0.85 档 151.6 → 1.15 档 151.2，变软反而略高）。也就是说：

> **该窗口的“右轨峰值力”对扣件参数几乎没有信息量**，不能作为反演观测量的主特征。

这与早前 `probe_bistability.py` 在窗口 B 上测到“灵敏度≈0”一致，属于同一结论的第二次独立验证。

## 对反演的直接影响
S4 的观测量应改为**整段波形残差**（`inverse/observation.align(strategy=\"station\")` 输出的
`rms`/`channel_metrics`），而不是峰值；这也解释了为什么合成反演里 `contact_c` 被判不可辨识。
下一步：把同一 fleet 的观测量从峰值换成波形 rms、并对照 `identifiability.py` 的列能量，看 k_z 是否恢复可观。

## 环境坑（已固化）
- 算例资产路径相对算例文件所在目录解析 → 派生算例必须与源算例同目录（放子目录报
  `FileNotFoundError: ...\fleet\bodies\main_r0791310.csv`）。
- **不要用 PowerShell `ConvertFrom-Json` 读 manifest**：`asset_hashes` 含反斜杠转义，抛
  `ArgumentException` 并把 200 KB 清单刷满控制台。改用 Python 只取标量（`summary_fleet.py`）。

## 观测量对照：峰值无用，波形可用（决定性）

`validation/crh380a_m/check_fleet_observability.py` 以 `fleet_01`（1.00×）为基准，逐采样比较
`axle1_right_normal_n` 波形：

| 算例 | 峰值 kN | 均值 kN | 波形 rms 差 kN | 相对 |
|---|---|---|---|---|
| fleet_00 (0.85×) | 151.6 | 59.9 | **2.548** | **4.00 %** |
| fleet_01 (1.00×, 基准) | 151.4 | 59.5 | 0 | 0 |
| fleet_02 (1.15×) | 151.2 | 59.2 | **2.206** | **3.46 %** |
| fleet_03 (0.90×/1.10× 反向) | 151.5 | 59.6 | 1.214 | 1.91 % |

同一组算例：

- **用峰值**：±15 % 参数变化 → 0.26 % 差异（不可观测）；
- **用整段波形**：同样变化 → **4.0 % 相对差异**，信息量高 15 倍，且 0.85× 与 1.15× 对称偏离
  （4.00 % / 3.46 %），反向 0.90×/1.10× 因两效应部分抵消而只偏 1.91 %——与物理一致。

## 结论（写进 S4 设计约束）
1. 反演观测量 = **整段波形残差**（`inverse/observation.align` 的 `rms` / `channel_metrics`），禁止用峰值力；
2. 该窗口对 k_z 的波形灵敏度约 `S ≈ 0.27 /单位相对参数`，要求测量噪声 < 2 % 才能辨识；
3. fleet 生成器产生的样本彼此可分辨（4 % ≫ 数值噪声 0），S3 的样本通路成立。

## 定量结论：波形比峰值好 118 倍（可直接写进论文）

`validation/crh380a_m/cmp_observables.py` 用同一组算例（0.85× 与 1.15× 中心差分）构造
`d(观测)/d(ln k_z)` 列向量，再交给 `inverse/identifiability.analyse`：

| 观测量 | 列范数（每 ln 单位） | 1 kN 测量噪声下的 σ(ln k_z) | 折算参数误差 |
|---|---|---|---|
| 峰值力（标量） | 1.347 kN | **0.742** | ±110 %（不可用） |
| 整段波形（101 点） | **158.6 kN** | **0.0063** | **±0.63 %** |

列范数增益 **117.7 倍**；两种情况 `analyse` 都判 `rank=1, identifiable=True`——
**判据本身看不出差别，差别在“同样噪声下参数能定多准”**。这正是此前合成反演里
`contact_c` 被判不可辨识的根源：不是数据不行，是观测量选错了。

设计约束（写入 S4）：观测量用整段波形；若实测噪声 1 kN（CH01 量级），k_z 的理论辨识精度
约 ±0.6 %，远优于工程需要的 ±10 %。

## 判据加固：`resolution` 字段（防止再有人拿峰值反演）

`src/velch/inverse/identifiability.py` 变更：

- `Sensitivity` 新增 `observable: str = "unspecified"`（非空校验）；
- `Verdict` 新增 `resolution: dict[str, float]`（= 1/列范数，即"残差移动一个 sigma 时 θ 变化多少"）
  与 `observable`，`summary()` 会一并打印；
- `analyse()` 新增两条 note：`resolution > 0.1` 时报 "poorly resolved: <参数> (+-X %)"；
  `observable ∈ {peak,max,maximum,scalar}` 时报"单点极值不能作为参数指纹"。

配套测试 `tests/test_identifiability_resolution.py`（9 项）：resolution = 1/列范数、灵敏度加倍则
resolution 减半、峰值观测量被标记、粗分辨率按百分比报出、波形观测量不告警、波形优于峰值 100 倍、
空 observable 被拒、summary 含 observable、`Verdict` 旧构造方式不破。

## 轮 26：用整段波形把两个扣件参数一起反演回来（真动态，闭环）

前面证明了"峰值不可用、波形好 118 倍"。这一轮把闭环做完：

**估计器**（新增 `src/velch/inverse/estimator.py`，9 项测试）
- 参数住在 log 空间（`theta = ln(scale)`，`theta=0` 表示不变），所以尺度天然为正、协方差给出的是相对误差；
- Levenberg-Marquardt：中心差分雅可比（`finite_difference_jacobian`，`step` 是 log 半步长）、
  逐次阻尼调节（拒绝就 ×10、接受就 ÷3）、单步 log 范数上限（`max_step_norm`）、协方差 `sigma^2 (J^T J)^-1`；
- `inverse` 包不导入求解器，只吃一个 `residual(theta) -> ndarray`，依赖方向仍是 `inverse -> case`；
- `Estimate` 带 `scale` / `sigma` / `convergence` / `report()` / `summary()`。

**真动态闭环**（`validation/crh380a_m/inversion_waveform_demo.py`，0.02 s 辙叉窗、101 采样、51 DOF）
- 观测量：`axle1_right_normal_n` 整段波形，噪声 1 kN（正态）
- 真值：`rail_k_z ×1.10`、`rail_c_z ×0.90`；起点取基准值
- 结果（4 步 LM、**30 次正演**）：

| 参数 | 真值 | 反演值 | 误差 | 1 sigma |
|---|---|---|---|---|
| `rail_k_z` | ×1.1000 | ×1.09856 | **−0.131 %** | 1.03 % |
| `rail_c_z` | ×0.9000 | ×0.90317 | **+0.352 %** | 0.87 % |

两个误差都在 1 sigma 内，且 c_z 真的被分出来了——这正是上一轮判据预测的结果（波形 rank 2/2、
cond 1.44；峰值 rank 1/2、cond inf、c_z 分辨率 872 %）。产物 `validation/crh380a_m/inversion_waveform_demo.json`。

**给后续反演的硬结论**
1. 观测量必须是整段波形或频带，否则 c_z 一律不可辨识；
2. 1 kN 噪声下这两个参数的分辨率约 1 %，所以测点噪声要压到 kN 量级才有意义——这与实测
   CH01 的 114.5–119.3 kN（三次变异系数 2.3 %）是一致的量级；
3. 每次 LM 步 4 次正演，1.2 s 整程单次约 850 s → 整程反演必须等 S2（解析雅可比 + 隐式积分）或
   S3（GPU 批量）落地，本轮的 0.02 s 窗口是反演的当前工作尺度。
