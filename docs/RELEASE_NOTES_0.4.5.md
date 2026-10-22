# Velch 0.4.5 发布说明

发布日期：2026-10-22（深夜）
上一版：0.4.4

---

## 一句话

**读 Simpack 模型的道岔区断面，现在能真的算出来了**——因为上一版量断面时量错了地方，量到的是轨顶侧面而不是冠部；
同时派生算例漏掉了后轴要压的那 10 m 钢轨。两处修好后，同一个 60 m 转辙器窗口从"静平衡必然失败"变成
`numerically_checked`，最大侵入 65.466 µm、前轴右轨 59.68 kN。

## 装什么

```
Velch-0.4.5-win64.zip   （93.3 MB 压缩 / 195.5 MB 解开 / 1618 个文件）
├─ Velch.exe            窗口版：七个屏，双击就能用（不要指望它往控制台打印）
├─ velch-cli.exe        命令行版：run-vehicle / assess / simpack-case / agent 都在这儿
├─ 启动 Velch.cmd        双击它最省事（设了 PYTHONUTF8=1，中文不会乱码）
├─ 安装说明.txt          怎么开、语料放哪、七屏各回答什么、快捷键
└─ .velch-data.example.json   语料目录标记文件的模板
```

语料（算例、断面、冻结 oracle）**不在包里**，装在哪由你决定：

1. 环境变量 `VELCH_DATA_ROOT` 指到 `...\validation`（最直接）；
2. 或把 `.velch-data.json` 放在 `%LOCALAPPDATA%\Velch\`；
3. 或放在安装目录旁边。

三级都找不到时，① 算例屏会写清"查了哪几个位置、标记文件怎么写"，而不是空表。

## 这一版改了什么

### 1. 断面量测：从"侧面"改到"冠部"

旧代码在固定横向位置 `y = 0.753 m` 取轨顶高度。模板断面载入后的包络是 `y ∈ [−0.790, −0.717] m`、
冠部在 `−0.7896 m`，所以 `0.753` 落在**轨顶侧面**上，比冠部高 **+29.86 mm**。于是过去报出的
"断面下沉 5.18 mm / 11.24 mm"记录的其实是**冠部横向漂移 × 侧面坡度**，与垂直下沉无关。

按冠部重测（226 个右轨站位）：冠部高度差 **0.000–0.155 mm**；真正在变的是**冠部横向位置**
（0.714–0.868 m，相对模板最多漂移 **103 mm**）。

### 2. 派生算例：导入整车足迹，不是"向后 2 m"

后轴在 `x_start` 之后 **10 m**（`bogie_half_spacing_m + wheelbase_m/2`）。旧窗口
`[x_start − 2, x_start + 车速×时长 + 2]` 里没有后轴要压的断面，导入的站位表缺了那一段，
静平衡必然报"单侧脱空、最重接触 119 315 N"——**那是后轴没有钢轨，不是道岔几何坐不住**。

窗口改成 `[x_start − 10, x_start + 车速×时长]` 后，同一个 60 m 窗口：

| 窗口 | 冠部差 | 足迹 | `seats` | 结果 |
|---|---|---|---|---|
| 60 m | 0.155 mm | 50.0–64.861 m | **true** | `numerically_checked`、`nfev 116`、最大侵入 **65.466 µm**、`axle1_right 59.68 kN` |
| 82 m | 0.155 mm | 80.0–88.861 m | true | `numerically_checked`、`nfev 1094`、最大侵入 88.63 µm、八接触 60.59–71.89 kN |

60 m 那行的最大侵入与前轴右轨恰好是冻结静载门（65.47 µm / 59 680.5769 N），说明导入链路没有动已标定的物理。

### 3. 拒绝变成裁决：`simpack-case` 派生完会真跑一次静平衡

- 冠部差 > `CROWN_WARN_MM = 0.5 mm` → 只写一条 **warning**（"the run may seat, but say so before quoting it"），
  **不再拒绝**——实测证明它分不出能不能坐。
- 派生完调用 `seat_report()` 真跑 `_static_vertical_equilibrium`：坐得住 → 退出码 0 并打印八接触载荷；
  坐不住 → 退出码 2，打印原因、冠部差、整车足迹，以及一句**明确不推荐任何窗口**的建议。
- 不想让派生动作跑静平衡就显式 `--no-seat-check`。
- 旧的 `--allow-surface-drop` / `--max-surface-drop` / `--lateral-m` 三个开关随阈值一起删掉。

## 验证

| 项 | 结果 |
|---|---|
| `pytest tests` | **506 passed, 1 skipped**（skip 是"真实 Simpack 模型在时才跑"那条） |
| `packaging/smoke_test.py` | **ACCEPT**（5 步：selftest / cli-run / missing-corpus / unicode-path PASS，readonly SKIP） |
| 提交前闸门 | `verdict: ACCEPT`（tests + doctor + contract） |
| 提交 / 标签 | `f13fc6b` / `v0.4.5` |

命令（源码模式，等价于 exe）：

```powershell
$env:PYTHONPATH="<repo>\src"
python -X utf8 -m velch simpack-case --catalog catalog.json `
    --template case_A_final_law.json --out out\case.json --x-start 60 --duration 0.05 --sample 60
python -X utf8 -m velch run-vehicle out\case.json --output out\run --fast
```

## 仍然没有的东西（说清楚，别当成有）

1. **横向布置没有导入**：轮对初始横向位置仍取模板的 `y_offset_m = 0.753`，而模型冠部最多少漂移 103 mm →
   接触点相对冠部的位置与模型不完全一致。要消除需导入模型自己的轮对横向布置 + 双体（基本轨/尖轨）交接。
2. **Simpack 侧的数只作对照值**：轴重、`E*`、`R*`、蠕滑、一/二系刚度阻尼、模态、容差都不导入；
   `physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`。
3. **没有与 Simpack 结果的定量对照**（同一工况下峰值/频带的逐项比较仍待做）。
4. **安装包没有代码签名**：首次运行 Windows 会提示；删掉整个文件夹等于卸载（没有安装程序写注册表）。
5. **只读安装目录的自动测试仍是 SKIP**（要管理员权限造目录），手工步骤写在 `安装说明.txt`。
