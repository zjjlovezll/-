# 曲股工况为什么跑不过 81 m：路线的横向速率被当成了横向蠕滑

日期：2026-10-28。对象：18 号道岔曲股（`case_diverging_R1100.json`，导曲线 R = 1100 m，侧向限速
80 km/h），车辆为 35 坐标内联布局 + 8 根弹性轨（共 51 坐标）。

## 1. 先说结论

**目前所有「曲股跑通」的读数都不能当作曲线通过的结果。** 这一轮把它跑长了一点就暴露了：

```
velch.solver.SimulationFailure: graph slope limit at axle1_right/right:main, x=81.289777 m
```

在 `seat_x_start_m = 45`、`x_start_m = 69`、80 km/h、BDF + 解析雅可比的配置下，车辆从 69 m 出发，
只走了 **≈2.29 m**（t ≈ 0.10 s）就被斜率守卫拦下。

那个 `x=81.289777 m` **不是车辆走到的里程**，而是**钢轨站位的里程**：`station_m` 里已经含了该轴的
纵向偏置（1 位轴 +10 m），所以 `81.29 − 69 − 10 = 2.29 m`。这一条我一开始读错成 12.29 m，在本文件
第一次落盘时也是那么写的，这里更正 —— 相差 5.4 倍，而且方向是「更早就失败」。

同一算例只跑 0.08 s（1.78 m）时状态是 `numerically_checked`、七门 7/7（见 §2b），所以之前那批 7/7
**只证明它能起步到守卫之前，不证明它在曲线上**。

## 2. 起步时就已经是错的：横向蠕滑 0.57 m/s

`scripts/s28_curve_contact_table.py` 打印第一帧接触表（t = 0，除自转外状态速度全为零）：

| 接触斑 | 法向力 | 侵入 | `lever_y` | 横向蠕滑 `slip_lat` |
|---|---|---|---|---|
| axle1_left | 57 740.5 N | 61.23 µm | −0.38519 | **+0.5737 m/s** |
| axle2_left | 57 766.6 N | 61.25 µm | −0.44690 | **+0.5232** |
| axle1_right | 无几何 | — | — | — |
| axle2_right | 无几何 | — | — | — |
| axle3_right | **160 554.1 N (2.69×)** | **120.60 µm** | +0.80552 | +0.2205 |
| axle4_right | 61 573.7 N | 65.07 µm | +0.78410 | +0.1700 |

三件事同时不对：

1. **横向蠕滑在 t = 0 就有 0.57 m/s**，而此刻车辆的 `ẏ` 全为零。蠕滑饱和速度量级是 0.01–0.1 m/s，
   所以接触一上来就是饱和的：`Fy` 每斑 −2.2 … −9.2 kN，合计约 −53 kN，而这条曲线需要的向心力是
   **21.8 kN**。也就是横向力方向相反、量级 2.4 倍 —— 车轮被推向内侧，随后贴轮缘。
2. **左右不对称**：两个右轮根本没有接触，而 `axle3_right` 承担 2.69 倍均分、侵入 120.6 µm。
   对称的几何不可能给出这种结果，它只能是某个横向偏移在起作用。
3. 峰值侵入 **127.36 µm** 是全记录最大值，是静载侵入 65.47 µm 的近两倍。

## 3. 根因：`lateral_rate` 把「坐标系搬运」当成了「物理滑移」

`src/velch/vehicle_solver.py:643-647`：

```python
# The case's path is expressed in the rail reference frame, so its *offset* is absorbed by the
# rail placement and only its slope matters here: the route's curvature turns the wheel against
# the rail, which is a lateral creepage.  Feed it as extra lateral surface velocity.
lateral_extra = path.at(x) if path is not None else 0.0
lateral_rate = path.lateral_velocity_m_s(x, self.speed_at(t_s)) if path is not None else 0.0
```

第 :672 行把 `lateral_extra` 加进**车轮横向偏移**（位置是对的：它把车轮搬到了设计线上），
第 :726 行又把 `lateral_rate` 加进**车轮横向速度**（这一步是错的）：

```python
wheel_v_y_m_s=float(v[axes["y"]]) + lateral_rate,
```

`lateral_rate = v · dy/ds`。在这条曲线上 `dy/ds ≈ 0.0257`，`v = 22.22 m/s`，于是
`lateral_rate = 0.571 m/s` —— 与上表实测的 0.5737 逐位吻合。

**为什么它是错的**：顺着曲线走的车辆，相对钢轨的横向位移是常数（`dq[y]/dt = 0`），横向蠕滑因此为零。
`v·dy/ds` 是**曲线在笛卡尔坐标里的搬运速率**，不是材料点之间的相对滑移。把它当蠕滑喂进去，
等于让每一辆正常通过曲线的车都被判成 0.57 m/s 的横向滑动，接触立刻饱和、把轮对推向内侧。

这也解释了第 5 节要说的另一件事：把它算进蠕滑之后，「对齐」自然“越对越糟”，因为对齐让
`q[y]` 追上了设计线，而 `lateral_rate` 仍然在往蠕滑里灌同一个量。

## 4. 附带的量化：钢轨确实在横向漂

同一个探针在四个里程上量轨距中心（`profile.y_m` 的左右均值之半）：

| 里程 | 左轨均值 | 右轨均值 | 轨距中心 | 轨距 |
|---|---|---|---|---|
| 79 m | −0.3864 | +1.1837 | **+0.3987** | 1.5701 m |
| 84 m | −0.2459 | +1.3424 | **+0.5482** | 1.5883 |
| 89 m | −0.0828 | +1.5010 | **+0.7091** | 1.5837 |
| 94 m | +0.1031 | +1.6596 | **+0.8814** | 1.5565 |

中心线以 **32 mm/m** 的速率向 +y 漂，也就是 22.22 m/s 下 0.71 m/s 的横向搬运 —— 与 `path` 给出的
`lateral_rate` 同量级。车轮由 `lateral_extra` 同步搬运（位置正确），但钢轨本身是**静止**的，
所以「相对滑移 = 车轮绝对速度」这个替换在曲线上必然给出非零的假蠕滑。

## 5. 这一轮同时否掉的两条路

- **准静态滚动座**（`scripts/s26_quasistatic_seat.py`，轮对自转取 `v/r`）：36 个未知量、三个种子，
  最好一次 `|r|max 6.5699e+04 N`、`cond 5.441e+07`、**只有 2/8 轮承力**（`axle3_right 2.209×`、
  `axle4_right 2.330×`）。曲股的侧向状态是**运行平衡**，压成静态根必落贴靠支（Elkins & Gostling,
  Vehicle System Dynamics, 1977）。
- **在曲线上直接做垂直座**：81.6 m 处设计线已偏移 +0.47502 m、切线 +0.03018 rad，四种帧组合
  （placement 开/关 × 车辆搬/不搬）**全部 0 个接触斑**。座只能在接近直线的岔前范围里做。

## 6. 修法与验收（下一轮）

**B040：`lateral_rate` 不进蠕滑。** 位置搬运保留（`lateral_extra` 是对的），速度搬运从
`wheel_v_y_m_s` 里去掉。

验收门（先写死，再动手）：

1. 曲股算例第一帧 `slip_lat` 从 0.52–0.57 m/s 降到 **< 0.01 m/s**；
2. 同一算例从 69 m 跑到 **≥ 0.20 s（22 m，越过 79.6–83.6 m 的波磨补片）**，`numerically_checked`、
   七门全过；
3. 八个接触斑的载荷份额落在 **[0.625, 1.6]×**（外部轮应偏重，但不允许 2.7 倍）；
4. **直线算例逐位不变**：`lateral_rate` 在 `path is None` 时本来就是 0，所以冻结基线的
   `straight_rigid 06928c9db944796d` / `straight_flexible ab81290f5924c3a5` 必须 `UNCHANGED`；
5. 冻结物理不动：59 680.5769 N / 65.47 µm、八接触峰值 89.68/170.61 kN。

**修好之前，`docs/CURVE_*.md` 里所有「曲股 7/7」都在本文件第 1 节被降级为「能起步」。**

## 7. 复算

```
cd F:\ai道岔状态反演辨识\Velch
PYTHONPATH=src python -X utf8 scripts\s28_curve_contact_table.py --duration 0.005
PYTHONPATH=src python -X utf8 scripts\s29_path_rate.py --duration 0.08
PYTHONPATH=src python -X utf8 scripts\s26_quasistatic_seat.py none shift
PYTHONPATH=src python -X utf8 scripts\s26c_seat_frames.py
```

## 8. B040 已修（`wheel_v_y_m_s` 不再加 `lateral_rate`），修好了什么、没修好什么

改动只有一行（`src/velch/vehicle_solver.py` 的接触调用），另外把 `PathTrack.lateral_velocity_m_s` 的
docstring 改成它真实的含义（坐标系搬运，**不是**接触量），并加 `tests/test_path_transport.py` 两项。

**修好了（实测）：**

| 量 | 修前 | 修后 |
|---|---|---|
| t = 0 的 `slip_lateral`（四个轴） | +0.5737 / +0.5232 / +0.2205 / +0.1700 m/s | **0.00000**（逐位零） |
| t = 0 的 `sum(Fy)` | **−36 939 N**（方向相反，且是所需 21 842 N 的 1.7 倍） | **+292.5 N** |
| 斜率守卫触发点 | `x=81.289777 m`（走 2.29 m，t ≈ 0.103 s） | `x=83.525026 m`（走 **4.53 m**，t ≈ 0.204 s） |

**没修好（这才是下一件事）：** 曲股仍然过不去。B040 把失败点往后推了一倍，但没有消除右轨上
2.69–2.91 倍的过载 —— 那是**几何**问题，见
[CURVE_RAIL_GEOMETRY_2026-10-28.md](<CURVE_RAIL_GEOMETRY_2026-10-28.md>)（B041）。

**直向为什么不受影响**：`lateral_rate = v · dy/ds`，直线算例 `dy/ds = 0`，所以这一行原本恒为零。
两个冻结基线（`straight_rigid 06928c9db944796d` / `straight_flexible ab81290f5924c3a5`）在改动后
`--check` 仍是 `UNCHANGED`。

**一个可判据的旁证**：把同一算例的 `lateral_rate` 强行置零（monkeypatch）与改代码后逐位比较，
两次 `slip_lateral` 都恰好是 0.00000、`sum(Fy)` 都恰好 +292.5 N —— 说明改的是那一处，不是别的地方。

## 9. 这一轮同时否掉的三条路

1. **加长行程解决**：0.16 s / 0.30 s 都试过，`0.30 s` 在 784.7 s 后仍是同一个守卫、只是里程不同 ——
   失败是几何性的，不是时长问题。
2. **只把 `path` 的速率去掉就够**：0.16 s 内 7/7，但右轨 2.69–2.91 倍过载依旧在，见上表。
3. **把曲股的静平衡扩到 y/roll/yaw**：见 [CURVE_QUASISTATIC_SEAT_2026-10-28.md](<CURVE_QUASISTATIC_SEAT_2026-10-28.md>)
   —— 36 个未知量、最好 `|r|max 6.57e4 N`、2/8 轮承力。
