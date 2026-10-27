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

## 8. 关于 yaw：三种做法都试过，都不成立——所以它不是"座椅"问题

道岔曲股（`case_diverging_R1100.json`）的曲率只存在于站位表里（19 001 站，30–125 m，`curve_radius_m = None`），
前一轮给的结论是"需要把 yaw 纳入座未知量"。这一轮把三种可能性都实测了，结论要改。

| 做法 | 实测 | 判读 |
|---|---|---|
| 原样（不给半径） | `7 of 8 wheels carry load, lightest 0.0 N, heaviest 118538.9 N`（正好 2×均分） | 横向方程根本没进问题 |
| 显式给 R=1100、超高 0.107 | **静平衡通过**，第一步 `graph slope limit at axle1_left/left:main, x=79 m` | 座解出来了，姿态不对 |
| 把 yaw 加进座未知量 | 座"通过"（八轮都在 0.5–1.6×），但积分在 `axle3_left/left:main, x=52.5 m` 挂 | 解出一个**满足载荷却姿态错**的分支 |
| 刚体 yaw 偏置扫 0 / ±2 / ±5 / ±9.1 / ±14 mrad | 九个值**全部失败**，失败轴在 4/1/4/2/2 之间来回换 | 单个刚性角无法匹配整台车 |

最后那一行是关键诊断：**R=1100 m 下 20 m 足迹的切线角相差 18 mrad（前后轴）**，而一个刚体偏置只能平移这个分布、
不能产生分布本身——所以扫多少都不行。yaw 因此**不是座该解的量**，而是"车按几何摆到线路上"的初值问题，
属于 S4 随动坐标系（放置由几何决定：每个 contact body 取自己里程处的 `y_c/切线`）。

`tests/test_curve_seat.py` 新增第 6 项把这个边界钉住：曲线座**不得**改动 yaw 行（`np.array_equal` 前后相等），
并把上面这段证据写进 docstring，避免下一轮又把它当成"加一个未知量就好"。

证据：`pytest tests\test_curve_seat.py -q` → 6 passed；`scripts/freeze_baseline.py --check` → **UNCHANGED**。

## 10. 车辆的放置（S4 第一半）：算出来了，但解析几何这条路被接触搜索挡住

`_curve_placement` 把**轨道**搬到 `y(s) = s²/(2R)`，而车辆仍站在原地，于是"车在旁边、轮往轮缘上爬"。
新增 `_place_on_alignment()`：给每个刚体按**它自己的里程**加 `y = s²/(2R)` 与 `yaw = atan(s/R)`，
`y` 与 `yaw` 都只在 35 坐标布局没有 `x` 时由几何推出（轮对取 `axle_offsets_m`，构架取两轴中点，车体取中心）。

**放置本身是对的**（`case_A_final_law`，R=1100，前轴 +10 m）：

| 车轴 offset | 加上的 y | 加上的 yaw |
|---|---|---|
| +10.0 m | 45.45 mm | **+9.0907 mrad** |
| +7.5 m | 25.57 mm | +6.8181 mrad |
| −7.5 m | 25.57 mm | −6.8181 mrad |
| −10.0 m | 45.45 mm | −9.0907 mrad |

前后轴航向差 **18.18 mrad = 20 m / 1100 m**，正是"足迹/R"，也就是上一轮刚体偏置扫不出来、扫也扫不到的那个分布。

### 但解析几何这条路现在跑不了

`curve_geometry = true`（轨道被搬到曲线上并按超高滚转）下，四个超高全部失败：

| 超高 | 结果 |
|---|---|
| 0.000 m | `ValueError: wheel roll made the lower envelope non-monotonic in lateral y`（`contact.py:106`） |
| 0.020 m | `graph slope limit at axle3_right/right:main, x=52.5 m` |
| 0.050 m | `graph slope limit at axle1_right/right:main, x=70 m` |
| 0.107 m（平衡超高） | 同 0.000：`ValueError ... non-monotonic` |

两条读法都要留下：

1. **放置不是瓶颈**：`yaw` 分布已经与几何一致，剩下的失败发生在接触搜索内部——滚转后的车轮下包络在横向 `y` 上不再单值，搜索直接拒绝。这不是容差、也不是接触刚度，是**几何表示**的问题。
2. **"只用几何"本来就是专家列的 8 条错答案之一**：轨道搬到曲线上而力与速度场不动，等价于"车被摆到曲线上却不受离心力"，物理上不成立。所以这一条**不该**再往深里修——正确的路仍是随动坐标系（`(1−κy)` 因子、`Δv_x = ∓vκb`、离心竖向分量 `m v² κ sinφ`），几何只是它的显示层。

`tests/test_curve_seat.py` 现在 7 passed + **1 strict xfail**：`test_the_analytic_geometry_route_would_run_if_the_contact_search_allowed_it`
把上面这张表钉成"已知阻塞"。strict 的含义是——一旦接触搜索能处理滚转后的包络，这个 xfail 会**变红**，逼着把它改成正式验收。

## 11. 滚转车轮的下包络（挡住了所有"几何一致"的曲线），以及一个物理上不成立的验收例子

### 11.1 挡住路的那一行

`contact.py` 把车轮型面从轮系坐标搬到轨道坐标时做的是

```
wheel_y = wheel_y_m + c * local_y - s * local_z      # c = cos(roll), s = sin(roll)
```

然后要求 `wheel_y` 严格递增，否则抛 `wheel roll made the lower envelope non-monotonic in lateral y`。
滚转把轮子的**高度**混进了横向坐标，于是判据是 `|s · dz/dy| < c`，即 `|dz/dy| < 1/tan(roll)`：
踏面斜率远小于这个值（没问题），但**轮缘的斜率是几十**（轮缘背面还倒扣），一旦 `roll` 真的等于
超高角（0.107 m 超高 → 4.08°，`1/tan = 14`），轮缘那一段就把曲线折回自己身上，直接抛错。

这就是为什么**所有**"几何一致"的曲线（轨道搬到 `y(s)` 上、车辆也放上去）在第一步就退出，
而"只用体力"的曲线（轨道不动）反而能跑——后者不需要滚转轮子。

修法：`_single_valued_envelope()`——按 `y` 排序，同一 `y` 只保留**最低**的那个点。
"在这个横向位置上，轮子有多高"本来就该取下分支。`roll = 0` 时输入已递增，函数原样返回，
因此**逐位不变**（`freeze_baseline --check` → UNCHANGED）。

### 11.2 两个半场可以分开问了

`run.curve_placement`（默认 `None` = 跟随 `curve_geometry`）把"车辆摆在设计线上"与"轨道搬到
设计线上"拆开，用来分别测量。加上 11.1 的修法后实测：

| 算例（几何一致：轨道+车辆都上曲线） | 结果 |
|---|---|
| R=1100, h=107 mm, 100 km/h（平衡超高） | `graph slope limit at axle1_right/right:main, x=70 m` |
| R=1100, h=107 mm, 160 km/h（欠超高） | `graph slope limit at axle4_right/right:main, x=50 m` |
| R=350, h=150 mm, 66.7 km/h（平衡超高） | `graph slope limit at axle4_right/right:main, x=50 m` |

包络错误消失，失败点移动到**|s| 最大的那两根轴**（x = 60±10 = 50 / 70 m）。这是一个新的一阶
判据：轨道按某一里程被搬了 `s²/(2R)`（45 mm），车轮按另一里程被放了 `s²/(2R)`，两者不同步 →
相对横移 45 mm → 贴到轮缘。下一步就是让**每个接触体在自己的里程上取放置**（`local_state` 的
`placement` 参数已经在，只是现在传的是整车同一个值）。

### 11.3 一个物理上不成立的验收例子（口径更正）

目标第 4 项的例子是"R = 350 m、100 km/h、8/8 轮着地、每轮 ∈[0.5,1.6]×均分"。按平衡超高

```
h_th = 1.5 v² / (g R) = 1.5 · 27.78² / (9.81 · 350) = 0.337 m
```

**0.337 m 的超高不存在**：模型自己在 `model.py:203` 就拒绝 `|cant| > 0.20 m`（判定为"这是毫米"），
而实际线路最大超高约 **0.15 m**。也就是说 R=350 m 在 100 km/h 下定然是**欠超高**工况，轮载必然
不均，"每轮 1.00×"不是它该有的验收。

按 0.15 m 反解设计速度：`v = sqrt(h g R / 1.5) = 18.53 m/s = 66.7 km/h`。所以这一项的**物理一致写法**是：

| 算例 | 半径 | 超高 | 速度 | 期望 |
|---|---|---|---|---|
| 平衡 | 350 m | 150 mm | **66.7 km/h** | 8/8 着地、每轮 ≈1.00× |
| 欠超高 | 350 m | 150 mm | 100 km/h | 8/8 着地、ΔP/P 由限值门判定 |
| 平衡 | 1100 m | 107 mm | 100 km/h | 8/8 着地、每轮 1.00×（已实测 1.000–1.001） |

不改目标文字，但后续一律按这张表实测，并在报告里说明"R=350@100 km/h 的平衡超高不可实现"。

### 11.4 验证

```
pytest tests -q --basetemp F:\velch_tmp\pytest      905 passed, 1 skipped, 1 xfailed
scripts/freeze_baseline.py --check                   VERDICT: UNCHANGED
```

## 12. 放置已经一致，剩下的错在超高：模型把超高做成了"台阶"，不是"倾斜"

### 12.1 先证明放置没错

上一轮猜测"轨道按某里程搬、车轮按另一里程放，45 mm 不同步"。实测（R=1100，107 mm 超高，t=0，
`geometry` 一致，`_place_on_alignment` 之后逐轴对比）：

| 钢轨 | x_m | 轨道 dy | 轨道绝对 y | 车体 s | 车轮 dy |
|---|---|---|---|---|---|
| axle1_left | 70.00 | 45.455 mm | 45.455 mm | +10.0 | 45.455 mm |
| axle2_left | 67.50 | 25.568 | 25.568 | +7.5 | 25.568 |
| axle3_left | 52.50 | 25.568 | 25.568 | −7.5 | 25.568 |
| axle4_left | 50.00 | 45.455 | 45.455 | −10.0 | 45.455 |

**轨道与车轮逐轴完全一致**（放置是按 `(rail_index, x_m)` 与按刚体各自里程算的，本来就没错）。
所以上一轮那个"不同步"的猜测是错的，记在这里以免重走。

### 12.2 真正的错：`_curve_placement` 的 `dz` 是垂直平移

```
def placement(rail_index, x_m):
    s = x_m - start
    return s*s/(2R), (rise if outer else -rise), s/R
                ↑ dy            ↑ dz：整根轨**上下平移** rise，而不是**转动** θ
```

外侧轨被抬高 `rise`、型面却仍是水平的；车轮（哪怕也跟着滚了 θ）与一个"被平移但没转"的轨面相遇，
接触法向立刻偏离竖直，`|normal_y/normal_z| > 1.0` → 斜率门在第一步退出。

- 实测（车体按超高角滚 θ=asin(cant/2b)=4.08°）：R=1100/107 mm/100 km/h 在 `axle2_right, x=67.5 m` 退出；
  R=350/150 mm/66.7 km/h 在 `axle1_right, x=70 m`；欠超高 160 km/h 在 `axle3_right, x=52.5 m` —— **全在右（外）轨**。
- 把 θ **反号**再跑：失败点变成 `axle3_right x=52.5` / `axle3_right x=52.5` / `axle1_right x=70` —— 仍然失败，
  说明这**不是符号问题**，是"轨面没转"这个表示问题。所以 θ 保留 `+`（物理方向对：右轨抬高 → 车体同向滚），
  缺的是另一半。

### 12.3 缺的那一半说明白

要几何一致，超高必须让**轨面也转**：

* 轮侧已有 `wheel_roll_rad`（`contact.py` 的 `wheel_y/wheel_z` 变换里用 `c,s`）；
* 轨侧没有对应参数——`rail_z = rail_z_m + rail_sample.profile.z_m` 只做平移。

所以下一步是给 `find_graph_contact` / `find_strip_contact` 增加 `rail_roll_rad`（把轨型面绕线路中心转 −θ，
并把法向一起转），由 `local_state` 从 `placement` 的三元组扩成四元组（`dy, dz, dz_dy, dy_ds`）传入。
在此之前，`curve_geometry = true` 属于**已知表示不完备**，继续用体力路线（`curve_geometry = false` + 平衡超高）
作为可交付口径，并在任何报告里标明。

### 12.4 验证

```
pytest tests/test_curve_seat.py tests/test_speed_profile_case.py -q    11 passed, 1 xfailed
scripts/freeze_baseline.py --check                                     VERDICT: UNCHANGED
```

## 13. 超高在几何路线上改为**明确拒绝**；而"几何一致"仍然在第一步退出（原因收窄了一格）

### 13.1 拒绝而不是假装

`_curve_placement` 的超高原来只做 `dz = ±rise`（整根轨**平移**，型面不转）。上一轮已证明这会让车轮
与"平移未转"的轨面在轮缘根部相遇。与其发布一个接触表示不了的高差，现在直接拒绝：

```
SimulationFailure: curve_cant_m needs the rail surface to be tilted, which this geometry route does
not do yet (the rail is only raised, not rotated). Use curve_geometry = false, where the cant enters
as a lateral force, or set curve_cant_m = 0.
```

理由写在代码里：**拒绝优于"看起来像物理"的龙门失败**。可交付口径仍然是体力路线
（`curve_geometry = false` + 平衡超高），R=1100/107 mm/100 km/h 实测 8/8、1.000–1.001×。

### 13.2 但超高并不是唯一原因——三组对照把它排除了

`cant = 0`（没有高差、没有滚转）下，几何路线仍然在第一步退出。把放置拆成两半分别测：

| 放置 | 结果 |
|---|---|
| 只加横向偏移 `y = s²/2R` | `graph slope limit at axle1_left, x=70 m` |
| 只加航向 `yaw = atan(s/R)` | `graph slope limit at axle3_left, x=52.5 m` |
| 两者都加（现行） | `graph slope limit at axle1_right, x=70 m` |

三个都失败，所以**"缺轨侧旋转"不是唯一缺口**：只要把车相对一张**直**轨表挪动（无论挪横向还是挪航向），
座椅就会把轮子拖到轮缘；而 `curve_geometry = true` 同时挪轨道时**也**失败，说明轨道那一侧的放置
要么没有真正进入接触，要么进入的量与车轮侧不是同一个量。

下一轮要做的不是继续猜，而是量：在 `evaluate` 里打印**同一个轴位**上
`local_state(...)` 返回的 `y`、`placement(index, x_m)[0]` 与接触搜索实际使用的 `rail_y_m`，
三者必须满足 `rail_y_m == local_state_y`。这一条一旦对上，几何路线要么跑通、要么失败点会移动到
别的地方——无论哪种都比现在这种"三组都失败"的现状信息量大。

### 13.3 验证

```
pytest tests/test_curve_seat.py -q      8 passed, 1 xfailed
scripts/freeze_baseline.py --check      VERDICT: UNCHANGED
```
