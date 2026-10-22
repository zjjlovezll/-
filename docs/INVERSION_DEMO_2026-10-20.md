# 合成反演：可辨识性门 + 高斯‑牛顿（2026-10-20）

第一次把求解器当正演模型接进估计器。**数据是合成的**：先由同一模型在已知参数下跑一遍，
再让估计器从"测量"里把它们找回来。这样做的唯一目的是把估计器的问题和模型误差分开——
真数据反演必须等这一步干净之后再做。

复现：`python -X utf8 validation/crh380a_m/demo_inversion.py`（39 次正演，约 4 分 40 秒）

## 设置

| 项 | 值 |
|---|---|
| 算例 | `case_inverse_window.json`，由 `case_Z_local_rail.json` 派生 |
| 工况 | x_start 69.0 m，0.02 s（101 采样，前轴 79.0→80.94 m，含辙叉交接） |
| 自由度 | 51（35 车 + 8 钢轨 ×2 侧） |
| 观测量 | `axle1_right_normal_n`（σ=2 kN）、`axle1_z_m`（σ=20 µm） |
| 未知量 θ₀ | `rail_templates[0].support.k_z_n_m`，基准 5.0e7 N/m |
| 未知量 θ₁ | `contact.normal_damping_n_s_m_1p5`，基准 1.0e6 |
| 真值 | θ = (+0.30, −0.40)，即扣件软 30 %、接触阻尼小 40 % |

## 第一步：可辨识性（在估计之前）

中心差分 Jacobian（2 参数 → 4 次正演），加权后做 SVD：

```
rank 1/2  cond inf
  rail_k_z      sens 1.5e+07   identifiable  (observed)
  contact_c     sens 5.83e+03  NOT identifiable  (column energy far below the others)
  note: rank 1 < 2: parameters trade off along the null space
  note: condition number inf: normal equations dominated by rounding
```

结论：这两条通道**看不见接触阻尼**——它的列能量比刚度低 4 个数量级，两者在残差空间里
几乎平行。于是 `contact_c` 被**移出优化向量**，不是给它编一个数。

这一步花 7 次正演，比一次迭代还便宜；省下的是"估出一个 66 % 错的值还配一个假置信区间"。

## 第二步：Levenberg 阻尼高斯‑牛顿

| 迭代 | 代价 Σ(r/σ)² | θ (rail_k_z, contact_c) |
|---|---|---|
| 1 | 5 725 | 0.000, 0.000 |
| 2 | 230.3 | 0.233, 0.000 |
| 3 | 35.87 | 0.297, 0.000 |
| 4 | 35.64 | **0.300**, 0.000 |

4 次迭代、步长 < 1e-3 收敛，代价下降 99.4 %。

## 结果

| 参数 | 真值 | 恢复值 | 误差 |
|---|---|---|---|
| `rail_k_z` | 6.500e7 N/m | **6.50034e7** | **+0.01 %** |
| `contact_c` | 6.000e5 | 1.00e6（未估，被门剔除） | +66.7 %（已知且已声明） |

`contact_c` 那 66.7 % 不是估计器的失败，是**数据没有信息**的如实结果：即使模型里它错了
40 %，这两条通道也分辨不出；残留代价 35.64 就是它在残差里留下的地板。

## 三条可复用的结论

1. **可辨识性门必须在估计之前**，而且很便宜（7 次正演）。它把"参数不可观"和"当前工况不
   激励它"分开，避免优化器在零空间里乱走。
2. **合成反演是估计器的单元测试**：0.01 % 的恢复精度说明正演、残差装配、Jacobian、阻尼
   策略都没有系统偏差，剩下的误差才轮到模型与数据去解释。
3. **本例的正演在辙叉交接处是双稳的**：把接触搜索的离散相位改半个格（0.25 mm）就能把
   峰值从 170.9 kN 翻到 1 447 kN（见 `SPEED_2026-10-20.md` 的负结果）。所以反演窗口
   要么避开交接的亚区段，要么用多条工况把双稳平均掉——这是下一步设计观测方案时必须先
   回答的问题。

## 产物

- `validation/crh380a_m/demo_inversion.py`、`case_inverse_window.json`、`inversion_demo.json`
- `src/velch/inverse/identifiability.py`（`Sensitivity`/`analyse`/`finite_difference_jacobian`）
- `src/velch/case/spec.py`（`CaseSpec`/`ParameterSpec`，θ 不进 `VehicleCase`）
- `tests/test_identifiability.py`（8 项）
