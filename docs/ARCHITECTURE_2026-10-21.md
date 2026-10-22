# Velch 架构收口与 Simpack 2021x 对标（2026-10-21）

> **一句话结论**：Velch 在**反演与可辨识性**上已越过 Simpack（Simpack 2021x 没有内置估计器，
> 它的强项是前向保真度与工程化）；在**前向保真度**上，剩下的差距不是"物理定律写错了"，
> 而是四道结构性取舍——接触搜索缺分支跟踪、积分器停在显式、钢轨没有空间离散、
> 车辆没有轴箱体。这四道缺口各自可以独立落地、各自有可验收的回归门，本文给出顺序与门。
>
> **架构层面**：真正的问题不是"模块太多"，而是 ①`contact.py`（1115 行）与
> `vehicle_solver.py`（769 行）各自承担 5 类职责，②数据层 `io` 在类型上反向依赖分析层
> `inverse`（靠 `TYPE_CHECKING` + 函数内 import 两处技巧维持，没有契约模块），
> ③`case/spec.py` 直接依赖前向契约模块，④v1 求解器 `solver.py` 只为一个异常类被 v2 拉进依赖图。
> 这四条都有"只移动代码、用已落盘产物证等价"的拆分路径。

---

## 0. 本文的边界与复核方式

### 0.1 行号基准、以及它为什么可能已经漂了

本文所有 `文件:行号` 的行号取自 **2026-10-21 11:40 前后的工作树**。取证期间该工作树正被
另一个进程并发修改（无 `.git`，只能靠 mtime 判断）：

| 时刻 | 文件（改动后的行数） | 影响本文的 |
|---|---|---|
| 01:21 / 02:33 | `profiles.py`(305)、`contact.py`(**1115**) | 无人改动，行号稳定 |
| 09:37 | `gui.py`(643) | §4 GUI 引用 |
| 11:25 | `support_compliance.py`(186) | `series_normal_force_slope` 行号 |
| 11:26 / 11:28 | `inverse/bands.py`、`inverse/sensors.py` | §1 反演行 |
| 11:31 | `track_models.py`(326) | 模态分支行号（`q[35:]`） |
| 11:36 | `vehicle_solver.py` **763→769**（新增 `jacobian="analytic"` 分支）、`model.py`(269)、`jacobian.py`(346) | §2/§3 求解器与雅可比引用 |
| 11:37–11:43 | **新建整个 `src/velch/ui/` 子包**（`store.py` 608、`app.py` 544、`widgets.py` 543、6 个 `screen_*.py`、`selftest.py`） | §4 UI 边界 |

本文引用的行号在 **11:43 之后没有再变**；若与当前工作树不符，以 `_cite_check.py` 的输出为准
（它会把每条 `文件:行号` 对应的源码行打印出来，对不上就是漂了）。

因此：**行号只用于快速定位，符号名才是稳定锚点**。复核一条引用的方法：

```powershell
python -X utf8 _cite_check.py            # 全部锚点重解析，输出 路径:行号: 源码行
python -X utf8 _cite_check.py track_models   # 只看某个文件
python -X utf8 _arch_scan.py                 # 重算 import 图（本文 §2 的原始数据）
python -X utf8 _symidx.py                    # 全包符号索引 文件:行号: def/class
```

### 0.2 测试基线（本文写作时实跑）

```powershell
python -X utf8 -m pytest tests -q --basetemp F:\velch_tmp\pytest_arch
# 233 passed in 9.55s
```

其中新增 `tests/test_architecture_rules.py` 16 项（附录 A）。写作过程中还修掉了一条**他人遗留的
过期断言**（`tests/test_implicit_options.py` 断言 `jacobian="analytic"` 必须抛错，而
`src/velch/model.py:151` 已把它放开为合法值，导致套件红了一条）。总数随时间上涨
（取证开始时 212 项、我首次全量 1 failed + 211 passed、收尾 233 passed），
**验收只认 0 failed，不认具体数字**。

---

## 1. 能力矩阵：Velch × Simpack 2021x

### 1.1 差距性质口径

| 分类 | 含义 | 判据 |
|---|---|---|
| **能力缺失** | Simpack 能做、Velch 根本没有对应机制 | Velch 侧找不到入口函数/字段 |
| **精度** | 两边都有机制，模型假定不同 | 同一工程量差 > 5%，且差异可归因到假定 |
| **性能** | 机制等价，代价不可接受 | 墙钟/单步成本比 > 3× |
| **工程化** | 数值等价，可用性不足 | 缺 CLI/文档/通道字典/批处理 |

### 1.2 主表

| 维度 | Velch 现状（文件:行号） | Simpack 2021x 现状（证据） | 差距性质 |
|---|---|---|---|
| **接触几何** | 型面为折线/样条 `z(y)`，接触点 = 有界窗内全局 `argmax`：`contact.py:824 find_graph_contact`（窗由 `run.contact_search_half_width_m` 给，**生产算例未设 → 全跨度全局搜索**）；三条搜索路径 patch/strip/graph：`contact.py:543 / :676 / :824`；型面随里程插值 `profiles.py:198 / :238`；解析几何实验路径 `contact_geometry.py:202 swept_contact`（未进生产） | 型面先离散成 **0.5 mm 表**（`rail.r.prof.disc = 5.0e-4`），搜索在该表上做**局部连续搜索**（以上一步位置为初值在某分支上找，`cont_searchdeltay` / `cont_searchymax` / `cont_gtupdatekeys` 控制步长/上限/键更新）；型面随里程 **236 张**（`rail.r.prof.file(1..236)`、`rail.r.prof.s = 0,5,…,150 m`）；轨距点 `rail.gaugepos = 0.016 m`、`rail.lat.kind = 1`；`rwpair.cont.kind = 4`（型面—型面）；`rwcontact000..007` **八套**接触实现可切换 | **能力缺失 + 精度**。Velch 没有"分支跟踪"（跨跨度处接触点可从轮缘跳到踏面而不受任何连续性约束），也没有把多斑接进生产路径 |
| **多点接触** | `find_graph_contacts`（多瓣）存在但**生产未调用**：`contact.py:1041`；生产逐轨体单斑 `vehicle_solver.py:275 _evaluate_patch` → `merge_contact_responses` `contact.py:198` | 每个 RWP 输出 **5 个接触斑容器** `$RS_RWP_R_1..5_Adv`，`result.type = 80`，`result.par(4)` 为斑序号 → 一对轮轨允许**同时最多 5 个斑**，跨斑力连续 | **能力缺失** |
| **接触律（法向）** | 可插拔：`point_hertz` / `strip_integral`（`contact.py:46 NORMAL_POLICIES`）；生产 = `strip_integral`，`strip_dy_m = 5.0e-4`，`effective_radius_m = 0.02`，`effective_modulus_pa = 1.1393e11`（`validation/crh380a_m/case_full12_cap05.json`）；曲率由 `local_circular` 导出 `contact_law.py:95 local_curvature`；串联支承柔度 `support_compliance.py:134 series_normal_force`（**生产未启用**） | `rw.cont.meth = 2` 选中**离散弹性**（`p_eqv` 恒 0）——即弹簧底座上的压力分布，片间有弹性耦合；`fn.kind = 2`；材料 `cont.e = 2.1e11`、`cont.pois = 0.28` | **精度**。Velch 的 strip 是"每片独立 Hertz 再求和"，片间无弹性耦合，深侵入时偏硬/偏软取决于切片数 |
| **接触律（切向）** | **只有一种**：`sditt_cubic_saturation`，`contact.py:98` 硬报错拒绝其它值；线性蠕滑刚度硬编码 `creep_stiffness_x_n = 1e6`、`creep_stiffness_lateral_n = 5e5`（生产算例）；三次饱和 `contact.py:951 saturate_creep_force` | `ft.refvel.kind = 3`、`ft.minvel = 0.01`；摩擦系数 `$_WS_RWP_FricCoeff = 0.4`；Kalker/FASTSIM 类接触解可在 8 套实现里选 | **能力缺失**。没有自旋蠕滑矩 `Mz`，没有真实的蠕滑力—蠕滑率曲线 |
| **接触阻尼** | `delta_half_velocity` + Hunt-Crossley 系数 `contact_law.py:180`，生产 `normal_damping_n_s_m_1p5 = 3e7` 且 `damping_force_cap_ratio = 0.5`（**上限是必需的**：无界阻尼把转辙器 0.17 mm 台阶变成 406 kN） | `$_WS_RWP_ContactDamping = 1e5 N·s/m` | **精度**。两边量纲与定标方式不同；Velch 已用 57.14 vs 57.97 Hz 主频对齐 |
| **积分器** | 生产 = 显式 `DOP853`（`run.method`），`max_solver_step_s = 1e-4`、`output_step_s = 5e-4`、`rtol = 1e-6` → 1.2 s 用掉 **331 949 次 RHS**；BDF/Radau 可选但整车 1.2 s 在 `t ≈ 0.61 s` 出现 non-finite（`docs/S2_REMAINING_PATHS_2026-10-21.md`）；稀疏有限差分 `vehicle_solver.py:609`、解析雅可比 `:610 / :611` + `jacobian.py:39`（接触几何**冻结**求导，`jacobian.py:8`） | `SODASRT_2` **隐式 BDF**，Fortran 内核（`FortranInterface.dll::solver_calc_time_integration`，REA 逆向到此为止，公式不可见）；**32 线程**；整程 **85.08 s 墙钟 / 718.91 s CPU** | **性能**。Velch 单次 RHS 1.19 ms（Simpack 4.25 ms CPU）反而更快，但全局限步长使总墙钟 ≈850 s（10×） |
| **轨道结构** | 五种：`rigid` / `local_compliant`（每轨 2 DOF）/ `two_layer` / `layered`（任意层数）/ `modal`，`track_models.py:111 TrackKernel`、`:169 dimension`；生产 = `local_compliant`，`track_dof = 16`（8 条轨 × 2）；下支承柔度 `support_compliance.py:98`（默认关） | 本模型轨道由参考轨体 `$RWR_Rail_1` + `rail.sides = 2` + 236 张型面表组织；柔性轨道/FE 入口在证据范围内**未见启用**（spck 无 FE 输入引用） | **能力缺失 + 精度**。Velch 没有空间离散的钢轨，也没有地面反力旁证（modal 分支 `track_models.py:295` 返回 `None`） |
| **车辆自由度** | **35**：轮对 5×4（y,z,roll,spin,yaw）+ 构架 5×2 + 车体 5（`vehicle.py:191`，`:290` 处同一公式重复一遍）；**无轴箱、无纵向 `x` 自由度**——`axle{i}_x_m = x_start + speed·t` 是运动学强加，纵向蠕滑只产生偏航力矩 `vehicle_solver.py:221` | `wheel.state = 6`（满 6 状态刚体）；完整多体可含轴箱、齿轮箱、制动盘 | **能力缺失**。轴箱加速度只能由轮对加速度给**下界**（`inverse/sensors.py:82 wheelset_acceleration`） |
| **道岔执行机构** | **无**。可动部件靠静态 s-窗表达：`vehicle.py:117 RailBody.active_at`、`:149 contact_bodies`；尖轨/心轨断面沿里程变化可以表达（`profiles.py:198`），但**不能动**。全包 grep `actuator|switch_blade|tongue|throw` 只命中反演侧的事件名 `inverse/channels.py:262 detect_peak_event` | 本模型亦**无转辙机**：用 236 张型面表把"几何随里程变化"外部化。证据范围内未见 actuator 通道 | **能力缺失（双方皆缺）**。但对"反演道岔状态"这是必须自建的能力，无法向 Simpack 对标 |
| **观测量** | `history.csv` 生产算例 **155 通道**：`time_s` + 4×`axle{i}_x_m` + 35 车辆状态 + 16 轨道状态 + 51 个 `_per_s` + 48 个接触输出（每轨 `{normal_n,fx_n,fy_n,fz_n,penetration_m,active}`）；单位在 `manifest.json["units"]`，类别由 `io/history.py:56 classify`；标准指标 `metrics.py:73 / :140`（脱轨系数、轮重减载率、轮轴横向力） | 结果容器元素 **78/79/80** 各有完整通道表（含接触斑几何、蠕滑率、力），带单位与方向约定 | **工程化**。Velch 通道够用但**没有机器可读的通道字典**（语义只在 `classify` 的分支里） |
| **反演** | 完整且分层：通道契约 `inverse/channels.py:39 / :92`；应变→力 `:222`；对齐 `inverse/observation.py:247`；可辨识性 `inverse/identifiability.py:92`；LM 估计器 `inverse/estimator.py:118`；频带 `inverse/bands.py:153`；事件 `inverse/events.py:57` | **无内置估计器**（Simpack 是前向工具；参数辨识靠外部优化循环驱动前向求解） | **能力领先** |
| **UQ** | 线性化协方差 `σ²(JᵗJ)⁻¹`，`inverse/estimator.py:37 Estimate`（`scale` / `convergence` / `report` / `summary`）；有可辨识性判据 `normalised_sensitivity`（列范数 + 条件数） | 无 | **精度**。只到线性化，没有后验采样/剖面似然 |
| **批处理** | 进程池 `parallel.py:39 run_vehicle_batch`（8 工况 **6.99×**、4 工况 3.65×）；线程 `--workers` 实测**更慢**（0.58× / 0.53×，CPython GIL）；`vehicle_solver.py:66` 另有接触线程池 `contact_workers` | 32 线程；自带脚本/批量接口 | **工程化**。Velch 的吞吐靠进程，单次延迟没解 |
| **UI** | 两套并行：v0.3 Tk 工作台 `gui.py:90 VelchWorkbench`（`subprocess.Popen` 起 CLI，`gui.py:502`）+ 新六屏 `src/velch/ui/`（`store.py:608`，`--selftest` 0 报错） | 完整前后处理 GUI + **46186 页**离线文档 | **工程化** |

### 1.3 五条决定性差距

按"它解释了哪个数字"排序——每条都能落到一个已测指标上：

1. **接触搜索没有分支跟踪、多斑没接进生产** → 辙叉窗峰值 **89.7 kN vs 134.97 kN**、
   AC RMS **9.13 vs 23.30 kN**。Simpack 更"尖"，是因为它在轮缘/踏面分支上连续跟踪并在
   5 个斑之间连续分配；Velch 在全跨度取最大侵入，跨分支时接触点跳变，力被"平滑"掉了。
   这就是 `docs/ROADMAP_BEYOND_SIMPACK.md` 里"差距只剩'我们更平滑'"的机制解释。
2. **积分器停在显式** → 331 949 次 RHS、**≈850 s vs 85.08 s**。单步 Velch 更快，
   但隐式不可用（整车在 `t ≈ 0.61 s` 发散，根因是刚性接触 `∂N/∂δ ≈ 1.37e9 N/m` 的
   条件数），所以只能用 `max_solver_step_s = 1e-4` 硬顶。
3. **35 DOF 无轴箱、无纵向动力学** → 轴箱加速度只能给下界；纵向蠕滑不反馈到 `x`。
   这一条直接限制了"轴箱加速度反演道岔状态"这条路线的置信度。
4. **钢轨没有空间离散、模态只有一套坐标** → 30–60 Hz 结构响应缺失（加轨道板的负结果
   4.09→2.39 kN rms）。`track_models.py:188` 的 `q[35:]` 让左右轨共用一套模态坐标，
   `load_modal_track` 自己在 `track_models.py:84` 的报错信息里承认了这一点。
5. **反演能力领先但接不上工程链** → `inverse/` 在 CLI 里**零入口**（`cli.py:22` 的 8 个子命令
   没有一个是反演），实测数据接入只有 `io/measured.py:431 load_observations`，UQ 只到线性化。
   领先的能力没有被任何人调用，等于不存在。

---

## 2. 模块依赖与真实违规

### 2.1 实测 import 图

`python -X utf8 _arch_scan.py` 的 AST 扫描结果（相对导入已按 `level` 修正），只有内部边：

```
                       ┌─ cli ───────────────────────────────┐
   __main__ ──────────►│ run / run-vehicle / run-vehicle-batch│
                       │ inspect-* / contact-* / assess       │
                       └──┬────────┬────────┬────────┬────────┘
                          │        │        │        │
              ┌───────────▼──┐  ┌──▼────┐ ┌─▼─────┐ ┌▼────────┐
              │ vehicle_solver│ │metrics│ │solver │ │ parallel│
              └──┬───┬───┬───┘ └───────┘ └──┬────┘ └────┬────┘
                 │   │   │                   │           │
     ┌───────────▼┐ ┌▼───▼──────────┐        │           │
     │  jacobian  │ │ track_models  │        │           │
     └─────┬──────┘ └───┬───────┬───┘        │           │
           │            │       │            │           │
      ┌────▼────────────▼───┐ ┌─▼────────────▼───┐       │
      │      contact        │ │      vehicle      │◄──────┘
      └──┬────────┬─────────┘ └──┬─────┬──────────┘
         │        │              │     │
    ┌────▼───┐ ┌──▼──────────────▼┐ ┌──▼────────┐
    │profiles│ │support_compliance│ │   model   │
    └────────┘ └──────────────────┘ └───────────┘
                                     （v1 单轮对契约）

  独立下游：inverse/* ──► io.history          （运行时长边）
            io.measured ──► inverse.{channels,observation}
                            ↑ 只在函数体内 / if TYPE_CHECKING 里（=V1，运行时不连）
            case.spec ──► vehicle            ui.store ──► inverse.bands, metrics
```

实测入度（被多少模块 import）：

| 模块 | 入度 | 说明 |
|---|---|---|
| `profiles.py` | **6** | 最高。几何读取被所有人用，属正常共享内核 |
| `contact.py` | **5** | 次高。但它同时是最大的模块 → 见 2.3 |
| `vehicle.py` | 5 | 契约，合理 |
| `model.py` | 4 | v1 契约，**与 `vehicle.py` 概念重叠** |
| `vehicle_solver.py` | 2 | 只有 `cli` / `parallel` 用 |
| `io` / `inverse` / `case` | **0** | 前向侧无人引用。`inverse` 只被 `io.measured`（非运行时）与 `ui.store` 引用，`io` 只被 `inverse` 与 UI 引用，`case.spec` 无人引用（只有 `case/__init__`） |

### 2.2 四条真实违规（不是风格问题，是能力/可维护性直接受损）

**V1｜`io` ↔ `inverse` 包级反向依赖（靠两处人工技巧维持，没有契约模块）**

```python
# src/velch/io/measured.py:39               ← 作者显式承认这里有个环
if TYPE_CHECKING:  # pragma: no cover - import cycle broken at run time
    from ..inverse.channels import SensorChannel, SensorPlan        # :40
    from ..inverse.observation import ChannelSpec, ObservationSet    # :41
# 同一对 import 又在两个函数体内重复一次：
io/measured.py:192  from ..inverse.channels import SensorChannel, SensorPlan
io/measured.py:440  from ..inverse.observation import ChannelSpec, ObservationSet
# 反方向的运行时长边（真实存在）：
inverse/observation.py:25  from ..io.history import HistoryTable
```

**运行时没有环**——这一点必须说清楚，否则会误判。反向边由 `TYPE_CHECKING`（类型检查期才存在）
与函数体内惰性 import 两处技巧挡住，而且源码里就写着 `import cycle broken at run time`。
`import velch.io` 与 `import velch.inverse` 都干净通过（`tests/test_architecture_rules.py` 的
`test_downstream_packages_import_headless[velch.io]` / `[velch.inverse]` 两个子进程用例守着）。

**真正的问题是方向反了，而且缝没有名字**：`io` 是数据层，`inverse` 是分析层，现在
**数据层在类型上依赖分析层**。代价有三条，都不是理论风险：

1. 想做实测数据 I/O（读一个 `.xlsx`、写一个 CSV）就得让类型检查器解析整个分析层；
   `velch.io` 单独发布/复用到另一个项目时，`TYPE_CHECKING` 块会让 `mypy` 报缺模块。
2. 那两处技巧是**约定，不是约束**：谁把 `if TYPE_CHECKING:` 删了，环就在运行时回来，
   而错误会出现在一个和改动毫无关系的模块里（`ImportError: cannot import name
   'SensorChannel' from partially initialized module 'velch.io.measured'`）。
3. 缝的两侧共用了 4 个类型（`SensorChannel` / `SensorPlan` / `ChannelSpec` / `ObservationSet`），
   它们既不是 `io` 的、也不是 `inverse` 的——**没有归属就没有兼容性边界**，任何一侧改字段
   都会静默影响另一侧的 CSV 列名。

> 修法（见 2.4 的 S4）：新增 `src/velch/inverse/contracts.py` 只放这 4 个纯数据类的定义
> （不 import `io`、不 import `contact`），`io.measured` 只 import `contracts`，
> `inverse.channels` / `inverse.observation` 从 `contracts` 导入并逐名 re-export。
> 收益不是"修 bug"，而是**去掉两处技巧并把依赖方向翻正**：
> `io → contracts ← inverse`，两侧都只依赖契约。
> 在那之前，`test_io_measured_touches_inverse_only_below_run_time` 钉住"这两处 import
> 不得升到模块级"——这是当前唯一能自动发现"技巧被拆掉"的哨兵。

**V2｜`case/spec.py` 直接依赖前向契约模块**

```python
# src/velch/case/spec.py:27
from ..vehicle import VehicleCase, load_vehicle_case
```

`case/` 的设计意图是"参数扫描/案例生成的纯数据层"，但它 import 了 `vehicle.py`，而
`vehicle.py` 又 import `contact.py`→`profiles.py`/`support_compliance.py`/`track_models.py`。
结果：**想只读一个算例文件、做参数遍历，就必须把整个接触几何栈导入进来**。
（`vehicle.py` 本身不 import 求解器，所以这还不算"case 依赖 dyn 侧"的硬违规，
但它是同一条依赖方向的下一步。）

**V3｜`vehicle_solver.py` 只为借一个异常类就拉进整个 v1 求解器**

```python
# src/velch/vehicle_solver.py:23
from .solver import SimulationFailure
```

`solver.py`（232 行）是 v1 单轮对求解器，含 `simulate`（`solver.py:129`）与 scipy 编排；
v2 一行都不用，只要 `SimulationFailure`（`solver.py:18`）。后果：
`import velch.vehicle_solver` 时 v1 求解器全部被导入，两个求解器的生命周期被绑在一起。
已由 `test_vehicle_solver_borrows_only_the_exception_from_v1` 把这件事**固定在"只借一个名字"**，
防止 v2 悄悄复用 v1 的编排。

**V4｜`contact.py` 内部导入与数据定义交错**

```python
# src/velch/contact.py
:22  GEOMETRY_POLICIES = ("grid", "patch", "fixed_grid", "cached_grid")
:32  from .support_compliance import series_normal_force     ← 夹在常量中间
:34  CURVATURE_POLICIES = ("window", "grid_stencil")
:46  NORMAL_POLICIES = ("point_hertz", "strip_integral")
```
功能性无害，但它是一个信号：这个文件已经长到"新代码只能就地插进去"的程度。

另有一处**符号来源错位**（不影响运行，影响可读性）：
`jacobian.py:173` 函数内 `from .contact import hunt_crossley_coefficient`，而该符号真正定义在
`contact_law.py:180`，`contact` 只是把它 re-export 了。

### 2.3 上帝模块：`contact.py` 与 `vehicle_solver.py`

| 文件 | 体量 | 承担的职责 | 证据 |
|---|---|---|---|
| `src/velch/contact.py` | **拆前 1573 行 / 52.4 KB / 18 个顶层符号；2026-10-22 拆分后 384 行**（模块地图见 §2.4 S1） | ① 数据类与策略常量（`contact.py:22–:231`）② 型面栅格化与差分（`:258–:540`）③ 三条接触搜索算法（`:543–:940`）④ 法向/切向力律与力装配（`:951–:1041`）⑤ 进程级可变全局 LRU 缓存（`:258 _RAIL_GRID_CACHE_SIZE`、`:265 _rail_grid_cache`） | 20 个 `ContactParameters` 字段 + 约 30 条校验（`:61`/`:92`）；`ContactResponse` 20 个字段（`:174`） |
| `src/velch/vehicle_solver.py` | **769 行 / 40.8 KB / 8 个顶层符号** | ① 悬挂装配 `Connector`（`:29–:150`）② RHS 编排 + 种子/年龄/换体状态机（`:152–:409`）③ 静平衡求解（`:442–:527`）④ 时间推进与求解器选项（`:530–:718`）⑤ **冻结落盘契约**（`:720–:769`） | 跨调用可变状态 5 个：`_contact_seed` / `_body_cache` / `_seed_misses` / `_contact_age` / `_active_body`；三个魔法常数 `CONTACT_RESEARCH_INTERVAL = 40`（`:92`）、`BODY_SWITCH_MARGIN_M = 2.0e-5`（`:97`）、`BODY_SWITCH_RELEASE_M = 5.0e-5`（`:98`） |

`contact.py:265` 的进程级 LRU 缓存与 `derivative_pure`（`vehicle_solver.py:409`）的"纯函数"
承诺在语义上冲突（缓存只影响速度不影响值，但它是**跨调用状态**，且 `_rhs_sparsity` 依赖
"同一次快照"假设）。这一点在拆分时必须显式处理（把缓存变成 `ContactContext` 的实例字段）。

**重复实现**：DOF 公式在 `vehicle.py:191` 与 `vehicle.py:290` 各写一遍，语义必须永远一致——
这就是"每轨一套模态"改造时最容易漏改的地方。

### 2.4 拆分顺序（每步只移动代码，用已落盘产物证等价）

原则：**先切断最细的、无风险的边，再动大的**。每一步都是纯移动（函数体一字不改），
并用现有磁盘产物做逐字节等价证明。

| 步骤 | 动作 | 等价证明 | 风险 |
|---|---|---|---|
| **S0** | 新建 `src/velch/errors.py`，把 `SimulationFailure`（现 `solver.py:18`）搬过去；`solver.py` 与 `vehicle_solver.py:23` 都改成 `from .errors import SimulationFailure` | `python -X utf8 -m velch run-vehicle validation/crh380a_m/case_full12_cap05.json --output F:\velch_tmp\eq_s0` 后比对 `history.csv` 与 `validation/crh380a_m/out_full12_cap05/history.csv` 的 SHA-256 | 极低。切断 V3 |
| **S1** | 拆 `contact.py` → `contact_params.py`（`:22–:153`）、`contact_grid.py`（`:258–:540`）、`contact_search.py`（`:543–:1044`）；`contact.py` 保留 `ContactGeometry`/`ContactResponse`/`merge`/`dedup`/`evaluate_contact`/`saturate_creep_force`，并**显式 re-export** 全部旧名 | ① `pytest tests -q`（8 个 contact 测试模块全过）② 0.05 s 窗口算例两次运行 `history.csv` 逐字节一致 | 中。必须显式列名 re-export（不用 `import *`），否则测试里的 monkeypatch 目标会漂 |
| **S1 ✅ 已落地（2026-10-22）** | 实际命名为 `contact_models.py`（302 行：策略常量 + 四个 dataclass + `merge`/`dedup`）、`contact_grid.py`（157 行：站位栅格、坡度、曲率、`_rail_grid_cache`/`_RAIL_SLOPE_CACHE`/`RAIL_SLOPE_TABLE`）、`contact_search.py`（804 行：`_contact_on_span`/`find_patch_contact`/`find_strip_contact`/`find_spline_contact`）；`contact.py` 384 行，只剩策略分派（`find_graph_contact`/`find_graph_contacts`）与力律（`evaluate_contact`/`saturate_creep_force`），并显式 re-export 23 个旧名（含私有 `_contact_on_span`，`tests/test_contact_patch.py` 在用） | `pytest` **429 passed**（423 + `tests/test_contact_split.py` 6 项）；`scripts/auto_accept.py` → `verdict: ACCEPT`；冻结 oracle 与静载门未动 | 已消化。依赖方向 models ← grid ← search ← contact，无环；三个新模块仍在 `contact*` 叶子内，`test_contact_layer_does_not_import_its_callers` 自动覆盖 |
| **S2** | 拆 `vehicle_solver.py` → `assembly.py`（`Connector` + `_build_connectors`）、`contact_bookkeeping.py`（种子/年龄/换体）、`equilibrium.py`（`:442–:527`）、`integrator.py`（`:530–:718`）；`VehicleDynamics` 用**组合**持有前三者 | 整程 1.2 s 算例 `history.csv` 与 `out_final_full1p2s` 逐字节一致；`pytest tests/test_vehicle.py` | 中高。`save_vehicle_result`（`:720`）**一行都不动**，这是冻结 oracle 的落盘字节来源 |
| **S3** | DOF 公式去重：`vehicle.py:191` 与 `:290` 合成一个 `track_dof(kind, rails, layers, modal)` | 构造 5 种 `track_kind` 的算例，`Case.dimension` 与 `history.csv` 通道数全部不变 | 低 |
| **S4** | 切断 V1：新增 `src/velch/inverse/contracts.py`，把 `SensorChannel` / `SensorPlan` / `ObservationSet` / `ChannelSpec` 的**纯数据定义**搬进去（不依赖 `io`、不依赖 `contact`）；`io.measured` 只 import `contracts`、并删掉 `:39` 的 `TYPE_CHECKING` 块与 `:192`/`:440` 两处函数内 import；`inverse.channels`/`inverse.observation` 从 `contracts` 导入并逐名 re-export | `python -X utf8 -c "import velch.io"` / `"import velch.inverse"`；`pytest tests/test_measured_processing.py tests/test_observation.py tests/test_architecture_rules.py`；`_arch_scan.py` 里 `io.measured → inverse` 的边必须为 0 | 中。`inverse/__init__.py` 的公开 API 必须逐名不变；CSV 列名不得变（`io.measured` 的 `CAMPAIGN_CHANNELS` 是外部契约） |
| **S5** | 切断 V2：`case/spec.py` 改为只依赖一个 `case/contract.py`（`Protocol`：`patched`/`resolve`/`names` 需要的那几个方法），由 `vehicle_case_adapter` 在 `cli` 侧注入 | 参数扫描测试 + 一个 `CaseSpec` 算例端到端跑通 | 中。这是唯一会动公开 API 的一步，放在最后 |

**不做**：不拆 `profiles.py`（6 个入度但职责单一）、不拆 `metrics.py`、不动 `track_models.py`
的数值分支（它是 §3.1 的改造对象，不是拆分的对象）。

---

## 3. 四道结构性缺口的落地方案与验收门

四道缺口的**依赖关系**是硬的，顺序不能乱：

```
①模态每轨一套 ──┐
                ├──► ④轨底应变桥路（影响线需要"哪条轨、哪个节点"）
②钢轨离散化 ────┘

③轴箱体 ──► （独立，但必须先定"新增质量怎么进静载门"）
```

②是①的超集：一旦钢轨有 N 个节点，"每轨一套"自动成立。但①的成本低一个数量级
（只改布局与 4 个方法的切片），所以**先做①验证接口，再做②替换实现**。

### 3.1 ① 模态块改为每轨一套

**现状（缺口本体）**

```python
# src/velch/track_models.py:188   local_state 的 modal 分支
eta, etadot = q[35:], v[35:]
# src/velch/track_models.py:239   internal_force
return -self.modal.stiffness_n_m * q[35:] - self.modal.damping_n_s_m * v[35:]
```

`q[35:]` 是**全部轨共用**的一段模态坐标。`load_modal_track`（`track_models.py:59`）在
`track_models.py:84` 自己承认了：

> `the modal block is shared by all rails (single set of modal coordinates), so it cannot
> represent independent left/right rail motion -- use track_dynamics kind 'layered' for that`

**目标 DOF 布局**

```
track_dof = len(rails) × mode_count
q[35 + r·K + k]   r = 轨序号（case.rails 的顺序）, k = 模态阶, K = mode_count
v[35 + r·K + k]   对应模态速度
```

**接口改动**

| 位置 | 改动 |
|---|---|
| `track_models.py:39 ModalTrack` | 新增 `per_rail: bool = False`；`mode_count` 保持总阶数，新增 `block(rail_index)` 返回该轨的 `(py, pz, dpy, dpz, k, c)` 切片视图 |
| `track_models.py:59 load_modal_track` | 参数语义从"rail template ids 必须完全一致"改为"允许的 rail id 白名单"；文件 schema 升 `velch-modal-track-v2`，允许 `shapes` 是 `dict[rail_id, modes]` |
| `track_models.py:172/:193/:241/:260` | `local_state` / `internal_force` / `contact_reaction` / `potential_j` 的 modal 分支改用 `self._slice(rail_index)`；`contact_reaction` 已带 `rail_index` 形参，天然可分 |
| `track_models.py:295 support_reaction` | 仍返回 `None`（模态无地面反力旁证），但每轨一套后可以给**每轨**的广义接触功率，`_integrate_vehicle` 的 `modal_generalized_contact_power` 门从"全局"收紧为"逐轨" |
| `vehicle.py:191` 与 `:290` | 第 4 分支 `modal_track.mode_count` → `modal_track.mode_count * len(rails)` |

**验收门**

| 门 | 断言 | 为什么这条门能证等价 |
|---|---|---|
| **G1 单轨退化** | `len(rails) == 1` 的模态算例，改造前后 `history.csv` **逐字节相同** | 单轨时 `r = 0`，`35 + 0·K + k` 与 `35 + k` 完全相同，布局退化为旧布局——这是唯一能要求"逐位"的场景，必须要求 |
| **G2 左右解耦** | 只激励 `axle1_left` 的初始模态位移，`axle1_right` 的模态通道 `max|η| < 1e-12 m` | 旧实现必然串（同一段坐标）；这条门在新实现下才可能过，是**能力成立**的判据 |
| **G3 冻结基线不动** | `out_full12_cap05` 与 `out_final_full1p2s` 的 `history.csv` SHA-256 不变 | 生产算例是 `local_compliant`，根本不进 modal 分支 → 基线必须一位不动 |
| **G4 DOF 公式一致** | 5 种 `track_kind` 下 `Case.dimension == len(history 通道里非接触列)` | 防止 S3 去重时两处公式再次分叉 |
| **G5 测试** | `tests/test_modal_contract.py` 扩充：逐轨 slice 互不重叠且并集 = `range(35, 35+track_dof)` | 布局正确性的直接证明 |

### 3.2 ② 钢轨离散化（真梁 / 多节点）

**现状**：钢轨只有 2 DOF（`local_compliant`：每轨 y、z 各 1），或一套全局模态。
`track_models.py:172 local_state` 返回"该站位的位移与速度"，本质是**集总参数**。

**目标**：`RailBeamTrack`——每轨 N 个节点，Euler-Bernoulli 或 Timoshenko 梁，
离散支承（轨枕间距 + 扣件刚度/阻尼），接触点在节点间用 Hermite 形函数插值。

**接口**

```jsonc
"track_dynamics": {
  "kind": "beam",
  "elements": 32,              // 每轨单元数
  "length_m": 25.0,            // 建模窗长（随车移动或固定窗，见下）
  "young_pa": 2.06e11,
  "second_moment_m4": 3.2e-5,
  "mass_per_m": 60.0,
  "damping_ratio": 0.02,
  "fasteners": { "spacing_m": 0.6, "stiffness_n_m": 5.0e7, "damping_n_s_m": 4.0e4 },
  "ends": "free"
}
```

**DOF 布局**

```
track_dof = len(rails) × 2 × (elements + 1)      # 每节点 (z, θy)；y 方向沿用局部柔度
q[35 + r·2(N+1) + 2n + 0] = z_n        q[... + 1] = θy_n
```

**接口改动**：`track_models.py` 新增 `RailBeamTrack` 类，`TrackKernel` 的 `local_state`
增加 `beam` 分支（Hermite 插值 + 形函数导数给速度）；`contact_reaction` 把点力按形函数
分配到两个相邻节点；`internal_force` 用梁单元刚度矩阵组装（带状，可直接复用
`_rhs_sparsity` 的骨架）。

**验收门**

| 门 | 断言 | 依据 |
|---|---|---|
| **B1 静力解析解** | 单点载荷 P 下的轨顶挠度 `w = P·β/(2k)`，`β = (k/(4EI))^{1/4}`，容差 2% | 弹性地基梁经典解 |
| **B2 网格收敛** | N: 16→32→64，挠度相对变化 < 0.5% | 离散化可靠性 |
| **B3 自由-自由一阶弯曲** | `f1 = (4.730/L)²/(2π)·√(EI/m)`，N = 32 时容差 1% | 与模态实现交叉验证 |
| **B4 与集总模型可比** | 静载下轨顶侵入与 `local_compliant` 的 65.5 µm 差 ≤ 2%（`local_compliant` 是 `k = 5e7` 的集总近似） | 说明 beam 不是"另一套物理"，只是更细的同一物理 |
| **B5 性能** | 单次 RHS 从 1.19 ms 增量 ≤ 3×（N=32、8 轨） | 否则 850 s 的整程会变成 2500 s，路线不可行 |
| **B6 冻结基线** | 生产算例 `kind` 不变 → `out_full12_cap05` 逐字节不变 | 同上 |

### 3.3 ③ 轴箱体

**现状**：35 DOF 里**没有轴箱**。一系悬挂把构架直接连到轮对
（`vehicle_solver.py:104 _build_connectors`，`primary_preload` 在 `:134`）。
后果是轴箱加速度只能由轮对加速度给**下界**（`inverse/sensors.py:82`），
而"轴箱加速度反演道岔状态"是本项目最现实的一条观测路线（轴箱比轮对好装、比钢轨好维护）。

**目标 DOF**：先做最简可行版本——每轴 2 个轴箱，每箱 2 DOF（`z`, `roll`），共 **+8 DOF**；
结构上把一系弹簧拆成"构架→轴箱"+"轴箱→轮对"两段。

```
n = 35 + 8 (+ track_dof)
axlebox(axle i, side s) 的基址 = 35 + 2·(2i + s)   s = 0 左 / 1 右
```

**接口改动**

- `vehicle.py`：新增 `AxleBox(mass_kg, inertia_roll_kg_m2, primary_top: SuspensionStage, primary_bottom: SuspensionStage)`；
  `VehicleCase` 新增 `axle_boxes: tuple[AxleBox, ...]`，`schema_version` → `velch-vehicle-v3`；
  `dimension` 公式第 2 项 +`2·len(axle_boxes)`。
- `vehicle_solver.py:104 _build_connectors`：一系 `Connector` 由 2 个变 4 个/轴（上下两段）；
  `body` 索引从 `wheel = 5i` 扩展为 `axlebox = 35 + ...`，**索引函数集中到一个 `index.py`**，
  禁止再散布魔数（当前 `20 + 5i` / `5i` / `30` 散布在 `:117`/`:134` 等处）。
- `inverse/sensors.py`：新增 `axlebox_acceleration(history, axle, side)`。

**验收门**

| 门 | 断言 |
|---|---|
| **A1 静载可解释** | 轴箱质量**属于新增质量**，静载门从 59 680.577 N 更新为 `59 680.577 + Σm_axlebox·g/4`，并在文档登记新基线。**不允许"隐式把质量从构架里挪"来凑旧数字** |
| **A2 一系力分配** | 静平衡时 `Σ(轴箱上方一系力) = Σ(下方一系力) = 半轴荷/2`，残差 < 1 N |
| **A3 新模态** | 线性化 A 矩阵特征值出现 ≥1 个落在 60–120 Hz 的新模态（轴箱垂向/侧滚），且不与既有 131.9 Hz 钢轨浮沉模态混淆 |
| **A4 观测能力成立** | `axlebox_acceleration` 与 `wheelset_acceleration` 在 >200 Hz 的 PSD 差 ≥ 3 dB（证明不再是下界） |
| **A5 冻结基线** | 不带 `axle_boxes` 的旧算例，`history.csv` 逐字节不变 |

### 3.4 ④ 轨底应变桥路（影响线积分）

**现状**：`inverse/channels.py:222 strain_channel_to_force` 走的是
`moment_from_strain` → `force_from_moment` → `influence_ordinate_simple_support`，
即"简支梁影响线"（`inverse/channels.py:200` 附近）。真实道岔区是**多点离散支承 + 变截面**，
简支假定在辙叉区误差最大——而辙叉区正是我们要反演的地方。

**目标**：把影响线从"解析简支"换成"由轨道模型算出的真实柔度"，并补上桥路类型。

**接口**

```python
# src/velch/inverse/channels.py 新增，只读轨道柔度、不进前向 RHS
def strain_from_beam(track, gauge_x_m: float, wheel_x_m: float, load_n: float, *,
                     section_modulus_m3: float, young_pa: float) -> float:
    """轨底应变：M = P·G(gauge_x, wheel_x)，ε = M/(E·W)。"""

@dataclass(frozen=True)
class StrainBridge:      # 桥路，决定温度与轴向应变的耦合
    kind: str            # "quarter" | "half" | "full"
    gauge_length_m: float
```

`SensorChannel`（`inverse/channels.py:39`）新增 `bridge: StrainBridge | None`；
`strain_channel_to_force` 增加 `influence: Literal["simple_support", "track_model"]` 开关
（**默认仍是 `simple_support`**，保证既有标定结果不漂）。

**验收门**

| 门 | 断言 | 目的 |
|---|---|---|
| **S1 同构退火** | 当梁的端部支承退化为简支且 EI 常数时，`strain_from_beam` 与 `influence_ordinate_simple_support` 差 < 1e-9 | 证明新实现是旧实现的**超集**，不是另一套公式 |
| **S2 量级** | `P = 80 kN`、跨中测点、`W = 3.0e-4 m³`、`E = 2.06e11 Pa` → ε ≈ 100 µε 量级，与 CRH380A 轨底实测同量级 | 量纲与量级自检 |
| **S3 现状误差量化** | 用 beam 生成"真值"应变，用简支影响线反演，记录 `误差%` —— 这个数字要进文档，作为"当前简化代价"的基线 | 把"简化"变成可验收的数字，而不是形容词 |
| **S4 桥路温度抑制** | `quarter` 保留温度应变、`half`/`full` 抵消：构造 `ε_temp` 输入，断言 `|ε_half − ε_mech| < 1e-12` | 桥路模型正确性 |
| **S5 反演闭环** | 用 beam 真值 + 1 µε 噪声，`estimator.gauss_newton` 收敛到 `k_s` 误差 < 1%，`1σ < 3%` | 端到端 |

---

## 4. UI 与 CLI 的边界

### 4.1 三层边界

```
┌──────────────────────────────────────────────────────────┐
│ UI（Tk: gui.py / 六屏: ui/*）                             │
│  职责：选算例、改参数、发起运行、读产物、画图、对比          │
│  依赖：只许 subprocess 调 CLI + 只读公开 API（见 4.2）      │
└───────────────┬──────────────────────────────────────────┘
                │ subprocess: python -m velch run-vehicle <case> --output <dir>
                │ 磁盘契约: out_*/{manifest.json, history.csv, case_snapshot.json}
┌───────────────▼──────────────────────────────────────────┐
│ CLI（cli.py:22）  8 个子命令 + 退出码 0/2 + stderr JSON      │
└───────────────┬──────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────┐
│ 前向 / 反演 / 数据层（vehicle_solver, track_models,         │
│ contact, jacobian, metrics, io, inverse）                 │
└──────────────────────────────────────────────────────────┘
```

**三条硬规则**（已由 `tests/test_architecture_rules.py::test_presentation_does_not_import_the_forward_stack`
机械执行）：

1. **UI 不复制数值逻辑**——不重算接触力、不重做积分、不自己实现脱轨系数。
2. **UI 不写产物**——`manifest.json` / `history.csv` / `case_snapshot.json` 只读。
   写算例只许写**新的** `case_*.json`（`ui.store` 目前正确遵守：它只有读路径）。
3. **UI 起算例必须走 CLI 子进程**——不许在 UI 进程里 `import vehicle_solver` 跑算例，
   否则一次长算例会把 UI 卡死，且无法用 `--workers/--jobs`。

### 4.2 稳定接口清单（UI 只许依赖这些）

**A. 算例目录与产物布局**

```
<workspace>/validation/<campaign>/case_*.json         输入算例（可枚举：glob case_*.json）
<workspace>/validation/<campaign>/out_*/manifest.json 每次运行的元数据
                          out_*/history.csv           状态与接触时间序列
                          out_*/case_snapshot.json    算例原始字节（用于溯源与复现）
```
`out_*` 目录名不含语义，**不要从目录名推断内容**——一切从 `manifest.json` 读。

**B. `manifest.json` 字段（`vehicle_solver.py:720 save_vehicle_result` 写出，冻结）**

| 字段 | 语义 | UI 用途 |
|---|---|---|
| `software` | `"Velch <version>"` | 版本徽标 |
| `case_sha256` | 算例文件哈希 | 判断"产物是否对应当前算例"（缓存失效） |
| `case_snapshot` | 快照文件名 | 溯源 |
| `input_asset_sha256` | 全部输入资产哈希 | 判断型面/数据库是否被换过 |
| `track_model` | `{kind, track_dof, modal_count, modal_exchange_schema}` | 决定"轨道通道怎么分组" |
| `state_order` | 长度 = `total_dof` 的状态名列表 | **唯一的通道顺序权威** |
| `units` | `{time, x, translation, rotation, force, penetration}` | 画图轴标签 |
| `summary` | 见 C | 状态徽标、gates、峰值、能量 |

**C. `summary` 关键字段**

`case_id` / `case_purpose` / `result_status`（`numerically_checked` \| `numerical_gate_failed`）/
`physics_validation_status`（**恒为 `unvalidated_against_measurement_or_Simpack`**，UI 必须原样显示，
不许美化成"已验证"）/ `vehicle_dof` / `total_dof` / `track_kind` / `track_dof` /
`rail_patch_count` / `connector_count` / `gates`（逐门 bool）/ `solver{method,nfev,rtol,atol}` /
`vertical_preload_max_residual_n` / `max_translation_balance_error_n` /
`max_modal_contact_power_error_w` / `max_penetration_m` / `max_friction_excess_n` /
`max_hertz_penetration_m` / `max_support_settlement_m` / `edge_limited_active_output_samples` /
`peak_normal_force_n` / `active_output_samples` / `initial_mechanical_energy_j` /
`final_mechanical_energy_j` / `energy_change_j` / `note`

**D. `history.csv` 通道命名契约**（生产算例实测 155 列）

| 组 | 数量 | 命名 | 备注 |
|---|---|---|---|
| 时间 | 1 | `time_s` | 等间隔 `output_step_s` |
| 轮对纵向位置 | 4 | `axle{1..4}_x_m` | **运动学**（`x_start + v·t`），不是自由度 |
| 车辆状态 | 35 | `axle{i}_{y_m,z_m,roll_rad,spin_rad,yaw_rad}`、`bogie{1,2}_{...}`、`carbody_{...}` | 见 C 的 `state_order` |
| 轨道状态 | `track_dof` | 例：`axle1_left_y_m`、`axle1_left_z_m`（`local_compliant`）；`layered` 为 `{rail}_{rail\|layerK}_{y_m,z_m}`；`modal` 为逐阶模态坐标 | **不要硬编码模式**——以 `TrackKernel(case).state_names` / `state_order` 为准 |
| 状态导数 | `total_dof` | 上述状态名 + `_per_s` | 51 个（35 + 16） |
| 接触输出 | `6 × 轨数` | `{rail_id}_{normal_n,fx_n,fy_n,fz_n,penetration_m,active}` | `active` 是 0/1 浮点 |

单位：`manifest.units`；类别（位移/速度/力/标志）：`io/history.py:56 classify`。

**E. `assess` 输出 JSON（`metrics.py:108 Assessment.as_dict`）**

```jsonc
{
  "history": "…", "samples": 2401,
  "limits": { "derailment_coefficient_max": 0.8, "wheel_load_reduction_max": 0.6,
              "lateral_force_limit_n": 29.9e3, "source": "GB/T 5599 …" },
  "axles": [ { "axle_index": 1, "samples": …, "normal_left_min_n": …,
               "derailment_coefficient": …, "derailment_side": "left",
               "wheel_load_reduction": …, "lateral_force_n": …,
               "contact_lost_samples": 0 } ],
  "maximum": { "…": 0.0 },
  "verdict": { "static_axle_load_n": …, "checks": { "…": {"value","limit","pass"} },
               "pass": true }
}
```

**F. CLI 契约**（`cli.py:22`）

| 子命令 | 参数 | 产出 |
|---|---|---|
| `run` | v1 算例 | v1 产物（**v1，已不推荐**） |
| `run-vehicle` | `<case.json> --output <dir> [--workers N]` | `out_*/` 三件套 |
| `run-vehicle-batch` | `<case...> --output-root <dir> --jobs N [--workers N]` | 每算例一个 `out_*/` + 汇总 dict |
| `inspect-profile` / `inspect-simpack-track` | 型面 / spck 路径 | JSON 到 stdout |
| `contact-native-status` / `contact-hertz-probe` | 可选 CONTACT 根目录 | JSON |
| `assess` | `<run 目录或 csv> [--static-axle-load-n P0] [--output f.json]` | 见 E |

退出码：`0` 成功；`2` 失败，且 stderr 是
`{"status":"failed","error_type":…,"message":…}`（`cli.py:143`）。

### 4.3 UI 允许 / 禁止 import 的边界

| 允许（只读或校验） | 禁止 |
|---|---|
| `velch.model`（v1 算例校验） | `velch.vehicle_solver` |
| `velch.vehicle`（v2 算例校验） | `velch.solver` |
| `velch.profiles`（型面绘图） | `velch.contact` / `contact_law` / `contact_grid` |
| `velch.metrics`（assess） | `velch.jacobian` |
| `velch.inverse.bands`（频谱，纯后处理） | `velch.track_models` |
| `velch.io.history`（读表） | `velch.parallel`（批量必须走 CLI） |
| `velch.case.spec`（参数扫描） | `velch.cli`（要用 CLI 就 subprocess） |

> `velch.profiles` 被允许，是因为画型面要用求解器同一条 `ProfileSeries`——
> 它是几何读取器，不是动力学模块，不构成数值逻辑复制。

### 4.4 现状对照（哪些已经合规，哪些还没）

| 组件 | 现状 | 判定 |
|---|---|---|
| `gui.py:90 VelchWorkbench` | 一切运行走 `subprocess.Popen`（`gui.py:502`，命令在 `:488` 组装为 `python -m velch run-vehicle`）；直接 import 只有 `model` / `profiles` / `vehicle` 用于编辑与校验 | ✅ 合规 |
| `gui_support.py:98 plot_series` | 只读 CSV 画图，`max_points = 3000` | ✅ 合规 |
| `ui/store.py` | 只读产物，import 仅 `inverse.bands`（`:24`）与 `metrics`（`:26`）；`read_history`（`:404`）、`spectrum`（`:519`）、`assess`（`:582`）、`compare`（`:696`）、`simpack_reference`（`:626`） | ✅ 合规 |
| `src/velch/ui/` 整体 | 11:37 开始新建、11:44 完成并**自检通过**：`python -X utf8 -m velch.ui --selftest` → 退出码 0，`6 屏 / 350 个控件 / 3128 行数据 / 0 个屏报错`；数据面 145 个运行目录、最宽 187 列、`out_full12_cap05` 154 个通道 / 2000 Hz、16 个 1/3 倍频程带（主导 39.37 Hz）、评价 3 项限值 + 7 项门全通过、Simpack 对照 4 项差值 / 400 个共里程点 @[23.5, 140.17] m、子进程流式通路 0.06 s 收到 3 行日志 | ✅ **已落地且自证**。注意它比本文 §4.1 的"三层图"少一层：UI **直接 import `metrics`/`inverse.bands` 做频谱与评价**，只有"跑求解"这件事经过 CLI 子进程 |
| `inverse/` | 无任何 CLI 入口 | ❌ **缺口**：反演能力没有对外接口，UI 无法调用 → 三个月路线 M3 补 `velch inverse` 子命令 |

---

## 5. 三个月路线

### 5.1 四轴与可验收指标

每条都写成"可测"，且**引用一个已存在的数**作为起点。

| 轴 | 起点（已测） | 目标 | 验收方式 |
|---|---|---|---|
| **能力** | 35 DOF 无轴箱；模态共用一套坐标；多斑未接入；无转辙执行机构 | +8 轴箱 DOF；每轨一套模态；多斑进生产；可动心轨几何 | 每项一条结构门（A2/A3、G2、接触斑数 = 2 出现在辙叉窗、执行机构有独立 DOF） |
| **精度** | 峰值 89.7 vs 134.97 kN；AC RMS 9.13 vs 23.30 kN；行程 0.641 vs 0.5944 mm；静载 −0.81% | 峰值进入 110–135 kN 且无量级跳变；rms 进入 15–25 kN；静载与侵入 ±2% | 与 Simpack 四量对照表 + `check_static_gate.py` |
| **性能** | 整程 ≈850 s（331 949 nfev）；单次 RHS 1.19 ms | 整程 ≤ 300 s（M1）→ ≤ 120 s（M3） | 墙钟 + `nfev` 双指标，且 `history.csv` 不变 |
| **工程化** | 反演无 CLI；通道无字典；测试 233 项 | 反演 CLI + 通道字典 + CI 脚本 | `velch inverse --help` 可用；`manifest.channel_dictionary` 存在；CI 一条命令 |

### 5.2 逐月

**M1（能力优先，把"平滑"解释掉）**

| 项 | 内容 | 验收 |
|---|---|---|
| 能力 | ① 模态每轨一套（§3.1） | G1–G5 全过 |
| 精度 | 接触搜索：把 `contact_search_half_width_m` 变为**生产默认**（有界窗 + 分支连续性），并把 `find_graph_contacts` 接到 `_evaluate_patch`（多斑） | 辙叉窗 80.278→80.911 m 段连续 20 帧 `\|ΔN\| < 20 kN`（现在会出现量级跳变）；峰值进入 110–135 kN |
| 性能 | 隐式打通：`jacobian="analytic"`（`jacobian.py:39`）跑整车 1.2 s，接触状态事件检测作为 BDF 的 restart 点 | 1.2 s 整车不出现 non-finite；墙钟 ≤ 300 s |
| 工程化 | 通道字典进 manifest；`_arch_scan.py` + `pytest` 进一条 CI 脚本 | `manifest.channel_dictionary` 可读；CI 单命令全绿 |

**M2（能力 + 精度并行）**

| 项 | 内容 | 验收 |
|---|---|---|
| 能力 | ③ 轴箱体 +8 DOF（§3.3） | A1–A5 |
| 精度 | 切向律：接 CONTACT 或近似 FASTSIM，产出 `(Fx, Fy, Mz)`；保留 `sditt_cubic_saturation` 作降级路径 | rms 与 Simpack 差距缩到 ±30% 内；`history.csv` 新增 `mz_nm` 通道 |
| 性能 | 批量：32 工况进程池；`contact_workers` 线程池单独定标（注意 GIL 实测 0.53×） | 32 工况 `effective_speedup ≥ 6×` |
| 工程化 | UI 六屏接 `assess` / 频谱 / 对比；`--selftest` 全屏通过 | `python -X utf8 -m velch.ui --selftest` 退出码 0 |

**M3（结构缺口收口）**

| 项 | 内容 | 验收 |
|---|---|---|
| 能力 | ② 钢轨离散化 `beam`（§3.2） | B1–B6 |
| 精度 | 四点对齐：静载 59 680.577 / 侵入 65.5 µm / 峰值 / 行程 0.593 mm，全部 ±5% | 对照表进 `docs/` |
| 性能 | 单次 RHS ≤ 3 ms（N=32、8 轨）且整程 ≤ 120 s | 墙钟 |
| 工程化 | 反演 CLI：`velch inverse --history <run> --channels <spec> --estimate rail_k_z,rail_c_z` | 端到端跑通 `inversion_waveform_demo.py` 的同一算例 |
| 工程化 | ④ 轨底应变桥路（§3.4）接口先落地（只读影响线） | S1–S5 |

### 5.3 明确不做（沿用 `docs/ROADMAP_BEYOND_SIMPACK.md` §7）

- 不做通用多体约束引擎（Velch 的 35+ DOF 是**结构化**的，通用化会毁掉性能与可读性）。
- 不做通用前后处理 GUI（Simpack 有 46186 页文档，不可能对标；Velch 只做"本项目的六个屏"）。
- 不在 M1–M2 碰轨下结构（负结果已两次确认：加轨道板 4.09→2.39 kN rms）。
- 不再调接触力律常数（`c = 3e7` + `cap = 0.5` 已定标，主频 57.14 vs 57.97 Hz）。
- 不为了"数字更接近 Simpack"而改冻结基线——冻结 oracle 是唯一可信的锚，
  任何基线变更都必须显式登记并说明质量模型差异（Simpack 静载 60 167.7 N 与我们差 412 kg 质量模型）。

---

## 附录 A：架构适应度函数（`tests/test_architecture_rules.py`，16 项）

全部是 AST 静态扫描，不 import 被测模块（无显示器、无 CONTACT DLL、无 h5py 也能跑）。

| 规则 | 断言 | 防的是什么 |
|---|---|---|
| `test_src_tree_is_populated` | 扫描到 `vehicle_solver`、`inverse.estimator` 等，边数 > 30 | 扫描器在错路径上"静默全过" |
| `test_inverse_is_never_reached_from_forward_code` | 前向/驱动/case 模块不得 import `velch.inverse.*` | 前向不能依赖分析层（可复现性） |
| `test_only_the_data_layer_and_presentation_read_inverse` | 唯二读者：`io.measured`（只借 channels/observation）、UI（只借 `inverse.bands`） | 缝被悄悄加宽 |
| `test_inverse_does_not_import_the_forward_solver` | `inverse/*` 不得 import 任何前向模块 | 分析层反吃动力学 |
| `test_contact_layer_does_not_import_its_callers` | `contact*` 不得 import `vehicle/solver/vehicle_solver/cli/...` | 叶子变成环 |
| `test_case_spec_only_touches_the_vehicle_contract` | `case/*` 只能 import `velch.vehicle` | V2 扩散 |
| `test_history_table_is_a_leaf_module` | `io.history` 不得 import 任何 Velch 模块 | `io` 与 `inverse` 之间唯一的无环锚点 |
| `test_contract_modules_do_not_import_the_implementation` | `model/vehicle/track_models/support_compliance` 不得 import 求解器 | 契约依赖实现 |
| `test_vehicle_solver_borrows_only_the_exception_from_v1` | `from .solver import` 的名字集合必须**恰好** `{SimulationFailure}` | v2 悄悄复用 v1 编排 |
| `test_presentation_does_not_import_the_forward_stack` | `gui/gui_support/ui.*` 只能 import 允许清单；`from velch import __version__` 逐行比对放行 | UI 复制数值逻辑 |
| `test_no_import_time_cycle` | **import 时**图无环（`deferred`/`typing` 边不算） | 循环导入 |
| `test_io_measured_touches_inverse_only_below_run_time` | `io.measured → inverse` 的边不得有一条是 `runtime`（必须是函数体内或 `TYPE_CHECKING`） | V1 的两处技巧被无声拆掉 |
| `test_downstream_packages_import_headless`（4 例） | `velch.inverse` / `velch.io` / `velch.case.spec` / `velch.metrics` 可独立 import | 下游层被迫依赖显示器/求解器 |

扫描器给每条边标注 `kind ∈ {runtime, deferred, typing}`：`runtime` 是模块级、import 就执行；
`deferred` 在函数体内、首次调用才执行；`typing` 在 `if TYPE_CHECKING:` 里、永不执行。
**方向类规则三种都算**（类型级的反向依赖仍然是反向），**只有环检测按 `runtime` 判**。

失败信息一律打印**完整的违规边**（`模块:行号 -> 被导入模块`），不需要再去 grep。

## 附录 B：复现命令

```powershell
# 全量测试（Windows 必须给 basetemp，否则默认临时目录 WinError 5）
python -X utf8 -m pytest tests -q --basetemp F:\velch_tmp\pytest

# 只跑架构规则
python -X utf8 -m pytest tests\test_architecture_rules.py -q --basetemp F:\velch_tmp\pytest_arch

# 冻结基线（不得破坏）
python -X utf8 -m velch run-vehicle validation\crh380a_m\case_full12_cap05.json --output validation\crh380a_m\out_full12_cap05
python -X utf8 validation\crh380a_m\check_static_gate.py
python -X utf8 validation\crh380a_m\minpen_report.py validation\crh380a_m\out_full12_cap05\history.csv
python -X utf8 validation\crh380a_m\bands_from_history.py validation\crh380a_m\out_full12_cap05

# 本文取证工具
python -X utf8 _arch_scan.py        # import 图（§2）
python -X utf8 _cite_check.py       # 行号锚点重解析（§0.1）
python -X utf8 _symidx.py           # 符号索引

# 反演能力（已存在，尚未有 CLI 入口）
python -X utf8 validation\crh380a_m\inversion_waveform_demo.py
python -X utf8 validation\crh380a_m\ab_observable_inversion.py
```

**冻结 oracle（不得破坏）**：静载 59 680.577 N、静平衡侵入 65.5 µm、整程 1.2 s
辙叉窗 89.7 kN 峰值 / 0 脱空 / 轮对行程 0.593 mm（`validation/crh380a_m/out_full12_cap05`、
`out_final_full1p2s`）。任何改动后 `save_vehicle_result`（`vehicle_solver.py:720`）的落盘字节
格式不得改变。
