# B052：三档"速度"其实是一趟 80 km/h，以及由此要撤回的一条判定（2026-11-01，第 293 轮）

> 第 290–292 轮的全部跨速度结论建立在一件事上：`--speed-kmh` 改了车速。
> 本轮证明它**没有**改——三个标签、一趟物理。第 292 轮那条"轮缘根接触"的判定随之作废。

## 一、缺陷

规范算例 `straight_one_set.json` 的 `run` 里写着：

```json
"speed_profile": {"constant": {"speed_kmh": 80.0}}
```

加载器让**声明的速度剖面**赢过 `vehicle.travel_speed_m_s`（第 241 轮为了让算例自己决定速度而加的
`v = dict(v, travel_speed_m_s=scheduled_speed)`），而 `s99 --speed-kmh` 只替换了 `vehicle.travel_speed_m_s`。
于是：**标签变了，物理没变**。

## 二、证据链（四步，都可复算）

1. **载荷时序**：三趟（60/80/100 km/h）的尖轨首次承载时间都是 **0.817–0.819 s**。若三速度真的不同，
   应为 `(58.4 − 40)/v = 1.10 / 0.83 / 0.66 s`。
2. **反推车速**：`(58.4 − 40)/0.818 = 22.5 m/s = 81 km/h`——三趟都是它。
3. **抽样站位**（决定性）：把 `body.series.sample` 装成探针，重算 60 km/h 归档趟在"54.000 m"那一帧，
   记录到的实际抽样站是 **58.667 m**（stock 与 blade 都是）；`58.667 − 30 = 28.667 = 22.222 × 0.840`。
4. **元数据**：三趟的 `case_sha256` 完全相同（`019747f6…`），差异只在 `meta.speed_kmh` 与 `duration_s`。

## 三、因此要撤回的两条

- **第 292 轮"60 km/h 的尖轨载荷是轮缘根接触"撤回。** 那条判定用的是我用 80 km/h 的算例对象去重算一趟
  标着 60 km/h 的归档，抽样落到 58.667 m —— 那里尖轨本来就接近齐平，踏面转移完全合法。
  `scripts/s148_regime_probe.py` 的**动态度**因此不成立；它的**静态度**（54.0 m 尖轨空载，残差 2.93e-08 N）仍然成立，
  因为它用的是同一个算例自己的站表。
- **第 290/291 轮的"幅值散布 12.81 % / 154.76 %"不是跨速度结论。** 那是同一趟 80 km/h 被三个标签切开后的差异，
  含的是"窗口与站位换算"的差别，不是物理随速度的变化。同理，"100 km/h 全程尖轨零载"只是"80 km/h 只跑了 0.8 s"。

## 四、修法（`scripts/s99_run_archive.py`）

新增纯函数 `apply_speed(case, speed_kmh)`：

- 若算例声明了**常量** `speed_profile`，同时改写它与 `vehicle.travel_speed_m_s`；
- 若声明的是**多段** profile，直接 `SystemExit`（"multi-leg"），因为把多段压成一段等于改工况；
- `meta.json` 增加 `profile_speed_kmh`，与 `speed_kmh` 必须一致；
- `apply_speed` 是纯重建，不改原对象。

`tests/test_speed_override.py`（4 项）：常量 profile 与车辆速度一起被改写、二者改写后仍一致、多段 profile 被拒、
归档 meta 里 `profile_speed_kmh == speed_kmh`（新归档出现后自动生效，之前 skip）。

## 四之二、第二层：加载器把 `SpeedSchedule` 固化在算例上

第一层修完之后（profile 与 `vehicle.travel_speed_m_s` 一起改写、`meta.profile_speed_kmh = 60.0`），
重跑 60 km/h 的那趟**仍然是 80 km/h**：把 `body.series.sample` 装成探针，t = 0.819 s 那一帧前轴抽样站是
**58.2 m**，而 60 km/h 应为 **53.65 m**。

根因在 `src/velch/vehicle_solver.py:149`：

```python
self._schedule = getattr(case, "speed_schedule", None) or SpeedSchedule.constant(
    abs(float(cfg.travel_speed_m_s)), duration_s=float(case.run.duration_s))
```

加载器已经在算例对象上materialised 了一个 `speed_schedule`（按声明的 80 km/h 建），求解器**优先用它**，
于是改写 `run.speed_profile` 与 `vehicle.travel_speed_m_s` 都无用。

`apply_speed` 因此再重建这一层：

```python
if getattr(out, "speed_schedule", None) is not None:
    out = dataclasses.replace(out, speed_schedule=SpeedSchedule.constant(
        abs(speed_kmh) / 3.6, duration_s=float(out.run.duration_s)))
```

验证（`tests/test_speed_override.py` 第 5 项）：原算例 `x_at(0.819) = 58.2 m`，修正后 `53.65 m`，相差 **4.55 m**
——正是 80 与 60 km/h 在同一时刻的距离差。

## 五、不受影响的部分（要说清）

- 第 251–291 轮所有标着 **80 km/h** 的运行 **不受影响**：它们的标签与 profile 都是 80，物理与标签一致。
- 800 多份归档里，凡是 `--speed-kmh` 与算例 profile 不同的，都受本轮影响；核对方式就是看 `meta.speed_kmh`
  与 `meta.profile_speed_kmh`（新归档）或重算抽样站位（旧归档）。

## 六、下一件

用修好的入口重跑 **60 / 100 km/h**（各一趟无凸起 + 一趟 60 µm 凸起），再判"跨速度是否成立"。
这一次时间与站位都会变：首次承载应在 **1.10 s（60 km/h）/ 0.66 s（100 km/h）**，站位仍在 **~58.4 m**。
若站位一致而时间按 `1/v` 走，则第 291 轮"时间锁定"的结论也要一起改。

## 七、复算

```bash
cd Velch
python -X utf8 -m pytest tests/test_speed_override.py -q
python -X utf8 scripts/s99_run_archive.py --case ../scratch/s146/one_set_x30.json --speed-kmh 60 --duration 1.2
```

## 八、归档级守卫：每一趟都得是它自己声称的那个速度

两层修法（`apply_speed` 改写 profile + 重建 `SpeedSchedule`）只保证**新**运行对。数据这一侧还需要一道
便宜的守卫，否则同类缺陷可以再次悄悄发生而不被任何物理测试抓住：

`tests/test_archive_speed_guard.py`（3 项，只读 index + `meta.json`，从不加载状态数组）：

1. `test_every_archived_one_set_run_was_driven_at_the_speed_it_claims` —— 每趟归档的
   `|speed_m_s| × 3.6` 必须等于它自己记的 `speed_kmh`（误差 ≤1e-6）。B052 时期的记录会在这里直接红。
2. `test_the_declared_profile_speed_agrees_whenever_it_is_recorded` —— 写了 `profile_speed_kmh` 的趟，
   它必须与 `speed_kmh` 一致；修法之前的老趟没有这个字段，不算失败。
3. `test_the_speed_schedule_is_the_one_the_run_used` —— 对同一个算例调 `apply_speed(60/100)`：
   `speed_schedule.constant_speed_m_s`、`run.speed_profile["constant"]["speed_kmh"]` 都要跟着变，
   而**原对象必须不动**（`80/3.6` 仍在）。

它跑在每轮 campaign 上，成本 0.8 s。

## 九、60 km/h 的真实成本（本轮实测，未完成）

把修正后的 60 km/h 拉到 1.35 s（`one_set_x30.json`，前轴 40 → 62 m）时，**41 分钟墙钟后仍未归档**
（CPU 2 458 s 单核饱和）。对照同几何的 80 km/h 1.0 s 只要 **724 s** ⇒ 60 km/h 在切换区里每模拟秒的
代价是 80 km/h 的 **≥3 倍**（不是 1.5 倍的线性比例）。这是 `body_hysteresis` 关闭时两体同时求值、
接触集合频繁切换的直接代价，也是"跨速度要跑 6 趟"这条路线必须先把成本算清的原因。
