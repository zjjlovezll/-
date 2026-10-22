# Velch AI 调用层设计（Agent Tool Layer，2026-10-22）

> 状态：**设计稿，未落代码**。本文只给方案与接口签名，不改 `src/` 下任何文件。
> 依据：`docs/ONBOARDING_2026-10-21.md`、`docs/RACK_CASE_DATA_CONTRACT_2026-10-21.md`、
> `docs/ARCHITECTURE_2026-10-21.md`（§4.2 稳定接口清单、§5 路线）、
> `src/velch/cli.py`、`src/velch/model.py`、`src/velch/vehicle.py`、
> `src/velch/ui/parameters.py`、`src/velch/case/spec.py`、`src/velch/io/`、
> `src/velch/vehicle_solver.py`、`src/velch/parallel.py`、`src/velch/metrics.py`、
> `src/velch/ui/store.py`、`tests/test_architecture_rules.py`。

---

## 0. 一句话方案

在 `src/velch/agent/` 里新增一个**只依赖 numpy/scipy + 标准库**的薄适配层：
它把现有的五个稳定入口（`load_vehicle_case` / `simulate_vehicle` / `save_vehicle_result` /
`metrics.assess_history` / `ui.parameters.apply_patch`）包装成 **20 个带 JSON Schema 的工具**，
用**文件系统的 job store** 承担 850 s 级长任务，用**只追加、哈希链式的算例修订账本**承担参数改写，
并把 `ui/parameters.py` 已有的 72 项注册表**直接导出成 LLM 的 patch schema**——
这个模块的 docstring 本来就写了这件事（`parameters.py:6-15`：*"an AI assistant can be handed this
table as its tool schema instead of guessing field names"*）。

三条不可谈判的红线：

1. **绝不原地改算例**。任何参数修改都产生一份新算例文件，父算例字节不变。
2. **绝不改冻结产物**。`history.csv` / `manifest.json` 的格式一字不动；AI 层自己的溯源写
   `ai_provenance.json` 旁挂文件。`docs/ARCHITECTURE_2026-10-21.md` §5 的验收门是"`history.csv` 不变"，
   任何为可观测性而改产物格式的做法都会直接违约。
3. **失败必须显式**。当前 CLI 把所有失败都压成 exit code 2（`cli.py:143-147`），
   自动化没法据此分支；Agent 层必须给出**错误码**，且 `ok=false` 时下游不允许消费 `data`。

---

## 1. 工具清单设计

### 1.1 命名与分层

工具名用 `域.动作` 的点分形式（MCP 会把它映射成 `velch_case_derive` 之类的合法名）。
五个域对应五个权限域（scope），见 §4.2。

| Tier | 域 | 工具数 | 权限 scope | 典型墙钟 |
|---|---|---|---|---|
| meta | `velch.*` | 2 | （无，永远可见） | instant |
| case | `case.*` | 7 | `read_case` / `write_case` | ms |
| run | `run.*` | 4 | `run` | 秒 / 850 s |
| result | `result.*` | 5 | `read_result` | 秒 |
| inverse | `inverse.*` | 2 | `inversion` | 分钟~小时 |
| dev | `dev.*` | 1 | `dev` | 分钟 |

### 1.2 统一返回信封（所有工具一致）

```python
# src/velch/agent/envelope.py
{
  "ok": bool,                     # 唯一的下游消费判据
  "status": "ok" | "gate_failed" | "failed" | "partial",
  "tool": "case.derive",
  "tool_version": "1.0",
  "data": {...} | None,           # ok=false 时恒为 None
  "error": {
      "code": "parameter_rejected",   # 见 §1.3，闭集
      "message": "contact.friction_coefficient: 1.8 > maximum 1.5",
      "hint": "registry 上限 1.5；如需超越请改 registry 而不是绕过工具",
      "detail": {"path": "contact.friction_coefficient", "value": 1.8, "maximum": 1.5},
      "retryable": false
  } | None,
  "provenance": {"velch_version": "0.4.0", "git_sha": "...", "policy_version": "p7",
                 "case_sha256": "...", "job_id": None},
  "limits": {"wall_s": 0.04, "truncated": false, "next_cursor": None}
}
```

`status="gate_failed"` 是 v2 语义：算例跑完了、产物齐了，但
`summary["result_status"] != "numerically_checked"`（`vehicle_solver.py:744`）。
**它能被读取、不能被引用为合格结果**——这是 `ok=false` 但 `data` 仍返回摘要的唯一例外，
且必须带 `data.gates` 原样透出。

### 1.3 错误码闭集（`fail-closed` 的执行体）

```python
# src/velch/agent/errors.py
class ErrorCode(str, Enum):
    INVALID_INPUT        = "invalid_input"          # schema 校验不过
    PARAMETER_REJECTED   = "parameter_rejected"     # apply_patch 拒绝（未知路径/非数/超范围/写穿容器）
    SCHEMA_UNSUPPORTED   = "schema_unsupported"     # schema_version 不认识
    PATH_OUTSIDE_WORKSPACE = "path_outside_workspace"
    CASE_INVALID         = "case_invalid"           # load_*_case 抛出
    CASE_MUTATED_DURING_RUN = "case_mutated_during_run"   # save_vehicle_result 的二次哈希失败
    ARTIFACT_INTEGRITY   = "artifact_integrity"     # manifest 缺失 / case_sha256 不符 / history 头不符
    GATE_FAILED          = "gate_failed"
    BUDGET_EXCEEDED      = "budget_exceeded"        # 预测墙钟/总预算超限，拒绝而不是悄悄跑
    SCOPE_DENIED         = "scope_denied"
    CONFIRMATION_REQUIRED = "confirmation_required"
    BUSY                 = "busy"                   # 并发上限
    TIMEOUT              = "timeout"
    CANCELLED            = "cancelled"
    UPSTREAM_FAILURE     = "upstream_failure"       # 未分类异常，永远 fail-closed

class AgentError(Exception):
    def __init__(self, code: ErrorCode, message: str, *, hint: str = "",
                 detail: dict | None = None, retryable: bool = False) -> None: ...
```

异常映射表（**唯一允许把领域异常翻译成工具结果的地方**）：

| 领域异常 | 来源 | → code |
|---|---|---|
| `ParameterError` | `ui/parameters.py:34`、`apply_patch:266-291` | `PARAMETER_REJECTED` |
| `SpecError` | `case/spec.py:30` | `PARAMETER_REJECTED` / `CASE_INVALID` |
| `SimulationFailure("v2 case changed during simulation")` | `vehicle_solver.py:774,777` | `CASE_MUTATED_DURING_RUN` |
| `ValueError("unsupported vehicle case schema")` | `vehicle.py` | `SCHEMA_UNSUPPORTED` |
| `MeasuredIOError` | `io/measured.py:74` | `INVALID_INPUT` |
| `AssessmentError` | `metrics.py:25` | `ARTIFACT_INTEGRITY` |
| `FileNotFoundError` / `PermissionError` | OS | `PATH_OUTSIDE_WORKSPACE` / `ARTIFACT_INTEGRITY` |
| 其他 `Exception` | — | `UPSTREAM_FAILURE`（**不吞、不重试**） |

---

### 1.4 meta 域

#### `velch.capabilities`
发现入口。**第一个被调用的工具**。

```python
input: {}                                   # 无参
output: {
  "tools": [ToolSummary, ...],              # 当前 scope 可见的工具（不可见的直接不列，不是拒绝）
  "case_schemas": ["velch", "velch-vehicle-v2"],
  "history_schema": "velch-history-v1",
  "parameter_groups": ["车辆","悬挂","轮轨接触","求解设置","轨道"],
  "si_units_only": true,
  "budget": {"max_runs": 20, "max_total_wall_s": 3600, "used": {...}},
  "scopes": ["read_case","write_case","run","read_result"],
  "limits": {"inline_ceiling_s": 60, "max_concurrent_jobs": 3, "series_max_points": 2000}
}
fail-closed: 无（这是唯一永不失败的业务工具；失败=进程起不来）
```

#### `velch.doctor`
自检：numpy/scipy 版本、物理核数、可用内存、workspace 可写性、`simpack_available()`、
冻结基线存在性（`docs/` 下 gate 文件）、本机 `wall_per_nfev_s` 标定值。
返回 `{"ready": bool, "problems": [{"code","detail"}...]}`；`ready=false` 时**其余写类工具全部拒绝**。

---

### 1.5 case 域（安全模型的主体，见 §2）

#### `case.list`
```python
input:  {"directory": str = "cases", "pattern": str = "case_*.json", "limit": int = 50}
output: {"cases": [{"path","case_id","schema","dof","duration_s","sha256","problem"}, ...]}
# 直接复用 ui/store.py:233 scan_cases / :197 case_info —— 已有实现，不重写
```

#### `case.read`
```python
input:  {"path": str, "include_params": bool = true}
output: {"path","sha256","schema_version","raw": {...},        # raw 只在 <=64 KiB 时内联
         "resolved": {"case_id","track_kind","dof","rail_ids","profile_assets": {path: sha}},
         "params": [{"path","label_zh","unit","group","value","minimum","maximum","step",
                     "resolvable": true}],                       # = ui/parameters.py:219 editable()
         "coverage": {"named": 61, "missing": ["track_dynamics.layers[].mass_y_kg", ...]}}
fail-closed: 文件不在 workspace 内 → PATH_OUTSIDE_WORKSPACE；JSON 非法 → INVALID_INPUT
```

#### `case.validate`
```python
input:  {"path": str}
output: {"valid": bool, "schema_version","dof","total_dof","track_kind",
         "errors": [{"code","message"}], "asset_hashes": {path: sha},
         "entry_point": "vehicle" | "v1" | null}     # ← 关键：告诉 agent 该走哪条路
# 实现：调 load_vehicle_case(path)；v1 回落到 model.load_case(path)
fail-closed: 任一门不过 → valid=false + ok=false（**不返回半成品 resolved 对象**）
```

`entry_point` 是刻意的：见 §5 第 3 条。Agent **不允许猜** v1/v2。

#### `case.params`
```python
input:  {"path": str | null, "group": str | null}
output: {"registry_version": "1", "entries": [ParameterEntry...],
         "solver_allowlist": [{"path":"run.method","enum":["DOP853","Radau","BDF"], ...}, ...]}
# 无 path 时返回纯注册表（= REGISTRY 的机器可读投影，72 项）
```

#### `case.derive` ← **唯一的写入口**
```python
input: {
  "parent": str,                         # 父算例路径（或 "rev_0007" 引用账本）
  "patch": [                             # 数组而非对象：保序、可逐项审计、无重键歧义
    {"path": "contact.friction_coefficient", "value": 0.32},
    {"path": "vehicle.travel_speed_m_s", "value_in": 160.0, "unit": "km/h"}
  ],
  "solver_patch": [                      # 第二命名空间：注册表之外的 6 个求解策略字段，见 §2.5
    {"path": "run.method", "value": "Radau", "intent": "switch to implicit for 8x wall-clock"}
  ],
  "allow_wildcard": false,               # 默认 false：命中多个叶子就拒绝
  "out_path": str | null,                # null → 自动 cases/<stem>__r<n>.json
  "note": str,                           # 必填，写进账本与算例 purpose_detail
  "tag": str = ""                        # 例如 "sweep-speed-160"
}
output: CaseRevision
fail-closed: 见 §2.4 全表
```

```python
# src/velch/agent/cases.py
@dataclass(frozen=True)
class PatchItem:
    path: str
    value: float | None = None
    value_in: float | None = None
    unit: str | None = None

@dataclass(frozen=True)
class LeafChange:
    path: str
    index: int | None        # 通配路径命中的第几个元素
    before: float
    after: float
    unit: str
    delta_rel: float

@dataclass(frozen=True)
class CaseRevision:
    revision_id: str          # "rev_0007"
    parent_sha256: str
    sha256: str
    path: Path
    affected: tuple[LeafChange, ...]   # 真正写下去的每个叶子（通配会展开成 N 行）
    warnings: tuple[str, ...]          # 例如 "wildcard touched 3 layers"
    audit_prev_hash: str
    physics_changed: bool              # solver_patch 非空 或 改动跨"物理"字段时为 True

def derive_case(*, parent: str | Path, patch: Sequence[PatchItem] = (),
                solver_patch: Sequence[SolverPatchItem] = (),
                allow_wildcard: bool = False, out_path: str | Path | None = None,
                note: str, tag: str = "", policy: "Policy") -> CaseRevision: ...
```

#### `case.diff`
```python
input:  {"a": str, "b": str, "max_leaves": int = 500}
output: {"changes": [LeafChange...], "truncated": bool,
         "physics_changed": bool, "schema_changed": bool,
         "asset_changes": [{"path","sha_a","sha_b"}...]}
# 逐叶子数值比较；忽略 source_evidence / asset_hashes / initial_state（记录，不是旋钮）
fail-closed: 任一文件越界/缺失 → PATH_OUTSIDE_WORKSPACE / ARTIFACT_INTEGRITY（不返回"空 diff"）
```

#### `case.revisions` / `case.revert`
```python
case.revisions: {"parent": str | null, "limit": 50}
  → {"revisions": [{"revision_id","parent_sha256","sha256","note","tag","ts","agent","affected_count"}]}
case.revert:    {"revision_id": str, "note": str, "out_path": str | null}
  → CaseRevision    # 实现是 derive_case(parent=该修订快照, patch=())，**仍然只追加**，
                    # 绝不删除、绝不覆盖；回退本身也是一条新修订记录
```

---

### 1.6 run 域（执行模型，见 §3）

#### `run.submit`
```python
input: {
  "case_path": str,
  "workers": 1,                    # 接触线程数；jobs>1 时必须为 1（见 parallel.py:1-8 的说明）
  "output_dir": str | null,        # null → jobs/<job_id>/out
  "tag": str = "", "purpose": str = "",
  "mode": "auto" | "sync" | "background",   # auto = 按 §3.2 的代价模型路由
  "inline_ceiling_s": 60.0,
  "budget": {"max_wall_s": 900.0},          # 硬上限；超了拿不到 manifest
  "confirm": {"acknowledge_wall_s": 850.0} | null,   # 预测 >=300 s 时必填
  "idempotency_key": str | null,            # sha256(case_sha + policy + workers + version + git_sha)
  "expected_case_sha256": str | null         # 竞态防护：不符直接拒
}
output: JobHandle {"job_id","state","case_sha256","output_dir",
                   "predicted_wall_s","predicted_range_s":[lo,hi],"reused":bool}
fail-closed: 预测墙钟超 budget → BUDGET_EXCEEDED（**不截断、不改参数绕过**）；
             并发已满且 mode=background → BUSY(retryable=true)；
             预测 >=300 s 且无 confirm → CONFIRMATION_REQUIRED；
             case 校验不过 → CASE_INVALID
```

#### `run.status`
```python
input:  {"job_id": str, "wait_s": 0.0}       # wait_s>0 即长轮询（MCP 友好），上限 25 s
output: JobRecord {
  "job_id","state","phase","elapsed_s","predicted_wall_s",
  "pid","heartbeat_age_s","output_dir",
  "artifacts": {"history": path|None, "manifest": path|None, "case_snapshot": path|None},
  "summary": {...} | null,                   # 来自 manifest.json 的 summary，原样
  "error": {...} | null
}
```

#### `run.cancel`
```python
input:  {"job_id": str, "grace_s": 5.0}
output: {"job_id","state":"cancelled"|"not_running","signal":"terminate"}
# 诚实说明：solve_ivp 没有中断钩子。cancel = 终止 worker 进程 →
# 状态落 "cancelled"，**产物不完整即不可用**（没有 manifest.json 就当没有结果）。
# history.csv 可能残在半截：读取侧一律先验 manifest，见 result.* 的 fail-closed 规则。
```

#### `run.list`
```python
input:  {"state": [...] | null, "limit": 50, "cursor": str | null}
output: {"jobs": [JobSummary...], "next_cursor": str | null}
# 同时扫 jobs/ 与 legacy 的 out_* 目录（ui/store.py:365 scan_runs / :319 run_info）
```

---

### 1.7 result 域

#### `result.read`
```python
input:  {"run": str}                          # 目录或 history.csv
output: {"manifest": {...}, "summary": {...}, "gates": {...},
         "assessment": AssessmentView,         # ui/store.py:582 assess
         "verdict": {"pass": bool, "reasons": [...]},
         "integrity": {"case_sha256_matches": true, "history_schema": "velch-history-v1",
                       "state_order_len": 67, "sample_count": 2401}}
fail-closed: manifest 缺失 → ARTIFACT_INTEGRITY；
             manifest.case_sha256 != case_snapshot 的实际哈希 → ARTIFACT_INTEGRITY；
             history.csv 头与 manifest.state_order 不符 → ARTIFACT_INTEGRITY
             （宁可拒绝，也不给出一份"看起来有数"的错结果）
```

#### `result.series`
```python
input: {
  "run": str,
  "columns": [str],              # 必须在 manifest.state_order ∪ contact 列里，否则拒
  "window": {"t0_s": float, "t1_s": float} | null,
  "max_points": 2000,            # 硬上限，decimate 到 <= max_points
  "encoding": "inline" | "artifact"
}
output: inline  → {"t_s": [...], "series": {name: [...]}, "decimated_from": 2401, "truncated": false}
        artifact→ {"artifact": path, "format": "npz", "sha256": ...}    # 大数组永不内联
fail-closed: 列名不在 state_order → INVALID_INPUT 并回显可用的 12 个候选（不给全量 90 列）；
             window 超出 run 区间 → INVALID_INPUT（不 clamp）
```

#### `result.assess`
```python
input:  {"run": str, "static_axle_load_n": float | null}
output: {"assessment": Assessment.as_dict(load), "limits": AssessmentLimits,
         "verdict": {"pass": bool, ...}}
# 直接 = metrics.assess_history(path, static_axle_load_n=...) + .verdict(load)
fail-closed: history 不可读/列缺失 → ARTIFACT_INTEGRITY（AssessmentError）
```

#### `result.compare`
```python
input:  {"a": str, "b": str, "columns": [str], "align": "time"}
output: {"common_columns": [...], "only_in_a": [...], "only_in_b": [...],
         "diff": {col: {"rms":..., "max_abs":..., "peak_a":..., "peak_b":..., "rel":...}},
         "case_diff": CaseDiff}                  # 顺手挂上算例差异，A/B 才自证
fail-closed: 列集合不一致且未显式给 columns → INVALID_INPUT（不静默取交集）
```

#### `result.observations`
```python
input:  {"folder": str, "channels": [int] | null, "condition": {"speed_kmh","slope"} | null}
output: {"conditions": [...], "channels": [{"channel","name","unit","samples","rate_hz",
                                           "t0_s","t1_s"}], "windows": {...}}
# 包 io/measured.py: campaign_plan / read_record / load_observations / condition_windows
fail-closed: 文件数 < MIN_SAMPLES(100) 或时间轴超 TIME_TOLERANCE_S(0.002) → MeasuredIOError → INVALID_INPUT
```

---

### 1.8 inverse 域

#### `inverse.estimate`
```python
input: {
  "base_case": str,
  "parameters": [{"name": "support_k_z",
                  "path": ["rail_templates", 0, "support", "k_z_n_m"],
                  "bounds": [-0.9, 9.0]}],       # = case/spec.py:63 ParameterSpec.of
  "target": {"kind": "measured"|"run", "ref": str, "columns": [str], "window": {...}},
  "residual": {"kind": "series_rms", "weighting": "uniform"|"axle_load"},
  "budget": {"max_iterations": 20, "max_wall_s": 3600},
  "confirm": {"acknowledge_wall_s": 17000.0}     # 20 次 × 850 s；实测按 idempotency 缓存复用
}
output: {"estimate": {name: {"theta","value","sigma"}},
         "iterations": [{"k","theta","residual_norm","wall_s","job_id"}],
         "identifiability": Verdict | null,
         "advisory": "local linearised Gauss-Newton estimate; not a validated identification"}
fail-closed: 参数 path 不在 base_case → PARAMETER_REJECTED；
             bounds 下界 <= -1 → PARAMETER_REJECTED（保持正值，spec.py:60-61 已有该规则）；
             任一次迭代 gate_failed → 整体 status="failed"，不给 estimate；
             未给 confirm 且预测超预算 → CONFIRMATION_REQUIRED
```

#### `inverse.identifiability`
```python
input:  {"sensitivity": {"theta": [...], "residual_jacobian": [[...]]}, "reference_sensitivity": 0.0}
output: identifiability.Verdict（= analyse(Sensitivity(...))）
# 契约里必须出现 "linearised / local" 字样，禁止输出"已辨识"这类结论
```

---

### 1.9 dev 域

#### `dev.gates`
```python
input:  {"baseline_run": str | null}
output: {"gates": {"frozen_history_bit_identical": bool, "tests_passed": int,
                   "arch_rules_passed": 17, "wall_s": {...}}, "failures": [...]}
# 只读：跑 pytest 子集 + 比对冻结基线哈希；不写源码
fail-closed: 任何 gate 不通过 → ok=false（这是"扩展开发"的守门人）
```

---

## 2. 算例读写与参数补丁的安全模型

### 2.1 白名单：三层，逐层收窄

| 层 | 内容 | 执行体 |
|---|---|---|
| L1 章节白名单 | `EDITABLE_SECTIONS = (vehicle, contact, run, track_dynamics, rail_templates, support_compliance)`（`parameters.py:65-72`） | 路径必须以这六个前缀开头 |
| L2 注册表白名单 | `REGISTRY` 的 72 条（`parameters.py:83-183`） | `apply_patch` 内部 `if path not in table: raise`（`:276-277`） |
| L3 几何表黑名单 | `IGNORED_LEAF_PREFIXES`（`:75-81`）：`rail_templates[].stations`、`...bodies[].stations`、`contact.wheel_profile`、`contact.rail_profile` | 即使 L2 有路径也不许写 |

L1/L2 都过才算合法。**L3 是独立的一道**，因为几何表是"数据不是旋钮"（每张上千个数）。

### 2.2 单位：SI-only，闭集换算

注册表的 `unit` 字段（`kg`、`N/m`、`N·s/m`、`N·m/rad`、`m/s²`、`N·s/m^1.5` …）已经是内部单位。
规则：

- `value` = **注册表单位下的数值**，永远不做隐式换算。
- 想用人话单位就传 `{value_in, unit}`，且只接受下面的**闭集**；其它一律 `PARAMETER_REJECTED`：

```python
# src/velch/agent/units.py
CONVERSIONS = {
    ("km/h", "m/s"): 1.0 / 3.6,
    ("mm", "m"): 1.0e-3,
    ("kN", "N"): 1.0e3,
    ("MPa", "Pa"): 1.0e6,
    ("N/mm", "N/m"): 1.0e3,
    ("t", "kg"): 1.0e3,
    ("deg", "rad"): math.pi / 180.0,
}
def to_si(value_in: float, unit: str, target: str) -> float | None: ...
```

- `value` 与 `value_in` **互斥**，两个都给 → `INVALID_INPUT`。
- 账本同时记 `value`、`value_in`、`unit` 三者，事后能复现调用方原话。
- 单位不符（`unit="kN/m"` 而注册表是 `N/m`）→ 显式拒绝并回显注册表单位，**不猜**。

### 2.3 范围：两道闸

```
registry envelope   (硬, 不可配)  : spec.minimum / spec.maximum
agent policy envelope (软, 可配)  : policy.json 里更窄的区间，默认值如下
```

`policy.json` 对**自治模式**的默认收窄（理由：这些都是"一改就把 850 s 变 3000 s"或"改物理"的量）：

| 参数 | registry | 自治默认 |
|---|---|---|
| `run.duration_s` | `[1e-4, 60]` | `[1e-4, 2.0]` |
| `run.output_step_s` | `[1e-6, 0.1]` | `[1e-4, 1e-2]`（< 1e-4 只是徒增采样） |
| `run.max_solver_step_s` | `[1e-8, 0.1]` | `[1e-5, 1e-4]`（> 1e-4 会越过事件） |
| `run.rtol` | `[1e-14, 1e-2]` | `[1e-8, 1e-6]`（1e-14 是纯浪费） |
| `run.atol` | `[1e-16, 1e-2]` | `[1e-10, 1e-4]` |
| `contact.strip_dy_m` | `[1e-5, 1e-2]` | `[1e-4, 2e-3]` |
| `vehicle.travel_speed_m_s` | `[0.1, 200]` | `[1.0, 120]`（再往上需要显式 intent） |

超 policy 区间但未超 registry → `PARAMETER_REJECTED`，`hint` 里明确写"policy 上限 X，
如需放开请改 `policy/velch_agent_policy.json`"——**让人改策略，不让 agent 自己绕过**。

### 2.4 通配 `[]` 与"变更展开"（fail-closed 全表）

`apply_patch` 对带 `[]` 的路径是**静默改所有元素**（`parameters.py:308-314`：*"patch every element:
the registry demands uniform semantics"*）。这对人类 UI 是合理约定，对 agent 是隐蔽爆炸半径。
Agent 层的规则：

```python
# 命中 >1 个叶子且 allow_wildcard=False → 拒绝
if len(resolved_leaves) > 1 and not allow_wildcard:
    raise AgentError(ErrorCode.PARAMETER_REJECTED,
        f"{path} resolves to {n} leaves; pass allow_wildcard=true or address elements explicitly",
        hint="通配路径会同时改所有 layers/rails",
        detail={"path": path, "leaves": [...]})

# 命中 0 个叶子（该算例没这个结构）→ 拒绝
if not resolved_leaves:
    raise AgentError(ErrorCode.PARAMETER_REJECTED, f"{path} not present in this case")
```

`affected` 永远展开成逐叶行，agent 与人类都能看到"这一条 patch 动了 3 个道床层"。

**完整 fail-closed 清单**（`case.derive` 必须逐条测）：

| # | 输入 | 结果 |
|---|---|---|
| F1 | 路径不在 L1 章节 | `PARAMETER_REJECTED` |
| F2 | 路径不在 L2 注册表 | `PARAMETER_REJECTED`（复用 `apply_patch:276`） |
| F3 | 路径命中 L3 几何表 | `PARAMETER_REJECTED` |
| F4 | `value` 非数值 / bool / NaN / inf | `PARAMETER_REJECTED`（`apply_patch:279-282`） |
| F5 | 超 registry `minimum/maximum` | `PARAMETER_REJECTED` |
| F6 | 超 policy envelope | `PARAMETER_REJECTED` + hint 指向 policy 文件 |
| F7 | 写穿容器（目标是 mapping） | `PARAMETER_REJECTED`（`apply_patch:287-289`） |
| F8 | 通配命中 >1 且未 `allow_wildcard` | `PARAMETER_REJECTED` |
| F9 | 通配命中 0 | `PARAMETER_REJECTED` |
| F10 | `value` 与 `value_in` 同时给 | `INVALID_INPUT` |
| F11 | 未知 `unit` | `PARAMETER_REJECTED`（列出注册表单位） |
| F12 | `solver_patch` 的 key 不在 6 项允许表 | `PARAMETER_REJECTED` |
| F13 | `solver_patch` 缺 `intent` | `INVALID_INPUT` |
| F14 | `note` 为空 | `INVALID_INPUT`（没有理由就没有审计） |
| F15 | `out_path` 已存在 | `INVALID_INPUT`（**绝不覆盖**；让调用方换名） |
| F16 | `out_path` 越出 workspace | `PATH_OUTSIDE_WORKSPACE` |
| F17 | 派生结果 `load_vehicle_case` 失败 | `CASE_INVALID`，且**删掉刚写的半成品文件** |
| F18 | 父算例 sha 与账本记录不符（被外部改过） | `ARTIFACT_INTEGRITY` |

F17 的顺序很关键：先写临时文件 → 加载校验 → 通过才 `os.replace` 到目标名。原子化，
不会留下"看起来能用"的坏算例。

### 2.5 第二命名空间：`solver_patch`（6 项）

注册表**不含** `RunSettings` 的这几个字段（`parameters.py:157-164` 只有
`x_start_m / duration_s / output_step_s / max_solver_step_s / rtol / atol /
maximum_penetration_m / maximum_abs_contact_slope`）。但它们都是自动化真正需要的杠杆：

| 字段 | 允许值 | 为什么必须放行 |
|---|---|---|
| `run.method` | `DOP853` / `Radau` / `BDF` | `docs/S2_IMPLICIT_DONE_2026-10-22.md`：隐式 101.6 s vs DOP853 ≈850 s，**8.4×** |
| `run.jacobian` | `null` / `sparse_fd` / `analytic` | 隐式方法的前提（`model.py` 里 DOP853+ jacobian 是硬报错） |
| `run.refine_peak` | bool | `vehicle_solver.py:705-728`：输出步长采样伪峰 vs 步内真峰差 2.571 % |
| `run.contact_seed_scope` | `body` / `rail` / `rail_hold` | 接触搜索策略，影响速度与结果 |
| `run.body_hysteresis` | bool | 物理开关 |
| `run.contact_search_half_width_m` | `null` / 正数 | 接触搜索带宽 |

规则：必须带 `intent`（自由文本），必须记 `physics_changed=True`，
**且 `case.diff` 与 `run.submit` 都把它标红**——因为它们会让 A/B 对比失去可比性
（`model.py` 里 `jacobian` + DOP853 的硬报错就是同一个理由：*"A/B comparisons made on top of
that warning are wrong in a way nothing else catches"*）。

### 2.6 变更审计：只追加 + 哈希链（文件系统，不引依赖）

```
<workspace>/
  revisions/
    ledger.jsonl          # 一行一条 JSON，append-only
    snapshots/<sha256>.json   # 每次派生的完整算例快照（内容寻址、天然去重）
  cases/<stem>__r<n>.json     # 对外可读的派生算例
  audit/rejections.jsonl      # 被拒的补丁也记（重复尝试是信号）
```

```python
# src/velch/agent/revisions.py
def append_revision(*, revision_id: str, parent_sha256: str, sha256: str,
                    patch: Sequence[PatchItem], solver_patch: Sequence[SolverPatchItem],
                    affected: Sequence[LeafChange], path: Path, note: str, tag: str,
                    agent: str, tool_version: str, policy_version: str) -> str:
    """追加一行，返回本条记录的 hash。ledger 每条带 prev_hash，链断即检测到删改。"""

def verify_ledger() -> tuple[bool, str]:
    """重放哈希链；返回 (intact, first_broken_revision_id)。doctor 会调它。"""
```

`revisions.jsonl` 单行示例：

```json
{"revision_id":"rev_0007","ts":"2026-10-22T16:41:39+08:00","agent":"agent:session-3f2a",
 "parent_sha256":"a1b2…","sha256":"c3d4…","path":"cases/case_baseline__r7.json",
 "note":"soften ballast to match measured 3 mm settlement","tag":"calib-ballast",
 "patch":[{"path":"track_dynamics.layers[].k_z_n_m","value":2.4e7,"unit":"N/m"}],
 "solver_patch":[{"path":"run.method","value":"Radau","intent":"8x wall-clock"}],
 "affected":[{"path":"track_dynamics.layers[0].k_z_n_m","index":0,"before":6.0e7,"after":2.4e7,"unit":"N/m","delta_rel":-0.6},
             {"path":"track_dynamics.layers[1].k_z_n_m","index":1,"before":6.0e7,"after":2.4e7,"unit":"N/m","delta_rel":-0.6}],
 "tool_version":"1.0","policy_version":"p7","prev_hash":"9f8e…"}
```

### 2.7 可回退

- 语义回退 = `case.revert(revision_id)` → **再派生一次**（`patch=()`），四件事同时成立：
  字节可复现（快照内容寻址，sha 相同）、历史不丢、账本仍只追加、回退动作本身可审计。
- 物理回退 = git。算例是纯 JSON，`cases/` 与 `revisions/` 建议直接进仓库。
  **不靠 `git checkout` 做回退**（会破坏账本链），只用它做"人在旁边看"的第二双眼。
- 不做删除。工具面没有 delete。

---

## 3. 任务执行模型

### 3.1 为什么必须分两级（实测数字）

`docs/ARCHITECTURE_2026-10-21.md:80,98` 与 `docs/CAPABILITY_INVENTORY_2026-10-20.md:98`：
生产路径（DOP853 + `max_solver_step_s=1e-4` + `rtol=1e-6`）跑 1.2 s 工况要
**331 949 次 RHS / ≈850 s 墙钟 / 67 自由度**；隐式（Radau + `jacobian="analytic"`）把整程压到
**101.6 s**（`docs/S2_IMPLICIT_DONE_2026-10-22.md:19`，≈8.4×）。
所以"一次 `simulate_vehicle` 可能是 1 秒，也可能是 15 分钟"，任何同步 MCP 调用都会撞超时。

### 3.2 代价模型与路由（先算，再决定同步/后台）

```python
# src/velch/agent/cost.py
# 标定量（基线机实测，由 doctor 复核）：
WALL_PER_NFEV_S = 2.56e-3        # ≈850 s / 331 949 nfev
NFEV_PER_STEP = {"DOP853": 27.7, "Radau": 12.0, "BDF": 9.0}   # 首项由 331949/(1.2/1e-4) 反推

def predict_wall_s(case: VehicleCase, *, workers: int = 1) -> tuple[float, float, float]:
    """返回 (point, low, high)；区间 = point × [0.6, 1.7]（跨越不同机器的保守包络）。"""
    steps = case.run.duration_s / case.run.max_solver_step_s
    nfev = steps * NFEV_PER_STEP[case.run.method]
    speedup = min(max(1, workers), 8) ** 0.7          # 接触线程并行，收益次线性
    point = nfev * WALL_PER_NFEV_S / speedup
    return point, 0.6 * point, 1.7 * point
```

验算：1.2 s / 1e-4 → 12000 步 → 332 400 nfev → **≈851 s**，与冻结基线吻合；
0.1 s 工况 → ≈71 s → 进后台；0.05 s → ≈35 s → 可同步。

路由规则（`run.submit(mode="auto")`）：

| 预测墙钟 | 行为 |
|---|---|
| `< inline_ceiling_s`（默认 60 s） | **同步**执行，直接返回完整 `JobRecord`（state=succeeded） |
| `≥ 60 s` 且 `< 300 s` | **后台**，返回 `JobHandle`，agent 用 `run.status(wait_s=…)` 轮询 |
| `≥ 300 s` | **后台 + 强制 `confirm.acknowledge_wall_s`**（agent 必须复述它准备等多久） |
| `> budget.max_wall_s`（默认 900 s） | `BUDGET_EXCEEDED`，**拒绝提交**（不建议"跑一半"） |

### 3.3 job store（文件系统状态机，无数据库依赖）

```
jobs/<job_id>/
  job.json            # 状态机唯一真相；写入用 temp + os.replace（原子）
  case.json           # 本次真正加载的算例（绝对化资产路径后的快照）
  worker.log          # 子进程 stdout/stderr
  out/                # save_vehicle_result 的落点：case_snapshot.json / history.csv / manifest.json
  ai_provenance.json  # AI 层旁挂溯源：git_sha、policy_version、predicted/final wall、patch 引用
  heartbeat           # worker 每 5 s touch（mtime 即读）
```

```python
JobState = Literal["created","queued","running","succeeded","gate_failed","failed","cancelled","timeout"]
JobPhase = Literal["queued","loading_case","integrating","writing","assessing","done"]
```

状态迁移（**只允许这些边**，非法迁移直接 `UPSTREAM_FAILURE` 并冻结 job）：

```
created → queued → running → {succeeded | gate_failed | failed | cancelled | timeout}
queued  → cancelled
running → cancelled | timeout
```

`gate_failed` 与 `failed` 的区别（v2 语义，`vehicle_solver.py:744`）：

- `succeeded` ⇔ `manifest.summary.result_status == "numerically_checked"`
- `gate_failed` ⇔ 跑完了、有 manifest、但 `result_status == "numerical_gate_failed"`
  （gate 名字见 §5「honorable mentions」：`vertical_preload_residual` / `penetration_within_case_limit` /
  `friction_bound` / `no_edge_limited_active_contact` / `translational_action_reaction` /
  `modal_generalized_contact_power`）
- `failed` ⇔ 没 manifest（异常、崩溃、被 kill）

**没有 manifest 就不存在结果**——`result.*` 一律先验 manifest，这条规则把"残半的 history.csv"
彻底排除在可用数据之外。

### 3.4 进程模型：一个 job = 一个操作系统进程

```python
# src/velch/agent/worker.py —— 入口：python -m velch.agent.worker <job_id>
def main(job_id: str) -> int:
    rec = jobs.read(job_id)
    jobs.transition(job_id, "running", pid=os.getpid())
    case = load_vehicle_case(Path(rec["case_path"]))     # 加载 job 自带的那份 case.json
    result = simulate_vehicle(case, contact_workers=rec["workers"])
    jobs.set_phase(job_id, "writing")
    csv_path, manifest_path = save_vehicle_result(case, result, Path(rec["output_dir"]))
    jobs.set_phase(job_id, "assessing")
    assessment = assess_history(csv_path)                # 失败不影响 succeeded，只影响 verdict
    jobs.finish(job_id, state=_state_from(result.summary), artifacts={...})
    return 0
```

为什么不是线程：`simulate_vehicle` 是单条串行 IVP（`parallel.py:1-8` 已经写明
"one trajectory is a serial initial value problem"），线程不会有加速；而进程隔离换来
**干净的取消**（terminate）、**崩溃不污染父进程**、**per-job 环境变量**
（`OMP_NUM_THREADS=1`、`OPENBLAS_NUM_THREADS=1`，否则 `jobs × contact_workers` 会与 BLAS 线程叠加超订）。

`parallel.run_vehicle_batch(case_paths, output_root, jobs=, workers=)` 保留作为**批处理快路径**
（`--jobs` 个并发进程），Agent 层不重写它，只在 `run.submit(mode="batch")` 里透传。

### 3.5 并发与资源上限

```python
# policy.json
{
  "limits": {
    "max_concurrent_jobs": 3,          # 默认 min(4, physical_cores - 1)
    "max_contact_workers": 8,
    "rule": "jobs > 1 implies workers == 1",   # parallel.py 的既定建议
    "max_total_wall_s": 3600,
    "max_runs_per_session": 20,
    "max_disk_bytes": 5_000_000_000,
    "inline_ceiling_s": 60
  }
}
```

- 并发闸：`jobs/.semaphore` 目录里每个运行中 job 一个锁文件（`O_CREAT|O_EXCL`），
  取不到 → `BUSY(retryable=true)`。不用 `threading.Semaphore`（跨进程无效）。
- 环境钳制：worker 启动时强制 `OMP_NUM_THREADS=1 / OPENBLAS_NUM_THREADS=1 / MKL_NUM_THREADS=1`。
- 磁盘前置检查：估算 `rows ≈ duration_s / output_step_s`、`cols ≈ 1 + 4 + state_order_len × 2 + 6 × rails`，
  `bytes ≈ rows × cols × 20`。超出 `max_disk_bytes` 余量 → `BUDGET_EXCEEDED`（先拒，不写满盘）。
- 超时：worker 自己按 `budget.max_wall_s` 记账，父进程另有 watchdog（`heartbeat_age_s > 30` → 判 `timeout` 并 kill）。

### 3.6 幂等与复用（省的是 850 s，不是毫秒）

```python
def idempotency_key(case_sha256: str, *, workers: int, policy_version: str,
                    velch_version: str, git_sha: str) -> str:
    return hashlib.sha256(f"{case_sha256}|{workers}|{policy_version}|{velch_version}|{git_sha}".encode()).hexdigest()
```

`jobs/.index.jsonl` 按 key 建索引：命中且 `state in ("succeeded","gate_failed")` 且产物哈希仍对 →
返回 `JobHandle(reused=True)`，并把原 `job_id` 一起给出。这是 agent 反复试算例时唯一的成本护栏。

### 3.7 进度：诚实的三种粒度

`scipy.integrate.solve_ivp` 没有逐步回调，所以**不要伪造百分比**。分层给：

| 粒度 | 来源 | 何时可用 |
|---|---|---|
| `phase`（5 档） | worker 自己写 | 永远有 |
| `elapsed_s` + `predicted_wall_s` | 墙钟 + §3.2 代价模型 | 永远有 |
| `fraction`（真实） | 仅当 `simulate_vehicle` 增加可选 `progress_callback` | Phase-C 可选（见 §5 落地清单 M4） |

`fraction` 的落法（**唯一允许碰求解器的改动**，且默认关闭）：

```python
# 修改（可选）：src/velch/vehicle_solver.py
def simulate_vehicle(case: VehicleCase, contact_workers: int = 1,
                     progress_callback: Callable[[float, int], None] | None = None) -> VehicleResult: ...
# 语义：在 RHS 包装里每 N 次接受步调用一次 callback(t_s, nfev)；
# progress_callback=None 时零行为变化；闸门 = 冻结基线 history.csv 逐字节相等。
```

在此之前，Agent 的对外话术固定为"已跑 elapsed / 估计 wall（区间）"，不给假进度条。

### 3.8 产物目录约定

```
<workspace>/                         # policy.workspace，默认 Velch/../velch_agent_ws
  policy/velch_agent_policy.json
  cases/                             # 派生算例（永不覆盖源 case_*.json）
  revisions/{ledger.jsonl, snapshots/}
  audit/rejections.jsonl
  jobs/<job_id>/{job.json, case.json, out/, worker.log, ai_provenance.json, heartbeat}
  artifacts/<run_id>/...             # npz / png / csv 导出
  cache/idempotency.jsonl
```

**一个必须提前决定的取舍**：`ui/store.py:365 scan_runs(pattern="out_*")` 只认以 `out_` 开头的目录。
若 agent 的 job 目录叫 `jobs/<job_id>/out`，GUI 的结果列表**看不见它们**。两个选项：
(a) 保持隔离（推荐：agent 的试算不该污染人的结果列表），gui 需要时再单独加一页读 `jobs/`；
(b) 让 job 的产物目录直接叫 `<scanned_root>/out_<job_id>`，GUI 立刻可见，但结果列表会被 agent 的
几百次试算淹没。本文按 (a) 设计，`run.list` 同时扫 `jobs/` 与 legacy `out_*`，两者都能被 agent 读。

`out/` 内部**完全由 `save_vehicle_result` 决定**（`case_snapshot.json` / `history.csv` / `manifest.json`），
AI 层不往里加任何文件——溯源一律 `ai_provenance.json` 旁挂。
`ai_provenance.json` 关键字段：`{job_id, revision_id, case_sha256, patch, solver_patch, policy_version,
velch_version, git_sha(dirty?), predicted_wall_s, final_wall_s, nfev, host, started_at, finished_at,
cancel_requested}`。

---

## 4. 自描述与发现机制 + 防误用护栏

### 4.1 单一真相：Python 声明 → 三处导出

```python
# src/velch/agent/manifest.py
@dataclass(frozen=True)
class ToolSpec:
    name: str                                   # "case.derive"
    title_zh: str
    summary: str                                # 给 LLM 的一句话，<= 200 字
    tier: Literal["meta","case","run","result","inverse","dev"]
    scopes: frozenset[str]
    input_schema: dict                          # JSON Schema 2020-12 子集
    output_schema: dict
    failure_codes: tuple[ErrorCode, ...]        # 必须非空（除 meta 域）
    cost: Literal["instant","seconds","minutes","tens_of_minutes"]
    side_effects: tuple[str, ...]               # ("writes_case","spawns_process","writes_artifacts")
    idempotent: bool
    confirmation_above_s: float | None
    examples: tuple[ToolExample, ...]           # >= 1 条 golden call

TOOLS: tuple[ToolSpec, ...] = (...)
def manifest_json(*, scopes: frozenset[str] | None = None) -> dict: ...
def tool_schema(name: str) -> dict: ...
```

三处导出（一份数据，不许分叉）：

1. **MCP `tools/list`**：`server_mcp.py` 直接 `manifest_json()` 映射成 MCP 的 `{name, description, inputSchema}`。
2. **CLI**：`velch agent manifest --json`（整份）/ `velch agent schema --tool case.derive`（单份）/
   `velch agent call --tool case.derive --args @patch.json`（一次性调用，给 shell/脚本用）。
3. **文档**：`velch agent docs --output docs/AGENT_TOOL_CONTRACT.md` 生成人读快照（CI 里 diff 必须为空，
   否则工具契约变了却没更新文档）。

### 4.2 参数注册表的机器可读导出（LLM 真正看到的东西）

`ui/parameters.py` 的 72 条已经是"带中文标签 + 单位 + 分组 + 物理区间"的声明式表，直接投影：

```json
{
  "type": "array",
  "description": "参数补丁列表；路径必须来自 case.params 返回的注册表。通配 [] 会命中多个元素。",
  "items": {
    "oneOf": [
      {"type": "object", "additionalProperties": false, "required": ["path", "value"],
       "properties": {
         "path": {"const": "contact.friction_coefficient"},
         "value": {"type": "number", "minimum": 0.0, "maximum": 1.5,
                   "description": "轮轨摩擦系数（单位 -）"}}},
      … 71 more
    ]
  }
}
```

**为什么不给一个 72 键的大对象**：键名带 `.`、带 `[]`，一个 `additionalProperties:false` 的大对象
在多数模型上会被截断或拼错键；`oneOf` 的 72 分支每个只暴露一个 `const` 路径，模型只需**选分支 + 填一个数**，
而且 `minimum/maximum` 就在同一个分支里，范围约束与字段名同屏出现。

`case.params` 另给 `coverage() (named, missing)`：把注册表**没命名**的可编辑数值叶子列出来
（`parameters.py:230-263`）。Agent 看到 `missing` 就知道"这些数字我不能改"，而不是编一个路径试试。

### 4.3 防误用护栏（8 条，逐条可测）

| # | 护栏 | 实现点 | 违反时 |
|---|---|---|---|
| G1 | **scope 隐藏而非拒绝** | `manifest_json(scopes=…)` 只列可见工具 | 调用不可见工具 → `SCOPE_DENIED` |
| G2 | **路径监狱** | 所有 `path` 参数 `resolve()` 后必须是 `policy.workspace` 或 `policy.read_roots` 的子路径；禁 `..`、禁符号链接逃逸 | `PATH_OUTSIDE_WORKSPACE` |
| G3 | **预算账本** | `max_runs_per_session` / `max_total_wall_s` 累计；超了拒 | `BUDGET_EXCEEDED`（不降级、不重试） |
| G4 | **长任务确认** | 预测 ≥300 s 必须回传 `acknowledge_wall_s`（±20 % 内） | `CONFIRMATION_REQUIRED` |
| G5 | **产物先行校验** | `result.*` 先验 manifest + case_sha256 + state_order | `ARTIFACT_INTEGRITY` |
| G6 | **输出限流** | `max_points=2000` / `max_leaves=500` / raw 仅 ≤64 KiB 内联 | `limits.truncated=true` + 分页游标 |
| G7 | **结论纪律** | 任何结果都带 `physics_validation_status`（v2 summary 里就是 `"unvalidated_against_measurement_or_Simpack"`，`vehicle_solver.py:745`）；`inverse.*` 强制 `advisory` 含 "local/linearised" | 生成类工具（未来）拒绝越界措辞 |
| G8 | **物理开关显式化** | `solver_patch` 必带 `intent`；`case.diff`/`run.submit` 返回 `physics_changed=true` | 不阻断，但**永远可见** |

G7 值得强调：现有工程规范（`docs/DEVELOPMENT_GATES.md`、`docs/ARCHITECTURE_2026-10-21.md` §5）
明确"Velch 的物理有效性未对实测/Simpack 验证"。Agent 层把这句**变成返回值的一部分**，
而不是写在 prompt 里求模型自觉。

### 4.4 MCP 服务的最小实现（不引 SDK）

MCP 是 JSON-RPC 2.0 over stdio，实现下面四个方法就够：

```python
# src/velch/agent/server_mcp.py
def handle(request: dict) -> dict:
    method = request.get("method")
    if method == "initialize":      return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {...}}
    if method == "tools/list":      return {"tools": [to_mcp(s) for s in visible_tools()]}
    if method == "tools/call":      return {"content": [{"type": "text", "text": json.dumps(dispatch(...))}],
                                            "isError": not result["ok"]}
    if method == "resources/list":  return {"resources": artifact_resources()}   # 产物按 URI 暴露
    if method == "resources/read":  return {"contents": [read_resource(uri)]}
    if method == "ping":            return {}
    raise NotImplementedError(method)
```

注册方式（`pyproject.toml` 的 `[project.scripts]` 加一行）：

```toml
[project.scripts]
velch = "velch.cli:main"
velch-gui = "velch.gui:main"
velch-mcp = "velch.agent.server_mcp:main"     # 新增
```

与 `AGENTS.md` 里 GraphFlow 的 MCP 配置并列即可，同一台机器上互不干扰。

---

## 5. 最小可行落地清单（文件级）

### 5.1 新增（14 个文件，全部在 `src/velch/agent/` 下 + 1 个测试组）

| # | 文件 | 内容 | 行数估计 |
|---|---|---|---|
| N1 | `src/velch/agent/__init__.py` | 导出 `build_manifest` / `dispatch` / `AgentError` | 20 |
| N2 | `src/velch/agent/errors.py` | `ErrorCode` 闭集 + `AgentError` + 领域异常映射表 | 120 |
| N3 | `src/velch/agent/envelope.py` | 统一信封、`ok()/fail()` 构造、`limits` 装配 | 80 |
| N4 | `src/velch/agent/policy.py` | `Policy` 数据类、`load_policy()`、scope 集合、envelope 收窄、预算账本、路径监狱 | 220 |
| N5 | `src/velch/agent/units.py` | 闭集单位换算 `to_si()` | 70 |
| N6 | `src/velch/agent/schema.py` | JSON Schema 子集校验器（type/required/enum/const/min/max/items/oneOf/additionalProperties） | 200 |
| N7 | `src/velch/agent/manifest.py` | `ToolSpec` + `TOOLS`（20 项）+ `manifest_json()` + 参数 schema 生成器 | 600 |
| N8 | `src/velch/agent/revisions.py` | 账本追加、哈希链、`verify_ledger()`、内容寻址快照 | 180 |
| N9 | `src/velch/agent/cases.py` | `derive_case` / `validate_case` / `diff_cases` / `read_case` / `case.params` | 380 |
| N10 | `src/velch/agent/cost.py` | `predict_wall_s`、`idempotency_key`、磁盘估算、路由决策 | 110 |
| N11 | `src/velch/agent/jobs.py` | job store、状态机、原子写、并发信号量、watchdog | 340 |
| N12 | `src/velch/agent/worker.py` | `python -m velch.agent.worker <job_id>` 子进程入口 | 140 |
| N13 | `src/velch/agent/results.py` | `result.read/series/assess/compare/observations` 处理器 | 320 |
| N14 | `src/velch/agent/inverse.py` | `inverse.estimate`（`CaseSpec` + `gauss_newton`）、`identifiability` | 260 |
| N15 | `src/velch/agent/dispatch.py` | `dispatch(tool, args, ctx)`: schema 校验 → scope → handler → 信封 | 150 |
| N16 | `src/velch/agent/server_mcp.py` | JSON-RPC stdio、`tools/list`、`tools/call`、`resources/*` | 220 |
| N17 | `docs/AGENT_TOOL_CONTRACT_2026-10-22.md` | `velch agent docs` 生成的人读契约快照（含 §1.4-1.9 全表 + 错误码） | 生成物 |

（表里 17 行；其中 N17 是**生成物**——由 `velch agent docs` 从 manifest 导出，给人和 LLM 读；
本文 `docs/AGENT_TOOL_LAYER_2026-10-22.md` 是**设计文档**，两者不是同一个文件，不要互相覆盖。）

### 5.2 修改（3 处，全部是"接线"，不是改行为）

| # | 文件 | 改动 | 风险 |
|---|---|---|---|
| M1 | `src/velch/cli.py` | 加 `agent` 子命令（`manifest` / `schema` / `call` / `doctor` / `docs`），≈30 行，沿用现有 `try/except` 出口 | 零：不动现有 8 个子命令 |
| M2 | `pyproject.toml` | `[project.scripts]` 加 `velch-mcp = "velch.agent.server_mcp:main"` | 零 |
| M3 | `tests/test_architecture_rules.py` | 加 3 条规则（见 §5.3） | 零 |
| M4 | `src/velch/vehicle_solver.py` *（可选，Phase C 后）* | `simulate_vehicle(..., progress_callback=None)`；默认 None 时零行为变化 | 有：闸门必须是冻结基线 `history.csv` 逐字节相等 |
| M5 | `src/velch/params.py` *（可选，Phase D）* | 把 `ui/parameters.py` 的纯数据部分搬成叶子模块，`ui.parameters` 转 re-export | 有：需要一条"re-export 后 `REGISTRY` 逐项相等"的测试 |

**不建议改的**：`model.py`、`vehicle.py`、`io/**`、`metrics.py`、`save_vehicle_result`、
`manifest.json` / `history.csv` 的字段与格式。AI 层的全部溯源都在旁挂文件里。

### 5.3 必须新增的三条架构规则（`tests/test_architecture_rules.py`）

```python
def test_agent_never_imports_solver_internals() -> None:
    # agent 只许 import：vehicle.load_vehicle_case / vehicle_solver.simulate_vehicle /
    # vehicle_solver.save_vehicle_result / solver.simulate / solver.save_result /
    # metrics.assess_history / ui.parameters / ui.store / parallel.run_vehicle_batch /
    # io.history / io.measured / case.spec / inverse.*
    # 禁止：jacobian / contact* / track_models / profiles / surrogate / vehicle_solver._私名

def test_presentation_does_not_import_agent() -> None:
    # ui/** 与 gui.py 不得 import velch.agent（否则 agent↔ui 立即成环）

def test_agent_does_not_reach_the_solver_at_import_time() -> None:
    # import velch.agent 不得触发 numpy/scipy 重活或读盘（headless import 预算 < 50 ms）
```

第一条尤其重要：`docs/ARCHITECTURE_2026-10-21.md` §2.2 已经点名
`contact.py` 与 `vehicle_solver.py` 是上帝模块；Agent 层如果伸手进去，
它就会变成第二个上帝，且以后每个重构都得同时改两处。

### 5.4 分阶段（每阶段自带验收门）

| 阶段 | 内容 | 门（可机检） |
|---|---|---|
| **A. 只读**（1–2 天） | N2–N3, N5–N8, N15 + `capabilities/doctor/case.list/read/validate/params/diff` + `result.*` | 20 个真实算例全部 `case.read` 成功；`manifest.json` 金文件稳定 |
| **B. 写入**（1–2 天） | N9 + `case.derive` / `case.revisions` / `case.revert` | §2.4 的 F1–F18 逐条断言错误码；50 次派生后 `verify_ledger()==True`；`revert` 字节复现 |
| **C. 长任务**（2–3 天） | N10–N12 + `run.*` | 851 s 的整程必须进后台；kill -9 worker 后状态为 `failed` 且有 manifest 时为 `succeeded`/`gate_failed`，**无第三种可能** |
| **D. 反演**（2 天） | N14 | 每次迭代一个 job；`gate_failed` 的迭代不参与 estimate；总墙钟 ≤ 账本预算 |
| **E. 对外**（1 天） | N16 + N17 + M1/M2 | `initialize`/`tools/list`/`tools/call` 三个方法在真实 MCP 客户端下走通；`tools/call` 的错误以 `isError=true` + 结构化 JSON 呈现 |

### 5.5 验收的"硬数字"

- **A 门**：`import velch.agent` < 50 ms；`case.read` 单个算例 < 100 ms；`capabilities` 输出 < 8 KiB。
- **B 门**：`apply_patch` 拒绝率 100 %（F1–F18）；派生文件与父文件字节差异**只**出现在被 patch 的叶子 +
  `case_id` / `purpose_detail`（`case/spec.py:136-141` 的既有约定）。
- **C 门**：`predict_wall_s` 与实测偏差在 [0.6, 1.7] 区间内的比例 ≥ 90 %；幂等命中后 `reused=true` 且 wall ≈ 0.01 s。
- **E 门**：`velch agent docs` 的产物在 CI 里 `git diff --exit-code` 通过（契约漂移即失败）。

---

## 6. 现有代码在自动化下最容易崩的三个点

### ① 算例生命周期与"保存时二次哈希"互相咬住 —— 长任务在最后一秒全丢

`save_vehicle_result` 在**写完 history.csv 之后、写 manifest 之前**重新读
`case.source_path` 和每一个 `asset_hashes` 路径重新算哈希（`vehicle_solver.py:771-778`）：

```python
data = case.source_path.read_bytes()
if hashlib.sha256(data).hexdigest() != case.case_sha256:
    raise SimulationFailure("v2 case changed during simulation")
for path, digest in case.asset_hashes.items():
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
        raise SimulationFailure(f"v2 profile changed during simulation: {path}")
```

这个设计本身是对的（防"跑的时候算例被改"），但它对自动化有两个致命耦合：

1. **agent 的"改参数→重跑"若落在同一路径上，850 s 的整程会在最后一步抛错**，且抛出时
   `history.csv` 已经写完、`manifest.json` 还没写 → 目录里躺着一份**没有 manifest 的 history.csv**。
   自动化如果不做 §1.7 的 manifest 先验，就会把这份残次品当成结果。
2. 更隐蔽的一条：`CaseSpec.resolve()`（`case/spec.py:143-158`）把补丁算例写进
   `tempfile.TemporaryDirectory(prefix="velch_case_")`，`load_vehicle_case` 后**目录随 with 退出而删除**。
   于是 `VehicleCase.source_path` 指向一个已删除的文件。**任何用 `spec.resolve()` 得到的 case 直接交给
   `save_vehicle_result` 都会 `FileNotFoundError`**——而反演（`inverse.estimate`）每一轮都要 `resolve()`。
   这不是 bug，是"临时目录生命周期没覆盖到保存阶段"，但自动化一定会踩。

**对策（写进 N9/N12 的硬约定）**：`derive_case` 与 worker 一律先把算例落进
`jobs/<job_id>/case.json`（`_absolutise_assets` 之后），**从 job 自己的目录加载**，
再交给 `simulate_vehicle` / `save_vehicle_result`。任何情况下不允许"跨临时目录边界缓存 case"。
并且：无 manifest ⇒ 无结果。

### ② 通配 `[]` 的静默爆炸半径 —— A/B 对比会莫名其妙失效

`apply_patch` 的 `_assign`（`parameters.py:302-322`）遇到 `[]` 时**改所有列表元素并直接 return**：

```python
if wildcard:
    for element in node:
        _assign(element, tokens[index + 1:], value)
    return                       # ← 没有 "改了几个" 的回报
```

后果在自动化下被放大：

- `track_dynamics.layers[].k_z_n_m` → **同时**改道床所有层（`layers` 是 list）；
- `rail_templates[].support.k_z_n_m` → **同时**改所有钢轨模板的扣件刚度；
- `rail_templates[].bodies[].s_lo_m` / `s_hi_m` → 二维通配，改所有模板的所有轨体。

Agent 说"把第二层道床软化 20 %"时**无法表达**（没有索引语法），说"软化道床"时会静默改 N 层，
于是"改前/改后"两个算例的差异远超调用者的意图，而 `apply_patch` 的返回值里**没有任何痕迹**。
`editable()` 对多值路径返回 list（`:226`），`case/spec.py` 走的是另一套 `path` 元组（能索引），
两套寻址能力不一致——这也是自动化最容易"用错一套"的地方。

**对策**：§2.4 的 F8/F9（通配必须显式 `allow_wildcard`）、`affected` 逐叶展开、
`case.diff` 的 `max_leaves` 截断标记。中期再加 `layers[1].k_z_n_m` 这样的索引寻址。

### ③ 双算例 schema 与 exit code 2 的三义性 —— agent 没法可靠分支

`cli.py` 有两个并行的算例世界：v1（`model.load_case` → `solver.simulate` → `solver.save_result`，
子命令 `run`，`cli.py:137-142`）和 v2（`vehicle.load_vehicle_case` → `vehicle_solver.simulate_vehicle` →
`vehicle_solver.save_vehicle_result`，子命令 `run-vehicle`，`cli.py:124-130`）。
同一个 CLI 还把所有失败压成一个退出码（`cli.py:143-147`）：

```python
except (OSError, ValueError, TypeError, KeyError, SimulationFailure,
        ContactNativeUnavailable, AssessmentError) as exc:
    print(json.dumps({"status": "failed", "error_type": ..., "message": ...}), file=sys.stderr)
    return 2
```

于是 exit code `2` 同时表示：**入参错**（`ValueError`）、**算例不合法**、**数值门未过**
（`run-vehicle` 里 `result_status != "numerically_checked"` 也返回 2，`cli.py:130`）、
**环境缺 DLL**（`ContactNativeUnavailable`）。自动化拿到 2 只能去正则匹配 message，
而 message 是给人看的自由文本。再加两条：

- `physics_validation_status` 只存在于 v2 的 summary（`vehicle_solver.py:745`），v1 没有；
- `ui/store.py:319 run_info` / `:582 assess` 靠读 `history.csv` 头工作，不区分 v1/v2，
  **能读**两份结果但**语义不同**——agent 很容易把一份 v1 退化工况当成 v2 整车结果来比。

**对策**：`case.validate` 返回 `entry_point`（§1.5），`result.read` 返回 `schema_family`，
工具返回结构化 `error.code` 而**不依赖退出码**（退出码只留给 shell 和 CI）。

### 另外三条 honorable mention（同样会在自动化下炸，但优先级低一档）

1. **`parallel._solve_case` 吞掉所有异常**（`parallel.py:27-31`，`except Exception`），
   批处理报告的 `cases[i].result_status="failed"` 里可能既没有 `manifest` 也没有 `history`，
   而 `traceback` 只有 3 层。Agent 很容易把"失败"读成"跑完了但门没过"。
   → `run.submit(mode="batch")` 必须把 `failed` 与 `gate_failed` 分开，并把 stderr 全量落 `worker.log`。
2. **`manifest["case_snapshot"]` 是绝对路径**（`vehicle_solver.py:805`），
   跨机器/跨容器搬运一份结果后该字段失效；`result.read` 不能用它定位快照，要用 `out/case_snapshot.json` 相对定位。
3. **`history.csv` 的列集是动态的**（`vehicle_solver.py:779-788`：随 `rails` 数量与 `track_kind` 变化），
   `state_order` 只在 `manifest.json` 里。硬编码 `axle1_y_m` 之类的列名的自动化在换算例时会静默取到空列。
   → `result.series` 的列白名单**必须从 manifest 现读**，不在白名单就拒绝（§1.7）。

---

## 7. 与既有规范的衔接

| 既有约束 | 本文如何遵守 |
|---|---|
| 依赖只有 numpy/scipy（`pyproject.toml:10`） | Agent 层零新增依赖：JSON-RPC/JSON Schema 子集/文件锁全部 stdlib |
| `tests/test_architecture_rules.py` 16 条规则 | 只增 3 条（§5.3），不改既有；agent 只碰"稳定接口清单"（ARCHITECTURE §4.2） |
| 冻结基线 `history.csv` 逐字节不变 | AI 层不碰求解器与产物格式；唯一可选触碰（M4 `progress_callback`）以"字节相等"为闸门 |
| "未对实测/Simpack 验证"的诚实口径 | 作为返回值字段 `physics_validation_status` 强制透出（G7），而非依赖 prompt 自觉 |
| `apply_patch` 是唯一写入者（`parameters.py:15-16`） | 继续是唯一写入者；agent 在它**外面**加"注册表 + policy + 审计"，不新建第二条写路径 |
| `CaseSpec` 是反演的唯一入口（`case/spec.py:1-14`） | `inverse.estimate` 只用 `CaseSpec`，并且把 `resolve()` 的临时目录问题在 job 目录里解决（§6.①） |
| 850 s → ≤300 s（M1）→ ≤120 s（M3）的路线（ARCHITECTURE §5.1） | 执行模型按 850 s 设计（后台 + 预算 + 幂等），并用 `solver_patch` 让 agent 能自己打开隐式求解（101.6 s 那条路径），把这个性能缺口变成可操作的旋钮 |
