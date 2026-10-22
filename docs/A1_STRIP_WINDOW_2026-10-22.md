# A1：条带接触窗（bounded strip patch）

日期 2026-10-22　分支 goal-ac4fccd8 A1　结论：**机制不成立，默认不启用**（但修掉了一个真 bug）

## 1. 动机

`find_strip_contact` 在**整个轮/轨重叠带**上积分 `N = (π/4) E* Σ max(δ,0) Δy`。轮缘槽、台肩让位槽、心轨低头区只要被压到就会贡献法向力，并把报告接触点拖到槽里 —— 602/596 kN 与 0.30 mm 抬升补丁都源于此。A1 的想法是：只在实际承载的那一小段上积分。

## 2. 实现

```python
ContactParameters(
    normal_policy="strip_integral",
    strip_half_width_m=0.005,        # 与 strip_center_policy="deepest" 配合：定宽窗
    strip_center_policy="run",       # 自适应：只保留最深条带所在的连续啮合段
)
```

- `strip_center_policy="deepest"`：窗心取全重叠带上最深条带的位置（无种子时自举），有种子时跟随上一接触点（对齐 vendor `cont_searchdeltay` 的“斑不横跳”）。
- `strip_center_policy="reference"`：窗心取钢轨参考面 `rail_y_m`（即轨顶基准）。
- `strip_center_policy="run"`：不猜宽度，把重叠网格裁到“含最深条带的连续啮合段”（`find_strip_contact(..., clip_to_engaged_run=True)`）。

## 3. 修掉的 bug：`edge_limited` 把窗边当成几何边

`find_strip_contact` 原来写 `edge_limited = engaged[0] or engaged[-1]`。全重叠积分时这条是对的（重叠带就是几何边界），但一旦窗宽是**建模选择**，窗端点本来就是“斑的边缘”，于是**每一次有界运行都被 `no_edge_limited_active_contact` 门判死**（实测 h2/h5/h10 全部 FAIL，力 131–158 kN 明明已改善）。

修法：只有窗端**真的落在重叠边界上**且啮合时才置位。

```python
edge_limited=bool(
    (engaged[0] and lower <= full_lower + 1e-12)
    or (engaged[-1] and upper >= full_upper - 1e-12)
)
```

回归测试 `Velch\tests\test_strip_window.py`（9 项）：无界仍报边、有界不报窗边、窗内积分为解析值、啮合段裁剪丢掉第二条肩、不同宽度的力关系、窗完全在重叠外返回 None。

## 4. 宽度扫描（`Velch\validation\crh380a_m\ab_strip_window.py`）

算例 `case_frog_N_strip05`，0.05 s 窗，2401→101 采样，右股轴 1 法向力。

| 方案 | 峰值 kN | 谷值 kN | 零载样本 | nfev | 墙钟 s | 七门 |
|---|---|---|---|---|---|---|
| 无界（现状/基线） | 170.860 | 0.000 | 10 | 10 253 | 15.1 | PASS |
| ±3 mm | 116.639 | 6.923 | **0** | 11 081 | 18.0 | PASS |
| ±4 mm | 123.971 | 2.893 | **0** | 12 065 | 18.8 | PASS |
| ±5 mm | 131.066 | 0.094 | **0** | 12 449 | 19.9 | PASS |
| ±6 mm | 157.616 | 0.000 | 10 | 12 629 | 19.0 | PASS |
| ±7 mm | 165.929 | 0.000 | 13 | 12 413 | 18.7 | PASS |
| ±8 mm | 165.359 | 0.000 | 11 | 11 033 | 16.8 | PASS |
| ±10 mm | 165.543 | 0.000 | 11 | 10 253 | 16.1 | PASS |
| 自适应啮合段 | 170.860 | 0.000 | 10 | 10 253 | 15.0 | PASS |

Simpack 同窗参考：右轨 134.97 kN 峰值、27.67 kN 谷值、**从不脱空**。

## 5. 为什么判定不成立

1. **宽度没有可辩护的取值。** 3–5 mm 让脱空消失，6–10 mm 与无界几乎完全一致 —— 转折落在 5/6 mm 之间，那里正是窗开始跨过轮缘槽/让位槽、把第二个非承载面拉进来的位置。拿转折点当物理量就是拟参。
2. **5 mm 比真实赫兹半宽还窄。** 以 `R* = 0.585 m`、`E* = 1.1393e11 Pa`、`N = 60 kN` 反算半轴 `a = (3N R*/4E*)^(1/3) = 6.1 mm` ⇒ 真实斑半宽约 6 mm，落在“仍脱空”的一侧。也就是说**真实斑宽救不了辙叉脱空**，把窗压到 5 mm 是数值正则化，不是物理。
3. **峰值对上了、谷值没对上。** ±5 mm 峰值 131.07 kN 对 Simpack 134.97（−2.9 %），但谷值 0.094 kN 对 27.67 kN —— 仍处于“贴零”状态，只是采样点没落在零上。这是同一条缺陷换了个数值表现。
4. **`reference` 策略直接不可用。** 轨顶参考面是**基准**不是**轨顶**：辙叉段轨顶横向迁移 73 mm（753→826 mm），以参考面为窗心会在 0.9 s 内报 `vertical preload equilibrium failed: no seed converged`。
5. **`run` 策略在辙叉退化为无界。** 实测与基线**逐位相同**（170.860 kN／10 零载／nfev 10 253）—— 辙叉段整个重叠带都 `δ>0`（轮子埋进让位槽），没有“重新啮合边界”可裁。规则本身正确（合成两条肩的用例精确丢掉第二条），但这里需要一个**深度**判据，不是连续性判据。

## 6. 代价（若启用）

有界运行 `nfev` +21 %（10 253→12 449）、墙钟 +32 %（15.1→19.9 s）—— 窗把力分布变平、状态更难收敛，不是免费提速项。

## 7. 判定

- 默认保持 `strip_half_width_m=None`、`strip_center_policy="deepest"`（数值与冻结 oracle 逐位一致，`tests/test_oracle_frozen.py` 守卫）。
- `edge_limited` 修复**保留**（它是真 bug，与窗口方案无关；全重叠路径行为不变）。
- 辙叉脱空的正解仍未找到：需要的是**按轨体分体 + 每体独立接触 + 体间法向连续**（与转辙器双体交接同一件事），不是积分窗整形。

## 8. 顺带确认

- `strip_half_width_m` 必须在 `(0, ∞)` 内有限，`strip_center_policy ∈ {deepest, reference, run}`，均由 `ContactParameters.__post_init__` 校验。
- 有界窗的 `half_width_m` 回报的是**实际啮合宽度的一半**（`engaged_width/2`），不是请求宽度 —— 窄窗若部分未啮合会自动变小。
- `_deepest_depth_y` 自举扫描步长 `max(4·strip_dy_m, 0.2 mm)`，只用来定位，力仍由细条带积分给出。

## 9. 下一项 A3（轨底坡 1:40）受阻的原因

A3 原计划“把 1:40 横坡压平，量化局部倾角对峰值力的贡献”。查过算例口径后确认**不可按算例参数做**：
`case_frog_N_strip05` 的每个站位 profile spec 只有 `{file, format, units, y_sign, y_offset_m, z_sign}`
（实测 `rail_templates[1].bodies[*].stations[*].profile` 全部如此，**没有 roll/cant 字段**），
1:40 是**烘焙在 PRR 型面里**的（设计廓形自带倾斜），不是运行时姿态参数。

因此 A3 只能靠**重新生成型面**（绕轨顶旋转 −atan(1/40) 后重新基准化），这正是历史上两次事故的方向
（“全局 1:40 横坡”曾从 4.09 掉到 2.39 的频带比，`graph_from_points` 绕轨距面旋转曾报 1 930 kN）。
在拿到“旋转后静载/侵入不变”的门之前不做，记为待办而不是本轮结论。

