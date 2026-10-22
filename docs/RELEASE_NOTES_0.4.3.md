# Velch 0.4.3 发布说明（2026-10-22 夜）

0.4.2 之后只动了一件事：**从 Simpack 模型导入断面这件事，能不能算、算不了时说的是不是人话。**

## 装什么

- `Velch-0.4.3-win64.zip`（93.3 MB，解压 195.5 MB）：onedir 便携目录，解压即用。
- `Velch.exe`：窗口版（无控制台）。双击或用目录里的 `启动 Velch.cmd`。
- `velch-cli.exe`：控制台版。所有 CLI 子命令、`agent` MCP 服务、自检都走它——**窗口版没有 stdout，
  自检和脚本一律用这个**。
- `安装说明.txt`、`启动 Velch.cmd`、`.velch-data.example.json`、`manifest.json`（1618 文件 + 逐文件 sha256）。

## 这一版改了什么

### 1. 导入模型自己的断面，现在能跑通了

`velch-cli.exe simpack-case --catalog <模型目录>/catalog.json --template case_A_final_law.json   --out case.json --side right --x-start 82.0 --duration 0.05 --sample 400`

随后 `run-vehicle case.json --fast`：`numerically_checked`、七项门全 true、八接触峰值
60.59 / 66.85 / 63.55 / 60.56 / 60.79 / 68.52 / 71.89 / 60.75 kN、最大侵入 88.63 µm、BDF `nfev 1094`。

> 这次跑的是**模型自己的轨顶断面**（`right` 侧 226 站，逐站不同的 PRR 文件），
> 质量/悬挂/接触律/容差仍然来自模板算例——Simpack 只提供几何。

### 2. 里程不再整体平移

早期实现把模型里程挪到 `--x-start`，右轨只剩 13.5–163.5 m，第一个车轮位置就出界，静平衡报
"最轻接触斑 0.0 N、最重 119 357 N"。现在里程按模型原样导入；`x_start + 车速 × 时长` 超出模型覆盖范围
会直接报 `… leaves the model's coverage …`，而不是让积分器在一个错位的模型上算。

### 3. 断面下沉判据：先说清差多少，再说能不能算

派生之前量一件事：**行驶窗口内，模型断面比模板低多少**（只在车轮真的会经过的那段里程上量）。

| 起点 | 窗口内最大下沉 | 结果 |
|---|---|---|
| 60.0 m | 0.09 mm | 断面几乎对齐，**静平衡仍失败** |
| 65.0 / 70.0 m | 0.01 / −0.01 mm | 同上 |
| 75.0 / 80.0 m | **11.24 mm** @ 79.867 m | 被拒（默认 8 mm 上限） |
| 82.0 m | 5.18 mm @ 80.004 m | 构建成功 + warning，跑通 |

- `≤3 mm` 静默；`3–8 mm` 构建成功但旁挂 `surface_drop_warning`；`>8 mm` 直接拒绝，消息里带下沉量、
  里程、阈值和三条出路（换窗口 / `--keep-profiles` / `--allow-surface-drop` 自己读一遍再引用）。
- 量不到时记 `surface_delta_mm: null`——**"没量到"不等于"没下沉"**。
- `--keep-profiles`：只用模型的里程布置、型面沿用模板。60 m 窗口用它跑通，每接触峰值
  **59 680.5768587 N**（冻结静载门）、`nfev 116`。

### 4. 顺带说清它**不**保证什么

60–70 m 三档的冠部高度与模板差不到 0.1 mm，却照样坐不住：转辙区的断面**形状**（承载面宽度、圆角、
轨距面位置）逐站都在变，"冠部对齐"只是**必要不充分**条件。判据的作用是把明显不可能的窗口挡在
积分器之前，不承诺剩下的窗口一定跑得通。这一条已登记为 `docs/BUGS.md` 的 O008。

## 验证

- `pytest`：**497 passed, 1 skipped**（skip 是"真机上有 Simpack 模型才跑"的那条）。
- `packaging/smoke_test.py`：**ACCEPT**（5 步，失败 0、跳过 1）——自检 7 屏 / 424 控件 / 3550 行 /
  0 屏报错；`cli-run` 出 `numerically_checked`；缺语料给可读提示且无 traceback；中文+空格路径可跑。
- 提交闸门：每次提交实跑 `pytest + doctor + 契约`，`verdict: ACCEPT`。
- 物理未动：静载门 59 680.5769 N / 65.47 µm、八接触峰值、七项 manifest 门、DOP853 逐位等价（既有测试钉住）。

## 仍然没有的

1. 只读安装目录下的启动未自动测（`安装说明.txt` 里给了手工步骤）。
2. 无代码签名：首次运行可能被 SmartScreen 拦一次。
3. 卸载就是删目录。
4. Simpack 只到几何层：模型树的参数、执行机构、结果通道仍未导入（设计上要求人工显式映射）。
5. `physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`——能跑通不等于这段断面
   就是真实线路的断面。
