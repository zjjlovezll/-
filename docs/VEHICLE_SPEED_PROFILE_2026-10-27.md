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
