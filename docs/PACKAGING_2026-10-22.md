# 打包与安装包（Windows）

一、产物长什么样

```
dist_installer\Velch\
  Velch.exe            窗口版（七个屏，无控制台）—— 双击这个
  启动 Velch.cmd       同上，但先设 PYTHONUTF8=1（推荐）
  velch-cli.exe        控制台版：CLI、MCP、agent 工具，以及界面启动的所有子进程
  manifest.json        每个文件的字节数与 sha256（支持时可核对，不靠文件夹名）
  安装说明.txt         中文：怎么开、语料放哪、七个屏各回答什么
  .velch-data.example.json
  _internal\           Python 运行时、numpy/scipy/matplotlib/Tk 数据
dist_installer\Velch-0.4.1-win64.zip   同一份目录的压缩包（分发用）
```

二、为什么是两个 exe

- 窗口版没有 stdout。**界面"点运行"要起子进程**，如果继承窗口版 exe，日志会全部丢失，
  而且冻结后 `sys.executable` 就是 exe 本身：`<exe> -X utf8 -m velch …` 不是合法引导参数。
- 所以子进程一律走 `velch.launcher.console_executable()` —— 同目录的 `velch.exe`，
  它按 `<exe> <command> …` 的形式分发（`packaging/entry_console.py` 给它 `agent-worker`
  与 `--selftest-stream` 两个内部命令，其余转给 `velch.cli`）。
- 这条路径在源码模式下**永远走不到**，所以 `tests/test_launcher.py` 里除了逐分支断言，
  还有一条"全仓不得再出现 `sys.executable`"的扫描，防止有人把它写回去。

三、语料不在包里

程序 250–400 MB，语料 1.4 GB，且语料是研究数据不是产品。首次运行按这个顺序找：

1. 环境变量 `VELCH_DATA_ROOT`
2. 逐用户标记 `%LOCALAPPDATA%\Velch\.velch-data.json`（**安装目录可能只读，这是唯一可写位置**）
3. 安装目录下的 `.velch-data.json`
4. 安装目录下的 `validation\`

标记内容：`{"data_root": "F:/velch_data"}`，该目录下应有 `validation\crh380a_m\case_*.json`。
找不到时算例屏显示查找顺序与写法（`data_root.hint()`），不抛 traceback。

四、怎么构建

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 packaging\build_installer.py            # 构建 + 加料 + 写 manifest + 打 zip
python -X utf8 packaging\build_installer.py --skip-build  # 只重做加料与 zip
```

首次构建约 5–10 分钟（PyInstaller 要处理 numpy/scipy/matplotlib 的 hook）。
`packaging/Velch.spec` 里 `collect_data_files("matplotlib")` 是必需的：不收集字体与样式数据，
打包后的图表会缺字形；Tk 的 Tcl/Tk 由 PyInstaller 自带 hook 处理。

五、构建后必须实跑的 5 个动作（打包特有的失败都在这里）

| # | 动作 | 通过标准 |
|---|---|---|
| 1 | 双击 `Velch.exe` | 七个屏都能点开，中文无豆腐块；Ctrl+= 到 160% 无裁切 |
| 2 | ① 选 `case_frog_N_strip05.json` → ② `Ctrl+R` | 输出目录出现 `history.csv` + `manifest.json`；**这一步专打 B013** |
| 3 | 同算例命令行：`velch-cli.exe run-vehicle … --output out_cli` | 七项门全 true、`numerically_checked`、八接触峰值与源码逐位一致 |
| 4 | 把 `VELCH_DATA_ROOT` 指向不存在的目录再启动 | 算例屏给出可读提示（查找顺序 + 写法），不是 traceback |
| 5 | 装到 `C:\Program Files\Velch`、语料放在含空格与中文的路径、`--jobs 4` | 只读安装目录下仍能跑；子进程 4 个都退出 0 |

六、已知限制

- 没有代码签名：SmartScreen 会拦一次，选"更多信息 → 仍要运行"。
- 没有自动更新、没有卸载注册项：删文件夹即卸载。
- `manifest.json` 的 sha256 只覆盖发布目录里的文件，不覆盖 `_internal` 里的每个字节（体积原因）。
- 语料缺失时**多数屏是空态而不是错误**：这是设计，不是 bug（见 `docs/BUGS.md` B014）。

## 冒烟测试（打包之后必跑）

```bat
python -X utf8 packaging\smoke_test.py --root dist_installer\Velch
```

五步：冻结自检（7 屏 0 报错 + 日志管道）、冻结 CLI 跑真算例（七门 + manifest）、语料缺失给提示不抛栈、
路径含中文与空格、只读安装位置（记为 SKIP 并写明手工步骤）。报告落 `reports/packaging_smoke_<时间戳>.json`，
`verdict: ACCEPT` 才算可以交付。

0.4.1 实测（`reports/packaging_smoke_20261022-223010.json`）：

| 步骤 | 结果 |
|---|---|
| selftest | PASS · 7 屏 / 424 控件 / 3550 行 / 0 报错 · 日志管道 4 行 exit 0 |
| cli-run | PASS · `numerically_checked` · 七项门全 true |
| missing-corpus | PASS · 退出码 1 · 含 `VELCH_DATA_ROOT` · 无 traceback |
| unicode-path | PASS · 算例/工作目录/输出目录全含中文与空格 |
| readonly-install | SKIP · 见"已知限制" |

产物：目录 195.5 MB / 1613 文件；`Velch-0.4.1-win64.zip` 88.9 MB。

## 仍然手工的一步：真·只读安装目录

`smoke_test.py` 的 `install-dir-untouched` 用"运行前后安装树签名不变"证明**程序不往自己脚下写**
（新增/删除/改大小都会被列出）。它**不能**证明 ACL 拒绝时给出的是人话——那需要把目录放到
`C:\Program Files\Velch` 并把当前用户设为只写拒绝，属需要管理员的手工步骤：

1. 复制 `Velch\` 到 `C:\Program Files\Velch\`；
2. `icacls "C:\Program Files\Velch" /deny "%USERNAME%":(W,AD)`；
3. 双击 `启动 Velch.cmd`，① 屏应当正常出算例（数据根在 `F:\velch_data`），④ 屏不报写失败；
4. 把语料根写成不存在的路径，确认界面显示 `data_root.hint()` 的中文指引而不是 traceback。
