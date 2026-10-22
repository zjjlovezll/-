# Velch 0.4.1 · 发布说明（2026-10-22）

道岔动力学工作台，第一个"可以直接安装运行"的版本。

## 装什么、怎么开

产物在 `Velch/dist_installer/`：

| 文件 | 大小 | 用途 |
|---|---|---|
| `Velch-0.4.1-win64.zip` | 88.9 MB | **给人下载的安装包**（解压即用，无安装程序） |
| `Velch/` | 195.5 MB · 1613 文件 | 解压后的目录本体 |

1. 把 zip 解压到任意位置（**不要**解压到 `C:\Program Files` 之外的只读位置就更省事）。
2. 双击 `启动 Velch.cmd`（或直接双击 `Velch.exe`）。
3. 首次打开 ① 算例屏，点上方的提示链接看语料放在哪——见下面"语料"。

目录里两个 exe 分工明确：

- `Velch.exe` — 窗口版，七屏工作台（无控制台窗口）。
- `velch-cli.exe` — 控制台版，命令行 / MCP / 界面里"运行"时启动的子进程都用它。
  两个 exe 必须同目录存在：窗口版没有 stdout，算例日志要靠控制台兄弟进程才看得见。

## 语料（算例与型面文件，不进安装包）

1.4 GB 的算例/运行产物刻意不打进包里。程序按这个顺序找语料：

1. 环境变量 `VELCH_DATA_ROOT`
2. `%LOCALAPPDATA%\Velch\.velch-data.json`（安装目录只读时唯一可写处）
3. 安装目录里的 `.velch-data.json`
4. 安装目录下的 `validation/`

标记文件写法：

```json
{ "validation_root": "F:\\velch_data\\validation" }
```

找不到语料时，① 算例屏会给出上面这段中文说明与它查过的位置，而不是空白表格；命令行下 `velch-cli.exe agent doctor` 会返 `cases: ok=false` 并附同样的提示。

## 七屏各回答什么

| 屏 | 回答的问题 |
|---|---|
| ① 算例 | 有哪些算例？自由度、时长、哈希、契约是什么？ |
| ② 运行 | 跑哪几个？用什么求解器？日志与退出码在哪看？ |
| ③ 时程 | 这一列随时间怎么变？多通道各自独立纵轴 |
| ④ 频谱 | 1/3 倍频程带能量分布，主导频带在哪？ |
| ⑤ 评价 | 七项数值门过了吗？脱轨系数/减载率/轮轨横向力离限值多远？ |
| ⑥ 对照 | 与 Simpack / 实测同一里程轴叠起来差多少？ |
| ⑦ 三维 | 钢轨型面与车轮长什么样？（几何直接读本算例引用的型面文件） |

快捷键：`Ctrl+1…7` 切屏、`Ctrl+R` 运行、`Ctrl+=`/`Ctrl+-`/`Ctrl+0` 调字号、`F5` 刷新、`Esc` 取消、`Ctrl+L` 跳到搜索框。

## 速度

同一算例（`case_full12_cap05.json`，1.2 s，整车）：

| 配置 | 墙钟 | nfev |
|---|---|---|
| 声明配置（DOP853，逐位基线） | ≈850 s | 331 949 |
| `--fast`（BDF + 解析雅可比 + rtol 1e-4） | **≈79 s** | 58 113 |

`--fast` 的物理偏差：八接触峰值最差 0.30 kN（0.14 %），脱空计数、四频带到两位小数不变。要报告数字用声明配置，要趋势用 `--fast`。界面上在 ② 运行屏勾"快速预设"即可。

## AI 接口

```bat
velch-cli.exe agent doctor                :: 自检环境
velch-cli.exe agent manifest              :: 12 个工具的 JSON Schema
velch-cli.exe agent call payload.json     :: 单次调用
velch-cli.exe agent serve                 :: MCP stdio（给 AI 客户端接）
```

工具域：`capabilities / parameters / list_cases / read_case / derive_case / revisions /
predict_run / submit_run / job_status / list_jobs / cancel_job / read_result`。
写算例只能走 `derive_case`（父算例永不修改，差异进 ledger 链），作业是独立进程，结果目录带 `manifest.json`。

## 这次验证了什么

- `pytest`：**483 passed**（含 19 项 agent 契约、19 项界面健壮性、8 项字号、19 项可读性、3 项打包排除清单）。
- 打包冒烟 `python packaging/smoke_test.py --root dist_installer/Velch`：**ACCEPT**
  （`reports/packaging_smoke_20261022-223010.json`）
  1. 冻结自检：7 屏 / 424 控件 / 3550 行数据 / **0 个屏报错**，日志管道收到子进程输出且退出码 0；
  2. 冻结 CLI 跑真算例：`numerically_checked`，七项门全过，`manifest.json` 与 `case_snapshot.json` 齐；
  3. 语料缺失：退出码非 0，输出里能读到 `VELCH_DATA_ROOT` 提示，**无 traceback**；
  4. 路径含中文与空格（算例、工作目录、输出目录全部）：跑通；
  5. 只读安装位置：见下面"已知限制"。
- 物理不变量未动：静载门 59 680.5769 N / 65.47 µm、八接触峰值 89.68 / 170.61 kN、七项门、DOP853 轨迹逐位不变。

## 已知限制

- **没有代码签名**：Windows 可能弹"未知发布者"，选"仍要运行"。
- **卸载 = 删目录**：无注册表项；`%LOCALAPPDATA%\Velch` 里的标记文件可保留。
- **只读安装位置**（如 `C:\Program Files\Velch`）未自动测试：程序的设计是语料标记写 `%LOCALAPPDATA%`，但把 195 MB 复制进只读目录属于手工步骤，发布前请手动跑一次并确认首启提示可读。
- **Simpack 读取目前只到几何层**：`velch simpack-catalog` 解析 `.spck` 与 `.prr` 得到型面、站位、轨道与刚体质量清单；Simpack 的模型树参数、私有类型码和 Post 二进制**不猜**——那部分走仓库外 `simpack-mcp-2021x` 的 JSON 契约。物理量必须人工显式映射，不允许自动写进 `case.json`。
- **未与实测/Simpack 做物理标定**：`physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`。这一版保证的是"算得对得上自己的冻结基线"，不是"算得符合真实道岔"。
