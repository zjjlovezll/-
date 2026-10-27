# 车辆速度剖面：先把基线冻住，再把「v」变成一个值

日期：2026-10-27。对应审查的 A 段（速度剖面）与 A0/A1 两步。

## 0. 为什么要先做这个

现在 `v` 是 `cfg.travel_speed_m_s` 一个常数，被六种用途共用：里程映射、蠕滑参考速度、离心力、车体姿态、轮对自转、门与台账。用户要的是「在一个匀速区间内过车，模拟现实过车速度」，而真实过车速度随时间变，所以问题不是「v 取多少」，而是「**在 t 时刻 v 是多少**」。

审查给出的顺序是 **A0 冻基线 → A1 值对象 → A2 分段常速腿 → A3 连续 v(t) → A4 转速一致性与第 8 门**，理由是：A1 之后每一处把 `cfg` 换成 schedule 的改动都必须能证明「常速时逐位不变」，而没有基线就无法证明。

## 1. A0：时间历程基线（新增）

`scripts/freeze_baseline.py` 跑两个短算例，把 `history.csv` 的 sha256 写进 `docs/baselines/time_history.json`：

| 算例 | 配置 | 结果 | 墙钟 | sha256（前 16 位） |
|---|---|---|---|---|
| `straight_rigid` | `examples/vehicle_v2/case.json`，0.020 s，DOP853 | `numerically_checked` | 3.5 s | `06928c9db944796d` |
| `straight_flexible` | 同一算例 + `flexible_wheelset`（table-2-3，31 阶），0.020 s，BDF + 解析雅可比 | `numerically_checked` | 130.4 s | `ab81290f5924c3a5` |

`--check` 重跑并比对，任何漂移退 2。JSON 里写了两条**限制**，因为它们决定这份基线能证明什么：

- **同机同库比较**：换 numpy/BLAS 可能把同一批加法换个顺序，跨机不一致是信息、不是判决；
- **时长被缩短**：短算例走的是同一条右端，不是同一条轨迹。

`straight_flexible` 一次 130 s，所以它适合作**手动/CI 门**，不适合放进每次 `pytest`；rigid 那条 3.5 s，随时可跑。

## 2. A1：`velch.speed.SpeedSchedule`（新增，尚未接线）

`src/velch/speed.py` 提供两个不可变值对象：

```python
Leg(speed_m_s=20.0, duration_s=2.0)          # 或者 distance_m=100.0，二选一
SpeedSchedule.constant(97.2222, duration_s=1.2)
SpeedSchedule.from_legs([Leg(...), Leg(...)])
```

接口：`v_at(t)`、`x_at(t, x_start_m=…)`、`duration_s`、`distance_m`、`speeds`、`min/max_speed_m_s`、`is_constant`、`constant_speed_m_s`、`describe()`。

三个实现选择，理由都在代码里：

1. **常速走闭式**：`x_at = x_start + v t`，不是逐段累加。里程一旦有 1 ulp 变化，采样到的型面站位就变，所有历史结果都对不上——这正是 A1 验收要求的「常速逐位不变」。
2. **`v_at` 超出末端保持最后一档**，不外推：外推会悄悄编造一个用户没给的速度。
3. **`Leg` 必须恰好给 `duration_s` 或 `distance_m` 之一**，两个都给或都不给都直接报错，并在消息里写出实际收到的值。

`tests/test_speed_schedule.py` 8 项：常速闭式（含 `x_at(7.5 s)` 这种超出时长仍按常速）、常速报告长度、两段积分在交界处精确、`distance_m` 型当量时长、**段内 `x_at` 与该段速度严格线性**（这是可精确验证的性质；中点数值积分跨两个速度台阶只有一阶精度，`dt·Δv/2`，拿它验 1e-9 会误报）、同速多段仍判常速、9 条拒绝消息、`describe()` 报各档速度而不是平均值。

## 3. 还没做的（下一步，按顺序）

- **接线**：`RunSettings` 加 `speed_profile`，`vehicle.py` 解析成 `SpeedSchedule`，然后逐处把 `cfg.travel_speed_m_s` 换成 `schedule.v_at(t)`/`x_at(t)`——审查列出约 18 处，最高风险是 `vehicle_solver.py:168` 的 `station_m = x_start + v*t + axle_offset`（采样相位一变，所有几何读数都变）与 `jacobian.py:336` 的**第二份里程公式**。
- **转速一致性（A4）**：轮对自转必须跟 `v/r`，否则 `slip_x` 变成一个 0.05 m/s 的假需求，经 `saturate_creep_force` 的 `hypot` 吃掉横向力；做法是 `T = K(v/r − ω) + I v̇/r`，仅在非匀速剖面启用，并加第 8 门 `spin_tracking`。
- **A2 分段常速腿**优先于 A3 连续 `v(t)`：窗内仍走已标定的常速路径，按速度的 H 仍然有效。
- 验收（审查给的 A-1…A-8）：3 个算例 sha256 全等、静态 oracle 59 680.577 N 不动、`x_at` 与 ∫v ≤1e-12、里程闭合 ≤0.2 %、`max|v/r−ω|·r ≤ 0.5 mm/s`、台账同步、窗内速度跨度 ≤0.5 %、旧单轮对路径直接拒绝剖面。

## 4. 复算

```powershell
$env:PYTHONPATH = "F:\ai道岔状态反演辨识\Velch\src"
python -X utf8 scripts/freeze_baseline.py            # 写基线
python -X utf8 scripts/freeze_baseline.py --check    # 比对，漂移退 2
python -m pytest tests/test_speed_schedule.py -q
```

## 5. 接线（第 2 轮）：算例里的 `run.speed_profile` 已经生效

### 5.1 接口

```json
"run": { "speed_profile": { "constant": { "speed_kmh": 80.0 } } }
"run": { "speed_profile": { "legs": [
    { "speed_kmh": 80.0, "duration_s": 2.0 },
    { "speed_m_s": 30.0, "distance_m": 120.0 } ] } }
```

单位必须由**键名**给出（`speed_kmh` / `speed_m_s`），不给裸数字：同一个数字在两个人眼里一个是 m/s、一个是 km/h。长度同理二选一（`duration_s` / `distance_m`）。`RunSettings.speed_profile` 接收原始块，`load_vehicle_case` 用 `SpeedSchedule.from_spec` 解析，块本身记进算例字节，所以改速度剖面会改 `case_sha256`。

### 5.2 常速剖面是**唯一事实源**

`travel_speed_m_s = 99` 再加 `constant: {speed_m_s: 2.0}` 的算例，跑出来必须与「只有 `travel_speed_m_s = 2.0`、没有剖面」的算例**逐字节相同**。测试 `tests/test_speed_profile_case.py::test_a_constant_profile_overrides_the_travel_speed_it_replaces` 就是这条。

第一版没通过，原因值得记：剖面是在函数**末尾**才覆盖 `travel_speed_m_s`，而**轮对初始自转在函数中段就按旧速度算好了**（`vehicle.travel_speed_m_s / nominal_wheel_radius_m`），于是两个算例的 `history.csv` 差在最后几位。改法是**在读取之后、任何使用之前**覆盖 `raw["vehicle"]["travel_speed_m_s"]`，并把 `case_sha256` 改成提前算好的「磁盘字节哈希」——否则它会去哈希一个已经被改过的视图。

### 5.3 多段剖面：解析、随算例携带，然后**明确拒绝**

`speed_schedule` 挂在 `VehicleCase` 上，但 `simulate_vehicle` 在非匀速时直接抛：

```
SpeedScheduleError: a multi-leg speed profile is parsed but not yet wired into the solver:
2 legs: ... Use a constant profile, or add the spin-tracking gate first.
```

理由是审查 A4 指出的那条链：轮对自转由接触力积分，而蠕滑参考速度仍是单值；`v` 一变，两者不匹配会被 `saturate_creep_force` 的 `hypot` 吃成假纵向需求。所以顺序必须是「先把 12 处 `travel_speed_m_s` 换成 `schedule.v_at(t)`/`x_at(t)`，再加 `spin_tracking` 门，最后才允许非匀速」——**先把拒绝装上，而不是静默按第一段速度跑**。

### 5.4 测试

- `tests/test_speed_schedule.py` 11 项：把上一版的 8 项加上 3 项 `from_spec`（km/h 换算、两段混用两种单位与两种长度、5 条拒绝消息）。
- `tests/test_speed_profile_case.py` 2 项：常速剖面覆盖旧速度且**逐字节相同**（约 6.5 s，跑两次 0.015 s 算例）；多段剖面被携带且被拒绝。

## 6. 力路径改走调度（第 3 轮）：里程、蠕滑参考速度、离心项

`speed_profile` 之前只是「解析得出来、常速能生效」，而力路径仍直接读 `cfg.travel_speed_m_s`。这一轮把三处换成调度：

| 位置 | 原写法 | 现写法 | 为什么不能留两处 |
|---|---|---|---|
| `station_m`（`vehicle_solver.py:169`） | `x_start + v*t + offset` | `self.x_at(t_s) + offset` | 不平顺、型面、支撑柔度全按里程采样，两处算法一分叉就会把力与反力放到不同里程 |
| `jacobian.py:336` | 同一公式的**第二份拷贝** | `dynamics.x_at(t_s)` | 解析雅可比与右端必须用同一个里程，否则差分对照会「通过」而实际是两套几何 |
| 蠕滑参考（`:546`、`:552`、`:554`） | `cfg.travel_speed_m_s` | `self.speed_at(t_s)` | 变速度时滑移由实时速度乘出；用常数会把整段速度变化算成假滑移 |
| 离心项（`:291`） | `abs(cfg.travel_speed_m_s)` | `abs(self.speed_at(t_s))` | 等效直线曲线的 `m v²/R` 随速度变，用常数等于一直按起点速度过弯 |

三个新钩子都在 `VehicleDynamics` 上：

```python
self._schedule = case.speed_schedule or SpeedSchedule.constant(abs(v), duration_s=...)
self._direction = 1.0 if v >= 0 else -1.0
dynamics.speed_at(t_s)   # 有符号速度，常速时逐位等于 cfg.travel_speed_m_s
dynamics.x_at(t_s)       # 有符号里程，常速时逐位等于 x_start + v*t
```

**逐位等价怎么保证**：`_direction` 是 ±1.0，`1.0 * (v*t)` 与 `-1.0 * (v*t)` 在 IEEE 下与 `v*t`（v 为负）完全相同，所以常速路径一个 ulp 都不动。实测：`scripts/freeze_baseline.py --check` → **VERDICT: UNCHANGED**（`straight_rigid` `06928c9db944796d` 3.6 s、`straight_flexible` `ab81290f5924c3a5` 132.1 s）。

**还剩什么**：轮对自转仍是积分出来的状态，多段剖面因此仍被拒绝。第 4 轮要做的正是「让自转跟着速度」——否则 `slip_x` 会被 `saturate_creep_force` 的 `hypot` 吃成假纵向需求，这一点在拉通多段之前必须先关掉。

测试：`tests/test_speed_profile_case.py` 新增 2 项——`x_at` 与字面量**逐位相等**（三种速度含负速度 × 四个时刻）、以及「算例字段说 99 m/s 而剖面说 2 m/s 时里程按 2 m/s 前进」。

## 7. 转速跟着速度走（第 4 轮）：第 8 门 `spin_tracking`，多段剖面放开

多段剖面之前被明确拒绝，理由是「轮对自转由接触力积分，而蠕滑参考速度是单值」，两者一错位，差出来的滑移会被 `saturate_creep_force` 的 `hypot` 当成纵向需求吃掉横向力。这一轮把那个理由消掉。

### 7.1 一阶伺服

```python
target = self.speed_at(t_s) / nominal_wheel_radius_m
force[spin] += mass[spin] * (target - v[spin]) / SPIN_TIME_CONSTANT_S   # 2 ms
```

用**惯量当增益**，于是每个轮对的时间常数都恰好是 2 ms（与惯量大小无关，不必逐轴调）。峰值力矩实测 **176.7 kN·m**（2→4 m/s 阶跃、`I = 76 kg·m²`），在蠕滑律量级内。**常速剖面不开伺服**，所以常速路径逐位不变；`run.spin_control` 可显式打开。

### 7.2 第 8 门判据：测「每条腿结束时」，不测阶跃点

| 量 | 实测（2→4 m/s，两条 10 ms 腿） | 处理 |
|---|---|---|
| 阶跃点的踏面滑移 | **2.000 m/s** | 一个阶跃无法被任何伺服跟随，**如实报告、不入门** |
| 每条腿结束时的相对滑移 | **1.39e-4**（0.014 %） | 入门，阈值 **1 %** |

之所以用相对量：绝对阈值在 2 m/s 与 100 m/s 下含义完全不同。1 % 低于蠕滑饱和的膝点，所以「门过」意味着蠕滑律看到的不是被自转差值污染的量。

`summary` 里同时给 `spin_tracking_max_m`（全记录，含阶跃）、`spin_tracking_relative`（腿末，入门）与 `gates.spin_tracking`；**常速剖面不带这两项，门数仍是 7**，所以历史 manifest 仍可比。

### 7.3 反过来说清楚它不做什么

- 它**不是**牵引控制：伺服只让自转对齐 `v/r`，不对应任何车钩力；真实牵引/制动要另加扭矩并让它进入 `slip_x`（那是 S2 的活）。
- 它**不是**滚动约束：对齐靠力矩，所以接触里仍可能瞬时出现滑移（阶跃点就是例子）。
- 它**不改变**曲线能力：等效直线曲线的离心项随 `speed_at(t)` 走，但曲率仍未进蠕滑。

### 7.4 验收

| 项 | 结果 |
|---|---|
| 时间历程基线 | **UNCHANGED**（`straight_rigid` `06928c9db944796d`、`straight_flexible` `ab81290f5924c3a5`） |
| 全仓测试 | **897 passed, 1 skipped** |
| 新增测试 | `tests/test_spin_control.py` 2 项（常速不加门、不加指标；2→4 m/s 斜坡腿末相对滑移 ≤1 %） |

### 7.5 还没做的（属于第 3 项剩下的部分）

里程闭合 ≤0.2 %（`x_at` 与 ∫v 的一致性）目前只有单元级断言，还没有在「多段 + 长时程」算例上量；第 5 轮补上，同时把三段剖面（含一段降速）跑成一条归档基线。

## 8. 里程闭合（第 5 轮）：三段剖面，闭合 0.000，转速门过

目标第 3 项要的「里程闭合 ≤0.2 %」这一轮量了。测量点是**写出来的 `history.csv`**，不是产生它的函数——否则测的是同一个错误的两面。

`scripts/s11_mileage_closure.py`：80 / 60 / 40 km/h 各一段（20 / 15 / 15 ms），`duration 0.05 s`，101 帧：

| 量 | 值 |
|---|---|
| `result_status` / 门 | `numerically_checked`，含 `spin_tracking` |
| 腿末相对滑移 | **1.02e-4** |
| 调度说走过 | 0.861111111 m |
| 里程列末帧 − `x_start` | 0.861111111 m |
| **闭合** | **0.000e+00**（阈值 0.2 %） |

顺带记一个口径：用 101 帧做梯形积分只得 0.85833 m（−0.32 %），因为帧不落在腿上，跨过腿边界的那一格被平均掉了。**参考值只能取解析距离**（`schedule.distance_m` / `x_at`），梯形积分只能当交叉检查，不能当基准。

还有一处必须补：`save_vehicle_result` 里写里程列的那行原先是 `x_start + travel_speed_m_s * t`，多段剖面下会写出一条不属于该几何的轨迹。现在走 `travel_mileage_m(case, t)`，与力路径同一个函数；常速路径仍逐位相同（方向 ±1.0）。

测试：`tests/test_mileage_closure.py` 1 项——两段 80/40 km/h，`np.array_equal` 比较每帧里程与 `travel_mileage_m`，末帧与解析距离差 <1e-12，且 `spin_tracking` 为真。
