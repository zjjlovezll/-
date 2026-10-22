# 能力清单：现在的 Velch 到底准备好了什么（2026-10-20）

回答一个问题：**轮轨接触算法、车辆动力学算法、调用与修改入口，是否都已就绪？**

结论先说：**接触与车辆动力学都已就绪且经过冻结 oracle 与 Simpack 对照；调用与修改入口已固定并有测试保护；反演的“观测量层”已就绪，“可辨识性 + 估计器”尚未开始；实测数据尚未接入（我在这台机器上没找到你的过岔实测文件）。**

测试基线：`pytest tests` → **89 passed**。

---

## 1. 轮轨接触算法

| 能力 | 位置 | 状态 | 证据 |
|---|---|---|---|
| 单点接触搜索（有界窗 + 全局回退） | `src/velch/contact.py: find_graph_contact` | 就绪 | 有载站位与全跨度路径 worst \|Δpen\| **0.08 µm** |
| 多点/多轨体（每侧多体、斑去重） | `find_graph_contacts` `merge_contact_responses` | 就绪 | `RailBody` 3 体（main/point/wing）跑通 |
| 解析几何路径（样条 + 扫掠极值） | `src/velch/contact_geometry.py` | 就绪（实验） | 与网格路径 \|Δpen\| 0.08 µm、\|ΔR*\| 6.35% |
| 法向力律 | `contact_law.py` + `contact.py` | 就绪，可插拔 | `point_hertz` / `strip_integral`（(π/4)E*ΣδΔy + 自洽 δ_eq） |
| 接触刚度 | `local_circular`（曲率导出） | 就绪 | 平直段静载侵入 **65.5 µm**，Simpack 反算 **66.2 µm**（−1.1%） |
| 法向阻尼 | `fixed_coefficient` / `hunt_crossley` | 就绪，可插拔 | 硬刚度下 HC 使脱空 3→**0** |
| 轨下支撑柔度（串联） | `support_compliance.py` | 就绪，默认关 | 平直段 162 Hz 波纹、力幅 ±0.65 kN |
| 切向力 | `evaluate_contact` 蠕滑+μF_n 三次饱和 | 就绪（简化） | 未接 Kalker/FASTSIM |
| CONTACT 官方库 | `contact_native.py` | **仅 Hertz 探针** | 未接入 `run-vehicle` |
| 轨底坡 1:40 | `graph_from_points(roll_rad, roll_pivot_*)` | 就绪 | 静载逐位不变，侵入 65.5→**60.8 µm** |

**冻结对照**：1.2 s、350 km/h、CRH380A_M、18 号道岔直向
| | Velch | Simpack |
|---|---|---|
| 整程右轨峰值 | 123.60 kN（钢轨自由度）/ 158.04 kN（刚体轨道） | 134.97 kN |
| 最小力 | 16.76 kN | 27.67 kN |
| 脱空采样 | 0 / 2401 | 0 / 2401 |
| 轮对垂向行程 | 0.5954 mm | 0.5944 mm |
| 主频 | 36.65 Hz | 31.65 Hz |

## 2. 车辆动力学算法

| 能力 | 状态 |
|---|---|
| 35 自由度（4 轮对 + 2 构架 + 车体），Y/Z/roll/pitch/yaw | 就绪 |
| 垂向静平衡（超定 7 自由度 + 轨下自由度） | 就绪，残差 0.000 N，下沉 0.4628 mm |
| 积分器 DOP853 / Radau | 就绪（显式为主，隐式慢 1.46×） |
| 一/二系悬挂、抗蛇行、横向止挡 | 线性弹簧-阻尼就绪；非线性止挡未做 |
| 输出契约 | `history.csv`（123 通道）+ `manifest.json` + `case_snapshot.json` |
| 8 项数值门 | 就绪（完成性/有限性/预载/侵入上限/摩擦界/边缘接触/作用反作用/轨道反力） |

## 3. 轨道模型

`rigid` → `local_compliant`（每轨 2 DOF）→ `modal` → **`layered`（任意层数）**，`TrackLayer` 可堆叠钢轨/扣件/轨枕/垫板/轨道板；层数 1 与 `local_compliant` 逐点等价（0.13%）。1:40 轨底坡、`support_compliance`、岔枕 600 mm 参数均已可用。

## 4. 调用与修改入口（已固定）

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -m velch run-vehicle <case.json> --output <目录>     # 单工况
python -m velch run-vehicle-batch <case...> --jobs 8        # 多工况（8.58×）
```

- **改物理**：算例 JSON 的 `contact` 段选策略（`point_policy` / `stiffness_policy` / `normal_policy` / `damping_policy` / `geometry_policy`），`track_dynamics` 选轨道类型与层数，`support_compliance`、`rail_profiles` 的 `roll_rad`；默认值保持历史行为，旧算例不改即可跑。
- **改代码**：`contact.py`（搜索/力律）、`contact_law.py`（策略）、`vehicle_solver.py`（组装/积分/聚合）、`track_models.py`（轨道）、`io/history.py`（输出契约）。四处都有测试覆盖。
- **加观测量**：`inverse/observation.py` + `inverse/channels.py`。

## 5. 反演与实测（这是缺口所在）

已就绪：
- `io/history.py`：带单位/类别的 history 契约（`velch-history-v1`）；
- `inverse/observation.py`：`ChannelSpec`/`ObservationSet`/`align`，三策略（station / time / event），真实数据验证（仿真对仿真零点 rms **10.55 kN**，数据自推偏移 −0.65 m；事件锚定把 20 ms 错位从 62.4 压到 **0.000 m/s²**）；
- `inverse/channels.py`：四类传感器契约 + **应变→弯矩→轮轨力**（静载标定优先，或 E/I/c + 影响线）、事件检测（峰值/谷值、里程换算）。

未就绪：
- **可辨识性层**（`coverage` / `separating_excitation`）——没有它，反演会去估一个当前工况根本激励不到的参数；
- **估计器**（有限差分 → 伴随 → GPU 批量）与不确定度；
- **实测数据接入**：仓库与 H:/G: 常见目录里没有找到你的过岔实测文件（只找到 Simpack 磨耗输出与 CONTACT testbank），`from_csv` 目前只用合成数据验证过。

## 6. 实测验证方案（用另一个道岔）

需要你提供三样，缺一不可：

1. **实测文件**（路径即可）：时间 + 各通道数值；轴箱加速度三向、钢轨加速度、轨腰/轨底应变、位移计，任一子集都行，但要标明采样率与单位。
2. **测点里程**：每个传感器在道岔内的里程位置（相对直向起点或某基准点），以及过岔速度。
3. **该道岔的型面与支撑参数**：PRR 型面集合（按里程）、岔枕间距、扣件/垫板刚度（若与该 18 号不同）。

流程（代码已备）：
1. `standard_turnout_plan()` 建通道契约 → `observed_from_measured()` 载入实测；
2. `detect_peak_event()` 用应变/加速度峰定辙叉鼻端事件时刻；
3. 把该道岔建成 `case.json`（型面 + 支撑 + 轨底坡），跑 `run-vehicle`；
4. `align(..., strategy="event")` 得残差；再用 `station` 策略与 Simpack 同工况比；
5. 残差若不达标，先查**对齐**（偏移、速度、里程基准），再查**物理**（刚度、阻尼、层数）。

## 7. 计算效率：现状与目标

| 项 | 实测 |
|---|---|
| 单点接触 `find_graph_contact` | 101.2 µs/次 |
| 型面采样 `ProfileSeries.sample` | 24.9 µs/次 |
| 两者合计占墙钟 | **86.7%** |
| 单次 RHS（layered） | 1.76 ms |
| 0.05 s 辙叉窗 | 67.93 s |
| 1.2 s 整程（估算） | ≈ 850 s |
| Simpack 同工况 | 墙钟 85.08 s / CPU 718.91 s（32 线程） |
| 多进程 8 工况 | **8.58×**（543 s → 63 s） |
| 多线程（`--workers`） | 变慢（GIL） |

**判断**：单核算力与 Simpack 相当（同一量级的 CPU 时间），差距在并行度（32 线程 vs 单线程）和热点结构。**提速路线按收益排序**：
1. `(s, y)` 二维查表替代每次 `sample + 插值`（预计把 86.7% 的热点降到 1–2 µs，整程 5–8 s 量级）；
2. 接触几何表预建（对标 Simpack GT，但按轨体惰性建）；
3. 进程级并行（已有 8.58×）+ GPU 批量（S3）；
4. 隐式积分 + 解析 Jacobian（S2，配合 torch.func.jacrev）。

## 8. 复现

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 -m pytest tests -q --basetemp F:\velch_tmp\pytest   # 89 passed
cd validation\crh380a_m; python -X utf8 demo_observation.py
```
