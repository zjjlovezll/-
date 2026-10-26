# 设计方案：把安装包拷到干净机器就能跑模型（含 33 阶柔性轮对）

状态：Proposed（未改任何代码）
日期：2026-10-26
关联：`docs/PACKAGING_2026-10-22.md`（打包与已知限制）、`docs/FLEXIBLE_WHEELSET_PORT_2026-10-24.md`
（模态集导入）、`docs/SELFCHECK_2026-10-23.md`（自检语义）、`docs/BUGS.md` B014（空态不是错误）

---

## 0. 四个问题的一句话答案

| # | 问题 | 结论 |
|---|---|---|
| ① | 便携模型契约 | 保留「相对路径 = 相对算例文件」为默认（零迁移成本），新增唯一前缀 `lib:` 指向**已有的**车辆库根，四处引用点（profile/`.tre`/`modal_file`/`flexible_wheelset.file`）走同一个解析入口；逃逸分级：`lib:`/`data:` 逃逸硬错，算例相对逃逸只 WARN + 在 manifest 里记 `portable: false` |
| ② | 首次运行体验 | 不把「没语料」升级成 FAIL，而是**填满空态**：内置 `examples/minimal` 算例让界面永不为空；`data_root.hint()` 升级为结构化 `hint_lines()`，每条命令后面紧跟它自己的验收输出（这才是"可照抄"） |
| ③ | 语料进不进包 | 不进。1.4 GB / 358 个算例进包会把 189.9 MB 变成 ~1.6 GB，且包里没有任何一个算例用到 33 阶模态。改为「最小可跑算例集」：**新增 1 个算例 + 复用已有 ~40 KB 的 CSV**，净增 ≈ 0（模态文件 1.85 MB 已在包里） |
| ④ | 干净机器自动验证 | 新增 `packaging/clean_room_test.py`：临时目录副本、**白名单环境变量**（不是继承+删除）、`LOCALAPPDATA` 重定向、断言 `data_root.source == "default"`（防止假 PASS）、跑内置算例断 175 自由度、**再搬一次到带中文和空格的路径后 manifest 必须逐字节相同**、加一条负对照 |

核心判断：这个任务不是"补一个路径"，而是**现在有三套互相独立的根**，任何一套被环境变量或安装位置牵走，就出现"包能开、算例能跑、模型跑不起来"的半可用状态。方案的价值在于把三套根收敛成一套可解释、可断言、可测试的解析契约，而不是增加更多查找顺序。

---

## 1. 现状：三套根，三种失败方式

| 根 | 解析位置 | 查找顺序 | 失败表现 |
|---|---|---|---|
| 算例资产（轮轨型面 CSV、`.tre`、`modal_file`、模态集） | `vehicle.py:305-316`、`:314`、`:403`、`:426`、`:174-206` | 只有一种：`(case_path.resolve().parent / ref).resolve(strict=True)` | 裸 `FileNotFoundError`，只给拼好的绝对路径，不说是包坏了还是算例写错了 |
| 车辆库 `vehicles/` | `vehicle_db.py:105-132 _root()` | `VELCH_VEHICLE_DIR` → `repository_root()/vehicles` → frozen 时 `install/vehicles` 再 `install/_internal/vehicles` | 与算例资产的根**不同**，同一份 `CRH3C_wheelset_fe.json` 有两个可能的绝对路径 |
| 语料 `crh380a_m/case_*.json` | `data_root.py` `data_root()` | `VELCH_DATA_ROOT` → 标记文件 → `repository_root()/validation` | 空态而非错误（B014），界面出现空表 |

三个已实测的可移植性缺口：

1. **全仓库没有任何算例使用 `flexible_wheelset`。** 只有测试（`tests/test_modal_assembly.py:53`、`:84`，
   `tests/test_modal_deformation.py:49`，`tests/test_modal_coupling.py:151`）和脚本
   （`scripts/s9_inversion.py:62`、`s9_compare.py:60`、`s9f_shortwave.py:99-101`、`s9h_polygon.py:65-67`）
   在运行时拼出 `{"source": "file", "file": str(MODES), "axles": [1,2,3,4]}`，
   `MODES` 是绝对路径。也就是说：**33 阶模态集今天只有绝对路径这一种用法被验证过。**
   `FLEXIBLE_WHEELSET_PORT_2026-10-24.md:499` 里那条"看起来便携"的
   `"vehicles/modes/CRH3C_wheelset_fe.json"` 只在算例文件正好位于仓库根时才成立（`base = case.parent`）。
2. **`smoke_test.py` 的 `unicode-path` 步骤是先 `absolutise()` 再把算例搬进「中文 目录 with space」。**
   它证明的是"绝对化之后能跑"，不等于"相对引用能跑"。这一步的注释里还记着上一次的假 PASS：
   用坏掉的 `VELCH_DATA_ROOT` 跑算例 "proves nothing"。
3. **`manifest.json` 里 `profile_asset_sha256` 的键是绝对路径**
   （实测 `examples/vehicle_v2/output/manifest.json` 有 14 个 `F:\...` 键，另有绝对 `case_snapshot`）。
   同一算例在两台机器上产出的 manifest 永远不相等，等于**放弃了跨机对比这个能力**。

---

## 2. ① 便携模型契约

### 2.1 引用语法（唯一新增的东西是一个前缀）

| 写法 | 含义 | 根 |
|---|---|---|
| `wheel_lower.csv`、`sub/x.csv` | **默认**：相对算例文件所在目录（今天的行为，不变） | `case_path.resolve().parent` |
| `case:sub/x.csv` | 显式相对算例（文档里用，防止将来语义漂移） | 同上 |
| `lib:vehicles/modes/CRH3C_wheelset_fe.json` | 包内车辆库资产 | `vehicle_db._root()` |
| `data:crh380a_m/case_0007.json` | 语料资产 | `data_root()` |
| 绝对路径 `F:\...`、`\\server\...` | 历史写法，继续可用 | 原样，但被打上标记 |

不给默认相对路径加前缀要求的理由是**可逆性**：`Velch/scripts/` 下 40 多个脚本、`examples/` 下 5 个算例、
全部测试都写的是裸文件名或绝对路径，改默认值等于一次性改上百处，而这条契约最需要的是"今天就能验证对"。

`lib:` 复用 `vehicle_db._root()` **而不是新造一个根**。理由：车辆库已经必须解决"源码树 / 解包目录 / `_internal`
三种布局"这个完全相同的问题，且 `tests/test_vehicle_ship.py` 已经钉住了两种 frozen 布局。新造第二个根就是新造
第二种失败方式，而自检只会报告其中一种。

### 2.2 一个解析入口，替换四处调用点

新增 `velch/assets.py`（**不要塞进 `data_root.py`**：那个模块的语义是"语料在哪"，塞进去以后没人能说清
`data_root()` 到底管几件事；独立模块的好处是能在不改动 `data_root.py` 的前提下回滚）：

```
resolve_asset(ref: str, *, case_path: Path, mode: Literal["portable","lenient"]) -> ResolvedAsset
ResolvedAsset = (ref, kind, path, root, sha256, portable: bool)
AssetRefError(ref, kind, reason, resolved, root, hint)   # 机器可读 detail，与 O008 闸门的风格一致
```

四处调用点（`vehicle.py` 的 profile、`.tre`、`modal_file`、`flexible_wheelset.file`）全部改调它，
`base` 参数从"目录"变成"算例文件路径"，避免 `base = target.parent` 这种"算例一挪就变"的隐含假设。
`resolve_asset` 是唯一知道 `lib:` 语义的地方——`vehicle.py` 不再自己 `(base / spec["file"]).resolve()`。

### 2.3 身份与哈希：manifest 必须跨机可比

`assets` 的**键**从 `str(path)` 改成便携 id，**值**仍然是文件字节的 sha256（`case_sha256` 语义不变）：

| 引用形态 | manifest 键 |
|---|---|
| 算例相对 | `case:wheel_lower.csv` |
| 库内 | `lib:vehicles/modes/CRH3C_wheelset_fe.json` |
| 语料 | `data:crh380a_m/case_0007.json` |
| 绝对（历史） | `abs:F:\ai道岔状态反演辨识\...\wheel_lower.csv` |

再加一个计数器块：`portable_refs` / `library_refs` / `absolute_refs`，以及把 `case_snapshot` 记成相对
`output/` 的路径。绝对引用**故意保留** `abs:` 前缀——这样"这个算例到底能不能搬"变成 manifest 里一个可读的数字，
而不是一句承诺。

验收判据（这是 ① 的真正验收）：同一算例在两个不同父目录下各跑一次，两份 manifest 除声明的易变块
（软件版本、时间戳、`run_env`）外**逐字节相同**。

### 2.4 逃逸与校验

- 语法层拒绝：`lib:`/`data:` 后面出现 `..` 段、盘符、UNC、`\\?\`、`~`；`lib:%2e%2e` 之类不做解码，一律当普通字符处理（不做 URL 语义）。
- 物理层：两侧都 `Path.resolve(strict=True)` 后再判 `root in resolved.parents`，这样 Windows 的 junction 逃逸也会被抓到。
- 大小写与 Unicode：`os.path.normcase` + `unicodedata.normalize("NFC", …)` 后比较（「中文 目录」这条路径是真实存在过的用例，不能只在 ASCII 上成立）。
- **逃逸分级**（这是需要决策的点，我选保守侧）：
  - `lib:` / `data:` 逃逸 → 硬错。它是出厂物料的缺陷，不是用户输入。
  - 算例相对逃逸（`../..`）→ `WARN` + manifest `portable: false`。开发期合法（脚本就是这么写的），只在
    `--strict-portability` 下升级为错误。可逆性优先：不要为了整洁一次性打断 40 个脚本。
- 错误消息三件套：**引用原文 + 拼出的绝对路径 + 是哪个根产生的**。今天的 `FileNotFoundError` 只给最后一件。

### 2.5 兼容与迁移

绝对路径永久可用（脚本依赖它），只在 `--strict-portability` 下报错；`table-2-3`/`thesis` 这两种
`flexible_wheelset.source` 完全不动。没有任何默认值改变，所以任何一个现有算例的解析结果都不变——
这也是 ① 能先落地、后补测试的原因。

---

## 3. ② 首次运行体验：把空态填满，而不是把 WARN 升级成 FAIL

`screens_cases.py:181-183` 已经在复用 `data_root.hint()`，问题是 hint 是**给开发者看的查找顺序说明**，
不是能给用户照抄的东西。改形状：

- `data_root.hint()` 保留（测试和旧调用点要它），新增 `hint_lines() -> list[Hint]`，
  `Hint = (一行诊断, 可照抄命令, 期望看到什么)`。三个渲染面共用它：GUI 状态栏 + 每条一个「复制」按钮、
  `velch-cli.exe selfcheck --fix`、`安装说明.txt`。
- 干净机器首跑必须看到（断言级要求，不只是"写了"）：

  ```
  [WARN] 算例语料   未找到语料（新安装的正常状态，不是错误）
         已内置最小算例，可直接运行
    → velch-cli.exe run-vehicle "_internal\examples\minimal\case_flexible_wheelset_turnout.json" --fast
      期望：[PASS] … total_dof=175，模态 33 阶 ×4 轴
    → 接入完整语料（1.4 GB，需另拷）：
      setx VELCH_DATA_ROOT "F:\velch_data"
      期望：重开一个终端后 velch-cli.exe selfcheck → [PASS] 算例语料 358 个算例
    → 不想动环境变量，写当前用户标记文件（无需管理员）：
      cmd /c echo {"data_root": "F:\\velch_data"} > "%LOCALAPPDATA%\Velch\.velch-data.json"
      期望：同上（读取端已按 utf-8-sig 读，PowerShell 5.1 写出的 BOM 不影响）
    → 只读安装（C:\Program Files）还要这一条，否则 agent 功能不可用：
      setx VELCH_AGENT_HOME "%LOCALAPPDATA%\Velch\agent"
  ```

- **界面永不为空**：算例树里内置算例以「内置」标记常驻，语料缺失只影响"其余算例"这一层。
  这条同时把 B014（空态不是错误）从"已知限制"变成"已设计"。
- 保持 `VELCH_DATA_ROOT` 设了但没有 `case_*.json` = FAIL（`tests/test_selfcheck.py` 已钉住这条语义）。
  理由写进 ADR：设了变量就是用户的声明，声明落空是配置错误；没设是全新安装。② 的做法是填空，
  不是把正常状态报警。

---

## 4. ③ 语料不进包；进包的是「最小可跑算例集」

体积账：

| 项 | 现在 | 方案后 |
|---|---|---|
| 安装目录 | 199,100,716 B / 1704 文件（189.9 MB） | + ~10 KB（新算例 JSON） |
| 其中模态集 | `_internal/vehicles/modes/CRH3C_wheelset_fe.json` 1,849,734 B（已在包内，`test_vehicle_ship.py` 钉住 `len(modes) == 33`） | 不变 |
| 语料 | 1.4 GB / 358 个算例（`case_*.json` 计数），外部 | **仍然外部** |
| 若把语料打进去 | ~1.6 GB 单包、zip 也从 93 MB 涨到 ~1 GB 级 | 否决 |

否决理由按重要性排：(a) 交付物涨 8 倍，拷贝/校验/U 盘场景直接不可用；(b) 语料里 358 个算例没有任何一个
使用 33 阶模态，进包也**不解决**用户的原始诉求；(c) 语料是持续增长的评测资产，进包等于把数据和代码版本绑死。

`examples/minimal/` 的内容（新增，不是拷贝语料）：

1. `case_flexible_wheelset_turnout.json` —— 全仓库第一个真正带柔性轮对的算例：
   `"flexible_wheelset": {"source": "file", "file": "lib:vehicles/modes/CRH3C_wheelset_fe.json", "axles": [1,2,3,4]}`，
   并显式写 `radius_m: 0.460`（滚动圆；用轮缘 0.48577 会让自旋频率错 5.6%，`FLEXIBLE_WHEELSET_PORT:488`）
   与 `cutoff_hz`。
2. 复用 `examples/vehicle_v2/` 的 16 个 CSV（每个 ~2 KB，合计 ~40 KB）与 `track_modes_synthetic.json`——**体积可忽略**。
3. 打包时排除 `examples/**/output/` 与 `examples/**/__pycache__/`：今天 `_internal/examples/` 里确实带着
   6 个陈旧产物（两个 `output/manifest.json`、两个 `history.csv`、两个 `.pyc`），它们会让人把旧结果当新结果，
   也让 `install-dir-untouched` 的签名噪声变大。

验收判据（可跑，不是"看起来对"）：内置算例在**无语料**环境跑出 `result_status == "numerically_checked"`、
`total_dof == 175`（35 + 8 + 4×33，`FLEXIBLE_WHEELSET_PORT:502`）、每个柔性轴 33 阶、且在 200 km/h 下
ND1 报 88.25 → 70.05/106.45 Hz。频率对得上才叫"模态真的加载了"，文件找得到只叫"路径没错"。

**已识别的验收风险（必须在方案里写明，不许事后当地雷）**：`O010` 显示节点表车型在柔性轨道上静平衡失败
（内联 35 坐标通过 550.54 µm，节点表 38/86 坐标失败）。175 个自由度的算例可能撞上同一类静平衡问题。
若发生，那是物理/求解器发现（应新开一条 `O0xx`），**不是打包失败**；此时 clean-room 的断言降级为
"解析成功 + 状态维数正确 + 给出明确失败原因"，并在 `open_items.py` 里如实登记。

---

## 5. ④ 一条能把「拷到干净机器」自动验证的测试

新增 `Velch/packaging/clean_room_test.py`，一条命令、一个参数（安装目录），**不进 pytest**（它需要构建产物）。
六个阶段，每阶段一条 `[PASS]/[FAIL]`，输出风格与 `selfcheck.report()` 一致（复用既有约定比发明新格式好）。

1. **隔离**：`copytree` 到 `%TEMP%\velch_cleanroom_<rand>\Velch`；**不复制** `.agent/`、任何 `.velch-data.json`、任何 `validation\`。
2. **清场（白名单，不是继承后删除）**：子进程环境**从空开始**，只给
   `SystemRoot / WINDIR / TEMP / TMP / COMSPEC / PATH(=仅 System32) / PYTHONUTF8=1 / PYTHONIOENCODING=utf-8 /
   LOCALAPPDATA=<临时>\localappdata`。这是对 `smoke_test.py` 的 `_env()`（`dict(os.environ)` 复制，继承
   `VELCH_DATA_ROOT`）的直接纠正——那套环境跑出来的"干净"是假干净。
3. **自证清场成功**：跑 `selfcheck --json`，断言 `data_root.source == "default"`（既不是 `env` 也不是 `marker`），
   且 `case_dir_exists == false`。**没有这一步，整个测试可能在测开发机。**
4. **断言组**：
   - a. `selfcheck --json` 退出码 0；`算例语料` 是 WARN；其余全 PASS（Tk PASS 验 tkinter 可搬迁，matplotlib PASS 验 `collect_data_files` 真的落盘）；`hint` 里含 `setx VELCH_DATA_ROOT`。
   - b. `run-vehicle _internal\examples\minimal\case_flexible_wheelset_turnout.json --fast` 成功；manifest `total_dof == 175`、`absolute_refs == 0`、键里有 `lib:vehicles/modes/…`。
   - c. **再搬一次**：整个目录移到 `<temp>\移动 副本\`（中文 + 空格）重跑 b；要求 manifest 与 b **逐字节相同**（除易变块）。这才是"拷到另一台电脑"的替身，且严格强于现有 `unicode-path` 步骤。
   - d. **只读安装**（复用既有 `--readonly-acl` 配方，注意必须 `(W,AD)`，不能只写 `(W)`——`(W)` 含 SYNCHRONIZE，Tcl 会报 `Can't find a usable init.tcl`）：自检退出 2 且 `[FAIL] 可写目录`，但 b 仍能产出 manifest。
   - e. **负对照**：复制内置算例，把 `lib:vehicles/modes/…` 改成 `lib:vehicles/modes/missing.json`；要求非零退出、消息里同时出现引用原文与解析根、**无 traceback**。没有负对照，测试可能在解析器静默回退时照样全绿。
   - f. **时间预算**：整轮 ≤ 180 s（`--fast`）。超过就会被日常跳过，等于没有。
5. 产出 `clean_room_report.json` 供 CI/发布物归档。
6. 接线：`packaging/build_installer.py --verify` 在打 zip 之后调用；版本号必须在这个测试绿了之后才写。

---

## 6. 优先级与每步验收判据

P0 = 不做则"拷过去就能跑"这句话不成立；P1 = 从"能跑"到"可用"；P2 = 卫生与可维护性。

| 优先级 | 步骤 | 验收判据（可执行） |
|---|---|---|
| **P0-1** | 新增 `velch/assets.py`：`resolve_asset()` + `lib:`/`data:` + 分级逃逸 + `AssetRefError`；四处调用点改用它 | 任意目录下的算例用 `lib:vehicles/modes/CRH3C_wheelset_fe.json` 能跑；5 个现有 `examples` 结果不变；`pytest -k "vehicle or modal or ship"` 全绿；`selfcheck` 六项结论不变 |
| **P0-2** | 新增 `examples/minimal/case_flexible_wheelset_turnout.json`（`lib:` 引用 + `radius_m 0.460`）；打包排除 `examples/**/output`、`__pycache__` | 无语料环境下 `result_status == numerically_checked`、`total_dof == 175`、33 阶 ×4、200 km/h ND1 88.25→70.05/106.45 Hz；`_internal/examples` 里 0 个 `output/`、0 个 `.pyc` |
| **P0-3** | 新增 `packaging/clean_room_test.py`（阶段 1–4b、4c、4e） | 当前构建上全绿；**故意删掉 `Velch.spec` 里 `vehicles` 的 `datas` 或改坏 `lib:` 解析 => 必须红**（测假的测试不算） |
| **P1-4** | `data_root.hint_lines()` + GUI「修复面板」+ `selfcheck --fix` + `安装说明.txt` 同步 | 干净机器首跑输出里 ≥3 条可照抄命令，每条带"期望看到"；算例屏在无语料时**不为空**（内置算例可见）；`hint()` 旧接口仍通过现有测试 |
| **P1-5** | manifest 便携 id（`case:`/`lib:`/`data:`/`abs:`）+ 计数器 + 相对 `case_snapshot` | 两台不同父目录的 manifest 除易变块外逐字节相同；`absolute_refs` 对内置算例为 0 |
| **P1-6** | 发布卫生：清掉 `dist_installer\` 里 36 个历史 zip 与 `Velch-0.4.23-win64` 解包目录 | `install-dir-untouched` 基线干净：首次运行除 `output/`、`.agent/` 外无新增目录 |
| **P2-7** | `--strict-portability` 开关；算例相对逃逸 WARN + `portable: false` | 打开开关后 `../` 引用非零退出并点名引用；关掉后仅 WARN |
| **P2-8** | 文档纠偏：`FLEXIBLE_WHEELSET_PORT_2026-10-24.md:499` 那条形式标注"仅当算例在仓库根成立"，改为 `lib:` 写法；`PACKAGING_2026-10-22.md` 补 `lib:` 与 clean-room | 文档里出现的可移植写法，逐条能在 clean-room 里跑通（文档即测试用例） |
| **P2-9** | 只读安装与 `VELCH_AGENT_HOME` 的提示并入 `hint_lines()` | 只读副本自检退出 2 时，修复面板给出 `setx VELCH_AGENT_HOME`，且仿真仍可跑 |

建议节奏：P0-1、P0-2 是同一批改动（契约 + 用它），P0-3 紧随其后（不然前两者没有证据）；P1-4/5/6 可以并行。

---

## 7. 风险、权衡与明确不做的事

**风险**
- `O010` 类静平衡问题可能让 175 自由度算例不收敛 → 见 §4 的降级路径；先登记，不改物理。
- `lib:` 让模态文件从"算例邻域"变成"全局资产"，删错一次会影响所有算例——用 sha256 + `absolute_refs == 0` 计数兜住，不做版本目录。
- 只读安装 + 内置算例：内置算例的 `output/` 必须写到 `VELCH_AGENT_HOME` 或当前目录，否则只读场景会二次失败（阶段 4d 会抓到）。

**权衡（写清楚放弃了什么）**
- 放弃"一套统一 URI"：只在默认相对路径上叠一个前缀，语法不统一但迁移成本为 0，且随时可回滚。
- 放弃"语料进包换一次拷贝"：换来的是 8 倍体积和把评测资产绑死到代码版本。
- 放弃"空语料 = FAIL"：报警更响，但会让每台干净机器看起来都是坏的，用户会学会无视报警。

**明确不做**
- 不做资产清单/注册表式间接层（多一层 indirection，收益只有"看起来整齐"）。
- 不引入 URI 解析库。
- 不在首跑时自动复制语料（1.4 GB 的意外 + 只读安装没有写权限）。
- 不把契约只挂在环境变量上。
- 不改任何默认解析语义、不改 `table-2-3`/`thesis` 两条模态来源、不动 `O008` 的闸门。

---

## 8. 影响面清单（供实现时对照，本文不改代码）

- 新增：`src/velch/assets.py`、`examples/minimal/case_flexible_wheelset_turnout.json`、`packaging/clean_room_test.py`、本文件
- 修改：`src/velch/vehicle.py`（四处调用点 + `_load_wheel_modes` 的 `assets` 键）、`src/velch/data_root.py`（`hint_lines()`，保留 `hint()`）、`src/velch/ui/screen_cases.py`（内置算例 + 修复面板）、`src/velch/selfcheck.py`（`--fix` 渲染）、`src/velch/cli.py`（开关透传）、`packaging/Velch.spec`（排除产物）、`packaging/build_installer.py`（`--verify`、`安装说明.txt` 模板）、`packaging/smoke_test.py`（环境白名单复用）、`tests/test_vehicle_ship.py` 相邻新增契约测试、`src/velch/open_items.py`（如实登记新发现）
- 不改：`src/velch/paths.py`（那是 `PathTrack` 线路走向，与文件解析无关，别被名字骗了）
