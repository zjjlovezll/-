# S2 完成：隐式积分跑通，整程 8.4× 提速且物理不变

> 日期：2026-10-22
> 前置：`S2_HANDOFF_2026-10-21.md`（诊断与两条路线）、`S2_IMPLICIT_2026-10-21.md`（三次自我更正）

---

## 1. 结论（验收四门全过）

| 门 | 要求 | 实测 | 判定 |
|---|---|---|---|
| 整车 1.2 s 跑完 | `numerically_checked`、7 门全过 | BDF+解析，两个容差都跑完 | ✅ |
| 冻结 oracle 不变 | 峰值 89.7 kN / 0 脱空 / 行程 0.593 mm | **89.67 kN / 0 脱空 / 0.641 mm**（与 DOP853 基线逐项相同） | ✅ |

> **口径更正**：交接文档把 `行程 0.593 mm` 与 `峰值 89.7 kN` 并列，但这两个数来自不同目录。
> `s2_travel_scan.py` 扫遍 `out_*`：`out_final_full1p2s` = 0.593 mm / **158.04 kN**（旧基线），
> `out_full12_cap05` = **0.641 mm / 89.68 kN**（当前冻结基线）。两者不可混用；本报告全部以
> `out_full12_cap05` 为准。
| 墙钟 ≤ 1/3 DOP853 | ≤ 280 s | **101.6 s（≈850 s 的 1/8.4）** | ✅ |
| 全仓测试 | 全过 | **325 passed** | ✅ |

对照（同一算例 `case_full12_cap05.json`，整车 1.2 s，2401 采样）：

| run | 峰值 kN | 最大侵入 µm | 脱空 | 轮对行程 mm | 墙钟 |
|---|---|---|---|---|---|
| DOP853（冻结基线） | 89.68 | 551.89 | 0 | 0.641 | ≈850 s |
| **BDF + 解析雅可比 rtol=1e-5** | **89.67** | **551.89** | **0** | **0.641** | **101.6 s** |
| BDF + 解析雅可比 rtol=1e-6 | 89.67 | 551.89 | 0 | 0.641 | 129.7 s |

另注：Simpack 同工况 **85.08 s / 32 线程**；Velch 现在 **101.6 s / 单核**，单核口径已同量级。

---

## 2. 根因：不是"发散玄学"，是雅可比少了一层物理

交接文档把失败点定在"内层 Newton 用差分雅可比无法收敛"。这一轮把它做成了可判定的缺陷：

用 `validation\crh380a_m\s2_gate_columns.py` 逐列对拍中心差分，得到指纹——

```
col  2 axle1_roll   8.26e+06  6.91e-02  BAD
col  6 axle2_z      1.12e+07  6.70e-02  BAD
col 36 axle1_left_z 1.16e+07  6.46e-02  BAD
col  0 axle1_y      3.10e+05  4.41e-02  BAD
col 28 carbody_z    1.45e+02  2.0e-10   ok
```

**错列恰好是 4 个轮对的 `y/z/roll` + 4 根轨的 `y/z`（28/51），转向架、车体、`yaw` 精确到 1e-11。**

被排除的假设（都做了实验，不要再走）：
- 串联柔度因子：`support_compliance=None`、`track_kind=local_compliant`、扣件 k_z=5e7 —— 轨 z 是自由自由度，沉降不是算例级柔度；
- 力律不连续：`N(δ)` 连续单调（交接文档 §4.4）；
- 稀疏模板：稠密同样发散；
- 右端有状态：`check_purity.py` 三项全零。

真正的缺项，文献里是标准构件：接触约束雅可比必须带**型面在接触点处的斜率** `f'`、`g'` 与 `roll` 的 `cos φ` 因子（见 "High Speed Railway Track Dynamics" 的 `C_q^{wr}` 显式形式）。我们用的是**冻结角度的单一力臂**。

更具体地说，本项目默认 `normal_policy="strip_integral"`，法向力是**整条啮合带的积分**，所以

```
δᵢ = (z_rail(yᵢ) − z_wheel(yᵢ))·(1+s²)^(−1/2)
N  = ¼πE*ΣδᵢΔs
dN/dq = ¼πE*Δs · Σ_engaged ∂δᵢ/∂q
```

`dN/dq` 是**带内平均**的深度梯度（0.937× 最深条带的梯度 —— 正是那个均匀 6.7 % 指纹），而不是"最深点的力臂"。

---

## 3. 改动（只动雅可比，不动物理）

| 位置 | 内容 |
|---|---|
| [contact.py:172](F:\ai道岔状态反演辨识\Velch\src\velch\contact.py#L172) | `ContactPartials`：发布 `dF/dq`、`dlever/dq`、`dnormal_slope/dq`、`d(rail_dz_ds)/dq`，各 5 个模式（轮 y/z/roll、轨 y/z） |
| [contact.py:817](F:\ai道岔状态反演辨识\Velch\src\velch\contact.py#L817) | `_segment_slope`：分段线性型面的精确斜率（`np.gradient` 会把 0.5 mm 条带网格抹平，引入 4.7e-3 误差） |
| [contact.py:830](F:\ai道岔状态反演辨识\Velch\src\velch\contact.py#L830) | `_strip_functional_partials`：上面的带内平均推导 |
| [contact.py:946](F:\ai道岔状态反演辨识\Velch\src\velch\contact.py#L946) | `find_strip_contact(..., partials=True)`：按需装配 |
| [jacobian.py:314](F:\ai道岔状态反演辨识\Velch\src\velch\jacobian.py#L314) | `depth_gradient = (dF/dq)/elastic_slope`，`normal_dq = depth_slope·depth_gradient` |
| [jacobian.py:330](F:\ai道岔状态反演辨识\Velch\src\velch\jacobian.py#L330) | 补 `rate_slope·(d_approach @ mode_rows)`：阻尼通道的坡度项 `travel·rail_dz_ds·n_z` |
| [jacobian.py:378](F:\ai道岔状态反演辨识\Velch\src\velch\jacobian.py#L378) | `dJ/dq`：力臂随质心平移（roll/spin 行）与法向随拱形冠部的转动 |

安全性：`contact_partials` 默认 **False**，DOP853 路径根本不装配它；实测开启前后 **力逐位相同（max|Δ|=0.0）、几何逐位相同**。

---

## 4. 复现

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 validation\crh380a_m\s2_analytic.py gate          # 6 个时刻全 PASS，坏列 0
python -X utf8 validation\crh380a_m\s2_analytic.py matrix --duration 0.05
python -X utf8 validation\crh380a_m\s2_full.py                    # 整车 1.2 s，BDF+解析
python -X utf8 validation\crh380a_m\s2_accept.py                  # 与冻结 DOP853 逐项对照
python -X utf8 -m pytest tests -q --basetemp F:\velch_tmp\pytest  # 325 passed
```

## 5. 仍然已知的近似（不隐瞒）

1. **`dC/dq` 未微分**：`δ=(N/C)^(2/3)` 的精确式含 `dC/C`，实现用了弹性力梯度，丢掉的那部分在辙叉站位约 4.5e-6（低于 1e-5 门但不为零）。
2. **移动边界项**：只覆盖均匀网格 + `strip_min_depth_m=0` 的路径；带触界、正啮合阈值、`cached_grid` 或 point/patch/spline 策略会回落到旧的冻结角度形式（`partials=None`），此时精度回到 6.9e-2 级（仍在收敛域内，只是 Newton 退化为线性）。
3. **最差门残差** 3.31e-8（t=0.70，阻尼坡度项那条）。
4. 墙钟 101.6 s 仍略高于 Simpack 85.08 s，但 Simpack 用 32 线程；单核口径已 8.4× 快于自研显式积分。
