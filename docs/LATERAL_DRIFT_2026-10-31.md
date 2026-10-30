# M2 时程：整车横向游走 0.73 mm/0.40 s，源头是 +718 N 的净横向力（2026-10-31）

B047 退役之后 M2 只剩时程问题。本轮用**已归档的 0.40 s 运行**（`straight_one_set-080.00kmh-0.4000s-500us-8886e594`，801 帧、七门 7/7）读四个轮对的横向位移，再把归档缺的横向力通道补上，量出漂移的来源。

## 一、四个轮对一起走，不是转向架失稳

`scripts/s106_lateral_drift.py`（只读归档，不新跑仿真）：

| 轮对 | y 起点 (mm) | 漂移 (mm) | max\|y\| (mm) | 斜率 (mm/s) |
|---|---|---|---|---|
| wheelset1 | 0.0000 | **+0.7128** | 0.7128 | 1.782 |
| wheelset2 | 0.0000 | **+0.7305** | 0.7305 | 1.826 |
| wheelset3 | 0.0000 | **+0.6947** | 0.6947 | 1.737 |
| wheelset4 | 0.0000 | **+0.6937** | 0.6937 | 1.734 |

四条同号、量值只差 **0.037 mm**（5 %），斜率一致到 0.09 mm/s ⇒ 这是**整车横向平移**，不是某个转向架/轮对的蛇行。历史 1.6 s 在 `x=67.03 m` 触发 `graph slope limit` 时"导向轮对横向游走"的说法要按这条改口径。

**判据（预注册在脚本 docstring）的诚实结果**：

| 门 | 判据 | 实测 | 结论 |
|---|---|---|---|
| L1a 幅值 | `|dy| ≤ 1 mm` | 0.7305 mm | PASS |
| L1b 形态 | 不得单调漂移 | 0 → +0.73 mm 单调 | **FAIL** |
| L2 力—位移同号 | `sign(dy) = sign(ΣFy)` | 归档里没有 ΣFy 通道 | **不可测** |

L2 判不了不是我分析得不够，而是**数据契约缺一列**：`series.npz` 只存 `normal_force_n` 与 `body_normal_force_n`，没有 `wheel_force_y_n`。所以本轮同时把通道补上。

## 二、补通道之后：净横向力 +718 N

`s99_run_archive.py` 新增 `arrays["lateral_force_n"]`（帧 × 轨，取自每个 `response.wheel_force_y_n`，非承载帧记 0），`meta.json` 的 `python_notes` 同步说明列序。0.01 s 冒烟：

```
keys: ['accelerations','body_normal_force_n','lateral_force_n','normal_force_n','positions','times','velocities']
lateral_force_n (frames, rails) = (21, 8)
t0 per rail: +1490.4 +1490.4 +1490.4 +1490.4 -1310.8 -1310.8 -1310.8 -1310.8
```

四条左轨 **+1490.4 N**、四条右轨 **−1310.8 N**，净和 **+718.4 N**。

**这解释了两件事**：

1. **为什么对称直向也算不零**：左轨 `N·n_y = 60.15 kN × 0.02458 = +1478 N` 与右轨 `−1478 N` 本该抵消，实测却差 14 %——左右两侧的切向贡献不相等（左 +12 N、右 +167 N），即**蠕滑在两侧不对称**。
2. **为什么整辆车一起走**：`a = 718.4 / 49 040 = 0.0146 m/s²`，0.40 s 自由加速给 `½at² = 1.17 mm`；实测 0.73 mm，差额由一系横向刚度吸收（`3.0e7 N/m`）。外推到历史那次 1.6 s：`½at² = 18.7 mm`——足以把轮对推到轨距角并触发 `graph slope limit`。

## 三、下一轮判据（写死，不许事后改）

**诊断目标**：718 N 从哪来。三个候选，都可在座椅态一次判开：

| 候选 | 判据 |
|---|---|
| A 轮断面未按侧镜像（左右都用 `y_sign=+1`） | 左右接触点的**本征斜率**应互为相反数；实测 tilt 已是 ±0.02458，故本项只查 `wheel_profile(side, y_sign)` 的四个调用参数 |
| B 踏面左右不对称（`8.03` vs `−7.93` mm 内移） | 把右轨断面**镜像**后重测，`|lever−冠|` 左右差应从 0.10 mm 降到 ≤0.02 mm |
| C 蠕滑不对称（自转方向与镜像不匹配） | 把四个轮对的 spin 符号与两侧蠕滑逐项打印；`ΣFy` 应在座椅态 ≤20 N |

**验收门**：① 座椅态 `|净 ΣFy| ≤ 20 N`；② 0.40 s 内四个轮对 `|dy| ≤ 0.1 mm` 且不单调；③ 冻结基线 `UNCHANGED`；④ 不新增任何容差。

## 四、复算

```bash
cd Velch
PYTHONPATH=src python -X utf8 scripts/s106_lateral_drift.py --write   # -> ../scratch/s106/lateral_drift.json
PYTHONPATH=src python -X utf8 scripts/s99_run_archive.py --case vehicles/turnouts/CN60-1100-1_18/cases/straight_one_set.json \
    --speed-kmh 80 --duration 0.01 --note smoke=lateral-channel
```
