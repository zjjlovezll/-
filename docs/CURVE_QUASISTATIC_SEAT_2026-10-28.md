# 曲股能不能"坐"出一个静态平衡？——滚动静平衡实验（否定结论）

状态：**曲股的侧向状态是运行平衡，不是静态平衡；静态座只解垂向这件事是对的，不要再试图扩未知量。**
日期 2026-10-28。脚本 [`scripts/s26_quasistatic_seat.py`](scripts/s26_quasistatic_seat.py)（约 17 s 可复算）。

## 1. 为什么要做这个实验

验收门第 4 项写的是"静平衡未知量从只有 z 扩到 y/yaw/roll"。此前的记录给的是**零速**下的结论：
蠕滑力恒为零、轨顶接触没有横向分量，所以侧向方程秩亏（`cond 3.76e12`、σ_min 2.7e-11、所有种子停在
240 kN 驻点），于是 `_static_vertical_equilibrium` 只解 z。

但零速并不是唯一状态。`contact.py:732` 里已经有

```
creep_attack_velocity_m_s = float(travel * q[axes["yaw"]])
```

`contact.py:290-291` 里已经有

```
slip_x = travel_speed_m_s + wheel_spin_rate_rad_s * g.lever_z_m
        - curvature_1_per_m * travel_speed_m_s * g.lever_y_m
```

也就是说：**只要把轮对的自转设成 `omega = v / r`、把 `yaw` 当作冲角，蠕滑导向力就在方程里了。**
这台车不需要新增任何物理，只需要给静平衡一个"滚动"的初值场和多几个未知量。于是这一轮把这件事做完，
判据是"残差降到 0.1 N 以下 + 八轮着地 + 每轮在 0.625–1.6× 均分"。

## 2. 实验设置

`case_diverging_R1100.json`（18 号道岔，R = 1100 m，曲股写在站位表里），

- `x_start_m = 69`（过了 50.578 m 的切线）、`curve_geometry = true`、`align_to_track = true`；
- `travel_speed_m_s = 80/3.6 = 22.2222`，四个轮对自转 `51.6796 rad/s`；
- 51 个坐标（35 车辆 + 16 弹性轨）；**36 个未知量** = 每个体的 y/z/roll/yaw（4×4 + 2×4 + 4 = 28）
  + 8 根轨的垂向弹性行；方程取同样 36 行；
- `least_squares(method="trf", xtol=ftol=gtol=1e-12, max_nfev=600)`，残差 `force[indices] / 1e5`；
- 三个种子：对齐态、整体下沉 1 mm、整体下沉 2 mm。

## 3. 结果（否定，且三个种子一致）

```
seed aligned      -> |r|max 6.5699e+04 N   xtol
      wheelset4.roll              65698.9 N
      wheelset3.roll              56894.3 N
      bogie2.roll                 56284.7 N
      wheelset4.z                -45168.7 N
      bogie2.z                   -41914.5 N
      wheelset3.z                -41593.1 N
seed drop 2 mm    -> |r|max 1.0000e+05 N   gtol（全部行撞 1.0 势垒，guard 命中 76 次）
seed drop 1 mm    -> |r|max 1.0000e+05 N   gtol
condition number  : 5.441e+07  (sigma_max 1.839e+06, sigma_min 3.380e-02)
wheels carrying load: 2 of 8
  axle3_right 131807.9 N  2.209x
  axle4_right 138987.3 N  2.330x
  其余六轮 0.0 N
```

对齐的两种变体（`none` 与只给横移 `shift`）给出**逐位相同**的结果（同一个 5.7637e+04、同样 2/8、
134591.9–139094.6 N），说明这一配置下对齐不是差别所在：两个起点都落到同一支**外轨贴靠**的解上。

## 4. 判读

1. **加了滚动，仍然坐不住。** 残差 6.57e4 N（其中最大一项是 `wheelset4.roll` 的 65.7 kN·m 力矩），
   条件数 5.4e7，最后只有后转向架两个右轮承力、各 2.2–2.3 倍均分，四个左轮全部 0。
2. **这不是"少了一个力"，而是"这个问题不该这样问"。** 曲线上车辆的侧向状态由**运动**闭合：
   轮对靠两侧滚动半径差产生偏航力矩、靠冲角产生横向蠕滑力，二者在**行进中**才配平。
   把它压成"零速或准静态的根"就会落到贴靠分支上——这正是 Elkins & Gostling 准静态曲线通过理论
   （VSD 1977）说的事：曲线是**进入**的，不是**站上**的。
3. **支持这一点的现成证据**：同一算例（18 号道岔 R=1100 m、80 km/h、`seat_x_start_m=45`、
   从 69 m 起跑）在时程里 `numerically_checked`、七门 7/7、八轮全部承载。**轨迹自己找到了那个侧向平衡**，
   而静态座找不到。所以正确的分工是：**座只决定车轮坐多深（垂向），侧向交给时程。**

## 5. 顺带量到的一个隐患（未改代码，先记账）

同一根 `yaw` 坐标在两个地方含义不同：

| 位置 | 写法 | 含义 |
|---|---|---|
| `vehicle_solver.py:910-958` `_align_to_track_frame` | `yaw = arctan(dy/ds)` | 相对地面的**绝对航向** |
| `contact.py:732` | `creep_attack_velocity = travel * q[yaw]` | 相对钢轨的**冲角** |

在这条曲线上两者相差切线角 0.0158 rad，于是 `travel * yaw = 0.352 m/s` 的横向蠕滑速度（约 0.9° 冲角），
按 `f11 ≈ 1e7 N` 估算相当于每接触斑数十至上百 kN 的**虚假横向力**。这与历史上多次"对齐反而更糟"
（78 786 → 150 690 kN）的读数方向一致。

**为什么这一轮不改它**：当前 7/7 通过的道岔运行没有打开 `align_to_track`，改口径会同时改变那条已验证的
轨迹；而没有一条独立测量能判定"绝对航向还是冲角"哪个才对。所以先把它作为**待定缺陷**登记，
下一轮用可判定的实验来定：在同一状态、同一条曲线上比较 `yaw` 取 0 与取切线角时 `evaluate` 的横向合力，
看它是否等于 `m v²/R = 21.4 kN`（正确应为相等，当前会远大于它）。

## 6. 复算

```
cd F:\ai道岔状态反演辨识\Velch
PYTHONPATH=src python -X utf8 scripts\s26_quasistatic_seat.py none shift
```

脚本本身写在 `scratch/seat26/` 下生成派生算例（`F:\velch_tmp` 在写沙箱外）。
