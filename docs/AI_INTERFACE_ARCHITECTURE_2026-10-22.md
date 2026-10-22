# Velch 软件分层与 AI 接口架构（设计草案）

> **状态**：DRAFT（待评审，未落地任何代码）
> **日期**：2026-10-22
> **问题**：怎样把 Velch 从"一份能跑的研究代码"升级成**可交付的道岔动力学软件**，并给外部 agent/LLM
> 一个能建模、改参、跑仿真、取结果的接口层——同时**不动物理不变量**。
> **前置文档**：`docs/ARCHITECTURE_2026-10-21.md`（能力矩阵、4 条 import 违规、S0–S5 拆分、
> 四道结构性缺口）、`docs/UNIFIED_SCALE_AND_SOFTWARE_READINESS_2026-10-22.md`（口径定案、P0/P1/P2
> 缺口、六步落地顺序）、`docs/CHANGELOG_DOCS.md`（每轮实测与作废结论）。
> **本文不重复**上述文档已确认的物理结论；只回答分层、接口形态、契约、落地顺序四件事。
> **约束（硬）**：不得改动物理不变量（静载 59 680.5769 N / 静平衡侵入 65.47 µm、冻结 oracle、
> 332 项测试全绿）；Windows；不引入 sklearn（也不引入任何新运行时依赖）；分层必须继续由
> `tests/test_architecture_rules.py` 的静态 AST 规则强制。

---

## 0. 结论摘要

1. **分层**：在现有 L0 内核 / L1 编排 / L2 契约 / L3 驱动 / L4 展示之上，**只加两个新层**：
   `velch.params`（从 UI 里搬出来的纯数据参数契约）与 `velch.api` + `velch.jobs`（应用层/作业层）。
   适配器（MCP/HTTP）是第四层的第二种形态，与 Tk UI 平级，**不得向下穿透**。
2. **接口形态**：**混合，但严格排序**——进程内 `VelchService` 是唯一语义核心（先做，纯 pytest 可测），
   **MCP stdio server 是交付给 AI 的正式形态**（第二步），本地 HTTP/JSON-RPC **延后且可选**（第三步）。
   三者共用同一份 wire schema，契约测试只写一次、换传输重放。
3. **控制面/数据面分离**：MCP 进程**不 import 求解器**（只 import `params`/`jobs`/`io`/`metrics`），
   凡是要算的一律 `subprocess` 调 `velch` CLI。这与项目既有的"UI 起算例必须走 CLI 子进程"是**同一条
   论证**（`ARCHITECTURE_2026-10-21.md` §4），只是把执行者从人手换成 agent。
4. **写路径唯一**：AI 只能发"基例 id + `{registry_path: number}` 补丁"，落到 `apply_patch`
   （`src/velch/ui/parameters.py:266`）。**没有任何工具接受 case JSON 正文、路径或 shell**。
   参数注册表新增 `policy ∈ {free, guarded, forbidden}` 分级：验收门阈值、物理常数对 agent 一律
   `forbidden`，接触力律常数只在"声明的辨识任务"里可动。
5. **可回退靠磁盘与 git，不靠内存**：基例永不被写；变体与作业各自占一个唯一目录；作业状态
   **从磁盘派生**（`manifest.json` 在不在）而不是存在进程字典里——服务重启不丢真相。
6. **验收门**：每个阶段都以"332 passed 不变 + oracle 五项不变 + 架构规则绿"为下限，另加该阶段
   专属门（见 §5）。**任何阶段都不允许出现"默认路径变快但数字变了"**。

**明确不做**（与 `ARCHITECTURE_2026-10-21.md` §5 的"不做清单"一致）：

- 不做通用多体约束引擎、不做通用前后处理 GUI、M1–M2 不碰轨下结构；
- 不在 AI 层复制任何数值逻辑（不重算峰值、不重算脱空、不重算频带）；
- 不给 agent 写文件、写 case JSON、指定输出路径、设置 `result_status` 或
  `physics_validation_status` 的能力；
- 不为接口层引入 FastAPI/Flask/pydantic 等新依赖（stdlib 足够，见 §3.4）。

---

## 1. 设计输入（来自实证，不是假设）

| 事实 | 出处 | 对本文的含义 |
|---|---|---|
| 架构已由 16 条 AST 规则强制，含 headless import 与 import 时无环 | `tests/test_architecture_rules.py`（419 行） | 新层必须**同样**用规则钉住，否则一周内就会长出反向依赖 |
| `ui/parameters.py` 只 import stdlib（`math`/`dataclasses`/`typing`） | 文件头 | 它是事实上的叶子模块，**搬到 `velch.params` 零风险** |
| 注册表 72 条（车辆 19 / 悬挂 18 / 轨道 14 / 轮轨接触 13 / 求解设置 8） | `len(REGISTRY)` 实测 | 这就是 AI 的**全部**可写表面；不需要第二套 schema |
| 参考算例上注册表覆盖**全部**可编辑数值叶子（`missing == []`、`named > 60`） | `tests/test_parameters_registry.py:51-57` | 已有"漏一个字段就红"的漂移守卫，可直接复用为 AI schema 守卫 |
| `apply_patch` 已做未知路径/非数值/非有限/越界/穿容器五类拒绝，且**返回深拷贝、不动入参** | `ui/parameters.py:266-291` | 写路径已经是对的，AI 层**只准复用它**，不准另写一套 |
| `IGNORED_LEAF_PREFIXES` 把型面几何（数千点）排除在注册表外 | `ui/parameters.py:75-81` | 型面数据天然不是 AI 可写物理量——这条边界已经存在 |
| CLI 8 子命令、无交互、退出码 0/2、失败时 stderr 是 `{"status":"failed","error_type":…,"message":…}` | `arch §4.2`、`cli.py` | 作业层可以**完全用退出码 + 产物存在性**判定结果，不必解析人话 |
| `save_vehicle_result` 写 `{manifest.json, history.csv, case_snapshot.json}`，且 `mkdir(exist_ok=True)` | `vehicle_solver.py:767` | **会覆盖**同名目录 → 作业层必须自己保证输出目录唯一，不能指望求解器 |
| manifest 冻结字段：`software/case_sha256/case_snapshot/input_asset_sha256/track_model/state_order/units/summary` | 同上 | AI 结果契约**包裹**它，不改它 |
| `summary.physics_validation_status` 恒为 `unvalidated_against_measurement_or_Simpack` | `arch §4.2` | AI 面必须原样透出，且不可写 |
| 默认路径 nfev 109 628 / 172.5 s；快速预设 nfev 58 113 / 79.0 s；DOP853 归档 331 949 / ≈850 s | `UNIFIED…` §A.2 | **成本是接口设计的第一约束**：一次 agent 讨论就可能触发 30 次正演 |
| 反演 demo 用 30 次正演、`rail_k_z` 误差 −0.131 %、`rail_c_z` +0.352 % | `CHANGELOG` 轮 26 | 反演是**作业**不是**函数调用**，必须异步 |
| 358 个算例里只有 5 个打开 `support_compliance`，没有一个进验收门 → D1/D2 两个真缺陷穿过多轮测试 | `CHANGELOG` 轮 22 | 柔度相关参数对 agent 必须 `guarded`（无门保护的区域不能放开） |
| `inverse/` 在 CLI 里**零入口** | `arch` 差距⑥ | 反演作业排在最后，先有 `velch invert` 子命令，再有 job 类型 |
| 无 git、无 LICENSE、`validation/` 1.4 GB 与源码同树 | `UNIFIED…` §B.3 P0 | 回退能力的地基是版本控制，所以 Phase 0 必须先做 |

---

## 2. ① 目标分层与模块边界

### 2.1 五层模型（箭头只能向下）

```
 L4  适配器 / 展示        velch/ui/*  (Tk)              velch/serve/mcp.py   velch/serve/http.py
      transport only       │ 读产物 + 写参数             │ 唯一入口            │ 唯一入口
                           │                            ▼                     ▼
 L3  应用 / 编排           velch/cli.py          velch/api/{service,wire,errors}.py
      orchestration only   (8 子命令, 现状)      velch/jobs/{model,store,runner,reader}.py
                           │                            │
                           │                            └── subprocess: python -m velch …
                           ▼                            ▼
 L2  契约 / 分析           velch/params/*   velch/io/*   velch/metrics.py   velch/case/spec.py
      纯数据, headless     velch/inverse/*  velch/model.py  velch/vehicle.py
                           │  只读
                           ▼
 L1  求解编排              velch/vehicle_solver.py      velch/solver.py (v1 核对算例)
                           │
                           ▼
 L0  物理内核              contact*  contact_law  contact_geometry  jacobian  profiles
                           track_models  support_compliance  contact_native  surrogate
```

**四条方向规则**（每条都要有测试，见 §2.4）：

- **R1 只能向下**：L4 不得 import L3 以下的任何模块；L3 不得 import L1/L0；L2 不得 import L1/L0
  （`inverse`/`io`/`metrics` 现状已满足，`case.spec` 借 `vehicle` 是**已知违规 V2**，见 §2.5）。
- **R2 数据面与控制面分离**：L3 要算数，只能 `subprocess` 调 `velch` CLI。**import 求解器 = 违规**。
- **R3 写路径唯一**：任何层的参数修改只能经过 `velch.params.apply_patch`。文件系统写操作只允许
  落在作业自己分配的目录里。
- **R4 叶子不下沉**：`velch.params`、`velch.io.history` 必须保持"import 不到任何 velch 模块"
  （`io.history` 现在就是这样，是 `io`↔`inverse` 之间唯一无环锚点）。

### 2.2 新模块清单

| 新模块 | 职责（一句话） | 允许 import（velch 内） | 明确禁止 import | 公共符号 |
|---|---|---|---|---|
| `velch/params/__init__.py` | 重新导出，保持 `from velch.params import apply_patch` | 本包 | 一切其他 velch 模块 | `ParameterSpec, REGISTRY, ParameterError, apply_patch, editable, coverage, registry_by_path, to_chinese, agent_schema` |
| `velch/params/registry.py` | **迁移**：`ParameterSpec` + `REGISTRY`（72 条）+ `policy` 字段 | 无 | 无 | `ParameterSpec, REGISTRY, registry_by_path, EDITABLE_SECTIONS` |
| `velch/params/patch.py` | **迁移**：`apply_patch` / `_walk` / `_assign` / `coverage` / `editable` | `velch.params.registry` | 无 | `apply_patch, ParameterError, coverage, editable` |
| `velch/params/schema.py` | **新增**：从 `REGISTRY` 生成 agent 可见的 JSON Schema（唯一来源，禁止手写） | `velch.params.registry` | 无 | `agent_schema(), describe(paths), POLICY_RANK` |
| `velch/jobs/model.py` | **新增**：`Session`/`Variant`/`Job`/`RunProgram`/`JobOutcome` 冻结 dataclass（纯数据） | `velch.params`（校验用） | 求解器、`case.spec`、`vehicle` | `Variant, Job, RunProgram, JobState, JobOutcome` |
| `velch/jobs/store.py` | **新增**：磁盘即真相——`create_variant / create_job / derive_state / list_jobs`，路径越界拒绝 | `jobs.model`, `params` | 求解器 | `JobStore` |
| `velch/jobs/runner.py` | **新增**：拼 argv、`subprocess.run([sys.executable, "-m", "velch", ...])`、超时、取消 | `jobs.model/store`, stdlib | `vehicle_solver`, `cli`（连 `import velch.cli` 都不许） | `LaunchResult, launch()` |
| `velch/jobs/reader.py` | **新增**：读 `manifest.json`/`history.csv`/评估，产出**视图**（summary / assessment / downsampled series，带点数上限） | `jobs.model`, `velch.io.history`, `velch.metrics` | 求解器 | `read_summary, read_assessment, read_series` |
| `velch/api/wire.py` | **新增**：请求/响应 JSON 形状 + `contract_version="velch-ai-1"`（**不含任何 case 正文字段**） | stdlib | 一切 velch 模块（形状层零依赖） | `ContractVersion, ErrorCode, ok(), err()` |
| `velch/api/errors.py` | **新增**：稳定错误码 ↔ CLI 退出码/stderr JSON 的映射 | `api.wire` | — | `ApiError, to_cli_error()` |
| `velch/api/service.py` | **新增**：`VelchService`——8 个方法，唯一的应用门面；**不碰数值、不碰 socket、不碰 stdio** | `params`, `jobs.*`, `io.history`, `metrics` | `vehicle_solver`, `solver`, `contact*`, `jacobian`, `track_models`, `parallel`, `cli` | `VelchService` |
| `velch/serve/mcp.py` | **新增**：MCP stdio server，8 个 tool + 2 个 resource，逐层转调 `VelchService` | `api.*` + stdlib | 除 `api` 外任何 velch 模块 | `main(), TOOLS` |
| `velch/serve/http.py` | **新增（Phase 4，可选）**：`127.0.0.1` 上的 JSON-RPC 2.0，单端点 `POST /rpc`，token 鉴权 | `api.*` + stdlib | 同上 | `main()` |

**被改动（不是新建）**：

| 文件 | 改动 | 兼容性 |
|---|---|---|
| `src/velch/ui/parameters.py` | 变成 **re-export 壳**（只剩 import + `__all__`），实现搬到 `velch/params/` | `tests/test_parameters_registry.py` 一行不改仍通过（它 import 的仍是这个路径） |
| `pyproject.toml` | 加 `[project.scripts] velch-mcp = "velch.serve.mcp:main"`、`license` 字段、`velch-http`（Phase 4） | 现有两个 entry point 不动 |
| `tests/test_architecture_rules.py` | **只加**新常量与新测试，不改既有 12 条 | 现有 16 项必须仍全绿 |

### 2.3 import 矩阵（谁可以 import 谁）

`✓` 允许｜`✗` 禁止｜`—` 无此关系

| ↓ 依赖 → | params | jobs | api | serve | cli | vehicle_solver | contact\* | io | metrics | inverse | case | ui |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **params** | — | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **jobs** | ✓ | — | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| **api** | ✓ | ✓ | — | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓(bands) | ✗ | ✗ |
| **serve** | ✗ | ✗ | ✓ | — | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **cli** | ✓(新增) | ✗ | ✗ | ✗ | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| **ui** | ✓(经 re-export) | ✗ | 可选 | ✗ | ✗(subprocess) | ✗ | ✗ | ✓ | ✓ | ✓(bands) | ✓ | — |

三条要点：

- `api` **不 import `case.spec`**：控制面只把 case 当"字节 + sha256"，不在进程内构造
  `VehicleCase`。这样 V2（`case/spec.py:27` 反向依赖 `vehicle`）不会扩散到 AI 层。
- `jobs` **不 import `cli`**：连拿子命令表都不许，argv 在 `runner.py` 里按 wire 契约硬拼，
  由 CLI 的 `--help` 与契约测试保证不漂。
- `serve` 只认 `api`：换传输（MCP→HTTP）不改语义层，等价性是**可测**的（§5 Phase 3 门）。

### 2.4 怎么用测试钉住（这是本文的"承重墙"）

现有 16 条规则的写法（AST 扫全树、每条边标注 `kind ∈ {runtime, deferred, typing}`、失败打印
`模块:行号 -> 被导入模块`）**原样照抄**，只加常量与新测试。

**对 `tests/test_architecture_rules.py` 的增补**（新增 6 项，现有 12 条一字不改）：

```python
#: AI 面的三个新包。它们一起构成"agent 能碰到的全部代码"。
AGENT_SURFACE = frozenset({"velch.params", "velch.jobs", "velch.api", "velch.serve"})
```

| 新测试名 | 断言 | 防的退化 |
|---|---|---|
| `test_parameter_contract_is_a_leaf` | `velch.params.*` 不出现任何 import velch 的边 | 参数契约长出对 vehicle/model 的依赖，schema 生成被迫加载 scipy |
| `test_ui_parameters_is_only_a_reexport` | `ui/parameters.py` 的 AST 里**没有** `REGISTRY = (...)` 元组字面量、没有 `ParameterSpec(...)` 调用；只有 `ImportFrom` + `Assign(__all__)` | 两份注册表并存，UI 改一处 AI 看不到 |
| `test_agent_surface_never_reaches_the_kernel` | `AGENT_SURFACE` 里没有一条边指向 `FORWARD ∪ SOLVER_SIDE ∪ {velch.case, velch.case.spec}` | agent 面偷偷把求解器 in-process 起来，绕过进程隔离 |
| `test_jobs_launch_the_solver_as_a_subprocess` | `jobs/*` 里 `import velch.cli` 为 0 条；且 `subprocess` 的每次调用首个参数含 `"-m", "velch"` | 有一天"顺手"把 `simulate_vehicle` import 进来 |
| `test_only_adapters_touch_the_transport` | `serve/*` 只 import `velch.api*`（+stdlib）；`api/*` 里 `socket`/`http.server`/`sys.stdin` 出现次数为 0 | 传输逻辑渗进语义层，HTTP/MCP 行为分叉 |
| `test_agent_surface_imports_headless`（parametrize 4 例） | `velch.params` / `velch.jobs` / `velch.api` / `velch.serve` 在无显示器、无 CONTACT DLL 时可 import | 与既有 `test_downstream_packages_import_headless` 同一条理由 |

**新增文件 `tests/test_ai_contract.py`**（契约门，不测物理）：

| 测试名 | 断言 | 防的退化 |
|---|---|---|
| `test_schema_is_generated_from_the_registry` | `set(agent_schema()["properties"]) == {p.path for p in REGISTRY if p.policy != "forbidden"}`，且 `set(agent_schema()["forbidden"]) == {p.path for p in REGISTRY if p.policy == "forbidden"}`（后者只出现在**文档字段**里，不在 `properties`） | 手写 schema 漂移；或把 forbidden 项悄悄放进可写集合 |
| `test_every_visible_path_round_trips_through_apply_patch` | 对参考算例，每条 agent 可见路径取注册表的 `minimum`（或当前值），`apply_patch(case, {p: v})` 成功；每条 `forbidden` 路径同值调用**必须**抛 `ParameterError` 且消息含 `forbidden` | forbidden 只是文档约定、代码不拦 |
| `test_registry_policy_partition_is_total` | 每条 `ParameterSpec.policy ∈ {free, guarded, forbidden}`；`forbidden` 集合**必须**含 `run.maximum_penetration_m`、`run.maximum_abs_contact_slope`、`vehicle.gravity_m_s2` | 验收门阈值某天被降级成 free，agent 自己给自己放行 |
| `test_wire_requests_have_no_case_body` | `velch.api.wire` 里的请求 dataclass 字段名不出现 `case`/`raw`/`json`/`path`/`output`（除 `job_dir` 之类的**服务端生成**字段） | AI 能提交 case JSON 或指定输出目录——这是整套安全边界的底线 |
| `test_idempotency_key_is_deterministic` | 同一 (base_sha256, patch, program, software_version) → 同 key；任一 bit 变 → key 变；patch 的**键序**不改变 key（排序后哈希） | 缓存串味 / 缓存失效 |
| `test_job_state_derives_from_disk` | 建 job → 删掉进程内对象 → 新建 `JobStore` 实例仍能列出该 job 且状态相同 | 真相存在内存里，重启即失忆 |
| `test_job_output_dir_never_collides` | 连续 100 次 `create_job` 的目录两两不同；目录已存在且非空时 `create_job` 抛错 | 两个作业写同一个 `out_*`，`save_vehicle_result` 的 `exist_ok=True` 静默覆盖 |
| `test_output_root_is_an_allowlist` | 任何请求里的 `../`、绝对路径、UNC 路径都被拒绝（抛 `ContractError`），且**写入前**判定 | 路径穿越写到 `validation/` 把 oracle 覆盖了 |
| `test_run_program_respects_the_budget` | `duration_s > cap`、`rtol < floor`、`workers != 1`、`method="DOP853"`+`jacobian` 组合 → 一律拒绝 | agent 提交 60 s 仿真把机器占死；组合校验与 `RunSettings.__post_init__` 保持一致 |

**为什么这些测试比"文档约定"值钱**：项目已经用同一手法拿到了两次收益——
`test_oracle_frozen.py` 让任何物理漂移立刻红；`test_architecture_rules.py` 让 UI 复制数值逻辑
变成 CI 失败而不是 code review 意见。AI 层引入的是**更弱的执行者**，所以需要**更强**的结构约束。

### 2.5 与既有 S0–S5 拆分的关系

`ARCHITECTURE_2026-10-21.md` 的 S0–S5 是**内核侧**整理（拆 `contact.py`、拆 `vehicle_solver.py`、
DOF 去重、切 V1、收敛 V2/`case.spec`）。本文的 Phase 1–3 是**外层**建设。两者**正交**，但有三处必须
按顺序：

1. **Phase 0（git）必须在所有拆分之前**。现在 `git status` → `fatal: not a git repository`，
   15 320 行源码没有一行有历史；任何"纯移动代码"的拆分如果没有 tag 可回退，就不该开始。
   `UNIFIED…` §B.4 已经把这一点写成第 1 步，并明确"先建仓再搬 `validation/`"。
2. **Phase 1（`params` 外移）必须早于 S1（拆 `contact.py`）**。理由：外移是**纯移动 + re-export**，
   有 `test_parameters_registry.py` 与覆盖门做逐项校验；而拆 `contact.py` 是数值高风险改动。
   把小而可证的动作排在大风险动作前面，任何一步出问题都能定位到单一变量。
3. **S4（切断 `io → inverse` 的 V1）可以与本设计并行**，但 `velch/api` **不要**依赖
   `inverse.observation`/`inverse.channels` 的**类型**——只用 `inverse.bands`（频带）与将来的
   `inverse.contracts`。这样 S4 落地时 `api` 不需要改。

**本文不重开 V2/V3/V4 的讨论**：V3（`vehicle_solver` 只借 `SimulationFailure`）与本设计无关；
V4（`contact.py` 常量与 import 交错）属 S1。

---

## 3. ② 面向 AI 的接口形态选型

### 3.1 四个候选

| 方案 | 进程隔离 | 非 Python agent 可达 | 新依赖 | Windows 运维 | LLM 工具语义 | 可测性 |
|---|---|---|---|---|---|---|
| **A. 纯进程内 Python API** | ✗ 共享进程 | ✗ | 0 | 无 | 弱（agent 得会写 Python） | ★★★ 纯 pytest |
| **B. 本地 HTTP / JSON-RPC** | ✓ | ✓ | 0（`http.server`） | 端口/防火墙/杀软/常驻服务 | 中（要有人写 tool wrapper） | ★★ 需起服务 |
| **C. MCP stdio server** | ✓ | ✓（任何 MCP 客户端） | 0（JSON-lines over stdio） | **无端口**，客户端拉起子进程 | ★★★ 原生 tool/resource/progress | ★★★ 可脚本化回放 |
| **D. 混合（A 为核 + C 为交付 + B 延后）** | ✓ | ✓ | 0 | 无 | ★★★ | ★★★ |

### 3.2 决策：D（混合，但**有严格排序**）

**逐条理由**：

1. **A 不是"可选项"，它是语义核心**。不管对外是 MCP 还是 HTTP，**请求的语义只能定义一次**。
   把 8 个方法写成 `VelchService` 的纯 Python 方法，就能用 pytest 在无 socket、无 stdio、无显示器
   的条件下跑完整契约（项目已有 `--selftest` 无头跑全部屏幕的先例，见 `ui/store.py` 文件头）。
   **A 不作为对外接口交付**，理由见 §3.3。
2. **C 作为正式 AI 面**。理由有三，都指向本项目的具体事实：
   - **LLM 的工具调用主流就是 MCP**，本机 harness 已挂 MCP server（`simpack-2021x`、`graphflow`），
     外部 agent 接进来不需要新的胶水层；
   - **零端口**：Windows 上开监听端口是最容易被防火墙/杀软/公司策略打断的一步，而本项目是
     单机交付（`F:\` 上的本地树 + `.cmd` 启动器），没有远程访问需求；
   - **进程随客户端生命周期**：MCP server 由客户端拉起，会话结束即退出，不留常驻服务要人管。
3. **B 延后且可选**。它唯一的独特价值是"非 MCP、非同机 Python 的消费者"（浏览器里的 tool runner、
   公司内网 CI、Web GUI）。在出现第一个真实消费者之前做它，是**为想象中的需求写代码**。
   一旦要做，代价很小：`serve/http.py` 只是把 `api.wire` 的请求体从 stdin 换成 `POST /rpc`
   的 body，**契约测试原样重放**。
4. **不选"每次工具调用 spawn 一个 CLI"**：`import` numpy+scipy 与解析型面约 0.5–1 s，而
   `params_list`/`job_status`/`result_get` 这类高频读操作会被放大成体验灾难。MCP 进程**常驻**，
   只有**真算数**的那一步才 spawn 子进程。

### 3.3 为什么"纯进程内 Python API"不能作为对 AI 的正式接口

三条硬理由，每条都对应一条已经发生过的教训：

1. **没有执行边界，安全边界就不存在**。会写 Python 的 agent 可以直接
   `open(case_path,"w").write(...)`、可以 `import velch.vehicle_solver`、可以改
   `run.maximum_penetration_m` 再宣布"门通过"。**模块边界拦不住 import**，只有**进程边界**拦得住。
   这正是项目已经对 UI 下过的那条结论："UI 起算例必须走 CLI 子进程"（`arch §4`）——
   agent 是比 UI 更不可信的调用者，没有理由给它更宽的权限。
2. **数值代码的失败模式会杀死整个会话**。1.2 s 整车算例要吃 1–2 GB 峰值内存、跑 79–172 s；
   发散时会抛 `non-finite v2 force at t=0.547528664 s`（`UNIFIED…` §A.2 实测）。同进程里这意味着
   agent 的上下文与半截状态一起没了。子进程崩了，作业层只丢一个 job。
3. **可复现性要求"跑过的字节"被钉住**。`save_vehicle_result` 会校验 `case_sha256` 与
   `input_asset_sha256`（`vehicle_solver.py:767`），但**同进程内**改过的对象不会被这个校验发现
   （哈希算的是**文件**）。只有"作业目录里的 case 文件 + 一份 manifest"才是可审计的。

### 3.4 控制面 / 数据面分离（本设计最要紧的一条）

```
          ┌──────────────────────── MCP 进程（常驻，轻） ────────────────────────┐
 agent ──►│ serve/mcp.py → api/service.py → jobs/store.py                        │
          │ 只 import: params, jobs, io.history, metrics   （实测 import 0.08 s） │
          └──────────────────────────────┬─────────────────────────────────────┘
                                         │ subprocess（每次求解一个新进程）
                                         ▼
          ┌──────────────── 求解进程（重，隔离，可被 kill） ─────────────────────┐
          │ python -m velch run-vehicle <job_dir>/case.json --output <job_dir>/out │
          └───────────────────────────────────────────────────────────────────────┘
```

- **MCP 进程永不 import 求解器** → 由 `test_agent_surface_never_reaches_the_kernel` 钉住；
  它崩溃不损失任何物理状态，重启后从磁盘重新读 state。
- **控制面确实很轻——这是有实测支撑的选型依据**：本机实测 `import velch.ui.parameters`
  **0.014 s**（进程总 0.056 s）；`import velch.io, velch.metrics, velch.ui.parameters`
  **0.078 s**（进程总 0.125 s）；而 `import velch.vehicle_solver` 是 **0.489 s**
  （进程总 0.561 s，代价来自 numpy/scipy）。所以"常驻 MCP 进程 + 求解放子进程"能把高频读工具
  的延迟压在 0.1 s 量级，同时不让求解器常驻内存。
- **求解器只从 CLI 进** → 参数校验、产物写盘、退出码语义**一条路**，与人类用户完全一致。
  也就是说：**agent 看到的世界和人在终端里看到的世界是同一个**，不存在"两套口径"。
- **依赖零新增**：JSON-lines over stdio 与 `http.server` 都是 stdlib。`pyproject.toml:10` 的
  `dependencies = ["numpy>=1.24","scipy>=1.10"]` 不变，这也顺带守住 sklearn ABI 那个坑
  （`CHANGELOG` 轮 B 阶段已记录 `numpy.dtype size changed … Expected 96 … got 88`）。

### 3.5 会不会被 MCP 的传输形状绑死？

不会。`velch/api/wire.py` 定义**传输无关**的请求/响应：

```jsonc
// 请求（8 个方法共用一个信封）
{"contract": "velch-ai-1", "method": "run_submit", "params": {...}, "request_id": "018f…"}
// 响应
{"contract": "velch-ai-1", "ok": true,  "result": {...}, "request_id": "018f…"}
{"contract": "velch-ai-1", "ok": false, "error": {"code": "out_of_range", "message": "…",
                                                  "detail": {"path": "…", "value": 9.0,
                                                             "minimum": 0.0, "maximum": 1.5}},
 "request_id": "018f…"}
```

MCP 的每个 tool 把 `params` 摊平成 tool 参数；HTTP 的 `POST /rpc` 直接传这个信封。
**契约测试写一次，两种传输各重放一次**（§5 Phase 3/4 的门就是这件事）。

---

## 4. ③ AI 接口的稳定契约

### 4.1 对象模型与磁盘布局

```
<workspace_root>/                     （默认 %LOCALAPPDATA%\Velch\workspaces，可配；只读 oracle 除外）
  sessions/s_<ulid>/session.json      {session_id, created_at, software, quota, base_case_refs}
  variants/v_<ulid>.json              {variant_id, base_case_id, base_sha256,
                                       patches:[{path, value, note, actor:"agent"}],
                                       resolved_sha256, created_at}
  jobs/<job_id>/
     job.json                         {job_id, variant_id, program, idempotency_key,
                                       state, outcome, exit_code, started_at, finished_at,
                                       nfev?, wall_s?, error?, artifacts{}}
     case.json                        ← 由基例 + 补丁**派生**出的完整 case（唯一被求解器读取的文件）
     stdout.log  stderr.json          原样落盘，不改写
     out/manifest.json  out/history.csv  out/case_snapshot.json
     assessment.json                  ← metrics.assess_history 的结果（若被请求）
     grant.json                       ← "谁批准了这次运行"（见 §4.6）
```

| 对象 | 可变形 | 身份 | 生命周期 |
|---|---|---|---|
| **BaseCase** | **不可变** | `sha256(bytes)` + 逻辑 id（如 `crh380a_m/case_full12_cap05`） | 由人登记；agent 只能引用 |
| **Variant** | **不可变**（新建而非修改） | `v_<ulid>` + `resolved_sha256` | 新建即终态；"改参"= 新 variant |
| **Job** | **只追加**（`created→…→终态` 单向） | `job_id` + `idempotency_key` | 终态后永不改写 |
| **Artifact** | 不可变 | 所属 job + 文件名 | 随 job 目录存亡 |

**为什么变体不可变**：`CaseSpec` 已经是这个思路（`case/spec.py:128` `patched()` 返回深拷贝、
`:143` `resolve()` 写临时文件再 `load_vehicle_case`），且 `case.spec` 的 docstring 明确写了
"identification must not mutate a case"。AI 层只是把这条纪律**从反演扩展到一切改参**。

**注意一个真实陷阱**：`save_vehicle_result` 用 `target.mkdir(parents=True, exist_ok=True)`
（`vehicle_solver.py:767`），**同名输出目录会被静默覆盖**。所以"输出目录唯一"必须由
`jobs/store.py` 保证（`test_job_output_dir_never_collides`），不能改求解器那行——
那行属于冻结核验面。

### 4.2 作业状态机（磁盘即真相）

```
                  ┌──────── cancelled ◄──────── cancel 请求
                  │
created ──► queued ──► running ──┬──► succeeded     exit 0 且 manifest.summary.result_status=="numerically_checked"
                                 ├──► gate_failed   exit 2 且有 manifest 且 result_status=="numerical_gate_failed"
                                 ├──► solver_error  exit 2 且 stderr 是 {"status":"failed","error_type":…}
                                 └──► timed_out     超过 wall-clock 预算被 runner 杀掉
```

**判定规则写死成三行**（`jobs/store.py::derive_state`），且**只读磁盘**：

```python
if manifest.exists() and manifest["summary"]["result_status"] == "numerically_checked": → succeeded
elif manifest.exists():                                                               → gate_failed
elif stderr.json has {"status": "failed"}:                                            → solver_error
else:                                                                                 → crashed / timed_out
```

三点后果，都是刻意设计的：

1. **`gate_failed` 不是错误**。门失败是**物理结论**（例如侵入超限），必须让 agent 看见
   `failed_gate` 的名字和数值，而不是看见一个异常去"重试修好它"。反之，`solver_error`
   才是"可以换配置重试"的。把两者混成一个 `error` 是本设计要避免的头号误判。
2. **服务重启零成本**：MCP 进程被客户端杀掉再拉起，`list_jobs` 仍给出全部历史。
3. **断点可考**：`running` 但没有 manifest 且进程已死 → `crashed`，且 `stdout.log` 尾部就是死因
   （例如 `non-finite v2 force at t=0.547528664 s`）。

### 4.3 参数 schema 的唯一来源

**唯一来源 = `velch/params/registry.py` 的 `REGISTRY`**（现 72 条，`ui/parameters.py` 原样迁入）。
三处投影，**任何一处都不许手写**：

| 投影 | 消费者 | 形态 | 守卫 |
|---|---|---|---|
| ① 控件表 | Tk UI | `editable(case) -> [(spec, value)]` | 现状（`test_parameters_registry.py`） |
| ② JSON Schema | MCP tool 输入 / HTTP 校验 | `agent_schema()` | `test_schema_is_generated_from_the_registry` |
| ③ 校验器 | **一切**写入 | `apply_patch(case, patch)` | 现有五类拒绝 + 新增 `policy` 拒绝 |

**新增字段 `policy`**（默认 `"free"`，向后兼容，不改任何现有行为）：

```python
@dataclass(frozen=True)
class ParameterSpec:
    path: str; label_zh: str; unit: str; group: str
    note: str = ""
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    policy: str = "free"          # ← 唯一新增：free | guarded | forbidden
```

| policy | 语义 | agent 可见 | 可写 | 本项目里谁属于这一档（附理由） |
|---|---|---|---|---|
| `free` | 工况/结构设计变量 | ✓ | ✓（范围校验） | 车辆质量/惯量、悬挂刚度阻尼、轴距/速度、`run.duration_s`/`output_step_s`/`x_start_m`、轨道层与扣件刚度质量 |
| `guarded` | 可动，但只在**声明的辨识任务**里动，或必须带 note | ✓（标 `guarded`） | 仅在 `invert` 作业的 bounds 内，或补丁带 `note` | **整个轮轨接触组（13 条）**：A2 已定案"真简并是 C↔k_z，禁止用额定侵入标定 C"；`run.rtol/atol/max_solver_step_s`（只能经 preset）；`vehicle.nominal_wheel_radius_m`（与型面 `z_offset_m` 强耦合，写错 → 静平衡残差 68 186 N）；`support_compliance.*`（358 个算例只有 5 个开、无验收门覆盖 → D1/D2 就是从这漏过去的） |
| `forbidden` | 验收门阈值 / 物理常数 / 不是旋钮 | ✗（**不出现在 `properties` 里**） | ✗ 抛 `ParameterError` | `run.maximum_penetration_m`、`run.maximum_abs_contact_slope`（自证危险：agent 放松阈值就能"通过"门）；`vehicle.gravity_m_s2`（物理常数，改了就不是同一台车） |

**为什么 `forbidden` 项要"不可见"而不只是"被拒绝"**：可见但被拒会诱导 agent 反复试探、
浪费上下文并把"越权"当成失败重试的理由。**不可见 + 明确列在 `forbidden` 文档字段里**，
既诚实又省 token。

**不进入注册表的东西（天然不可写）**：`initial_q`/`initial_v`（状态初值）、
`rail_templates[].stations`/`bodies[].stations`/`contact.wheel_profile`/`contact.rail_profile`
（型面几何，见 `IGNORED_LEAF_PREFIXES`）、`case_id`/`purpose`/`parameter_source`/`source_evidence`/
`asset_hashes`（溯源块）。这些**本来就不在注册表里**，`apply_patch` 会以 `unknown parameter` 拒绝——
这条边界已经存在，AI 层只是不再提供第二条路。

### 4.4 结果产物格式（三层，互不侵入）

```
第 1 层  solver 面（冻结，字节不许变）
    out/manifest.json   {software, case_sha256, case_snapshot, input_asset_sha256,
                         track_model{kind,track_dof,modal_count,modal_exchange_schema},
                         state_order, units, summary{…}}
    out/history.csv     155 列（生产算例）：time_s + 4×axle{i}_x_m + 35 车辆状态 + track_dof 轨道状态
                        + total_dof `_per_s` + 6×轨数 {rail_id}_{normal_n,fx_n,fy_n,fz_n,penetration_m,active}
    out/case_snapshot.json  求解器读到的 case 字节（= 我们的 case.json，逐字节）

第 2 层  job 面（新增，agent 只看这层）
    job.json      {state, outcome, exit_code, nfev, wall_s, artifacts{…}, error{…}}
    assessment.json   metrics.assess_history 的原样输出（limits / axles / maximum / verdict）

第 3 层  视图面（新增，按需生成，有硬上限）
    result_get(view="summary")   → ≤ 4 KB JSON：峰值、脱空帧数、最大侵入、频带、七门、nfev
    result_get(view="assessment")→ 评估 JSON（脱轨系数/减载率/横向力）
    result_get(view="series")    → {columns, window, points ≤ 2000, decimation="minmax-preserving"}
```

**三条规则**：

- **AI 面永不"重算"**：峰值/脱空/频带一律从 `manifest.summary` 或
  `inverse.bands`（已存在的纯函数，UI 也只准用它）取，不许在 `api` 里再写一遍算术。
  这与 `PRESENTATION_MAY_IMPORT` 放行 `inverse.bands` 是同一条论证。
- **`physics_validation_status` 原样透出**。它恒为
  `unvalidated_against_measurement_or_Simpack`；agent 不得覆盖、不得"解释成已验证"。
  建议在 `result_get` 的响应里把它放在**顶层**（与 `result_status` 并列），并在 MCP tool 描述里
  写死一句："this software is numerically checked, not physically validated"。
- **大对象走 resource，不走 tool 返回**：`history.csv` 可能几 MB。MCP 提供
  `velch://jobs/<job_id>/history` 与 `velch://jobs/<job_id>/manifest` 两个 resource，
  tool 只返回 URI + 列名 + 行数 + 时间跨度。这是控制上下文成本的关键一笔。

### 4.5 幂等与去重

```python
idempotency_key = sha256(json.dumps({
    "contract": "velch-ai-1",
    "base_sha256": base_sha256,                 # 基例字节哈希（不是路径）
    "patch": sorted(patches),                   # 排序后：键序不影响 key
    "program": program.canonical(),             # preset 展开成显式字段后排序
    "software": __version__,                    # 0.4.0；升级即失效重跑（正确）
}, sort_keys=True, ensure_ascii=False))
```

| 场景 | 行为 |
|---|---|
| 同一 key 已存在且 `succeeded` / `gate_failed` | **不重跑**，直接返回原 `job_id` + `reuse: true` |
| 同一 key 已存在但 `solver_error` / `timed_out` / `cancelled` / `crashed` | 允许新建 job（附 `retry_of: <旧 job_id>`），**不允许改写旧 job** |
| 同一 key 正在 `queued` / `running` | 返回该 job + `state`，不新建（天然去重，两层并发都安全） |
| `request_id` 重复（客户端重发） | 返回首次响应（`api` 层去重表，进程内 LRU，键含 `request_id`） |

**收益是实测的**：一次 1.2 s 整车算例 **nfev 109 628 / 172.5 s**（快速预设 58 113 / 79.0 s）。
一个"改一个参数 → 跑一次 → 看一眼"的 agent 循环，重复提交是常态；没有幂等，成本会翻好几倍。

**为什么用 `nfev` 而不是秒数做成本门**：`UNIFIED…` §A.5 已定案——两个会话的
`nfev 81 647` 逐位相同而墙钟差 60 s，差异只在机器负载。所以预算门（§5）用 `nfev` 与 `job 数`
计量，秒数只作展示。

### 4.6 可回退（四道）

| 道 | 机制 | 兜住什么 |
|---|---|---|
| 1 | **基例永不被写**：所有改动产物都是 `jobs/<job_id>/case.json` 或 `variants/*.json` | AI 把 `validation/crh380a_m/case_full12_cap05.json` 写坏 |
| 2 | **输出目录唯一 + 拒绝非空目录**（`test_job_output_dir_never_collides`） | 覆盖 oracle `out_full12_cap05`，冻结基线消失 |
| 3 | **git tag per 阶段**（Phase 0 起；`v0.4.0` 起点，Phase N 结束打 `ai-phase-N`） | 一次失败的落地需要整体回滚 |
| 4 | **`promote` 需人工**：agent 不能把 variant 提升为"登记算例"；提升是一个**人**执行的 CLI 动作（复制到 `validation/<campaign>/case_*.json` + 写一行 `CHANGELOG_DOCS`） | agent 自造算例污染证据树，"谁说的算"变模糊 |

`grant.json` 记录每次运行的三元组 `(谁, 哪个 variant, 什么预算)`。它不阻止任何事，但让事后审计
一句话能答："这个 89.7 kN 是谁、在哪个补丁下、花了多少 nfev 跑出来的。"

### 4.7 错误码（稳定，与 CLI 对齐）

| `code` | 触发 | HTTP-ish | CLI 退出码 | 可重试 |
|---|---|---|---|---|
| `unknown_parameter` | 补丁路径不在注册表 | 400 | 2 | ✗（先 `params_list`） |
| `out_of_range` | 超出 min/max（`detail` 带 value/min/max） | 400 | 2 | ✗ |
| `forbidden_parameter` | `policy="forbidden"` | 403 | 2 | ✗ |
| `guarded_parameter` | `guarded` 但缺 `note` 或不在辨识 bounds 内 | 403 | 2 | 带 note 后可 |
| `case_not_found` / `variant_not_found` / `job_not_found` | id 不存在 | 404 | 2 | ✗ |
| `contract_error` | 信封/字段/版本不符 | 400 | 2 | ✗ |
| `budget_exceeded` | 超 `duration_s`/`nfev`/`wall_s`/`jobs` 配额 | 429 | 2 | 换小算例 |
| `busy` | 已有求解进程在跑（默认单并发） | 409 | — | ✓ 稍后 |
| `solver_failed` | 子进程 exit 2 且 stderr 有 `error_type` | 500 | 2 | ✓（换配置） |
| `gate_failed` | 子进程 exit 2 且 `result_status="numerical_gate_failed"` | **200** | 2 | **不是错误**：返回门表让人判断 |
| `cancelled` / `timed_out` / `crashed` | runner 侧 | 499/504/500 | — | ✓ |

`gate_failed` 用 200 是刻意的：它在 HTTP 语义里是"请求成功、结论是否定的"。

### 4.8 版本与兼容

- `contract` 字符串 `velch-ai-1`，任何**破坏性**改动才进 `velch-ai-2`；加字段不动版本号。
- `software` 进 `idempotency_key`：**`pyproject.toml` 的 `version` 一改，全部缓存失效**——
  这是对的，因为 0.4.0→0.5.0 的数值结果不保证逐位相同。
- `manifest` / `history.csv` 的兼容性由冻结 oracle 与 `save_vehicle_result` 的字节格式把守，
  本文不改它们。
- 能力声明：`velch.params.agent_schema()["x-velch-capabilities"]` 列出当前可用作业类型
  （`run` / 将来 `invert` / `sweep`），客户端不需要猜。

---

## 5. ④ 分阶段落地顺序与验收门

**通用门（每阶段都必须满足，缺一即回滚）**：

```
G-COMMON
  C1  python -X utf8 -m pytest tests -q --basetemp F:\velch_tmp\pytest   → 0 failed（现 332）
  C2  tests/test_architecture_rules.py 全绿（现 16 项，只增不改）
  C3  冻结 oracle 不变：静载 59 680.5769 N / 侵入 65.47 µm；1.2 s 八接触峰值
      61.19/89.68/61.08/170.61/61.17/90.77/61.07/170.45 kN；最大侵入 551.89 µm；脱空 0/2401
  C4  save_vehicle_result 落盘字节格式未变（history.csv 列序/精度、manifest 字段集）
  C5  无新运行时依赖（dependencies 仍是 numpy+scipy）
  C6  git status 干净，阶段末打 tag
```

### Phase 0 · 地基（先做，2–3 天）

| 交付 | 验收门 | 回滚点 |
|---|---|---|
| `git init` + `.gitignore`（排除 `validation/out_*`、`build/`、`dist/`、`__pycache__`、`.pytest_tmp*`、`.tmp`）+ 首提交 + tag `v0.4.0` | `git log` 有历史；`git status` 干净；C1 不变 | — |
| `LICENSE` + `pyproject.toml` 的 `license` 字段 | `pip install .` 后元数据里有 license | 删除字段 |
| `validation/` 外移到 `F:\velch_validation\`，仓库只留 `out_full12_cap05`、`out_A_final_law` 两个 oracle + `INDEX.md` | 仓库 < 20 MB；C1/C3 不变 | 移回（有 git 历史可回退） |
| `--fast` 正式入口：`velch run-vehicle … --preset fast`（= `jacobian=analytic, rtol=1e-4, max_step=1e-3`） | 同算例 **nfev 58 113±1 %**、峰值 170.7 kN、0 脱空；`--preset default` 仍是 nfev 109 628 | 删 flag |
| 根目录 57 个游离脚本进 `archive/`；`validation` 脚本进 `validation/scripts/` | 根目录只剩 pyproject/README/LICENSE/.gitignore + 目录 | 移回 |

**为什么 Phase 0 必须先做**：回退能力（§4.6 第 3 道）与"搬 `validation/` 可回退"（`UNIFIED…`
§B.4 的注）都依赖 git 先存在。**且 `--fast` 是本文所有成本门的计量基准**——没有它，
`budget_exceeded` 就无从判定。

### Phase 1 · 参数契约外移（1–2 天，纯移动）

| 交付 | 验收门 | 回滚点 |
|---|---|---|
| `velch/params/{__init__,registry,patch}.py`：把 `ParameterSpec`/`REGISTRY`/`apply_patch`/`editable`/`coverage`/`to_chinese` **原样搬走**（代码不改一行逻辑） | `tests/test_parameters_registry.py` **一字不改**全绿；`test_coverage_is_complete_on_the_reference_case` 仍 `missing == []`、`named > 60` | `git revert` 单提交 |
| `ui/parameters.py` 变成 re-export 壳 | `test_ui_parameters_is_only_a_reexport` 绿；UI 手工跑 `--selftest` 正常 | 同上 |
| `ParameterSpec.policy` 字段（默认 `free`，暂不判定） | 72 条全 `free`；C1 不变 | 去掉字段 |
| `velch/params/schema.py::agent_schema()` | `test_schema_is_generated_from_the_registry` 绿（此时 forbidden 为空集，测试允许空） | — |
| 新架构规则 1 条（`test_parameter_contract_is_a_leaf`） | 绿 | — |

**风险最低、收益最早的一步**：`ui/parameters.py` 现在只 import stdlib，且已被
`test_parameters_registry.py`（10 项）与覆盖门双向钉住，搬动是**可证等价**的。

### Phase 2 · 作业层 + 进程内 API（3–5 天，本设计的承重阶段）

| 交付 | 验收门 | 回滚点 |
|---|---|---|
| `velch/jobs/{model,store,runner,reader}.py` | `test_job_state_derives_from_disk`、`test_job_output_dir_never_collides`、`test_output_root_is_an_allowlist`、`test_idempotency_key_is_deterministic`、`test_run_program_respects_the_budget` 全绿 | tag `ai-phase-2` 前可整体 revert |
| `velch/api/{wire,errors,service}.py`，8 个方法 | `test_wire_requests_have_no_case_body` 绿 | 同上 |
| **端到端 pytest（无 socket、无显示器、无 MCP）**：`variant_create → run_submit → run_status → result_get` 跑通一个 0.05 s 小算例 | ① 一次跑通的 job 状态序列 = `queued→running→succeeded`；② 同一补丁二次提交 **`reuse: true` 且 nfev 不增**；③ `forbidden` 补丁返回 `forbidden_parameter`；④ 越界补丁 `detail` 含 value/min/max；⑤ 故意让 runner 杀掉子进程 → 状态为 `crashed`，`stdout.log` 可读；⑥ `gate_failed` 用**故意把 `duration_s` 拉到含高侵入区间**的算例造出来，且**不被计为 error** | — |
| 新架构规则 4 条（`agent_surface_never_reaches_the_kernel`、`jobs_launch_…subprocess`、`only_adapters_touch_the_transport`、`agent_surface_imports_headless`） | 绿 | — |

**这一阶段完工的标志不是"能跑"，而是"能证明它不能乱跑"**：上面 6 条端到端断言里，
②④⑤⑥ 都是**负面能力**的证明。负面能力证明不了的接口，不该交给 agent。

### Phase 3 · MCP stdio 交付（2–4 天）

| 交付 | 验收门 | 回滚点 |
|---|---|---|
| `velch/serve/mcp.py` + `pyproject.toml` 的 `velch-mcp` entry point | `velch-mcp --selftest`：列出 8 个 tool、2 个 resource，且**每个 tool 的 inputSchema 都来自 `agent_schema()`**（不手写） | 删 entry point |
| 8 个 tool（§6 附录 A） | **契约等价门**：同一份脚本化 transcript（8 次调用 + 2 次资源读）分别经 `VelchService` 直调与经 MCP stdio 回放，两次产出的 `job.json` / `result_get` 响应 **逐字节相同**（时间戳字段白名单剔除） | 同上 |
| `--readonly` 模式（只挂 4 个读 tool） | 只读模式下 `run_submit` 不在工具表里（不是"调用被拒"） | — |
| tool 描述强制声明"numerically checked, not physically validated" | 断言 `result_get` 响应顶层含 `physics_validation_status` 且值恒为 `unvalidated_against_measurement_or_Simpack` | — |

**为什么"逐字节等价"是这道门的正确形状**：MCP 层唯一可能引入的缺陷就是**语义分叉**
（比如 MCP 侧自己做了单位换算、自己截断了 series）。等价门让分叉变成测试失败，
而不是"某个 agent 报了个怪数字"。

### Phase 4 · 本地 HTTP/JSON-RPC（可选，2–3 天）

| 交付 | 验收门 | 回滚点 |
|---|---|---|
| `velch/serve/http.py`：`POST /rpc`，JSON-RPC 2.0 信封，`127.0.0.1` only | Phase 3 的**同一份 transcript** 换传输重放，逐字节相同 | 删 entry point |
| token 鉴权（`--token-file`，仅内存比较） | 无 token → `401` + `contract_error`；错 token → 同上；**默认不监听 0.0.0.0**，要远程必须显式 `--bind` 且打印警告 | — |
| 单并发队列 | 并发提交 2 个求解请求 → 第二个得 `busy`（409）且**不被排队执行**（避免幻觉"已排队"） | — |

**这条线的立项条件是"出现第一个真实消费者"**。没有消费者就不做——这是"可逆性优先"
（宁可少做，也别做一个没人用还得维护的传输层）。

### Phase 5 · 反演与批量（依赖 CLI 先有入口）

| 交付 | 验收门 | 回滚点 |
|---|---|---|
| `velch invert` 子命令（`inverse/` 目前 CLI 零入口，`arch` 差距⑥） | 复现 `inversion_waveform_demo`：`rail_k_z` 误差 −0.131 %（1σ 1.03 %）、`rail_c_z` +0.352 %（0.87 %）；30 次正演；**oracle 不变** | 删子命令 |
| job 类型 `invert`（`guarded` 参数只能在 bounds 内动） | `guarded_parameter` 错误码门；越 bounds 拒绝；θ 由 `CaseSpec.resolve` 内部解析，**agent 从不直接提交 θ** | — |
| job 类型 `sweep` | 多进程（`--jobs`），**`--workers` 仍只许 1**（实测多线程慢 1.86×，GIL）；预算门 `max_jobs` | — |

**为什么反演排最后**：它需要 30+ 次正演（≈ 30 × 79 s ≈ 40 min），必须先有幂等、预算与取消，
否则一个跑飞的 agent 循环会把机器占满一整天。

### Phase 6 · 交付硬化（与 Phase 4 并行或之后）

| 交付 | 验收门 |
|---|---|
| wheel 重新构建（`dist/` 里 4 个旧 wheel 与 `build/` 残留清掉） | `pip install .` 后 `velch`、`velch-gui`、`velch-mcp` 三个命令可用 |
| `validation/INDEX.md`（算例 id / 目的 / 峰值 / 脱空 / **是否常数静载门**） | 207 个 `out_*` 里 10 个常数门被显式标注（`UNIFIED…` §B.3 P2-11） |
| README 移除过期自评（"尚未完成物理验证"），改写成"数值检查通过 + 与 Simpack 逐项对照 + 仍未经实测标定" | 数字与 `CHANGELOG_DOCS` 一致 |
| `docs/CHANGELOG_DOCS.md` 登记本文 + 新 ADR | 文档索引单一入口仍然成立 |

### 5.1 安全边界专节：AI 只能走既定写路径（贯穿 Phase 0–6，不是一个独立阶段）

**要防的具体事故**（按可能造成的伤害排序）：

| # | 事故 | 后果 | 防线 |
|---|---|---|---|
| 1 | agent 直接改 `validation/crh380a_m/case_full12_cap05.json` | 冻结 oracle 失效，此后一切对比失去意义 | R3 + 输出根 allowlist + `test_output_root_is_an_allowlist` |
| 2 | agent 放松 `run.maximum_penetration_m` 后宣布"门通过" | 自证通过，质量门形同虚设 | `policy="forbidden"`（不可见 + 抛错）+ `test_registry_policy_partition_is_total` |
| 3 | agent 提交整份 case JSON（含 `initial_q`、型面偏移） | 静平衡残差 68 186 N 那类事故重现 | `test_wire_requests_have_no_case_body`（信封里没有 case 字段） |
| 4 | agent 把 `result_status` / `physics_validation_status` 写成"已验证" | 对外的物理可信度被打穿 | 两个字段只从 `manifest.summary` 读，API 无写入面；响应恒透出 `unvalidated_…` |
| 5 | agent 起 20 个 1.2 s 算例 | 机器占满、其它会话全部变慢（`UNIFIED…` §A.5 的教训） | `budget_exceeded`（`max_jobs`/`max_nfev`/`max_wall_s`）+ 单并发 `busy` |
| 6 | agent 通过 `../` 或 UNC 路径写到 oracle 目录 | 同 #1 | 写入前路径规范化 + allowlist |

**五层防线**（纵深，删掉任何一层都仍有拦截）：

1. **工具面**：不提供 shell、不提供任意文件写、不提供 case 正文入口。只有 8 个方法。
2. **schema 面**：`forbidden` 项**不出现在** `properties` 里（agent 连"能试"都做不到）。
3. **校验面**：`apply_patch` 的未知/非数值/非有限/越界/穿容器五类拒绝（已存在）+ `policy` 拒绝（新增）。
4. **进程面**：求解在独立子进程里，参数化文件是作业目录里的派生副本；`save_vehicle_result` 的
   `case_sha256` 与 `input_asset_sha256` 双校验（已存在）保证"跑的字节就是登记的字节"。
5. **测试面**：本文 §2.4 的 15 条新断言 + 既有 16 条架构规则 + `test_oracle_frozen.py`。

**一条明确的"不做"**：**不**给 agent 任何形式的"临时放开"（`--unsafe`、`--no-gate`、
`force=true`）。这类 flag 一旦存在，就会出现在某次排障的复制粘贴里。要放宽，由**人**改注册表并写
`CHANGELOG_DOCS`，走 git review。

---

## 附录 A：MCP 工具表面（8 tools + 2 resources）

| # | tool | 输入（agent 可见字段） | 输出（截断后大小） | 副作用 |
|---|---|---|---|---|
| 1 | `cases_list` | — | `[{case_id, sha256, schema, purpose, duration_s, dof, track_kind, certified}]` ≤ 8 KB | 无 |
| 2 | `params_list` | `{case_id?}` | `[{path, label_zh, unit, group, policy, minimum, maximum, step, current}]` ≤ 24 KB（72 条） | 无 |
| 3 | `variant_create` | `{base_case_id, patch:{path:number}, note, dry_run?}` | `{ok, changed:[{path,from,to}], resolved_sha256, variant_id?, error?}` | 写 `variants/`（`dry_run` 则不写） |
| 4 | `run_submit` | `{variant_id, program:{preset:"default"\|"fast", duration_s?, output_step_s?, x_start_m?}}` | `{job_id, state, reuse, idempotency_key}` | 建 job、spawn 子进程 |
| 5 | `run_status` | `{job_id}` | `{state, outcome, progress{elapsed_s, nfev?}, error?}` ≤ 2 KB | 无 |
| 6 | `run_cancel` | `{job_id}` | `{state}` | 杀子进程（`running` 时） |
| 7 | `result_get` | `{job_id, view:"summary"\|"assessment"\|"series", columns?, window?, max_points?}` | summary ≤ 4 KB；series `points ≤ 2000` | 可写 `assessment.json` |
| 8 | `artifact_uri` | `{job_id, name:"manifest"\|"history"\|"case_snapshot"\|"assessment"}` | `{uri, bytes, rows?, columns?}` | 无 |

resources：`velch://jobs/<job_id>/manifest`、`velch://jobs/<job_id>/history`（大对象走这里）。

**工具数量为什么是 8**：LLM 一次能稳妥驾驭的工具数量有限；再拆（`validate_patch`、`create_job`、
`list_jobs`、`explain_gates`）会让"先干什么"变成歧义。合并策略：
`validate` 合进 `variant_create(dry_run=True)`；门表合进 `result_get(view="summary")`；
`list_jobs` 留给 `run_status`（`{job_id:"*"}`）或 Phase 5 再议。

## 附录 B：落地后的文件树增量

```
Velch/
  LICENSE                                    [Phase 0]
  docs/AI_INTERFACE_ARCHITECTURE_2026-10-22.md   ← 本文
  docs/adr/ADR-A1-layering.md                [Phase 1]
  docs/adr/ADR-A2-mcp-first.md               [Phase 3]
  docs/adr/ADR-A3-single-write-path.md       [Phase 1]
  src/velch/params/{__init__,registry,patch,schema}.py   [Phase 1]
  src/velch/jobs/{model,store,runner,reader}.py          [Phase 2]
  src/velch/api/{wire,errors,service}.py                 [Phase 2]
  src/velch/serve/{mcp.py,http.py}                       [Phase 3/4]
  tests/test_ai_contract.py                  [Phase 1–2]
  tests/test_architecture_rules.py           [只增，Phase 1/2]
  archive/                                   [Phase 0]
```

## 附录 C：本文引用的行号清单（可重解析）

`ui/parameters.py:65-72`（`EDITABLE_SECTIONS`）· `:75-81`（`IGNORED_LEAF_PREFIXES`）·
`:266-291`（`apply_patch`）· `vehicle_solver.py:767`（`save_vehicle_result`）·
`model.py:132-173`（`RunSettings`，其中 `:149-159` 是 method/jacobian 组合校验）·
`vehicle.py:155-174`（`VehicleCase`）· `:204`（`load_vehicle_case`）·
`case/spec.py:93-110`（`from_path`，含 `velch-vehicle-v2` 校验）· `:128`（`patched`）· `:143`（`resolve`）·
`io/history.py:56`（`classify`）· `:86`（`HistoryTable`）· `:133`（`read_history`）·
`metrics.py:140`（`assess_history`）· `:73`（`Assessment`）·
`ui/store.py:47-55`（`GATE_LABELS` 七门）· `:57-63`（`GATE_DETAIL_FIELDS`）· `:365`（`scan_runs`）·
`tests/test_architecture_rules.py:54`（`SOLVER_SIDE`）· `:62-74`（`PRESENTATION_MAY_IMPORT`）·
`:413-419`（headless parametrize）· `tests/test_parameters_registry.py:51-57`（覆盖门）·
`pyproject.toml:10`（依赖）

---

## 附录 D：ADR 草案（三条，供评审先决；定稿后拆到 `docs/adr/`）

### ADR-A1：新增 `params` / `jobs` / `api` / `serve` 四包，层级由测试强制

**Status**：Proposed

**Context**：分层规则已经存在且有效（16 条 AST 断言），但 AI 接口需要新的调用者。
给 agent 直连求解器的权限会同时毁掉"可复现"和"物理不变量"；只靠文档约不住新代码。

**Decision**：加四包：`velch.params`（叶子，参数契约）、`velch.jobs`（作业与磁盘真相）、
`velch.api`（语义门面）、`velch.serve`（传输）。方向规则 R1–R4 各配一条 AST 测试；
`serialize` 面（`wire`）零 velch 依赖。

**Consequences**：+6 条架构规则、+15 条契约断言要维护；换来的是"agent 面永不可能 in-process
加载求解器"这件事**由 CI 保证**而不是由 review 保证。代价：一条新 import 边要走两处
（`FORWARD`/`SOLVER_SIDE` 常量 + 新规则），但失败信息会直接打印 `模块:行号 -> 被导入模块`。

### ADR-A2：AI 面交付选 MCP stdio，HTTP 延后

**Status**：Proposed

**Context**：候选四案（§3.1）。本机是单机 Windows 交付，已挂 MCP server；没有远程访问需求；
一次整车算例 79–172 s，必须异步；不得引入新依赖。

**Decision**：MCP stdio 为正式面（stdlib JSON-lines，无端口）；进程内 `VelchService` 为语义核心
（先做、纯 pytest 可测）；HTTP/JSON-RPC 等出现真实消费者再做，且复用同一份 wire schema。

**Consequences**：好处是零端口、零依赖、无运维、会话结束即退出、与 LLM 工具语义原生匹配。
代价是"一个客户端一个进程"（多客户端要各自起），且不能远程。**明确的失败模式**：
若将来需要非 MCP 消费者，必须补 Phase 4——所以 `api` 层从第一天就不许假设 stdio
（`test_only_adapters_touch_the_transport` 钉住）。

### ADR-A3：参数写入只有 `apply_patch` 一条路，且表分 `free/guarded/forbidden` 三级

**Status**：Proposed

**Context**：`apply_patch` 已是唯一写路径且有五类拒绝、有覆盖门（参考算例无遗漏字段）、
有 10 项测试。但 agent 是比 UI 弱的执行者：它会把"放松验收门"当成"通过"，
会把 `nominal_wheel_radius_m` 与型面偏移改错（68 186 N 残差），会在没有验收门覆盖的
柔度分支上撞出 D1/D2 那类缺陷（358 算例只有 5 个开柔度、0 个进验收门）。

**Decision**：注册表新增 `policy` 字段（默认 `free`）。`forbidden`（门阈值、`gravity`）对 agent
**不可见且拒绝**；`guarded`（轮轨接触 13 条、`rtol/atol/max_solver_step_s`、
`nominal_wheel_radius_m`）只在声明的辨识任务 bounds 内或带 `note` 时可动。UI 与人不受影响。

**Consequences**：agent 的能力边界变成**数据表**而不是散落的分支判断，可被一条测试穷举
（`test_registry_policy_partition_is_total`）。代价：每次新增参数必须同时定 `policy`；
`guarded` 的语义需要 `invert` 作业配合（Phase 5），在此之前 `guarded` 对 agent 等价于
"需 note"。

---

## 附录 E：未决问题（需要在评审里定，本文不给假答案）

1. **`guarded` 的"声明的辨识任务"由谁声明？** 是 variant 里的一个 `intent: "identify"` 字段，
   还是必须由人预先在 campaign 里登记 bounds？前者省事但 agent 能自我授权，后者安全但需求侧要
   多一步人工。倾向后者，需产品侧确认。
2. **`x_start_m` 该不该 `free`**：它只改观察窗，不改物理，但改了就与归档 oracle 不可直接比。
   倾向 `free` 但 `result_get` 在 `x_start_m` 与基例不同时**显式返回 `comparable_to_base: false`**。
3. **多客户端并发**：MCP 天然一客户端一进程。若两个 agent 同时各起一个，两个求解进程并发会把
   80 s 跑成 160 s。倾向在 `jobs/store.py` 里放一个**跨进程文件锁**（`msvcrt.locking`，
   stdlib），让第二个等待或 `busy`。
4. **会话是否需要"对话式记忆"**：本文把 `Session` 定义成纯粹的资源配额容器，不存对话。
   是否需要"agent 上一次跑的是什么"这类提示？倾向**由客户端负责**，服务端只存 job，
   避免服务端长出第二套状态。
5. **`inverse.bands` 之外还要不要暴露更多分析**（如 `inverse.identifiability`）？
   倾向 Phase 5 再议，且只暴露**已进验收门**的能力——`inverse/` 目前 `identifiability` 有实测
   （波形 rank 2/2 cond 1.44；峰值 rank 1/2 cond inf、`c_z` 分辨率 872 %），
   后者是**负结果**，不该给 agent 当工具用。
6. **`docs/` 与 `archive/` 的边界**：57 个游离脚本里有多少是"证据"（负结果出处）有多少是
   一次性探针？`UNIFIED…` §B.3 P1-5 建议全进 `archive/`，但 `CHANGELOG_DOCS` 引用了其中若干
   作为证据——需要一次人肉清点，不能脚本一刀切。
