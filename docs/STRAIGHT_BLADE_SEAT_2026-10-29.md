# 直向尖轨降低值反演：静平衡能坐住，时程走不出 53.74 m

本轮（第 223 轮）要把「直向过岔的尖轨降低值反演」推到可测量的起点：造一个刚性轨、直向、把设计降低值注进
断面表的算例，从纯基本轨段起车，读尖轨**开始承载**的里程。**结论：静平衡已经坐住，但时程在
`x = 53.7358969 m` 被接触斜率门拦住，所以还没有任何反演数字。**

## 1. 静平衡的横向基准是量出来的，不是推出来的

右侧钢轨在直向上是本务轨（偏移恒定）。三轮尝试都以静平衡的读数作判据：

| 右侧偏移差 | 静平衡读数 |
|---|---|
| 1.4796 / 1.4863 | 4/8 轮承载（单侧） |
| 1.4930 | 不收敛（`gtol`） |
| 1.5000 / 1.5030 | 4/8 轮承载 |
| 1.5060 | 8/8 但 0.230..1.770x |
| **1.5090** | **残差 2.59e-08 N、8/8、0.951..1.049x** |
| 1.5120 | 8/8 但 0.220..1.771x |

判据只有一条：8/8 轮承载且每轮在 0.625..1.6 倍均分内。1.5090 是唯一通过的，比轮平面间距（1.4930）
宽 **16.0 mm**。这不是笔误：两套型面的最高点相对各自中点都偏外约 6.8 mm，所以「偏移差」不等于
「冠距」；而**用左轨族镜像出来的右轨给同一个数**（`scripts/s64_straight_rigid_blade.py` 现在的做法），
说明 16 mm 属于**车轮型面的基准**，不是左右钢轨族混用造成的。

早期两次失败的过程也留着，因为它们各自排除了一个假设：

* 把左轨模板也按右轨重建 → `4 of 8 wheels carry load, heaviest 119 443.3 N`（镜像了右轨型面）；
* 用 `left + 1.50649`（B041 的冠距口径）→ `8 of 8, lightest 21 531.3 N, heaviest 97 829.0 N`。

## 2. 时程走不过 53.74 m

`scripts/s65_rigid_blade_onset.py` 集成 0.45 s：

```
SimulationFailure: graph slope limit at axle1_right/right:stock, x=53.7358969 m
```

`x` 是**站表里程**（含轴位偏置 +10 m），所以车辆走到 43.74 m。53.736 m 在尖轨区（50.578..57.304 m）之内
3.16 m，此时设计降低值已从 0.5 mm 降到约 3.2 mm。**两次不同的建库路径（右轨来自 SDITT 族 / 右轨镜像左族）
给出逐位相同的里程**，因此停在这里的不是横向基准。

零状态下的斜率拒绝几何已经打印出来过（`scripts/s70_guard_geometry.py`）：

```
slope 1.274  lever_y +0.71535 m  lever_z -0.43435 m  pen +3143.53 um  n_y -0.7867 n_z +0.6174
```

3.14 mm 的侵入、接触点在冠中心内侧 18 mm、法向横竖比 1.27 —— 这是一次**轮缘/轨肩**接触，不是踏面。它
在「无尖轨体」的变体里同样出现，所以不是双体尖轨造成的。

## 3. 为什么还不能报数字

尖轨承载起始里程必须从**时程**里读（静平衡在纯基本轨段，看不到尖轨）。时程被门拦住，就没有承载起始，
也就没有「注入 0.5/0.25/0 倍设计降低值 → 起始里程如何移动」这一组可反演的量。**本轮不报任何反演精度。**

## 4. 下一步（先量，不改容差）

1. 把 `s70` 的探针接到**时程**上（集成到拒绝前最后一帧），打印那一帧的 `lever_y` / `pen` / 法向 —— 零状态
   的 3.14 mm 与运行中的拒绝未必同源，必须先证明是哪一个；
2. 若证实是基本轨在尖轨区被削出的**藏尖槽**（`jbg` 平板断面表达不了），那一区的基本轨必须换成带藏尖槽的
   断面族，而不是调偏移；
3. 之后才回到「降低值 → 承载起始里程」的标定与反演。

## 5. 复算

```
PYTHONPATH=src python -X utf8 scripts/s64_straight_rigid_blade.py --seat-at 40 --x-start 40 --duration 0.45 \
    --out ../scratch/s64/case_mirror.json --verify-only
PYTHONPATH=src python -X utf8 scripts/s68_seat_isolation.py --case ../scratch/s64/case_mirror.json \
    --gap 1.5090 --out ../scratch/s64/case_mirror_seated.json
PYTHONPATH=src python -X utf8 scripts/s65_rigid_blade_onset.py --case ../scratch/s64/case_mirror_seated.json --duration 0.45
PYTHONPATH=src python -X utf8 scripts/s66_gauge_sweep.py --case ../scratch/s64/case_mirror.json --gauges 1.5000 1.5030 1.5060 1.5090
PYTHONPATH=src python -X utf8 scripts/s70_guard_geometry.py --case ../scratch/s64/case_gap_no_blade.json
```

**边界**：刚性轨、单一车辆、直向；静平衡读数只对「纯基本轨段起车」成立；1.5090 m 是本算例的标定值，
不是通用轨距。
