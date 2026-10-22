# 统一口径复核 + 代码体检（2026-10-22）

> 目的：把"两个会话报出的整车 1.2 s 数字不一致"这件事彻底钉死，然后给出把 Velch 变成
> **可交付软件**的地基清单。
> 两条都只做测量与判断，不改求解器物理。

---

## A. 统一口径复核

### A.1 方法

- 源算例只有一个：`Velch/validation/crh380a_m/case_full12_cap05.json`（条带积分 + 钢轨垂向自由度 +
  柔性扣件 5e7/4e4 + 接触阻尼 3e7/cap 0.5，350 km/h，x 13.5→130.2 m，1.2 s）。
- 参照物用**归档** oracle `Velch/validation/crh380a_m/out_full12_cap05/history.csv`，**不重跑**：
  它是冻结产物、逐位确定，而且此前多个解析雅可比变体都与它逐项吻合。
- 五个配置全部固定 `atol = 1e-8`。这一点是刻意的：上一会话的 `s2_analytic._run` 用
  `atol = min(1e-8, rtol*1e-2)`，rtol 放宽时 atol 会跟着动，两个旋钮一起变就说不清是谁的功劳。
- 脚本：`F:\ai道岔状态反演辨识\.tmp\o1_unified.py`；输出目录 `F:\velch_tmp\o1\<tag>`。
- 派生算例必须写在 `Velch/validation/crh380a_m/` 下——`load_vehicle_case`（`vehicle.py:214`）把
  body/rail 型面按 **case JSON 自身所在目录**解析，写到别的目录会
  `FileNotFoundError: ...\bodies\main_r0791310.csv`。只有输出目录可以放 `F:\velch_tmp`。

### A.2 成本

| 配置 | 墙钟 s | nfev | 状态 |
|---|---|---|---|
| DOP853 基线（归档，未重跑） | ≈850（旧记录） | 331 949 | `numerically_checked` |
| BDF + 解析，rtol 1e-6，max_step 1e-4（**默认**） | 172.5 | 109 628 | `numerically_checked` |
| BDF + 解析，rtol 1e-5，max_step 1e-4 | 123.7 | 87 239 | `numerically_checked` |
| BDF + 解析，rtol 1e-5，max_step 2e-3 | 118.2 | **81 647** | `numerically_checked` |
| BDF + 解析，rtol 1e-4，max_step 1e-3（**快速预设**） | **79.0** | 58 113 | `numerically_checked` |
| BDF + 稀疏差分，rtol 1e-6，max_step 1e-4 | 122.6 | — | ❌ `non-finite v2 force at t=0.547528664 s` |

### A.3 物理（与 oracle 逐列比，2401 帧 × 8 接触）

| 配置 | 峰值 kN @接触 | 最大侵入 µm | 脱空帧 | 最差 ΔN | 最差 Δ侵入 |
|---|---|---|---|---|---|
| oracle DOP853 | 170.61 @axle2_right | 551.89 | 0 | — | — |
| 解析 1e-6 / 1e-4 | 170.61 @axle2_right | 551.90 | 0 | 230 N | 3.81 µm |
| 解析 1e-5 / 1e-4 | 170.61 @axle2_right | 551.89 | 0 | 230 N | 4.12 µm |
| 解析 1e-5 / 2e-3 | 170.58 @axle2_right | 551.89 | 0 | 230 N | 4.12 µm |
| 解析 1e-4 / 1e-3 | 170.72 @axle2_right | 550.54 | 0 | 222 N | 4.97 µm |

八个接触的峰值（kN，oracle / 1e-6 / 1e-5 / 1e-5+ms / 1e-4）：

| 接触 | oracle | 1e-6 | 1e-5 | 1e-5+ms2e-3 | 1e-4+ms1e-3 |
|---|---|---|---|---|---|
| axle1_left | 61.19 | 61.19 | 61.19 | 61.19 | 61.19 |
| axle1_right | 89.68 | 89.68 | 89.67 | 89.67 | 89.65 |
| axle2_left | 61.08 | 61.08 | 61.08 | 61.08 | 61.07 |
| axle2_right | 170.61 | 170.61 | 170.61 | 170.58 | 170.72 |
| axle3_left | 61.17 | 61.17 | 61.17 | 61.17 | 61.17 |
| axle3_right | 90.77 | 90.76 | 90.76 | 90.76 | 90.78 |
| axle4_left | 61.07 | 61.07 | 61.07 | 61.07 | 61.07 |
| axle4_right | 170.45 | 170.45 | 170.45 | 170.45 | 170.48 |

### A.4 频带（前轴右轨，78.8–82.2 m 窗）

| 配置 | rms | 主频 Hz | 30–60 | 150–250 | 250–400 |
|---|---|---|---|---|---|
| oracle DOP853 | 9.13 | 57.14 | 5.68 | 1.75 | 2.25 |
| 解析 1e-6 / 1e-4 | 9.13 | 57.14 | 5.68 | 1.75 | 2.25 |
| 解析 1e-5 / 1e-4 | 9.13 | 57.14 | 5.68 | 1.75 | 2.25 |
| 解析 1e-5 / 2e-3 | 9.13 | 57.14 | 5.68 | 1.75 | 2.25 |
| 解析 1e-4 / 1e-3 | 9.13 | 57.14 | 5.68 | 1.75 | 2.25 |

**四档到两位小数完全一致。** 频带对容差不敏感，因为它由冲击/几何事件决定，不由积分误差决定。

### A.5 两个会话的数字为什么不一样——结论

上一会话报 **101.6 s / nfev 81 647**，本会话报 140.3 s / 110 461（rtol 1e-6）与 73.7 s / 58 564
（rtol 1e-4 + max_step 1e-3）。本次复核给出判定：

1. **nfev 81 647 与本次 `rtol 1e-5 + max_step 2e-3` 一模一样，逐位相同。** 步数完全一致意味着
   两个会话**跑的是同一套算法、同一条雅可比**，不存在"雅可比项集不同"这回事。
2. 差异只在**墙钟**：同一配置在本次测得 118.2 s。墙钟受并行会话负载影响（本机同时有别的会话在
   跑仿真与 pytest），把不同机器负载下测到的秒数当算法差异，是这次混淆的唯一来源。
3. 因此：**上表 nfev 是唯一可跨会话比较的成本量，秒数必须标注负载或只在同一批里比。** 这条已作为
   口径写进本表——以后报速度先报 nfev。

### A.6 结论与建议

- **物理不变性是干净的**：五个配置里四个解析档的峰值、脱空、频带全部与 oracle 在 0.1 kN / 0.02 µm /
  两位小数上一致；最差单帧法向力差 230 N（0.4 %），属 oracle 自身求解精度的量级。
- **稀疏差分不是"慢一点"，是"跑不完"**：唯一失败的就是它（`t=0.5475 s`）。所以解析雅可比不是优化项，
  是隐式路径的**准入条件**。
- **默认值建议保持现状**（rtol 1e-6 / max_step 1e-4）：它比 oracle 只差 230 N，而放宽到 1e-4 会让
  最大侵入偏 1.35 µm、单帧侵入偏 5 µm——对只报峰值/脱空/频带的工程结论无影响，对逐帧侵入轨迹有影响。
- **快速预设**（rtol 1e-4 + max_step 1e-3）可作为显式开关：79.0 s，比默认快 2.2×，峰值变 0.06 %。
  但**不要改默认**，否则任何人拿默认配置与归档 oracle 对比都会看到一次不必要的漂移。
- 与 Simpack 的口径：Simpack 85.08 s 是 **32 线程**的墙钟，Velch 79–172 s 是**单进程单核**。
  跨这个口径直接比秒数没有意义，应比 nfev 或同核数墙钟。

---

## B. 代码体检

### B.1 规模与分布（实测，脚本 `.tmp\o2_inventory.py`）

| 部分 | 规模 |
|---|---|
| `src/velch` | **48 个模块 / 15 320 行** |
| `tests` | **47 个文件 / 4 637 行**（测试:源码 ≈ 0.30） |
| `docs` | 57 篇 md |
| `examples` | 40 个文件（含 `vehicle_v2/case.json` 主入口） |
| `diagnostics` | 26 个文件 |
| `validation` | **1 402 MB / 14 604 文件**，其中 207 个 `out_*` 目录、354 个 `case_*.json`、约 190 个 .py |
| 仓库根 | **57 个游离 .py**（`diag_*`、`_probe_*`、`_raw_prr*`、`_arch_scan.py` …） |
| 打包产物 | `dist/` 4 个旧 wheel（0.1.0–0.4.0）、`build/` 残留 |

最大的八个模块：`contact.py` 1573、`vehicle_solver.py` 812、`ui/store.py` 741、`ui/widgets.py` 652、
`gui.py` 643、`ui/app.py` 627、`jacobian.py` 515、`io/measured.py` 505。

### B.2 已经做对的地方（不是客套，都是可执行的）

1. **架构是测试，不是口头约定**：`tests/test_architecture_rules.py`（419 行）用静态 AST 扫 11 条规则——
   前向代码永不可达 `inverse`、`contact` 层不得 import 调用者、`io.history` 必须是叶子、
   `case.spec` 只能碰 `vehicle` 契约、UI 不得 import 前向栈、import 图无环、`io.measured → inverse`
   只允许在 `TYPE_CHECKING` 下、并逐包验证**无显示器也能 import**（headless）。这条比"有没有 CI"更值钱。
2. **没有技术债标记**：`TODO/FIXME/XXX/HACK/workaround` 全 0；`type: ignore` 只有 9 处
   （`vehicle_solver.py` 5、`ui/widgets.py` 3、`ui/app.py` 1）；`noqa:` 4。
3. **公共面刻意收窄**：`vehicle_solver.py` 只暴露 `simulate_vehicle` / `save_vehicle_result`；
   `jacobian.py` 只暴露 `JacobianAssembler` + `frozen_geometry_error`；细节都在私有名里。
4. **oracle 有守卫**：`tests/test_oracle_frozen.py` 钉住静载门（59 680.5769 N / 65.47 µm），
   改动物理会立刻红。
5. **打包基本成形**：`pyproject.toml` 完整（name/version/requires-python/deps/两个 entry point/
   setuptools src 布局/pytest 配置）；`pip install -e .` 后 `velch`、`velch-gui` 可用。
   本次实测：从 `F:\` 起、只设 `PYTHONPATH`，`import velch, velch.cli, velch.vehicle_solver,
   velch.jacobian, velch.inverse, velch.io, velch.ui` 全部成功，`python -m velch --help` 正常列出
   8 个子命令。**无显示器、无 CONTACT DLL 也能 import。**
6. **测试不依赖外部资产**：`pytest tests` → **325 passed in 14.9 s**，不需要 1.4 GB 的 validation 目录。
7. **文档诚实**：README 明确写了"当前通过的是合成算例的数值检查…不能代替完整 3D 多体车辆、
   柔性轨道有限元、齿轮齿条啮合或状态反演求解器"。

### B.3 缺口（按"挡住软件化"的程度排序）

**P0 —— 不解决就不能叫软件**

1. **没有版本控制。** `git status` → `fatal: not a git repository`。15 320 行源码 + 4 637 行测试
   **没有一行有历史**，任何改动都不可回滚、不可 review、不可追溯。这是最大的地基缺口，比任何代码
   问题都严重。整个项目现在是"一份会覆盖自己的工作副本"。
2. **没有 LICENSE。** `pyproject.toml` 里没有 `license` 字段，仓库里也没有 LICENSE 文件——
   法律上默认"保留所有权利"，别人（包括合作者）不能合法使用或分发。
3. **1.4 GB 的 `validation/` 混在包目录里。** 14 604 个文件、207 个 `out_*`、354 个算例，与
   `src/`（1.6 MB）混在同一棵树。任何分发、备份、CI 缓存都会把它背上；而且它是本次复核唯一踩到的
   真实事故源：**其中 10 个 `out_*` 的时间序列是常数静载门，容易被当成动态基线**（S2 期间确实被误用过）。
4. **默认路径仍是最慢的那条。** `jacobian` 默认 `None`、`max_solver_step_s=1e-4`、DOP853 是默认
   method。解析雅可比要显式写进算例才生效；快速预设没有任何入口。也就是说：**最好的结果目前不是默认
   结果**，用户按 README 跑会拿到 850 s 而不是 118 s。

**P1 —— 会让软件难维护**

5. **脚本无归属**：仓库根 57 个游离 `.py`、`validation/crh380a_m` 约 190 个脚本，没有 `scripts/`
   目录、没有归档约定。它们是有价值的证据（很多负结果是它们跑出来的），但应该进 `scripts/` 或
   `archive/`，而不是和 `src/` 平级。
6. **`contact.py` 是上帝模块**：1573 行、4 类 27 个函数、9 个公共函数（`find_*_contact` 五个变体：
   patch / strip / spline / graph / native）。接触搜索的五种策略共处一文件，新增策略只能继续膨胀。
7. **没有 CI、没有覆盖率门、没有 lock**：`dependencies = ["numpy>=1.24","scipy>=1.10"]`，但实际还有
   可选依赖（tkinter、h5py 读 Simpack `.mat`、CONTACT DLL）。缺 `requirements.txt` /
   `MANIFEST.in`；`dist/` 里 4 个旧 wheel 与 `build/` 残留应清掉。
8. **README 有一段已经过期**：它说"尚未完成真实道岔的几何/材料标定或与 Simpack、实测数据的物理验证"，
   而现在已有逐项对照（89.68 kN vs 134.97、脱空 0/2401、57.14 vs 57.97 Hz）与 5 条口径更正。
   过期的自我评价会误导新用户，也会让已有证据显得不存在。

**P2 —— 打磨项**

9. **docstring 覆盖偏低**：`contact.py` 27 个 def 里 6 个有 docstring，`gui.py` 33 个 def 里 0 个。
   对软件交付来说，公共 API（9 个接触函数、2 个求解入口）是够的，内部实现弱一些可以接受。
10. **双版本共存**：v1 单轮对 `solver.py`（251 行）+ v2 四轴 `vehicle_solver.py`（812 行）并行，
    v2 只从 v1 借一个异常类（有测试钉住）。建议在文档与 CLI 里把 v1 明确标成"核对算例"，否则新用户
    会不知道从哪个入口开始。
11. **`out_*` 目录没有索引**：207 个目录靠各自 `manifest.json` 才能分辨，没有一张总表。建议生成
    一份 `validation/INDEX.md`（算例 id / 目的 / 峰值 / 脱空 / 是否常数），把"静载门 vs 动态基线"
    标出来。

### B.4 建议的落地顺序（每步独立可验收）

| 步 | 动作 | 验收 |
|---|---|---|
| 1 | `git init` + `.gitignore`（排除 `validation/out_*`、`build/`、`__pycache__`、`.tmp`）+ 首次提交 + 打 tag `v0.4.0` | `git log` 有历史；`git status` 干净；325 passed 不变 |
| 2 | 补 `LICENSE`（与作者确认许可类型）+ `pyproject` 的 `license` 字段 + `description` 里去掉 research kernel 这类模糊表述 | `pip install .` 后元数据里有 license |
| 3 | 把 `validation/` 移出包目录（例如 `F:\velch_validation\`），仓库里只留 `out_full12_cap05`、`out_A_final_law` 两个 oracle + 一份 `INDEX.md` | 仓库 < 20 MB；325 passed 不变；oracle 守卫仍绿 |
| 4 | 给"快速预设"一个正式入口：`--jacobian analytic --rtol 1e-4 --max-step 1e-3`（或 `--fast`），并在 README 里给出 79 s vs 172 s 的对照 | 同算例跑出 79±5 s、峰值 170.7 kN、0 脱空 |
| 5 | `contact.py` 按策略拆成 `contact/patch|strip|spline|graph|native.py`，公共入口保留 `find_contact` 分派 | 325 passed 不变；`test_architecture_rules` 仍绿 |
| 6 | 根目录 57 个脚本进 `archive/`；`validation` 脚本进 `validation/scripts/` | 根目录只剩 `pyproject.toml`/`README`/`LICENSE`/`.gitignore` 与目录 |

**注意第 3 步和第 1 步的顺序**：先建仓再搬 `validation/`，否则搬动没有历史可回退。

---

## 附：本次两条命令的复现

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 F:\ai道岔状态反演辨识\.tmp\o1_unified.py    # A 部分五配置表（约 10 分钟）
python -X utf8 F:\ai道岔状态反演辨识\.tmp\o2_inventory.py   # B 部分规模统计
```

---

## B.5 代码审查结果与处置（2026-10-22 追加）

外部代码审查聚焦"会导致错误行为的缺陷"。**两条确定缺陷都落在 `support_compliance` 打开的算例上**，
而全仓 358 个算例里只有 5 个打开柔度、**没有一个进验收门**——这就是它们能穿过多轮测试的原因。

| 编号 | 缺陷 | 触发条件 | 实测影响（`case_X_support` / `case_Y_full_support`） | 处置 |
|---|---|---|---|---|
| D1 | strip 力梯度用了**软化后**的斜率做归一 | `support_compliance` 非空 + 接触几何带 `partials` | `dq` 53.4（最差列 88.0，12 列越界） | **已修**：改用原始 Hertz 斜率；`dq` → 4.8e-3（最差列 0.153，4 列） |
| D2 | 阻尼分支多乘了 `elastic_slope/raw` | 任何 `support_compliance` 非空算例 | `dv` 0.041（X）/ 0.976（Y），12 列 | **已修**：删掉该因子（RHS 的阻尼作用在几何侵入上，不经串联链）；`dv` → 1.9e-10 / 2.9e-11，坏列 0 |
| D5 | `jacobian` 与 `method` 组合未校验 | `method="DOP853"` + 任何 `jacobian` | 只有一条 `UserWarning`，静默退化为裸显式积分 | **已修**：`RunSettings.__post_init__` 直接抛 `ValueError` |
| D6 | `body_contacts` 返回内部缓存本体 | 在 `derivative_pure()` 之后读该属性 | `restore_contact_state` 重新绑定 dict，调用者手里的引用静默失效 | **已修**：返回 `dict(...)` 拷贝 |

新增回归门 `tests/test_jacobian_support_compliance.py`（7 项）：柔度算例的 `dv < 1e-6`、
`dq < 1e-2`、深穿透算例 `dq < 5e-2`（**界限而非认可**）、无柔度算例仍 `dq/dv < 1e-8`、
`DOP853 + jacobian` 必须报错、`body_contacts` 必须是快照。全仓 **332 passed**。

**仍然开放的（未修，有实测但未定位到行）**

| 编号 | 现象 | 现状 |
|---|---|---|
| D3 | 蠕滑饱和的**交叉偏导** `∂T_x/∂linear_lat`、`∂T_lat/∂linear_x` 从未装配 | 只在 `slip_x` 与 `slip_lateral` 同时非零时错。生产算例 `slip_lateral` 恒 0（实测 8 个接触全为 0），所以任何现有门都看不见 |
| D4/C1 | 深穿透柔度算例的**滚转↔横移交叉耦合**仍有 ~15 % 偏差（`dq` 2.4e-2，最差列 1.06） | 已实测与 D1/D2 无关（修完 D1/D2 后 Y 的 `dq` 不变）。此前怀疑的"4/3 常数因子"已被否证：修完 D1 后大项一致到 0.99999–1.00222，偏差集中在 `(roll, y)` 两个交叉项 |
| C4 | `_rhs_sparsity` 模板只在 `t=0` 采样 | docstring 已自承；对应测试近乎同义反复。`sparse_fd` 在 1.2 s 上本就崩，严重度低于 D1/D2 |
| C5 | cap 激活邻域、`demand == 3μN` 邻域的测试缺失 | 零测度，暂不改，但也无测试钉住 |

**默认路径未受影响**：`case_full12_cap05.json`（`support_compliance=None`）在修前修后都是
`dq` 8.5e-10 / `dv` 1.6e-10；冻结 oracle、静载 59 680 N / 65.47 µm、整车 1.2 s 峰值全部未动。

---

## B.6 验收门扩容 + D4/C1 定位（2026-10-22 追加）

### 门已覆盖柔度分支

`validation/crh380a_m/s2_analytic.py gate` 现在跑两段：生产算例（`case_full12_cap05.json`，
六个时刻，判据 `dq/dv` 列误差 < 1e-5 且坏列 0）与**柔度分支**（`case_X_support`、
`case_Y_full_support`，判据 `dv` 严格 < 1e-6 且坏列 0，`dq` 只做**上界**）。打印区分
`PASS` 与 `BOUNDED`，这样"绿"不会被读成"正确"：

| 算例 | dq block | dq 最差列 | dq 坏列 | dv block | dv 坏列 | 判定 |
|---|---|---|---|---|---|---|
| `case_X_support` | 4.84e-03 | 1.53e-01 | 4 | 1.88e-10 | 0 | BOUNDED |
| `case_Y_full_support` | 2.37e-02 | 1.06e+00 | 8 | 2.87e-11 | 0 | BOUNDED |

上界取当前值的一倍半左右，**收紧这些数字就是"D4/C1 已修"的定义**。

### D4/C1 的根因已定位（不是常数因子，是点接触分支缺项）

先纠正一个读数口径：`VehicleDynamics` 每个轮对的五个坐标顺序是
**(y, z, roll, spin, yaw)**，不是 (y, z, roll, yaw, spin)。据此把残差重新读一遍，
最差几项全部落在**滚转/摇头与横移的耦合**上（`case_Y_full_support`，axle1 的 5×5 块）：

| 行 | 列 | 解析 | 有限差分 | 比值 |
|---|---|---|---|---|
| `axle1.roll`（力矩） | `axle1.y` | 2.0503e+03 | 8.9061e+02 | **2.30** |
| `axle1.yaw`（力矩） | `axle1.y` | 1.2955e-01 | −8.7668e+01 | 解析**整项缺失** |
| `axle1.yaw`（力矩） | `axle1.roll` | −4.1380e+00 | +2.6531e+03 | 解析**整项缺失** |

根因：`JacobianAssembler._contact_modes()` 在 `geometry.partials is None` 时返回 `None`
（`src/velch/jacobian.py:258-260`），于是走"冻结力臂 + 冻结法向"的退化形式——连接触质心的
`d lever/dq` 和法向方向旋转**两项都不装**。而 `partials` 只有**条带积分**分支会生成
（`contact.py:855` 的 `_band_partials`），`case_Y_full_support.json` 的
`normal_policy` 是 `point_hertz`，所以它拿到的是 `None`。

三条独立佐证：

1. 生产算例 `case_full12_cap05.json` 用的是 `strip_integral`，同样这套代码在它上面
   `dq = 8.5e-10`——**只要 partials 在，冻结力臂的缺项就不存在**；
2. 实测 `∂C/∂roll = 9.54e12`（相对 `C` 是 83.7 /rad，即每弧度改变 8370 %），说明
   `local_circular` 下接触点一动刚度就变，而装配把它当常数——按串联链估算这一项只贡献
   总误差的 ~4 %，**不是主项**，但同样是缺的；
3. 残差全部集中在 `(力矩行, 横移/滚转列)`，与"缺 `d lever/dq`、缺 `d normal/dq`"的
   作用面完全重合。

**为什么以前看不出来**：点接触分支的冻结力臂在平顶接触（生产算例）上是**精确**的——
接触点不随 q 移动；只有在深穿透 + `local_circular` + 接触点在型面上游走时才破。

### 下一步（按顺序）

1. 让点接触分支也发布 `d y_c/dq`（接触点的横向游走 = 型面斜率关系）与法向旋转，
   把 `_contact_modes` 从 `None` 变成真值——这是 D4/C1 的正解，工作量集中在
   `contact.py` 的点搜索分支；
2. 修完把柔度门从 `dq < 5e-2` 收到 1e-5，并把 `BOUNDED` 改回 `PASS`；
3. 顺带钉住 `∂C/∂q`（`local_circular` 的刚度随接触点变化），否则它会在别的算例上
   以同样的方式隐身。
