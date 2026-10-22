# Velch 道岔车辆动力学研究软件（v0.4.0）

Velch 是一个**独立实现、可运行的降阶正向求解器**，带一套中文桌面工作台与面向 AI 的调用接口。
车辆 35 自由度（车体—前后转向架—4 轮对），道岔钢轨按每个轮对的候选截面补丁增加自由度；
两个版本的车辆纵向速度均由外部规定。v1 单轮对求解器继续作为较小的核对算例。

![三维模型屏：钢轨型面与车轮](/Velch/docs/images/model3d_preview.png)

## 先跑一次自检

```
python -X utf8 -m velch selfcheck
```

六项：版本与发布说明、算例语料、Tk、matplotlib、Simpack 路径、可写目录。每条失败都写着怎么补；退出码 0 可以启动、2 有必须修的东西。安装包里用 `velch-cli.exe selfcheck`（窗口版没有 stdout）。细节见 [docs/SELFCHECK_2026-10-23.md](docs/SELFCHECK_2026-10-23.md)。

## 三十秒上手

1. **双击** [启动Velch界面.cmd](启动Velch界面.cmd)（或桌面上的 `Velch 道岔动力学.cmd`）。
2. 在 ① 算例屏挑一个算例（`case_frog_N_strip05.json` 只要几秒），双击或按「在『运行』屏打开」。
3. ② 运行屏按 **Ctrl+R** 开始跑；跑完 ③ 时程 / ④ 频谱 / ⑤ 评价 / ⑥ 对照 各自加载该次运行。
4. 字号看不清：**Ctrl+=** 放大、**Ctrl+-** 缩小、**Ctrl+0** 还原（0.9–1.6 倍）。

命令行等价物：

```powershell
cd 'F:\ai道岔状态反演辨识\Velch'
$env:PYTHONPATH = "$PWD\src"
python -X utf8 -m velch.ui                  # 打开界面
python -X utf8 -m velch.ui --selftest       # 无头自检：7 屏逐个加载数据
```

`python -m pip install -e .` 之后也可以直接用 `velch-ui` 入口。界面只用标准库 Tkinter；
三维屏需要 `matplotlib`（`pip install -e ".[ui]"`，缺失时该屏降级为一句提示，其余六屏照常）。

## 七个屏各自回答什么

| 屏 | 回答的问题 | 数据来源 |
|---|---|---|
| ① 算例 | 有哪些算例、自由度多少、参数哈希是多少，怎么派生新算例 | `case_*.json` 清单 |
| ② 运行 | 用哪个算例、什么求解器、要不要多进程，跑得怎么样 | 启动 CLI 子进程，日志流式回显 |
| ③ 时程 | 哪条通道随时间怎么变（多选，按单位分组，各带独立纵轴） | `history.csv` |
| ④ 频谱 | 某个通道的能量落在哪些 1/3 倍频程带 | `velch.inverse.bands` |
| ⑤ 评价 | 这次运行过没过数值门，七项判据逐条是什么 | `manifest.json` + `summary` |
| ⑥ 对照 | 与 Simpack 或另一次运行差多少 | 两个运行目录的共里程比 |
| ⑦ 三维 | 钢轨型面和车轮长什么样、轮对怎么走 | 算例引用的型面文件 |

界面里的字是中文，通道名（`axle1_right_normal_n`）仍按原始列名保留 —— 它是数据契约，
翻译后无法再与 `history.csv`、manifest 对账；中文解释显示在标签与说明行。

## 提交前闸门（本仓库没有远端，闸门就是 CI）

```powershell
git config core.hooksPath .githooks     # 每个克隆做一次
```

之后每次 `git commit` 会先跑 `scripts/auto_accept.py --skip-run`（pytest 全绿 → agent doctor →
契约 → 跳过端到端），实测 **16 s**；任一步失败即阻断提交。完整验收（含一次真实仿真）用
`python -X utf8 scripts/auto_accept.py`。临时跳过：`VELCH_SKIP_HOOK=1 git commit ...`。

没有挂 1.4 GB 语料的克隆上，端到端一步会打印 `SKIP` 而不是假 PASS —— 那是较弱的闸门，但要明说。

## 让 AI 调用这套软件

```powershell
python -X utf8 -m velch.agent doctor        # 自检：注册表 72 参数 / 语料 358 算例 / 可写目录
python -X utf8 -m velch.agent manifest      # 12 个工具的 JSON Schema 清单
python -X utf8 -m velch.agent serve         # MCP stdio 服务（2024-11-05 协议）
python -X utf8 -m velch.agent call '{"tool":"capabilities"}'
```

写入口只有一个（`derive_case`：派生新算例，绝不原地改父算例），仿真一律走子进程，
失败给错误码（`gate_failed` 是状态不是错误）。设计与契约见
[AI 接口架构](docs/AI_INTERFACE_ARCHITECTURE_2026-10-22.md) 与
[工具层契约](docs/AGENT_TOOL_LAYER_2026-10-22.md)。

## 语料（算例与运行产物）放在仓库外

1.4 GB 的 `validation/` 语料在 `F:\velch_data\validation\crh380a_m`，仓库里只留判据长文与
`.velch-data.example.json` 模板。解析顺序：`VELCH_DATA_ROOT` → `.velch-data.json` 标记 → 仓内
`validation/`；缺语料时测试整体 skip 而不是报错。详见 [validation/INDEX.md](validation/INDEX.md)。

**当前通过的是合成算例的数值检查，尚未完成真实道岔的几何/材料标定或与 Simpack、实测数据的物理验证。**
车体与转向架采用小转角降阶坐标；轴箱并入轮对。它不能代替完整 3D 多体车辆、柔性轨道有限元、
齿轮齿条啮合或状态反演求解器。第二版的来源、方程、Simpack 只读连接证据与限制见
[车辆模型说明](docs/VEHICLE_V2_DESIGN_AND_EVIDENCE.md)。

## 快速运行（Windows PowerShell）

在 `F:\ai道岔状态反演辨识\Velch` 中：

```powershell
python -m pip install -e .
python examples\make_vehicle_v2_case.py
velch run-vehicle examples\vehicle_v2\case.json --output examples\vehicle_v2\output
python diagnostics\vehicle_v2_checks.py
python examples\make_synthetic_case.py
velch run examples\synthetic_transfer\case.json --output examples\synthetic_transfer\output
python -m pytest -q --basetemp .pytest_tmp
python diagnostics\final_review.py --prr "H:\总的齿轨项目\总和1\直逆_修改降低值后设计 -上坡度\RACK_RAILWAY_VEHICLE - XNEW - M\database\Profile_Mileage_ATG_57.85.prr"
```

不安装时可执行：

```powershell
$env:PYTHONPATH='src'
python -m velch run examples\synthetic_transfer\case.json --output examples\synthetic_transfer\output
```

两种求解都输出 `history.csv` 与 `manifest.json`。前者包含时间、各轴里程、车辆和轨道状态、接触力与活动标志；后者包含算例与轮廓 SHA-256、坐标顺序、单位、求解器设置和质量门。求解失败返回非零退出码；不会出现交互式 `input()`。

### 慢？用 `--fast` 预置（默认不改物理）

算例声明的求解器是为了**和 Simpack 对齐**（`DOP853` + `max_step=1e-4`），1.2 s 整车要 ≈850 s。
日常看趋势、扫参数时用实测预置，快一个量级：

```powershell
velch run-vehicle validation\crh380a_m\case_full12_cap05.json --output out_fast --fast
#   --fast = BDF + 解析雅可比 + rtol 1e-4 + max_step 1e-3
```

| 算例 | 声明配置 | `--fast` | 峰值偏差 | 最大侵入偏差 |
| --- | --- | --- | --- | --- |
| `case_full12_cap05.json`（1.2 s 整车） | 850 s / nfev 331 949 | **79 s / 58 113** | 最差 0.11 kN | 550.54 vs 551.89 µm |
| `case_frog_N_strip05.json`（0.05 s 辙叉） | 17.8 s / 10 253 | **3.7 s / 1 553** | 最差 0.30 kN | 155.03 vs 154.77 µm |

脱空样本数不变，两种都 `numerically_checked`。**要出报告数字就用声明配置**；`--fast` 只适合趋势与脚本扫描。
单项覆盖也支持：`--method BDF --jacobian analytic --rtol 1e-4 --max-step 1e-3`（显式参数优先于 `--fast`）。

覆盖不会"就地改算例"：它写一份派生算例到 `<输出目录>\case_used.json`（型面引用改成绝对路径），
再拿它去跑，因此 `manifest.json` 的 `case_sha256`、`case_snapshot.json` 与实际设置永远一致。
命令行输出里的 `solver` 段会同时列出 `declared` 与 `effective`。

## 单轮对基础内核与源代码对应关系

| Velch 模块 | 职责 | 与 SDITT MATLAB 的关系 |
| --- | --- | --- |
| `profiles.py` | TXT/CSV/PRR 轮廓、SI 单位、哈希、里程插值与同里程事件 | 对应截面里程表和 `Get_Profile_P1_Through_210624.m` 的流程；**独立解析与选择规则** |
| `contact.py` | 图形截面候选、法向/切向力 | 用 `Multi_Con_250812.m:417–418` 的正侵入 (3/2) 幂结构与 `:997–1006` 的三次饱和多项式；修复零蠕滑 `0/0` |
| `model.py` | 明确的 SI 参数、自由度、输入来源与算例契约 | 替代主 MATLAB 脚本内分散的硬编码和隐式工作区依赖 |
| `solver.py` | 轮轨作用反作用、质量/支承/重力组装、DOP853/Radau 积分、质量门 | 参考 `WR_Force_ModalFT.m` 与 `Integration_Park.m` 的**模块分层**，不复制其矩阵或积分公式 |
| `cli.py` | 无交互执行、截面检查、结构化错误与输出 | 便于批处理及以后接 MCP/反演控制器 |

Simpack 2021x 只读逆向结果说明“任务入口 → 方法分发 → 状态推进 → 结果/停止状态”的实现层次；它**没有**给出可信的内部轮轨接触公式。本软件未调用私有 Simpack 函数，也未把本模型说成 Simpack 数值等价。相关本机证据位于 `..\simpack-mcp-2021x\docs\SIMPACK_SOURCE_GUIDE_TURNOUT_V1.md` 和 `..\SDITT_analysis\SDITT_REA_CODE_AUDIT_V1.md`。

## 关键方程和单位

令 (q=[y_w,z_w,\phi_w,\theta_w,y_{r1},z_{r1},\ldots])，各自由度按质量对角阵 (M) 满足 (M\ddot q=Q_{support}+Q_{gravity}+Q_{contact}+Q_{drive})。轮对纵向位置 (x(t)=x_0+Vt) **由外部规定**，没有求解车辆纵向平动。

接触几何在同一横向坐标 (y) 比较轮下表面和轨上表面，近似法向侵入量为

\[
\delta=\max\!\left(0,\frac{z_r(y)-z_w(y)}{\sqrt{1+(\partial z_r/\partial y)^2}}\right).
\]

每根钢轨只取一个最大侵入候选；多根轨可以同时承载。此“图形截面”假设不覆盖倒扣、复杂轮缘多点接触。PRR 原始点列如同一 `y` 有多个 `z`，轨面取最大 `z`、轮下表面取最小 `z`；这是一项**显式简化**，不是 Simpack 的轮廓搜索方法。

法向弹力使用 (F_e=\frac43 E^*\sqrt{R^*}\delta^{3/2})，其中 (E^*\) 单位 Pa、(R^*\) 单位 m；它是有效半径的简化 Hertz 模型，与 SDITT 椭圆接触/STRIPES 并不等价。法向阻尼另定义 (F_d=c_n\sqrt\delta\,\dot\delta)，总力截断为 (F_n=\max(0,F_e+F_d))。`c_n` 的单位为 N·s·m⁻³ᐟ²，由算例显式提供；此式不是从 SDITT 的 Hu–Guo 阻尼直接移植。有效半径目前是**输入参数**，没有从 PRR 曲率自动可靠地计算。该 Hertz 球面有效半径形式也见 [CompuTiX 的接触模型文档](https://computix.gitlabpages.inria.fr/computix/db/d6e/group__Hertz.html)；[Project Chrono 的接触接口](https://api.projectchrono.org/classchrono_1_1_ch_default_contact_force_torque_s_m_c.html)同样明确要求侵入量和有效曲率半径作为输入，而不意味着两者算法等价。

纵向/横向线性蠕滑需求为 (P_x=-C_x v_{slip,x}/V_{ref}\)、(P_t=-C_t v_{slip,t}/V_{ref}\)，其中 (V_{ref}=\max(|V|,V_{floor})\)。令 (P=\sqrt{P_x^2+P_t^2}\)、(L=\mu F_n\)。当 (P=0) 或 (L=0) 时切向力**严格为零**；否则若 (P\le3L)，大小取 (L[(P/L)-(P/L)^2/3+(P/L)^3/27]\)，大于此范围取 (L\)，方向沿 (P_x,P_t)。此多项式直接对应 SDITT `Multi_Con_250812.m:997–1006` 的计算形状，但当前只使用两个蠕滑分量，没有复现其完整 Kalker 系数、旋转蠕滑或 FASTSIM。

所有算例值在 JSON 中使用明确的 SI 单位和来源字段。`examples/synthetic_transfer` 的质量、刚度、模量、摩擦系数及速度是**透明的演示参数**，不能当作 07(009) 道岔实测值。

## 截面与真实数据

```powershell
velch inspect-profile "H:\...\database\Profile_Mileage_ATG_57.85.prr" --format prr --surface rail_top
```

已在 H 盘现有 PRR 上实测只读解析：原始 1998 点经 `rail_top` 图形包络变为 1448 个唯一横坐标点，其中 550 个重合横坐标点被折叠。读入成功**不等于**该 PRR 在 Velch 中已完成坐标对齐或动力学验证。配置真实轮廓前，必须确认文件 `type`、`units.len`、左右手坐标、轮对中心与轮廓原点、轨距、里程原点、支承参数、轮对状态和接触材料。遇到同里程不同截面，`ProfileSeries` 在未指定 `event_branches.before/after` 时拒绝计算；不会把两份截面平均。

当前仅支持数值列为 `y,z` 的 TXT/CSV、单位为 `m` 的 PRR；TXT/CSV 可在算例里标 `m` 或 `mm`。对于真实 H 盘模型的 5 个同里程不同 PRR 事件，分支规则仍需从工况和官方结果核对；Velch 不会自行猜测活动截面。

### 刚性与柔性轨道案例

v2 车辆案例可选择三种轨道：`rigid` 固定轨道（0 个轨道自由度）、`local_compliant`（每个轮轨补丁独立的横/竖弹簧质量，当前缺省）和 `modal`（由独立模态交换 JSON 驱动的降阶柔性轨道）。生成刚性和模态演示案例：

```powershell
python examples\make_track_model_cases.py
$env:PYTHONPATH='src'
python -m velch run-vehicle examples\vehicle_v2\case_rigid.json --output examples\vehicle_v2\output_rigid
python -m velch run-vehicle examples\vehicle_v2\case_modal_synthetic.json --output examples\vehicle_v2\output_modal_demo
```

`track_modes_synthetic.json` 是合成占位数据，只用于演示求解器接口，绝非 Simpack 或有限元导出结果。Velch 目前可以从 `.spck` 读取被引用的 PRR 几何目录，但不能导入并运行 Simpack 的刚性/柔性轨道动力学模型，也不能直接解析 `.fbi/.fem` 模态数据。需要由可信来源导出并核实模态质量、频率、归一化、振型坐标后，才能替换占位文件开展工程分析。

查看真实 `.spck` 只读截面目录：

```powershell
velch inspect-simpack-track "path\to\main_model.spck" --model-root "path\to\model-root" --output diagnostics\simpack_track_catalog.json
```

本机 H 盘模型目录扫描到 192 条截面引用、190 个唯一 PRR、0 个缺失引用和 5 个同里程异截面位置。当前扫描未识别模态文件引用，不代表可以断言模型没有柔性体；导入结果仍需人工确认截面分支和坐标约定。

架构和模块边界见 [v0.4 软件架构说明](docs/SOFTWARE_ARCHITECTURE_V0_4.md)。现有 Python 求解器不在运行时调用 MATLAB；MATLAB 文件只作为方程结构和参数来源。Simpack 逆向分析所得对象层级也不等于完整恢复其内部求解方程。

可借鉴的开源轮轨接触代码、许可及适用于 Velch 的改进顺序见 [轮轨接触算法调查](docs/OPEN_SOURCE_WHEEL_RAIL_CONTACT_SURVEY_2026-10-19.md)。

CONTACT 原生 DLL 已在本机编译并通过 module 3 球面 Hertz 探针；构建、解析基准与车—道岔求解接入门见 [CONTACT 接入记录](docs/CONTACT_NATIVE_INTEGRATION_2026-10-19.md)。当前车辆动力学计算尚未切换到 CONTACT。

## 验证与现有限制

`tests/` 包含无接触严格零力、零蠕滑有限性、摩擦上界、PRR 单位/类型、同里程事件、轮轨反力以及完整合成运行。`diagnostics/step_convergence.json` 对最大步长减半后比较轮对末态与各轨峰值；`diagnostics/static_energy_probe.json` 检查固定截面、零阻尼、零摩擦极限的机械能变化。合成算例质量门和输入哈希在 `examples/synthetic_transfer/output/manifest.json`。

`diagnostics/final_review.json` 汇总两种运行的质量门、输入哈希、CSV 完整性、步长与能量探针、wheel 包内容、Simpack 模型关系只读证据，以及可选的真实 PRR 解析。旧版 wheel 位于 `dist/`；v0.4 使用本地源码安装步骤，不要拿旧 wheel 当作 v0.4。

目前 v2 已有降阶车体、转向架、轮对与线性悬挂耦合，但没有完整 3D 多体车辆、钢轨 FEM/模态导入、支承非线性、轮缘多点接触、纵向车辆动力学、齿轮齿条分段啮合、状态反演优化器或与实测的误差验证。这些属于后续独立模块，不以现有合成算例合格来宣称实现。
