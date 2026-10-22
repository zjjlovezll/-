# 阶段②：钢轨模态扩阶（60 → 320 阶）对接触力频谱的影响

日期：2026-10-21　目标：goal-e940d288 阶段②

## 1. 做法

同一里程窗、同一接触律、同一车辆，**只换轨道模型**：

| 算例 | `track_dynamics` | DOF | 模态频率范围 |
|---|---|---|---|
| `case_thru_Z_local_rail_0p05s.json` | `local_compliant`（单自由度等效柔度） | 51 | — |
| `case_thru_modal60_0p05s.json` | `modal` + `track_modes_turnout_60.json` | 95 = 35+60 | 131.93–156.00 Hz |
| `case_thru_modal320_0p05s.json` | `modal` + `track_modes_turnout_320.json` | 355 = 35+320 | 131.93–2717.91 Hz |

模态文件由 `build_rail_modes.py` 生成（欧拉-伯努利梁，EI=6.884e6 N·m²、μ=60.64 kg/m、扣件 0.6 m/25e6 N·m⁻¹、自由端、质量归一、模态阻尼 10%，251 个站位）；换轨由 `make_modal_variant.py` 完成，只改 `track_dynamics` 并把状态补零到 `35+mode_count`，其余块原样复制。

三次运行均 `result_status = numerically_checked`，`physics_validation_status = unvalidated_against_measurement_or_Simpack`，8 个轨斑、30 个连接器。

## 2. 结果（前轴右轨法向力，0.05 s 窗，350 km/h）

| 轨道模型 | rms kN | 主频 Hz | 30–60 | 150–250 | 250–400 | 400–800 | 峰值 kN | 谷值 kN | 脱空 |
|---|---|---|---|---|---|---|---|---|---|
| 单自由度柔度 | 0.788 | 540.0 | 0.154 | 0.082 | 0.086 | 0.749 | 61.79 | 56.63 | 0 |
| 模态 60 阶 | 5.869 | 200.0 | 1.103 | 5.011 | 0.447 | 2.539 | 77.95 | 46.05 | 0 |
| 模态 320 阶 | 7.355 | 200.0 | 2.615 | 5.670 | 0.883 | 2.613 | 80.67 | 47.19 | 0 |

（各频带为该带内谱分量的 rms，kN。Simpack 同窗对照：rms 23.30、主频 57.97、30–60 = 14.84、150–250 = 4.04、250–400 = 2.33。)

## 3. 结论

1. **换成梁式模态轨道本身就改变量级**：rms 0.788 → 5.869 kN（7.4×），150–250 Hz 带 0.082 → 5.011 kN（61×）。单自由度等效柔度把扣件间距引起的周期性完全抹平了，这正是文献里"离散支承才有 30–60 Hz 以上的轨面波动"的那部分。
2. **60 → 320 阶：低频段显著变化，400–800 Hz 几乎不变**。
   - rms +25.3 %（5.869 → 7.355）
   - 30–60 Hz +137 %（1.103 → 2.615）
   - 250–400 Hz +97.5 %（0.447 → 0.883）
   - **400–800 Hz 仅 +2.9 %（2.539 → 2.613）**
   - 主频仍 200 Hz，峰值 77.95 → 80.67 kN，两种截断都无脱空。
3. 也就是说，**"必须 ≥300 阶才能覆盖 400–800 Hz"这个前提在本算例上不成立**：400–800 Hz 的能量来自接触律与几何，不来自模态截断；扩阶真正补的是 30–400 Hz。这一点对后续决定模态规模很关键——320 阶把 DOF 从 95 抬到 355（3.7×），换来的是低频段修正，不是高频段。

## 4. 复现

```powershell
cd F:\ai道岔状态反演辨识\Velch\validation\crh380a_m
python -X utf8 build_rail_modes.py --max-hz 400 --limit 60 --out track_modes_turnout_60.json
python -X utf8 build_rail_modes.py --max-hz 4000 --limit 320 --out track_modes_turnout_320.json
python -X utf8 make_modal_variant.py case_thru_Z_local_rail_0p05s.json case_thru_modal60_0p05s.json --modal-file track_modes_turnout_60.json
python -X utf8 make_modal_variant.py case_thru_Z_local_rail_0p05s.json case_thru_modal320_0p05s.json --modal-file track_modes_turnout_320.json
cd ..\.. ; python -X utf8 -m velch run-vehicle validation\crh380a_m\case_thru_modal320_0p05s.json --output validation\crh380a_m\out_thru_modal320
cd validation\crh380a_m ; python -X utf8 cmp_modal_spectra.py out_thru_0p05s out_thru_modal60 out_thru_modal320
```

## 5. 限制与待办

- 模态集合**高度简并**（前 6 阶都是 131.93 Hz），因为 0.6 m 等间距、等刚度扣件；真实道岔变刚度支承会解除简并，尚未引入。
- 梁模型只有垂向弯曲（`phi_y = 0`），无扭转/横向，故横向力谱不可比。
- 320 阶仍是截断；若要 800 Hz 以上可信，需检查最高阶频率与接触带宽的比值（当前 2717.91 Hz / 800 Hz ≈ 3.4）。
- 下一阶段（③效率对标）直接用 `modal320` 与 SDITT（6204 模态、6897 节点）对照 DOF、每步右端耗时、步数、墙钟。
