# 曲线：先把静平衡问对，再把曲率放进蠕滑

本轮（目标第 6 轮）动了两处，都在 `src/velch/vehicle_solver.py` 与 `src/velch/contact.py`，直向路径逐位不动。

## 1. 为什么"等效直线 + 侧向体力"跑不了曲线

`run.curve_radius_m` 只在 `evaluate` 里给每个体加重力式的侧向力 `m(v²/R − g sinθ)`，几何仍是直线。实测两个失败点：

| 配置 | 结果 |
|---|---|
| R=350，无几何、无横向未知量 | `graph slope limit at axle1_left, x=41.2461871 m`（曲线不平顺试验） |
| R=350 + `curve_geometry` | `2 of 8 wheels carry load, lightest 0.0 N, heaviest 264504.2 N` |

第一处是**问题没问对**：静平衡的未知量只有 `z`（`indices = [require(body, "z") ...]`），横向力进了右端却没有横向坐标可以平衡它，于是轮胎只能被推到轮缘上；第二处是只有几何没有体力，车被轨道"硬拖"到曲线上。

## 2. 改动一：曲线时把 y 与 roll 变成未知量

```
curved = bool(getattr(case.run, "curve_radius_m", None))
indices = [z rows...]
if curved:
    indices += [y, roll rows for every body that owns them]
```

配套加了三个横向种子（0 / +2 mm / −2 mm），因为解落在"直线位"与"轮缘接触"之间，只给零种子会卡在游间里。

**直向不受影响**：没有 `curve_radius_m` 时 `curved` 为假，未知量、残差、种子与改动前完全一致。

## 3. 改动二：曲率进纵向蠕滑

`contact.py` 的 `evaluate_contact` 新增 `curvature_1_per_m: float = 0.0`：

```
slip_x = travel + ω·lever_z − κ·travel·lever_y
```

物理：曲线上同一轮对的两个接触点走过的弧长不同（横向偏移 `b` 处速度为 `v(1+κb)`），这正是转向架能"转向"的来源。缺这一项时，轮对没有滚动半径差可用，只能靠轮缘硬顶——那正是 `x=70 m`（第一个轴位）就触发斜率门的机理。

`vehicle_solver` 里 `self._curvature_1_per_m = 0.0 if not radius else 1.0/float(radius)`，并把值传进 `evaluate_contact`；直向时恒为 0，该项逐位无效。

## 4. 实测：第一条真正跑通的曲线

`case_A_final_law.json`（内联 35 坐标）改成 R=1100 m、超高 0.107 m、100 km/h、0.01 s（`x_start 60 m`）：

| 量 | 结果 |
|---|---|
| `result_status` | `numerically_checked` |
| 七门 | **全部 true**（含 `no_edge_limited_active_contact`、`translational_action_reaction`） |
| 八轮载荷 | 59 652–59 708 N，均分 59 662 N |
| 每轮 / 均分 | **1.00×（八轮全部在 [0.5, 1.6] 内）** |

这不是"调出来的"：0.107 m 正是该半径在 100 km/h 的理论超高 `h_th = 1.5 v²/(gR) = 0.107 m`，配平后左右轨载荷差自然落回 1.00×。

## 5. 斜率门没有被放宽，不平衡曲线仍然会停

同一半径、超高 0，100 km/h（理论超高 0.107 m，缺 0.107 m）→ 仍然 `SimulationFailure: graph slope limit`。这是**正确**结果：直线化轨道下，未平衡的侧向力只能靠轮缘承担，而 `maximum_abs_contact_slope = 1.0` 就是为识别这种情况设的。要跑这种工况，正确做法是按第 6 轮之后的 S4/S5 做（随动坐标系 + 超高同时进几何与力），不是把这个门调大。

## 6. 证据

- 新增 `tests/test_curve_seat.py` 5 项：直向 `_curvature_1_per_m == 0`；曲线等于 `1/R`；**蠕滑项符号与量值**（`curved − straight == −κ v b`，`rel=1e-12`）；配平曲线八轮着地 1.00× 且七门全真；不平衡曲线仍触发斜率门。
- 时间历程基线 `scripts/freeze_baseline.py --check`：**UNCHANGED**（直向逐位不变）。
- 复算：`pytest tests\test_curve_seat.py -q`。

## 7. 还没做的（按审查的顺序）

- **S4 随动坐标系**：现在曲线仍是"等效直线 + 体力"，`curve_geometry` 只是把直线轨面按 `s²/2R` 平移，接触的法向与横向速度场还不完整（缺 `(1−κy)` 因子与竖向离心分量 `m v² κ sinφ`）。
- **S5 超高进几何与力同时**：现在超高只进力（`−g sinθ`）与 `curve_geometry` 的 ±rise，两者不在同一个方程里。
- **B039**：`_curve_placement` 用 `s = x_m − x_start`，切线点被钉在 `run.x_start_m`，即"正在进入曲线"而不是"在曲线上"。
- 曲线入岔（`case_diverging_R1100.json`）仍未在配平超高下跑通；它同时还背着 O010 的 node-table 柔轨静平衡问题。
