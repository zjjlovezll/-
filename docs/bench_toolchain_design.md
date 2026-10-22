# Velch 性能基准与剖析工具链（v1 最小可用设计）

**结论**：新增 `velch bench`（6 子命令）+ `src/velch/bench.py`（约 460 行）+ `benchmarks/baselines/<env-digest>.json` 基线库。分项剖析靠"调用站点打补丁 + 上下文计时器"，`contact*.py` / `vehicle_solver.py` 零改动；CI 用 5 条**相对基线**门，噪声用"多批中位数 + 环境指纹一致 + 变异系数否决"抑制。

## 1. 命令设计

```
python -X utf8 -m velch bench <sub> [opts]        # 复用 cli.main 的 sub.add_parser，退出码同族

# 全局选项（每个 sub 都挂）
--case PATH           车辆工况 JSON（rhs / wall / scale --repeat-case 必填）
--json-out PATH       写 JSON 报告（默认打印到 stdout；原子写 tmp→os.replace）
--baseline PATH       显式基线（默认按 env.digest 在 benchmarks/baselines/ 下查）
--repeat N            整轮重复次数，取中位数（默认 5）
--warmup N            预热调用数（默认 3）
--pin-cpu / --no-pin-cpu   绑单核（默认 on，Windows 用 SetProcessAffinityMask）
--quiet               只打印一行 pass/fail

bench rhs       --repeats N（0=自动，单批≥50ms）  --stages geometry,profile,force,all（默认 all）
                --detail summary|per-call          --profile none|cprofile --profile-out X.prof
bench wall      --case C | --from-run DIR          --workers N（接触线程，默认 1）
                --t-end S --method RK45 --rtol F --atol F
bench scale     --cases A.json B.json ... | --repeat-case C --count N
                --executors processes,threads（默认两者）  --workers 1,2,4,8,16,20（截到 logical-1）
bench backends  --backends numpy,numba,torch-cpu,torch-gpu（默认全试）  --stages contact
bench gate      --case C [--baseline ...] [--allow-fingerprint-mismatch]   # 跑 rhs+wall+scale 后判定
bench baseline  --case C --write --reason "..."     # 重采样基线，写 index.json + CHANGELOG
```

退出码：`0` 通过；`1` 阈值回归（仅 `--gate` / `bench gate`）；`2` 用法/环境/加载错误（与现有 `cli.main` 的 2 一致）；`3` 跳过（基线缺失、指纹不匹配、噪声否决、后端全不可用）；`4` 平台不支持（非 Windows 的 pin-cpu）。

`--from-run DIR` 只读 `manifest.json`：**必须 `json.load`**。PowerShell 无 heredoc，且 `ConvertFrom-Json` 会因反斜杠转义抛 `ArgumentException`，文档与脚本一律给单行 `pwsh` 或 Python 片段。

## 2. JSON schema（`schema: "velch-bench-v1"`，unit 见注释）

```jsonc
{
  "schema": "velch-bench-v1",                        // ★ str
  "meta": {                                          // 不进 diff 的易变段，全部集中在 meta
    "generated_at": "2026-10-21T18:35:36+08:00",     // ISO8601
    "tool_version": "0.4.0", "argv": ["bench","rhs"], "host_label": "DESKTOP-X",
    "duration_s": 12.4, "exit_reason": "all_gates_pass"
  },
  "env": {                                           // ★ 环境指纹，与 git 无关
    "cpu_model": "AMD Ryzen 9 5900X 12-Core Processor",  // ★ str，winreg ProcessorNameString
    "cpu_logical": 20, "cpu_physical": 12,             // ★ int / int|null
    "ram_gib": 63.9,                                   // GiB
    "os": "Windows-10-10.0.19045-SP0",                 // ★ str，platform.platform()
    "python": "3.11.9", "numpy": "1.26.4", "scipy": "1.11.4",   // ★ numpy/scipy 必填
    "torch": "2.5.1+cpu" /*|null*/, "torch_cuda": false, "cuda_version": null,
    "gpu_present": false,                              // ★ bool（torch.cuda.is_available()）
    "gpu_name": null, "numba": "0.59.1", "blas_threads": 1,
    "timer_resolution_ns": 100,
    "digest": "3f9a2c7d1b40"                           // ★ str，^[0-9a-f]{12}$，指纹哈希
  },
  "case": {                                          // ★ path/case_id/case_sha256 必填
    "path": "validation/crh380a_m/case_x.json", "case_id": "crh380a_m", 
    "case_sha256": "…64hex", "asset_sha256": {"profiles/…": "…64hex"},
    "t_end_s": 0.05, "x_start_m": 60.0, "contact_workers": 1
  },
  "config": { "repeats": 200, "warmup": 3, "repeats_outer": 5, "pinned_cpu": true,
              "stages": ["geometry","profile","force"], "executors": ["processes","threads"],
              "workers": [1,2,4,8,16,20], "method": "RK45" },
  "measurements": {
    "rhs": {                                          // 微基准
      "us_per_call": {"p50": 1186.4, "p90": 1240.0, "min": 1170.2, "mad_rel": 0.011}, // us / 无量纲
      "calls_per_rhs": {"geometry": 4.0, "profile": 4.0, "force": 4.0},               // count/RHS
      "stages": {
        "geometry": {"us_per_rhs": 864.9, "us_per_call": 216.2, "calls_per_rhs": 4.0, "share": 0.729}, // us, 无量纲
        "profile":  {"us_per_rhs": 41.5,  "us_per_call": 10.4,  "calls_per_rhs": 4.0, "share": 0.035},
        "force":    {"us_per_rhs": 178.0, "us_per_call": 44.5,  "calls_per_rhs": 4.0, "share": 0.150},
        "other":    {"us_per_rhs": 102.0, "share": 0.086}                              // 残差项
      },
      "penetration_um": {"min": 12.5, "max": 480.3}     // um，用于确认跑在真实接触态
    },
    "wall": {"wall_s": 43.9, "nfev": 21233, "us_per_nfev": 2067.5,   // s / count / us（含装配开销）
             "summed_wall_s": null, "result_status": "numerically_checked"},
    "scale": {"points": [
      {"executor": "processes", "workers": 1, "wall_s": 351.2, "speedup": 1.0,   "efficiency": 1.0},
      {"executor": "processes", "workers": 8, "wall_s": 40.9,  "speedup": 8.58,  "efficiency": 1.072},
      {"executor": "threads",   "workers": 8, "wall_s": 330.0, "speedup": 1.06,  "efficiency": 0.133}
    ], "note": "speedup = wall_s(workers=1)/wall_s(N)；efficiency = speedup/N"},
    "backends": [
      {"name": "numpy", "status": "ok", "reason": null, "us_per_call": 216.2,
       "speedup_vs_numpy": 1.0, "agreement": {"max_abs_penetration_m": 0.0, "max_rel_normal_force": 0.0}},
      {"name": "torch-gpu", "status": "skipped", "reason": "torch.cuda.is_available() == false",
       "us_per_call": null, "speedup_vs_numpy": null, "agreement": null}
    ]
  },
  "gate": {"status": "pass", "exit_code": 0, "baseline_path": "benchmarks/baselines/3f9a2c7d1b40.json",
           "baseline_digest": "3f9a2c7d1b40", "items": [
             {"id": "rhs.us_per_call.p50", "unit": "us", "observed": 1186.4, "baseline": 1192.0,
              "ratio": 0.995, "limit": 1.10, "pass": true, "severity": "block"}]}
}
```

Diff 契约：`json.dumps(..., sort_keys=True, ensure_ascii=False, indent=2)`；所有浮点经 `_r()`（6 位有效数字）；键集恒等，无值写 `null` 不省略；路径/时间戳**只**出现在 `meta`/`case`，因此 `python -c "import json,sys;a,b=[json.load(open(f)) for f in sys.argv[1:]];[print(k,'<-',a['measurements'][k]==b['measurements'][k]) for k in a['measurements']]" a.json b.json` 即可判同。

## 3. CI 回归门（5 条）

| # | 指标（JSON 路径） | 阈值 | 拦什么 |
|---|---|---|---|
| G1 | `rhs.us_per_call.p50` | ≤ 基线×1.10 | RHS 总体变慢 |
| G2 | `rhs.stages.geometry.us_per_rhs` | ≤ 基线×1.10 | 占 72.9% 的接触几何退化 |
| G3 | `wall.us_per_nfev`（=wall_s/nfev） | ≤ 基线×1.10 | 单次求解成本（消掉 nfev 漂移） |
| G4 | `wall.nfev` | 0.98 ≤ ratio ≤ 1.02 | rtol/atol、几何策略被悄悄改动 |
| G5 | `scale.points[processes@8].speedup` | ≥ 基线×0.90 | 并行路径（pickle/共享态）回归 |

**防噪声**：①每批 `max(200, ceil(50ms/t))` 次，共 7 批，取**批均值的 p50**，同时报 `mad_rel`；②`--repeat 5` 外层再取中位数；③`mad_rel > 0.05` → `status:"noisy"`、退出 3，**不判失败**；④只在 `env.digest` 完全一致时判定，否则退出 3 并提示重建基线（`--allow-fingerprint-mismatch` 可强制）；⑤G5 用 `--repeat-case --count 16` 的小工况群，避免整工况 44 s×6 点；⑥预热 3 次并丢弃首次（缓存/页错误）。

**基线位置**：`Velch/benchmarks/baselines/<digest12>.json`（内容=完整 report 剪掉 `meta`），配 `benchmarks/baselines/index.json`（digest → host_label/created_at/tool_version）与 `benchmarks/CHANGELOG.md`。**更新**：仅在有意提速后 `bench baseline --write --reason "…"`；工具先连测 3 轮，`mad_rel ≤ 0.03` 才允许落盘；提交时 `git diff` 必须只改 metrics 行，reviewer 看 diff 即审。

## 4. 剖析钩子（物理代码零改动）

```python
# src/velch/bench.py
@contextlib.contextmanager
def stage(name: str) -> Iterator[None]:
    """累加一个阶段的一次调用耗时与次数（perf_counter_ns，空转失败也记账）。"""

@contextlib.contextmanager
def instrumentation(sites: Mapping[str, tuple[object, str]] | None = None) -> Iterator["ProfileReport"]:
    """按调用站点给函数打补丁，退出时在 finally 复原并断言复原成功。"""

DEFAULT_SITES = {                      # key -> (module, attr)  ★ 必须是「调用方命名空间」
    "geometry": (vehicle_solver, "find_graph_contact"),   # vehicle_solver.py:305 调用；patch velch.contact 无效
    "force":    (vehicle_solver, "evaluate_contact"),     # vehicle_solver.py:353
    "profile":  (profiles.ProfileSeries, "sample"),       # 类方法，vehicle_solver.py:300 与 :604 两处调用
}
```
理由：`vehicle_solver.py:21` 是 `from .contact import find_graph_contact, ...`，名字已绑定进 `vehicle_solver` 命名空间；这层"补丁打在 import 目标模块上"的坑已由 `validation/crh380a_m/profile_rhs_parts.py` 验证过，v1 直接固化为 `DEFAULT_SITES`。

其余接口：

```python
def measure_rhs(case: VehicleCase, *, repeats: int = 0, stages: Sequence[str] = ("geometry","profile","force"),
                settle: bool = True) -> dict:        # 冻结态 = initial_q/initial_v（可选 _static_vertical_equilibrium）
    """单次 RHS 微基准：返回 us_per_call + 分项 + other 残差（架构同 rhs["measurements"]）。"""

def collect_gates(report: dict, baseline: dict) -> list[dict]:  """按 5 条规则生成 gate.items。"""
def environment_fingerprint() -> dict:                  """CPU 型号/逻辑核/torch/numpy/GPU + digest。"""
def main(argv: list[str] | None = None) -> int:         """bench 子命令入口，返回退出码。"""
```
残差 `other = total − Σstages`；**若 `other < 0` 判定重复计时**（`find_graph_contact` 的入参已是 `ProfileSample`，正常无嵌套），报告 `status:"instrumentation_error"`。开销实测约 9–12×2 次 `perf_counter_ns ≈ 2 µs / 1190 µs = 0.17%`，在 G2 的 10% 门内可忽略。

## 5. `src/velch/bench.py` 骨架（约 460 行）

```python
"""Reproducible benchmarks and stage attribution for the Velch RHS."""   # 模块 docstring
SCHEMA = "velch-bench-v1"                                    # 2 行
class BenchError(RuntimeError): ...                          # 2
def _r(x: float | None, digits: int = 6) -> float | None      # 6   """按有效位数取整，保证可 diff。"""
def environment_fingerprint() -> dict                         # 45  """采集 CPU/核数/Python/numpy/scipy/torch/numba/GPU。"""
def _cpu_model() -> str                                       # 15  """winreg 读 ProcessorNameString，非 Windows 退化 platform.processor()。"""
def fingerprint_digest(env: dict) -> str                      # 8   """对 env 排序后 sha256，取前 12 位。"""
def load_bench_case(path: Path) -> tuple[VehicleCase, dict]   # 15  """load_vehicle_case + case_sha256/asset_sha256 快照。"""
def freeze_state(case: VehicleCase, dynamics) -> tuple[float, np.ndarray, np.ndarray]  # 20
def stage(name: str) -> Iterator[None]                        # 12  """累加一个阶段的一次调用耗时与次数。"""
def instrumentation(sites=None) -> Iterator[ProfileReport]    # 30  """打补丁计时，finally 复原。"""
def measure_rhs(case, *, repeats=0, stages=(...), settle=True) -> dict   # 55
def measure_wall(case, *, workers=1, overrides=None) -> dict   # 40  """simulate_vehicle 墙钟 + nfev + us_per_nfev。"""
def measure_scale(cases, *, executors=("processes","threads"), workers=(...)) -> dict  # 55
def compare_backends(case, *, backends=(...)) -> list[dict]    # 55  """numpy/numba/torch-cpu/torch-gpu 接触阶段对比，缺库 skipped。"""
def load_baseline(path: Path) -> dict                          # 10  """json.load 基线（绝不用 ConvertFrom-Json）。"""
def write_baseline(report: dict, *, reason: str) -> Path        # 25  """3 轮 mad_rel≤0.03 才落盘，更新 index.json/CHANGELOG。"""
def collect_gates(report: dict, baseline: dict) -> list[dict]   # 30
def render_text(report: dict) -> str                            # 25  """人读表格：stage/share/us。"""
def main(argv: list[str] | None = None) -> int                  # 70
```

`tests/test_bench_smoke.py`（目标 <20 s，重活 `@pytest.mark.slow`）应断：
1. `environment_fingerprint()` 必填键齐全且非空、`digest` 两次调用一致；篡改 `cpu_logical` 后 digest 变化。
2. `instrumentation()` 正常与抛异常两条路径都复原：`vehicle_solver.find_graph_contact is original`（身份比较）。
3. 真实小工况 `measure_rhs(repeats=50)`：`p50 > 0`；四个 stage 键齐；`Σshare ≤ 1.05`；`geometry.share > 0.25`（72.9% 的宽松下限，防"打错补丁但没报错"）；`other ≥ 0`。
4. `main(["bench","rhs",...])` 退出 0，`--json-out` 落盘可 `json.load`，`schema == "velch-bench-v1"`，`env`/`measurements` 键集与预期相等（snapshot 比对）；连跑两次剥掉 `meta` 后 `measurements` 逐键相等。
5. `collect_gates`：ratio 1.05 → pass；1.11 → fail；基线缺失 → `status:"skipped"` 且 `main` 返回 3。
6. `--from-run` 读一个临时 manifest（含反斜杠路径）不抛异常，`wall.nfev` 正确。
7. 每个子命令 `--help` 返回 0；未知子命令返回 2。8. 只写 `--json-out`，tmp 目录文件数不增。

## 6. 旧脚本迁移映射

| 旧脚本（`validation/crh380a_m/`，`Velch/` 根） | 新命令 | 说明 |
|---|---|---|
| `diag_contact_cost.py` | `bench rhs --case C --stages geometry --detail per-call --repeats 30` | 每 patch 一次几何成本 + strip 数 |
| `profile_rhs_parts.py` | `bench rhs --case C --repeats 200` | **成为唯一实现**；补丁站点固化为 `DEFAULT_SITES` |
| `diag_cprofile_rhs.py` | `bench rhs --profile cprofile --profile-out rhs.prof` | 函数内热点，与墙钟分项互补 |
| `bench_contact_parts.py` | `bench rhs --stages geometry --detail per-call` | 几何内部阶段（P2 加 `--breakdown contact`） |
| `bench_compute.py` | `bench rhs --case C` | 单次调用 µs |
| `bench_profile_run.py` | `bench rhs --stages profile,geometry` | 真实运行内占比 |
| `bench_settings.py` | `bench wall --case C --t-end 0.05 --rtol … --atol …` | 设置扫描（P2 加 `--sweep`） |
| `report_wall.py` / `show_wall.py` | `bench wall --from-run DIR` | 改 `json.load`，根治 `ConvertFrom-Json` |
| `diag_par_check.py`（根） | `bench scale --executors processes,threads --workers 1,2,4,8` | 8.58× 与线程池更慢同框对比 |
| `bench_geometry_policy.py` / `bench_cached_grid.py` | P2 `bench policy`（v1 先用 `bench rhs --case` 定性） | 策略+精度双指标，暂不进 CI |
| `cmp_modal_spectra.py` / `probe_speed_scaling.py` | **保留** | 物理/频谱对比，非性能口径 |

## 7. 落地顺序与验收

P0（0.5 d）`bench.py` 骨架 + `environment_fingerprint` + `stage/instrumentation` → P1（0.5 d）`rhs` + `wall` → P2（1 d）`scale` + `backends` → P3（0.5 d）`collect_gates` + 基线库 + `--from-run` → P4（0.5 d）迁移 5 个脚本、`tests/test_bench_smoke.py` 进 CI。

验收：①`pytest tests/test_bench_smoke.py -q` <20 s 通过；②同机连跑两次 `bench rhs --json-out` 剥 `meta` 后逐键相等；③注入 20% 人为放缓后 `bench gate` 退出 1 并指出 G1/G2；④`bench backends` 在无 numba/torch 环境下四项 `status:"skipped"`、退出 3 而非崩溃；⑤`contact*.py`、`vehicle_solver.py`、`parallel.py` 的 `git diff` 为空。
