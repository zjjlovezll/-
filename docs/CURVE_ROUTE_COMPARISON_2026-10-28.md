# 曲线两条路线各自的缺口（2026-10-28）

这一轮的起点是 B041：18 号道岔曲股算例 `case_diverging_R1100.json` 把两套不同的钢轨模型粘在一起
（左 `Profile_Mileage_JBG.prr` 来自 CRH380A，右 `jbg-20200418-R.prr` 来自 SDITT 07(009)），
轨距沿里程在 1.4438–1.5876 m 之间漂，而车轮按 1.493 m 摆放，右侧车轮因此压在轨距角上
（实测 2.69 倍均分）。用常数偏移修右轨试了三个值（1.4796 / 1.4930 / 1.5065 m）全部失败，
说明**右侧断面本身沿里程在变**，不是一条轨。所以这一轮改走"对称轨道 + 解析曲率"，
把曲率物理与道岔的数据缺陷分开测量。

## 1 对称直轨道 + `curve_radius_m`：静平衡是精确的

算例：`case_A_final_law`（刚性轨道、左右同源、轨距正好 1.493 m），
`run` 加 `curve_radius_m = 1100`、`curve_geometry = true`、`align_to_track = true`、
80 km/h、`x_start_m = seat_x_start_m = 30`。脚本 `scripts/s31_curve_smoke.py`。

坐实后第 0 帧（`_seat` → `_place_on_alignment` → `_align_to_track_frame`，与
`_integrate_vehicle` 完全同序）：

| 轨 | N (N) | 与均分之比 | 侵入 (µm) | lever_y (m) | n_y/n_z | slip_lat (m/s) |
|---|---|---|---|---|---|---|
| axle1_left | 60 433.2 | 1.013 | 65.47 | −0.75277 | +0.0250 | +0.0102 |
| axle2_left | 60 245.1 | 1.010 | 65.47 | −0.75277 | +0.0250 | +0.0101 |
| axle3_left | 59 116.1 | 0.991 | 65.47 | −0.75277 | +0.0250 | +0.0101 |
| axle4_left | 58 927.9 | 0.988 | 65.47 | −0.75277 | +0.0250 | +0.0100 |
| axle1_right | 58 927.9 | 0.988 | 65.47 | +0.75277 | −0.0250 | +0.0102 |
| axle2_right | 59 116.1 | 0.991 | 65.47 | +0.75277 | −0.0250 | +0.0101 |
| axle3_right | 60 245.1 | 1.010 | 65.47 | +0.75277 | −0.0250 | +0.0101 |
| axle4_right | 60 433.2 | 1.013 | 65.47 | +0.75277 | −0.0250 | +0.0100 |

合计 **477 444.6 N = 1.000 × 整车重**，静平衡残差 **1.109e-07 N**。

这张表说明两件事：

- **曲线静平衡在对称轨道上是可解的**，八轮全着地、载荷在 0.988–1.013 之间，法向几乎竖直
  （|n_y/n_z| = 0.025）。上一轮"曲股坐不住"的读数（4/8、2 倍均分、1e5–1e8 N）属于 B041 的数据缺陷，
  不是曲线的物理。
- 左右**逐位镜像**（1.013 对 0.988 是同一对），说明 `_place_on_alignment` 与
  `_align_to_track_frame` 在对称算例上没有引入偏置。

`0.02 s` 运行：`numerically_checked`，**门 7/7**，最大侵入 **73.27 µm**（静载 65.47 µm + 动态 7.8 µm），
八斑峰值 62.0–69.9 kN（均分 59.66 kN）。

## 2 但跑不过 1 m：几何路线没有向心力的来源

同一算例拉到 `0.30 s`：**失败**

```
SimulationFailure: graph slope limit at axle1_left/left:main, x=41.04259 m
```

`x` 是**钢轨里程**（含 +10 m 轴偏移），所以车只走了 **1.04 m**，t ≈ 0.047 s。

我怀疑过第 182 轮登记的那个偏航双重含义（`_align_to_track_frame` 把绝对航向写进 `q[yaw]`，
而蠕滑律把它当攻角 `travel * q[yaw]`）。用 `scripts/s31c_yaw_attack.py` 把对齐之后所有 `yaw`
清零（接触几何是 (y,z) 二维条带搜索，**不读 yaw**，所以这一步只改蠕滑项）重跑：

| 变体 | 结果 |
|---|---|
| 原样 | `graph slope limit at axle1_left, x=41.04259 m`（1.04 m） |
| 对齐后 yaw 清零 | `graph slope limit at axle1_left, x=40.7585517 m`（0.76 m） |

**清零反而更早失败**，所以漂移不是那个攻角驱动的。这一条把偏航双重含义从"曲线跑不了的嫌疑"
降级为"仍未定的口径问题"（它在别处仍然是缺陷，见第 182 轮登记）。

真正的原因在代码里写着：向心力 `m v²/R` 只加在**力路线**上

- `vehicle_solver.py` 的 `evaluate` 注释：*"Curve, as the equivalent straight track: a constant-radius
  curve is, in the vehicle's own frame, a lateral body force `m v^2 / R` plus a gravity component
  `m g sin(theta)` along the cant."*，条件是 `curve_radius_m` **且** 不是几何路线
  （`if curve_radius and not _placement_enabled(run)`）；
- 几何路线把车摆到弧线上，**不加任何法向力**——所以车按惯性走直线、轨按弧线弯走，相对横移按
  `s/R = 9.09 mrad`（9 mm/m）长大，车只能在轮缘上被硬拖，|n_y/n_z| 越过 1.0 的守卫就退出。

R = 1100 m、80 km/h 需要的向心力是 **21 842.4 N**，几何路线一点都给不出来。

## 3 力路线也不能把曲率放进蠕滑（这一条是有实测的）

`curvature_1_per_m` 现在是

```python
curvature_1_per_m=(self._curvature_1_per_m if self.placement_enabled else 0.0),
```

注释记录了原因：

> Measured on R = 1100 m at 80 km/h, flags on but placement off: 4 of 8 wheels loaded and
> 128 901 N on the heaviest, exactly 2x the share.

也就是：力路线有向心力、但蠕滑里没有 `−κ v lever_y`；几何路线有蠕滑曲率项、但没有向心力。
**两条路线各缺一半**，这就是"随动坐标系"一直没做成的那件事：

```
在车辆自己的（随动）坐标系里：
  轨道局部是直的          → 不需要 placement
  横向体力 m v²/R         → 已有（力路线）
  超高时重力沿坡面分量    → 已有（力路线 cant）
  纵向蠕滑 ∓v κ b         → 现在被关掉，因为静平衡吸收不了它
```

关掉它的直接后果是：静平衡的未知量里没有能平衡 ±vκb 产生的**摇头力矩**的自由度
（只有 z；y/roll/yaw 都试过，y+roll 在零速下 rank-deficient，cond 3.76e12）。所以随动坐标系的
下一刀不是"再把曲率打开"，而是**让静平衡能吸收这个力矩**：要么给轮对 yaw 一个平衡项
（两侧不同滚动半径 → 蠕滑自平衡），要么把曲率项按"静平衡只解垂向、力矩由时程闭合"的次序处理。

## 4 这一轮的净结论

| 命题 | 状态 |
|---|---|
| 曲线静平衡在对称轨道上可解（8/8、0.988–1.013×、残差 1.1e-7 N） | **已测** |
| 几何路线跑不过 1 m，因为没有向心力 | **已测**（1.04 m / 0.76 m 两组） |
| 漂移不是对齐的绝对航向造成的 | **已测**（清零更早失败） |
| 力路线不能带曲率进蠕滑，因为静平衡吸收不了 ±vκb | **已测**（128 901 N / 4 of 8，代码注释记录） |
| 道岔曲股 2.69 倍均分 = 两套钢轨模型粘连 | **已测**（B041） |
| 曲线波磨反演 | **未开始**：协议已写好（`scripts/s31b_curve_corrugation.py`），但被上面这一条挡住 |

`scripts/s31b_curve_corrugation.py` 的协议（跑之前就定好）：单侧内轨（+y 侧 = 右轨）、
0.10–0.30 m 四个对数分层波长、随机相位与权重的混合、峰峰归一化、
三档 0 / 0.1 / 0.3 mm、用最小档标定每分量复增益去预测大档（跨幅值外推）、
观察量是前轴垂向加速度、判据是"零档响应的 6 倍以上才算被激励"与"0.3 mm 复原峰峰在 ±2 dB"。
它现在只能跑在"能跑满 0.34 s 的曲线算例"上，而这样的算例还不存在。

## 5 复算

```bash
cd Velch
PYTHONPATH=src python -X utf8 scripts/s31_curve_smoke.py --duration 0.02      # 第 1、2 节的表
PYTHONPATH=src python -X utf8 scripts/s31c_yaw_attack.py --duration 0.30      # 原样 vs yaw 清零
PYTHONPATH=src python -X utf8 scripts/s30_fix_diverging_gauge.py --gauge 1.5065  # B041 最后一次尝试
PYTHONPATH=src python -X utf8 scripts/s31b_curve_corrugation.py --duration 0.30 --levels 0  # 协议自检
```
