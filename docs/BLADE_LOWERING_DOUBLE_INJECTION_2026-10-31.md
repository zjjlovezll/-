# 设计降低值被注入两次：尖轨比基本轨高 3.3 mm（B049）

本文记录 M0 的两条硬门读出的第一个真实缺陷，以及修好之后的三组可复算数字。

## 一、症状：一条物理上不可能的红测

`tests/test_body_attribution.py` 的第 3 项把前轴放到 **51.978 m**（尖轨区内 1.4 m，设计降低值仍在毫米级），
断言尖轨体不承载。实测：

```
axle1_right: the blade carries 1079365.53873064 N while it is still millimetres down
```

**1.08 MN = 18 倍均分**，位置上比历史上那次"尖轨在 50.627 m 就吃到 69.69 kN"更早、量级更大。

## 二、定位：不是载荷归属，是几何

先证归属链是对的（M0-1）：一次 0.85 s 运行 1701 帧、912 928 对记录，

```
max |sum(bodies) - merged| / merged = 0.000e+00     (gate 1e-9)
```

逐体之和与合轨响应**逐位相等**，`BODY_CONTACT_HOOK` 与 `body_contacts` 也一致。所以尖轨那 1.08 MN 不是
记账问题，而是车轮**真的**骑在尖轨上。

读断面即可确认。`z` 在模型帧里**向上为正**（`max(z)` 才是走行面，`min(z)` 是断面的底边——早期把
`min(z)` 当冠，正是 B047 一路误读的同源错误）：

| s (m) | stock 冠 | blade 冠 | blade − stock |
|---|---|---|---|
| 50.578 | +0.072 | −14.935 | **−15.007 mm** |
| 51.980 | +0.072 | **+3.385** | **+3.313 mm** |
| 55.000 | +0.072 | +1.545 | +1.473 |
| 60.047 | +0.072 | +0.086 | +0.014 |
| 64.900 | +0.072 | +0.094 | +0.021 |

尖轨在 52 m 一带比基本轨**高 3.3 mm**——设计说它应该低 14.94 mm。

## 三、根因（B049）：降低值被写了两遍

站表里那一条是决定性的：

```json
{"s_m": 50.578, "profile": {"file": "lib:.../07(009)-zjg-20200418-3.txt",
                            "y_sign": 1, "y_offset_m": 0.7930461, "z_sign": -1,
                            "z_offset_m": 0.01494}}
```

`z_offset_m` 从 0.01494 单调降到 0（57.019 m 处 0.000922，60.047 m 处 0.000178），数值序列**完全正确**。
错的是"要不要加"。把同一个断面分别用 `z_offset_m = 0` 与 `+0.01494` 装载：

| 断面 | z_offset | 冠（mm） | 相对 stock +0.072 |
|---|---|---|---|
| `zjg-…-3`（3 mm 宽） | **0** | **−14.935** | **−15.007 mm**（设计 14.94 ✔） |
| `zjg-…-3` | +0.01494 | +0.005 | −0.067 mm（被抬到齐平） |
| `zjg-…-3` | −0.01494 | −29.875 | −29.947 mm |
| `zjg-…-30`（30 mm 宽） | **0** | **−1.159** | **−1.231 mm**（设计 1.16 ✔） |
| `zjg-…-72`（72 mm 宽） | **0** | **+0.094** | +0.022 mm（设计 −0.09，即 0.09 之上 ✔） |

**设计降低值本来就长在画出来的断面里**（`docs/TURNOUT_PROFILE_ATLAS_2026-10-30.md` 的宽度-降低值表
只是这张几何的文字描述）。`scripts/s85_db_case.py` 又按那张表写了一层 `z_offset_m = +lowering`，等于
把同一个量加了两遍：尖端被抬 14.94 mm，从"低 15 mm"变成"高 3.3 mm"。

那条注释的原始判断错在哪也记下来了：它用的读数是 `min(z)`（断面底边 −23.019）与 `min(z)` 的尖轨
（−22.713），于是得出"尖轨高 0.306 mm，必须补偏移"。用 `max(z)` 读同一份数据，尖轨低 **15.007 mm**，
正合设计。

## 四、修法

`scripts/s85_db_case.py`：删掉 `BLADE_LOWERING_MM` / `blade_lowering_m` / `with_lowering`，尖轨站表按
断面原样装载（`z_offset_m = 0`），并把上面这张对照表写进注释。`cases/straight.json` 与
`cases/diverging.json` 都已重建（139 / 141 kB，站数不变：left 76 / stock 76 / blade 161 / frog 65）。

**改的是建库，不是求解器**：冻结物理、七门、DOP853 都没动。

## 五、修好之后的几何（`scripts/s98_m0_verdict.py` 从断面直接算，先于任何动力学）

```
tip gap                 -15.007 mm        （设计 -14.94）
blade crown 追上 stock   58.423 m          （gap = 0）
首次接触（gap = 65.4661 µm） 57.733 m
全程最大"高过 stock"      +0.021 mm（60.37 m）
```

## 六、三个"设计读法"的仲裁数据（M3 的入口）

同一个"尖轨何时到达走行面"，此前有四个读数。现在有第五个，而且是**从断面直接算的**：

| 读法 | 结果 |
|---|---|
| 断面几何：首次接触（一个静侵入以内） | **57.733 m** |
| 断面几何：冠齐平（gap = 0） | **58.423 m** |
| SDITT 里程表的齐平点 | 57.019 m |
| 宽度→降低值插值（旧 s85 偏移所依据的表） | 64.9 m（δ 穿过 65.47 µm） |
| 旧预注册（设计表 23 mm、坡长 5.428 m） | 68.16 m |

**旧预注册的 68.16 m 被断面几何否掉 10 m。** 断面与里程表之间还剩 **1.4 m** 的差（58.423 对 57.019），
这是"几何画到哪"与"里程表写到哪"的内部不一致，留给 M3 用 atlas 的七个几何读数裁决。

## 七、0.85 s 运行的读数（`scripts/s97_body_attribution.py`）

```
frames 1701   identity 0.000e+00   gates 7/7   wall 206 s for 0.850 s simulated

rail          body    first carrying (m)   force (kN)   peak (kN)   peak at (m)
axle1_right   blade        58.1277            1.018       41.722      59.7310
axle1_right   stock        50.0000           59.680       59.729      50.3103
axle2_right   blade        58.1275            1.014       41.674      59.7310
axle3_right   blade            -                 -        0.000      50.5781
```

三条读法：

1. **尖轨首次承载 58.128 m**，比断面几何的首触 57.733 m 晚 **+0.395 m**；这是"检测门 1 kN"的必然结果
   —— 6.4 m 坡道上尖轨力从 0 连续增长，1 kN 已经是有限份额。此差值如实报出，不当成误差抹平。
2. **载荷转移真的发生了**：59.731 m 处尖轨 41.72 kN、基本轨从 59.73 kN 落到 **19.27 kN**，即 67.6 %
   的载荷已交给尖轨。这正是 P1 要反演的那个观测量。
3. `axle3_right` 尖轨 0 kN，因为该轴只走到 50.578 m（尖轨起点），还没进入坡道。

## 八、M0 判定

| 门 | 判据 | 实测 | 结论 |
|---|---|---|---|
| M0-1 逐体之和 = 合轨 | ≤1e-9 相对 | **0.000e+00**（912 928 对） | PASS |
| M0-2 不该接触的体不承载 | 首触 −0.10 m 之前为 0 | 首载 58.128 m > 57.733 m | PASS |
| 七门 | 7/7 | 7/7 | PASS |

M0 关闭。**但它关掉的方式值得记住：红测不是因为归属记错，而是因为几何本身被注入了两遍。**

## 九、代价与后续影响

- `cases/straight.json` / `cases/diverging.json` 内容变了（sha 变），此前基于它们的一切直向读数
  （`scratch/s86/*`、`s87` 的 −10.03 / −17.53 m 两次失败读数）**作废，须重跑**。
- `scripts/s86_run_baseline.py` 的两条路线（straight / diverging）需要在修好的几何上重跑并存档。
- `docs/TASKBOOK_FINAL_GOAL_2026-10-31.md` 的 M3 判据（原写"64.9 或 68.16"）应改为"以断面几何为准，
  并用 atlas 七点裁决剩余 1.4 m"。

## 十、复算

```
PYTHONPATH=src python -X utf8 scripts/s85_db_case.py --route straight
PYTHONPATH=src python -X utf8 scripts/s85_db_case.py --route diverging
PYTHONPATH=src python -X utf8 -m pytest tests/test_body_attribution.py -q      # 4 passed
PYTHONPATH=src python -X utf8 scripts/s97_body_attribution.py --duration 0.85  # 206 s
PYTHONPATH=src python -X utf8 scripts/s98_m0_verdict.py --duration 0.85 --write
```
