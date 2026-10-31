# 交付总表：能反演什么、到哪一步、什么做不到（2026-10-31，第 286 轮 / M9 第一版）

> 这一轮不跑新的仿真。它把 251–285 轮的全部预注册判决收进一张**可机读**的表，
> 并让"结论"与"存档"不可能悄悄分家：所有数字都从 `reports/load_split_inversion_2026-10-31/*.json`
> 读出来，`scripts/s143_deliverable_summary.py` 重算一遍；有测试比对两者。

## 一、判决总表（20 项，状态只用 PASS / FAIL / EXCLUDED 三个词）

| 项 | 状态 | 说明 |
|---|---|---|
| `onset_resolution` | **PASS** | 降低值开始点随幅值单调，一帧 11.11 mm 折 **1.4–4.7 µm** |
| `shape_collapse` | FAIL | 起始站位不随 σ/中心塌缩（σ 4× 只动 33 mm，中心 ±1 m 只动 67 mm） |
| `lateral_observability` | FAIL | 可辨识横向宽度 **4 mm**（模型预测 6.9/7.7 mm，两个都不成立） |
| `joint_inversion` | PASS | 单凸起两参数拟合：5/9 档全门通过（p95 1.4–7.7 µm） |
| `holdout` | FAIL | 幅值留出 +8.5 %、p95 15.99 µm 过绝对门但相对门 3.22 % 不过；位置留出全破 |
| `two_peak_fit` | PASS | 两峰：57.611/59.404 m、52.2/32.0 µm、p95 **2.63 µm** |
| `peak_count` | FAIL | 实测律上 BIC：两峰数对（2），三峰数成 **5** |
| `composable_forward` | FAIL | 可复合正演数对（3）但幅值偏小、p95 23.56 µm |
| `two_stage` | **PASS** | 两段式：三峰 58.491/59.513/60.555 m、43.3/33.2/20.9 µm、p95 **3.37 µm** |
| `random_profile` | FAIL | 六分量随机：p95 **115.07 µm**、corr 0.066 |
| `floor_diagnosis` | PASS | 表示误差不是量程钳位（钳位 0.0 %，量程内外逐位相同） |
| `law_resolution` | PASS | 也不是查表插值分辨率（两条预测都为假） |
| `width_coordinate` | EXCLUDED | 接触半宽不是缺失坐标（相关 −0.447，留出只降 9.2 %） |
| `two_body_station` | EXCLUDED | 逐站点接触：floor 0.3132、偏置 −0.2220 |
| `residual_dynamics` | EXCLUDED | 竖向动力学排除（89 % 能量 <20 Hz、滞后 0.00 mm） |
| `strip_stiffness` | EXCLUDED | 条带积分：floor 0.1912、偏置 −0.0768，仍差前置门 10 倍 |
| `solver_calibration` | **PASS** | 座椅份额 = 滚动份额（中位差 **0.0022**，9/10 在 0.02 内） |
| `rolling_slope` | FAIL | 座椅斜率 ≠ 滚动斜率（**0.48** / **0.95**，且不是常数） |
| `band_assembly` | PASS | 换横向位置后同一套拟合仍成立（p95 4.18 µm） |
| `band_surface` | **PASS** | 两趟拼成单值带面，列间 **3.05 µm** |

```
counts: PASS 9 / FAIL 7 / EXCLUDED 4
```

## 二、Ω_obs（按用户 2026-10-31 定案："只要光带"）

| 量 | 值 | 出处 |
|---|---|---|
| 轨头宽度 | 61.46 mm（5 mm 深）/ 37.15 mm（1 mm 深） | `lateral_coverage` |
| 九档轨距下光带并集 | **58.4 %** / **69.9 %** | 同上 |
| 能起跑的档位 | **6/9**（−6 / −4 / +2 在模态沉降后座椅不可持续） | `seat_after_settle` |
| 单趟光带 | ≈16 mm（接触斑本身，漂移 0.14 mm） | `lateral_coverage` |
| 两趟拼成带面 | 20.6 mm / 37.15 mm = **55.4 %**，列间 3.05 µm | `band_surface` |

**缺口在冠外侧且不可达**：按 1.28 mm/mm 的杠杆，把接触推到更外侧需要再开约 **+14 mm** 轨距（δ≈+22 mm），
超出道岔结构。这不是算法问题，是**几何**问题。

## 三、能说与不能说（交付口径）

**能说**（都在 80 km/h、直向、一组模型、A/B 级证据上）：
1. 降低值/走行面**在坡道区（≈57.7–58.4 m 起）能被定位到 9–55 mm**、幅值到 0.17–1.5 %，剖面 p95 **2.6–4.2 µm**；
2. 含**两峰、三峰**（峰数未知时由两段式数出）的剖面能同时定量；
3. **换横向位置**（+4 mm 轨距）同一套拟合仍成立，两趟可拼成**单值带面**（列间 3.05 µm）；
4. 幅值 ≥50 µm 可定量、<50 µm 无此观测量；横向可辨识宽度 4 mm、单趟光带 16 mm。

**不能说**：
1. **随机宽谱不可反演**（p95 115 µm、corr 0.066）——四个独立读数指向正演：实测律叠加不复合（0.0133→0.1314）、
   座椅导数不对且随站变（0.48/0.95）、两族闭式接触模型都过不了无凸起趟、竖向动力学已排除；
2. **Ω_obs 到不了轨头 90 %**（58.4 % / 69.9 %），且这是几何限制；
3. **没有 C 级真值**：算例几何本身由同一批 PRR 断面建成，与 PRR 逐点对照是**自洽**，不是独立验证。

## 四、复算

```bash
cd Velch
python -X utf8 scripts/s143_deliverable_summary.py --write
python -X utf8 -m pytest tests/test_deliverable_summary.py -q
```

产物：`reports/surface_deliverable_2026-10-31/deliverable_summary.json`（20 项状态 + 覆盖率 + 带面 + 未达成清单）。
