# 一组模型装进同一算例：完备车辆 + 柔性轮对 + 柔性轨道 + 真道岔几何（M1）

日期：2026-10-31
对应任务书：`docs/TASKBOOK_FINAL_GOAL_2026-10-31.md`（M1）
算例：`vehicles/turnouts/CN60-1100-1_18/cases/straight_one_set.json`
装配脚本：`scripts/s101_one_set_case.py`　核对脚本：`scripts/s102_one_set_check.py`
数据：`scratch/runs/straight_one_set-080.00kmh-0.0200s-500us-8886e594/`、`…-0.4000s-…/`

## 1. 这一轮要回答的问题

任务书 M1 的定义是：把四件东西装进**同一个**算例并跑通七门——

1. **完备车辆**：`lib:CRH380A_M_axlebox.json`（86 坐标，7 车体 + **8 个轴箱体**，共 15 个刚体）
2. **柔性轮对**：`lib:modes/CRH3C_wheelset_fe.json`，用 `flexible_wheelset = {"source": "file", "file": …, "axles": [1,2,3,4]}`
3. **柔性轨道**：`track_dynamics = {"kind": "local_compliant"}`（8 根轨 × 2 个坐标）
4. **真道岔几何**：`CN60-1100-1:18` 的 8 根轨 / 16 个接触体（右股每轴 `stock` + `blade` + `frog`）

在此之前，这四件事**从未同时出现过**：`cases/straight.json` 有真道岔几何和柔性轨，但车辆是 35 坐标的刚性轮对车；`examples/portable/case_flexible.json` 有柔性轮对，但只有 12 站合成几何、无道岔；`CRH380A_M_axlebox.json` 有最完备的车，但**没有任何算例**。

## 2. 装配结果（G1）

```
case_id: turnout_cn60_1100_straight_one_set
track_kind: local_compliant      dimension: 234
vehicle_dof: 86                  modal_dof: 132
bodies: {wheelset 4, bogie 2, carbody 1, axlebox 8}   bodies_total 15
rails: 8   rail_bodies: 16   speed_kmh: 80.0   duration_s: 0.02
```

234 = **86**（车：4 轮对 × 5 + 2 构架 × 6 + 车体 6 + 8 轴箱 × 4 = 86）+ **16**（轨：8 根 × 2）+ **132**（模态：4 轮对 × 33 阶）。

装配方式的两个决定：

- 车辆**不复制**进算例，用 `vehicle_ref` 指向 `lib:CRH380A_M_axlebox.json`——车辆只有一份定义，算例改不了它，也不会漂移。
- 运行速度写在算例自己的 `run.speed_profile = {"constant": {"speed_kmh": 80.0}}`。**这是必须的**：axlebox 车辆模型自带线路设计速度 **350 km/h**，若算例不声明，道岔工况会以 350 km/h 起跑。

## 3. 为了装进去，修了两个加载器缺陷

两处都是 `vehicle_ref`（"算例引用车辆模型"）这条路径上**第一次被走到**的代码。

| # | 缺陷 | 症状 | 修法 |
|---|---|---|---|
| L1 | `vehicle_ref` 不认识 `lib:` / `case:` / `data:` 前缀 | `vehicle_db.load` 把 `lib:...` 当裸文件名，按 **cwd** 解析 ⇒ 找不到 | `src/velch/vehicle.py:423` 先 `resolve_asset(text, case_path=target, kind="vehicle model")` |
| L2 | `run.speed_profile` 的常量分支写 `raw["vehicle"]["travel_speed_m_s"]` | `vehicle_ref` 算例没有 `raw["vehicle"]` ⇒ `KeyError: 'vehicle'` | 先记 `scheduled_speed`，拿到 `v`（内联块或模型块）后 `v = dict(v, travel_speed_m_s=scheduled_speed)` |

L2 的修法对**内联车辆**算例是等价变换（改的是字典副本、不是 `raw`），所以历史算例逐位不变——这一点由冻结基线验证：

```
straight_rigid     numerically_checked     7.4 s  295809cb24c8e24b
straight_flexible  numerically_checked    13.8 s  7b1daef7e80664ac
VERDICT: UNCHANGED
```

## 4. 四条门（G2–G5）的实测

### G2 座椅

```
dimension 234  seat residual 6.927e-09 N   wall 0.6 s
total weight 481078.5 N
  axle1..4_left / axle1..4_right  N 60153.0  share 1.000  active True  pen 63.70 um
worst |share-1| 0.000    SEAT PASS
```

**注意贯入是 63.70 µm，不是冻结基线那 65.4661 µm。** 这不是缺陷：这款车更重（481 078.5 N / 9.81 = **49 039.8 kg**，35 坐标车是 48 654 kg），同一个接触刚度换载荷必然换贯入。**因此 51 坐标算例的历史数字不能与本算例混用。**

### G3 七门（0.02 s 与 0.40 s 各一次）

```
straight_one_set-080.00kmh-0.0200s-500us-8886e594: frames 41   gates 7/7   wall 9.3 s
straight_one_set-080.00kmh-0.4000s-500us-8886e594: frames 801  gates 7/7   wall 180.0 s
```

七门：`solver_completed` / `finite_states_and_forces` / `vertical_preload_residual` / `penetration_within_case_limit` / `friction_bound` / `no_edge_limited_active_contact` / `translational_action_reaction` 全 True。

### G4 越过错尖与首载里程（0.40 s）

```
front axle reached 58.889 m   (tip 50.578, first touch 57.733, flush 58.423)
blade first load at 58.144 m  (+0.411 m vs the geometric first touch)
peak 40.77 kN at 58.589 m     (stock there 19.35 kN -> 67.8 % of the right side on the blade)
```

`+0.411 m` 与 51 坐标算例的 `+0.395 m` 同量级：1 kN 检测门 + 6.4 m 弹性坡道上力从 0 连续增长，这一项是**观测定义**的固有偏移，不是误差。

### G5 逐轨份额（整段 801 帧）

```
share 0.966 .. 1.029   (worst axle1_right at 58.633 m)  -> inside [0.625, 1.6]
```

## 5. 这一轮能说与不能说

**能说**

- 四件（完备车辆 / 柔性轮对 / 柔性轨道 / 真道岔几何）第一次装进同一算例：234 坐标、15 刚体、16 接触体，**七门 7/7**。
- 该算例能**跨过尖轨尖端并读出载荷转移**：首载 58.144 m、峰值 40.77 kN、右侧 67.8 % 在尖轨上——这是后续反演要用的观测量，且第一次由"最完备的车"给出。
- 座椅 6.927e-09 N、八轮 1.000× 均分，**座椅只花 0.6 s** ⇒ 成本瓶颈在积分不在装配。

**不能说**

- 这不是曲线能力：只跑**直向**、单一进场点、80 km/h 一档。
- 这不含 M2（B047 横向注册）与 M3（3.3 m 设计读法仲裁）的结论，二者仍开着，横向量仍不可引用。
- 这不等于目标主门（Ω_obs 上绝对误差 p95 ≤ 22 µm）有进展：反演尚未开始。
- 逐体列只有 **10** 个标签出现（`axle*_left/left:main` 4 个、`axle*_right/stock` 4 个、`axle1/2_right/blade` 2 个），因为`frog` 在 103 m 之后、`blade` 只在坡道上才承载——**14 个声明体里 4 个全程无载，是几何决定的，不是丢数据**。

## 6. 成本

| 时长 | 帧数 | 墙钟 |
|---|---|---|
| 0.02 s | 41 | 9.3 s |
| 0.40 s | 801 | 180.0 s |
| 座椅 | — | 0.6 s |

⇒ 约 **450 s / 模拟秒**（234 维，含座椅）。跑到尖轨区出口（前轴 60 m ⇒ 0.45 s）约 200 s；跑到心轨（前轴 110 m ⇒ 3.1 s）约 1 400 s。

## 7. 复算

```bash
cd Velch
PYTHONPATH=src python -X utf8 scripts/s101_one_set_case.py --dry          # 装配与维数
PYTHONPATH=src python -X utf8 scripts/s101_one_set_case.py --seat         # 座椅 + 逐轨载荷
PYTHONPATH=src python -X utf8 scripts/freeze_baseline.py --check          # 冻结基线
PYTHONPATH=src python -X utf8 scripts/s99_run_archive.py \
    --case vehicles/turnouts/CN60-1100-1_18/cases/straight_one_set.json \
    --speed-kmh 80 --duration 0.40 --note campaign=one-set-m1
PYTHONPATH=src python -X utf8 scripts/s102_one_set_check.py --write       # G3–G5
PYTHONPATH=src python -m pytest tests/test_one_set_case.py -q             # 回归
```
