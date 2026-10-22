import pathlib

SECTION = """

---

# 7. 决定性结果：钢轨自己带质量和垂向自由度（`local_compliant`）

结论先说：**S1-e 的正确实现不是"静力串联柔度"，而是让钢轨成为带质量的自由度。**
而这条路径**不需要新代码**——`track_dynamics.kind = "local_compliant"` 早就存在，
参数直接从 SDITT `Par_TrackSystem.m`（FT-Modal）取：扣件 `kz = 25e6 N/m / cz = 20e3`
（每个轮下约 2 个扣件 → `50e6 / 40e3`），一个轮看到的有效钢轨质量约 2 m×60 kg/m = 120 kg。

## 7.1 辙叉窗口（0.05 s，x_start 69.0）

| 算例 | 峰值 | 最小力 | 脱空 | 最大侵入 | 轮对行程 | 主频 | 150-250 Hz rms | 30-60 Hz rms |
|---|---|---|---|---|---|---|---|---|
| `out_X_base`（刚体轨道） | 170.86 kN | 0.000 | 10 | 0.155 mm | 0.241 mm | 179.8 Hz | 62.33 | 11.18 |
| `out_X_support`（静力柔度） | 119.17 kN | 0.081 | 0 | 1.227 mm | 0.833 mm | 59.9 Hz | 7.13 | 40.02 |
| **`out_Z_local_rail`（钢轨自由度）** | **122.48 kN** | **5.875** | **0** | **0.101 mm** | **0.357 mm** | **39.96 Hz** | **1.43** | 9.57 |
| Simpack 同段 | 127.84 kN | 26.03 | 0 | 0.433 mm | 0.594 mm | 39 Hz | 1.09 | 4.84 |

## 7.2 满 1.2 s 全工况（2401 采样，与 `350.mat` 同窗口）

| 指标 | 刚体轨道 | 静力柔度 | **钢轨自由度** | Simpack |
|---|---|---|---|---|
| 右轨峰值 | 158.04 kN | 224.88 kN | **123.60 kN** | 134.97 kN |
| 最小力 | 3.021 kN | 0.000 kN | **16.76 kN** | 27.67 kN |
| 脱空采样 | 0 / 2401 | 16 / 2401 | **0 / 2401** | 0 / 2401 |
| 最大总接近量 | 0.294 mm | 0.792 mm | **0.225 mm** | — |
| 轮对垂向行程 | 0.5933 mm | 0.9521 mm | **0.5954 mm** | **0.5944 mm** |
| 力主频 | 175.8 Hz | 72.5 Hz | **36.65 Hz** | 31.65 Hz |
| 150-250 Hz 带 rms | 9.054 kN | 5.926 kN | **0.577 kN** | 1.088 kN |
| 30-60 Hz 带 rms | 1.673 kN | 3.753 kN | **2.844 kN** | 4.839 kN |
| 均值 | 59.689 kN | 59.615 kN | 59.567 kN | 60.153 kN |
| 状态 | numerically_checked | numerically_checked | numerically_checked | reference |

## 7.3 三条可核验的结论

1. **轮对垂向行程 0.5954 vs 0.5944 mm，差 0.17%**——这是全项目第一次在这个量上
   与 Simpack 达到千分级一致（在此之前是 200× 偏差）。
2. **力主频 36.65 vs 31.65 Hz**，量级对上；150-250 Hz 的伪振铃从 9.05 降到 0.577 kN，
   已低于 Simpack 的 1.088 kN（略微过阻尼，`cz` 可取 20e3 而不是 40e3 再试）。
3. **峰值 123.60 vs 134.97 kN（-8.4%）**，且不脱空、最小力 16.76 kN；
   侵入 0.225 mm 反算 `C = N/delta^1.5 = 1.16e11`，与曲率刚度 1.1267e11 自洽。

## 7.4 为什么静力柔度失败、钢轨自由度成功

静力串联柔度把 "钢轨下沉" 当成位置的瞬时函数：给定接近量，钢轨立刻让位，
小接近量时力被吃掉 → 更容易断力（满 1.2 s 出现 16 个脱空采样，集中在 80.326-81.007 m）。
带质量的钢轨不能瞬间让位，于是
- 削峰依旧（载荷被钢轨惯性分担），
- 但 δ->0 附近仍有 16.76 kN 的残余支撑，不会脱空，
- 且 600 mm 扣件间距的周期激励以 39 Hz 的形式出现，而不是在接触弹簧上激出 175 Hz 的伪振铃。

这些定性说法在两张表里都能核验：静力柔度的 `max_settle_mm` 有 0.682 mm 而
`max_hertz_mm` 只有 0.206 mm（力被沉降吃掉）；钢轨自由度的 `max_settle_mm` 为 0
（沉降进了状态量，不再从接近量里扣），`max_hertz_mm` 回到 0.225 mm。

## 7.5 复算命令

```
python -X utf8 -m velch run-vehicle validation/crh380a_m/case_Z_local_rail.json --output validation/crh380a_m/out_Z_local_rail
python -X utf8 -m velch run-vehicle validation/crh380a_m/case_Z_full_local_rail.json --output validation/crh380a_m/out_Z_full_local_rail
python -X utf8 validation/crh380a_m/cmp_support_ab.py     # 窗口三例 + 参考值
python -X utf8 validation/crh380a_m/cmp_s1e_full.py       # 满 1.2 s 四行表
```
"""

path = pathlib.Path('validation/turnout18_ref/S1E_SUPPORT_COMPLIANCE_2026-10-20.md')
text = path.read_text(encoding='utf-8')
if '钢轨自己带质量和垂向自由度' in text:
    print('section already present')
else:
    path.write_text(text.rstrip('\n') + SECTION, encoding='utf-8')
    print('appended, bytes', path.stat().st_size)

changelog = pathlib.Path('docs/CHANGELOG_DOCS.md')
body = changelog.read_text(encoding='utf-8')
row = ('S1-e 轨下离散支撑（600 mm 岔枕）：窗口峰值 170.9 -> 119.2 kN、脱空 10 -> 0、180 Hz 振铃 -89%；'
       '但满 1.2 s 反转为 158 -> 225 kN、16 脱空采样，缺钢轨惯性（默认关闭）')
replacement = ('S1-e 轨下离散支撑（600 mm 岔枕）：**正确实现是钢轨带质量的自由度，不是静力串联**。'
               '`local_compliant` + SDITT 扣件 kz=50e6/cz=40e3 + 钢轨 120 kg：'
               '满 1.2 s 峰值 158.04 -> **123.60 kN**（Simpack 134.97）、脱空 0、'
               '轮对行程 0.5954 vs Simpack 0.5944 mm（差 0.17%）、主频 36.7 vs 31.7 Hz、'
               '150-250 Hz 振铃 9.05 -> 0.58 kN（Simpack 1.09）。静力串联柔度（`support_compliance`）'
               '削峰但会脱空，保持默认关闭')
if row in body:
    changelog.write_text(body.replace(row, replacement), encoding='utf-8')
    print('changelog row replaced')
else:
    print('changelog row not found (left unchanged)')
