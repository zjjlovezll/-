# 多核并行、Simpack RWP 机制与 CONTACT 接入

本文记录三件事：Velch 的多核改造（含实测）、从 REA 与模型文件能确定的 Simpack 轮轨对（RWP）实现方式、
以及接入 CONTACT 原生库的接口约定。所有数字均为本机实测，不是估算。

---

## 1. 多核改造

### 1.1 为什么单次求解不能靠多核

一次 1.2 s 工况是初值问题：`q(t+Δt)` 依赖 `q(t)`，时间轴上无法切分。可并行的只有两个轴：

| 并行轴 | 粒度 | 是否可用 | 实测 |
|---|---|---|---|
| 时间轴 | 一次求解内部 | 不行（串行初值问题） | — |
| 每个 RHS 的 8 个轮轨 patch | 一次求解内部 | 可行（无共享状态） | **更慢，见 1.2** |
| 独立算例（扫参、反演、多工况） | 算例之间 | 可行 | **近线性，见 1.3** |

### 1.2 线程并行（`--workers`）：实测更慢

`VehicleDynamics` 现在可以把 8 个 `axle{n}_{side}` patch 分派到 `ThreadPoolExecutor`：

```bash
python -m velch run-vehicle case.json --output out --workers 8
```

结果逐位一致（`history.csv` SHA-256 完全相同），但**墙钟变慢**：

| 配置 | 墙钟 | 相对 |
|---|---|---|
| `--workers 1`（串行） | 2.42 s | 1.00× |
| `--workers 4` | 4.20 s | 0.58× |
| `--workers 8` | 4.57 s | 0.53× |

原因是 CPython GIL：每个 patch 的计算是大量小数组上的 `np.unique` / `np.interp` / `np.gradient`，
单次只有几十微秒，线程调度与 GIL 争用的开销超过并行收益。**因此默认 `--workers 1`，该开关只作为
正确性对照保留，不作为提速手段。** 真正的单次求解提速只能来自减少每次 RHS 的工作量
（接触局部化、批量向量化、查表），不是线程。

### 1.3 进程并行（`--jobs`）：近线性

新增 `velch/parallel.py` 与 CLI 子命令：

```bash
python -m velch run-vehicle-batch case_a.json case_b.json ... --output-root out --jobs 8
```

每个 worker 进程独立加载自己的算例、独立写输出目录，无共享状态。每个进程内部仍用 BLAS 单线程，
所以 `jobs` 可以直接取物理核数。

实测（本机 20 逻辑核，8 个独立算例，每个 0.02 s 道岔工况）：

| jobs | 墙钟 | 各算例累计 | 加速比 |
|---|---|---|---|
| 1 | 46.65 s | 46.64 s | 1.00× |
| 8 | 6.30 s | 44.04 s | **6.99×** |

4 个算例时 `jobs=4` 为 **3.65×**（32.06 → 7.71 s）。并行前后同一算例的 `history.csv` 逐位一致
（`cd6950786ff87bac…`），8 个算例的门限全部 `numerically_checked`。

### 1.4 换算到实际任务

| 任务 | 串行 | `--jobs` 8 | `--jobs` 20 |
|---|---|---|---|
| 1 个 1.2 s 道岔工况（已带站间缓存，245 s） | 245 s | 不变（单算例） | 不变 |
| 8 个 1.2 s 工况 | 1960 s | ≈250 s | ≈110 s |
| 反演 1000 组（每组 1.2 s） | 68 h | 8.5 h | 3.4 h |

结论：**多核解决的是吞吐量问题，不是单次求解的延迟问题。** 反演、灵敏度扫掠、参数标定这类
"成百上千次独立正演" 立刻可获得 7–18 倍；单次 1.2 s 工况仍受单核算力约束，需要 1.2 节以外的
单核优化（接触局部化窗口、8 patch 批量向量化、0.5 mm 型面查表）。

---

## 2. Simpack 的 RWP 是怎么做的（REA 能给到哪一层）

### 2.1 REA 实际给了什么、没给什么

2026-10-14/15 用 Ghidra 12.1.4 + REA 6.4.0 逆向 `_simpack-com-slv.exe`（130,827 个函数），
并按地址最前段导出前 100 个函数的伪 C。**结论必须说清楚**：

- 定位到 44 个脚本方法槽位，前四个依次是 `integ`、`integMeas`、`integBG` 的两个参数形式；
- 调用链：`integ`/`integMeas` → 时间积分包装 → `SolverTaskTimeIntegration::perform`（由
  `FortranCoop.dll` 导出）；`integBG` → `SolverTaskBackgroundIntegration::create`；
- 再下一层到 `FortranInterface.dll::solver_calc_time_integration` → 方法选择 → 通用时间推进 →
  对被选积分函数指针的间接调用；
- **到此为止只有"任务编排层"。轮轨接触的法向/切向公式、接触搜索、积分器内部实现都在 Fortran
  内核里，REA 没有拿到。** 所以"REA 让我了解了 Simpack 的接触算法"这个说法是不成立的。

REA 的真正价值是确认了求解是"官方 CLI 子进程 + Fortran 内核"，从而可以放心地把
`simpack-slv.exe` 当作黑箱基准，而不是试图复刻它的内部。

### 2.2 从模型文件可以确定的 RWP 机制（这些是硬证据）

`CRH380A_M_Wheelset.spck` 里 `$RWR_Rail_1` 与 `$RWP_L/$RWP_R` 的原始语句：

| 语句 | 值 | 含义（可推断） |
|---|---|---|
| `rail.sides` | 2 | 一根参考轨，左右各一条 |
| `rail.r.prof.file(1..236)` | `Profile_Mileage_*.prr` | 右轨 236 个型面 |
| `rail.r.prof.s(1..236)` | 0.0, 5.0, 10.0 … 150.0 | 每个型面的里程，与型面序号一一对应 |
| `rail.r.lat.dist` | 0.753 m | 右轨横向位置（单值，不随里程变） |
| `rail.lat.kind` | 1 | 横向距离的定义方式（按 `gaugepos` 处的轨距点） |
| `rail.gaugepos` | 0.016 m | 轨距测量点在轨顶下 16 mm |
| `rail.r.prof.disc` | 5.0e-4 m | **型面离散化步长 0.5 mm** |
| `rail.r.cant` | `$_WS_RWP_RailCant` = 0 | 轨底坡（模型取 0） |
| `rwpair.cont.kind` | 4 | 型面—型面接触 |
| `fn.kind` | 2 | 法向力模型 |
| `ft.refvel.kind` | 3, `ft.minvel` 0.01 | 切向参考速度模型 |
| `wheel.state` | 6, `wheel.rot.sign` -1 | 车轮自由度/转向约定 |
| `cont.e` / `cont.pois` | 2.1e11 / 0.28 | 接触材料常数 |
| `$_WS_RWP_ContactDamping` | 1e5 N·s/m | 接触阻尼 |
| `$_WS_RWP_FricCoeff` | 0.4 | 摩擦系数 |

再结合结果文件结构：每个 RWP 输出 **5 个接触斑容器**（`$RS_RWP_R_1..5_Adv`，`result.type = 80`，
`result.par(4)` 为接触斑序号 1…5）。这说明 Simpack 的一对轮轨**允许同时存在最多 5 个接触斑**，
而不是只取一个。

由此可以确定的三条实现要点，正好是 Velch 当前缺的：

1. **型面先离散化成 0.5 mm 表**（`prof.disc`），接触搜索在这张表上做，代价被压到很低；
2. **接触是局部/连续搜索**：以上一步的接触位置为初值，在某条分支上找，而不是全局取最大侵入；
3. **允许多个接触斑**：辙叉区基本轨/翼轨/心轨可以同时接触，跨斑时力是连续的。

Velch 现在是"整条 z(y) 折线 + 全局 argmax + 单斑"，于是在 80.278→80.911 m 这种型面横向回落
73 mm 的位置，接触点会在分支间跳变，每次跳变都被当作几何台阶，侵入从 0.17 mm 抬到约 1 mm，
再乘上偏软的接触刚度，就得到 599 kN 的假冲击。**这不是型面数据错误，是接触搜索策略的差异。**

---

## 3. CONTACT 接入的接口约定

`contact_addon_win64.dll`（约 55.6 MB，Intel oneAPI 编译，Hertz 球面算例与解析解差 0.0083%）已经可用。
Vech 侧要替换的是 `contact.evaluate_contact` 的两个部分：

| 现在 | 目标 |
|---|---|
| `hertz_effective_radius`，`effective_radius_m` 硬编码 0.02 | CONTACT 模块 3：输入轮/轨型面点 + 法向力，返回接触斑尺寸 a、b、法向力与压力分布 |
| `sditt_cubic_saturation` 线性蠕滑 + 三次饱和，刚度 1e6/5e5 硬编码 | CONTACT 切向模块：输入 a、b、蠕滑率、μ，返回 (Fx, Fy, Mz) |
| 全局 argmax 单接触斑 | 局部连续搜索 + 每侧多斑（与 Simpack 的 1…5 斑对齐） |

保留 `hertz_effective_radius` 作为无 DLL 时的降级路径，便于回归对比；正式算例默认走 CONTACT。

需要的输入（都已经能从模型与型面拿到）：

- 接触点处轮/轨的曲率半径（由型面数值求导，不再用常量 0.02）；
- 接触材料 E = 2.1e11、ν = 0.28（`cont.e` / `cont.pois`）；
- 摩擦系数 0.4（`$_WS_RWP_FricCoeff`）、接触阻尼 1e5 N·s/m（`$_WS_RWP_ContactDamping`）；
- 蠕滑率由 `v`、自旋、横移速度与 `travel_speed` 组合得到（已是现成量）。

---

## 4. 复现命令

```bash
# 单算例（串行，接触线程默认 1）
python -m velch run-vehicle validation/crh380a_m/case_B_turnout.json --output out_B --workers 1

# 多算例并行（jobs = 物理核数）
python -m velch run-vehicle-batch validation/crh380a_m/case_A_plain.json \
    validation/crh380a_m/case_B_turnout.json --output-root out_batch --jobs 8
```

`manifest.json` 的 `summary` 里 `result_status` 仍是 `numerically_checked` 才算通过；
`physics_validation_status` 恒为 `unvalidated_against_measurement_or_Simpack`，并行不改变这个事实。
