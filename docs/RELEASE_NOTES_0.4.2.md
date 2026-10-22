# Velch 0.4.2（2026-10-22 夜间）

在 0.4.1 的基础上做了两件事：把界面可读性收尾，以及**让软件真的能读一个 Simpack 模型来算**。

## 装什么

`Velch-0.4.2-win64.zip`（约 89 MB，解开约 195 MB）：解压到任意目录，双击
`启动 Velch.cmd`（或 `Velch.exe`）。**免安装**：删掉文件夹就是卸载。
目录内有 `安装说明.txt`、`.velch-data.example.json`、`manifest.json`（1618 个文件的 sha256）。

两个 exe：`Velch.exe` 是窗口版（无控制台），`velch-cli.exe` 是命令行/MCP 版（有 stdout）。
窗口版跑不了自检，因为 windowed 构建的 `sys.stdout` 是 `None` —— 要跑 `--selftest` 请用 `velch-cli.exe`。

## 这一版新增

### 界面（可读性四项）

| 项 | 之前 | 现在 |
|---|---|---|
| 控件边界对比度 | 1.37:1 / 1.83:1 | **3.99:1 / 4.32:1**（WCAG 1.4.11 要求 3:1） |
| 表格斑马纹 | 无 | `ROW_ALT` 每两行一条（`INK` 14.03:1 仍达标） |
| 焦点环 | 1 px | **2 px** |
| 字号阶梯 | body 11 px / 行高 26 | **body 12 px / 行高 28**（title 20、section 15、micro 10） |

抬字号后暴露的两处问题都用"减法"解决：① 算例表从四列减到三列（起始里程移进右侧契约卡）；
② 横向滚动条只在真的放不下时出现，不再假装"右边还有内容"。

### 读 Simpack 模型

新增 `velch simpack-case`：**几何从 Simpack 模型来，物理从你指定的模板算例来**。

```powershell
velch-cli.exe inspect-simpack-track <model>.spck --model-root <database> --output catalog.json
velch-cli.exe simpack-case --catalog catalog.json --template case_A_final_law.json ^
    --out case_from_simpack.json --side right --x-start 60 --duration 0.05 ^
    --sample 60 --keep-profiles
velch-cli.exe run-vehicle case_from_simpack.json --output out_simpack --fast
```

实测本机真实数据库（`CRH380A_M_Wheelset.spck`）：238 条型面引用、233 个唯一 PRR 文件、0 缺失、
10 处同里程多表面、里程 0–150 m、`geometry_readable = true`。

- 只导入**里程布置**（`--keep-profiles`）：跑通，`numerically_checked`、七门全 true、静载
  **59 680.5769 N**、侵入 **65.47 µm**。
- 导入模型**自己的断面**：静平衡阶段失败（单侧承担两倍载荷），因为同一里程有两个承载面而
  `ProfileSeries` 每个里程只能插值一个表面，且模型自己的横向布置还没导入。这是**已知的下一层**，
  已写进 `docs/SIMPACK_IMPORT_2026-10-22.md`，不是被掩盖的 bug。

明确不导入：轴重/惯量、赫兹与蠕滑参数、悬挂刚度阻尼、模态文件、求解器容差、任何从 `.spck`
文本里推断出来的数。派生出的算例旁边一定有 `<算例>.simpack.json`，写清哪些来自模型、哪些来自
模板、哪些没导入。

## 验证

| 项 | 结果 |
|---|---|
| `pytest` | **492 passed, 1 skipped**（skip 的是"真实模型在时才跑"的那条） |
| 冻结自检（打包版） | 7 屏 / 424 控件 / 3550 行 / **0 屏报错** |
| 打包冒烟 5 步 | **ACCEPT**：自检 / CLI 跑一个算例 / 缺语料可读报错 / 中文+空格路径 / 只读安装（SKIP） |
| 冻结物理 | 静载 59 680.5769 N、侵入 65.47 µm、七项门全 true —— 与 0.4.1 一致 |

## 仍然没有的

- 没有代码签名（首次运行 Windows 会提示"未知发布者"）
- 只读安装目录（`C:\Program Files`）未自动测，需手工验证
- Simpack 只到几何层；模型自己的横向布置与双体交接未做
- `physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`
