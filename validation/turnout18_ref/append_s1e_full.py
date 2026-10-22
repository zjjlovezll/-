import pathlib

SECTION = """

---

# 6. 补测：满 1.2 s 全工况（结果反转，必须记录）

`case_Y_full_base.json` / `case_Y_full_support.json`（x_start 13.5 m、1.2 s、2401 采样、
翼轨体 + 曲率刚度 + Hunt-Crossley），两例均 `numerically_checked`、7 门全过：

| 指标 | 基线 | + 支撑柔度 | Simpack |
|---|---|---|---|
| 右轨峰值 | **158.04 kN** | **224.88 kN** | 134.97 kN |
| 最小力 | 3.021 kN | **0.000 kN** | 27.67 kN |
| 脱空采样 | **0 / 2401** | **16 / 2401** | 0 / 2401 |
| 最大总接近量 | 0.294 mm | 0.792 mm | — |
| 最大 Hertz 压入 | 0.294 mm | **0.206 mm** | 0.433 mm（几何侵入） |
| 最大钢轨沉降 | 0 mm | **0.682 mm** | — |
| 轮对垂向行程 | 0.593 mm | 0.952 mm | 0.594 mm |
| 力主频 | 175.8 Hz | 72.5 Hz | 31.7 Hz |
| 150-250 Hz 带 rms | 9.05 kN | **5.93 kN** | 1.09 kN |
| 30-60 Hz 带 rms | 1.67 kN | **3.75 kN** | 4.84 kN |
| 能量变化 | +9788 J | +9833 J | — |
| nfev | 336 185 | 577 637 | — |

**结论：频率对上了、峰值反而变差。** 频谱重心从 175.8 Hz 搬到 72.5 Hz，30-60 Hz 带
从 1.67 涨到 3.75 kN（Simpack 4.84），150-250 Hz 从 9.05 降到 5.93；但峰值 +42%、
出现 16 个脱空采样（集中在 80.326-81.007 m 辙叉融合段）。

**机理（已量化）**：这条柔度是"跟随轮子的静力量"，没有钢轨质量与惯性。给定的接近量下，
载荷被钢轨沉降分掉一部分，于是

- 小接近量时力极小，delta->0 附近更容易断力（16 个脱空采样的来源）；
- 大接近量时载荷被削，尖峰变低（0.05 s 窗口 171 -> 119 kN 就是这一条）。

能量变化两例几乎相同（+9788 vs +9833 J，差 0.5%），所以**不是数值不稳定**，是模型缺惯性。

**正确的做法**：把钢轨沉降做成真正的自由度（钢轨质量 + 扣件刚度 + 阻尼，即已有的
`track_dynamics = local_compliant`，或 SDITT 的两自由度"钢轨-轨枕"），而不是静力串联。
有质量的钢轨不会瞬间落下，才能在削峰的同时保住接触。当前 `support_compliance` 因此
**保持默认关闭**，只作窗口诊断与频谱工具使用。
"""

path = pathlib.Path('validation/turnout18_ref/S1E_SUPPORT_COMPLIANCE_2026-10-20.md')
text = path.read_text(encoding='utf-8')
if '补测：满 1.2 s' in text:
    print('section already present')
else:
    path.write_text(text.rstrip('\n') + SECTION, encoding='utf-8')
    print('appended, chars', path.stat().st_size)
