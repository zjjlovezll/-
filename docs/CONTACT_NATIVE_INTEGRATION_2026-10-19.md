# CONTACT 原生接触求解接入记录（2026-10-19）

## 当前结果

Velch 新增 `contact_native.py`：只读取官方开源 CONTACT 的 Python 接口和原生动态库，不复制或重命名 Velch 原有的力学公式。`contact-native-status` 可检查接口、DLL 和哈希；`contact-hertz-probe` 在 DLL 可加载后用官方 module 3 对指定局部 Hertz 接触做 16/32/64 等网格的收敛与耗时记录。所有输入在 JSON 中使用 SI；调用前转换为 CONTACT 的 mm、mm/s、N、N/mm²、1/mm。输出保持 CONTACT 局部坐标原始方向。

本机从 [CONTACT 官方仓库](https://github.com/eve70a/CONTACT) 克隆源码到 `..\CONTACT_reference`（提交 `5644061ade1b0214e7ce70d780066f630d05f782`）。用户已安装 Intel oneAPI 2026.1 的 ifx 与 oneMKL，安装位置为 `D:\Program Files (x86)\Intel\oneAPI`。用 `..\CONTACT_reference\toolchain\build_contact_windows.ps1` 编译出 `bin\contact_addon_win64.dll`，大小 55,618,560 字节，SHA-256 为 `DBEEE1EA868600C9B828B392575E70439D28EE8FD27712425A0564B9FAD57531`。构建日志在 `..\CONTACT_reference\toolchain\build_contact.log`。源码只做了一处编译器兼容调整：`src\m_temperature.f90` 的同一 `associate` 语句内，将 `row1st/rowlst` 的右侧引用从同语句定义的别名 `igs` 改成 `outpt%igs`；计算表达式未变。检测报告为 `diagnostics/contact_native_status.json`。**当前车辆求解器仍使用 `contact.py` 的简化接触力，不得把已有车辆结果称为 CONTACT 结果。**

真实原生探针已成功加载此 DLL 并运行官方 CONTACT module 3。示例对称间隙对应等效球半径 0.46 m；按相同材料的 Hertz 球面—平面解析式，法向力为 104,343.538 N。16、32、64 网格分别得到 104,516.302、104,359.035、104,352.209 N；最细网格相对解析值差 0.00831%。32 到 64 网格法向力变化约 0.00654%，纵向切向力变化约 0.500%。64 网格纵向切向力为 −13,778.519 N，合力占摩擦上限约 44.0%；局部切向力方向仍需与 Velch 车体坐标标定。详见 `diagnostics/contact_hertz_grid_study.json`。这些是**合成局部接触**结果，不能证明真实道岔 PRR/PRW、车辆时域积分或 Simpack 对照已通过。

## 复现实验命令

```powershell
cd 'F:\ai道岔状态反演辨识\Velch'
$env:PYTHONPATH='src'
python -m velch contact-native-status --contact-root '..\CONTACT_reference' --output diagnostics\contact_native_status.json
python -m velch contact-hertz-probe examples\contact_hertz_probe.json --contact-root '..\CONTACT_reference' --grids 16 32 64 --output diagnostics\contact_hertz_grid_study.json
```

第二条命令已在真实 CONTACT DLL 上成功执行；缺 DLL 时仍明确失败，不退回 Velch 的 Hertz 公式。示例是**合成球面对平面**局部接触，两个 `effective_gap_curvature_*_per_m` 是间隙二次项系数 `1/(2R)`；不是用户道岔轮廓自动提取值。报告的 `analytic_benchmark` 用独立 Hertz 解析式检查法向力和库仑界限。`calculate_time_s` 只量 `cntc.calculate`，`wall_time_s` 包含初始化和读取结果。当前每个网格独立初始化一次，不能据此推断积分中复用 CONTACT 实例的真实吞吐量。相对最细网格的差异只表示网格收敛；解析基准仅适用于这个对称弹性球面算例。

## 将 CONTACT 变成车—道岔动力学接触求解的必要步骤

1. **几何与坐标**：优先使用官方 module 1 读取 PRW/PRR，核对每一轨实体和里程、轮对中心、滚动半径、侧滚、偏航、速度及活动分支。用户 H 盘模型存在 `Wheel_LM.prw` 与大量 PRR，但仍需验证 Simpack 到 CONTACT 的坐标变换。module 3 只解指定接触斑，不能替代接触点定位。道岔基本轨、尖轨、翼轨的并行接触必须分别保持实体 ID 和作用反作用。
2. **力与功率**：用解析球面/平面和官方示例检查模块 3 法向载荷、面积、黏滑面积、正负纵横蠕滑及旋转蠕滑。再由 module 1 输出位置/法线与局部力映射到 Velch 轮对和轨道自由度，验证力矩、作用反作用、滑移耗散。Velch 当前法向阻尼独立于 CONTACT 弹性求解；若需阻尼，应单独定义和校准，不能隐式叠加。
3. **同工况对照**：按相同轮轨文件哈希、坐标、载荷、速度、材料、摩擦与积分条件，比较 CONTACT、Simpack 和已知解析结果。特别检查踏面—轮缘过渡、两轨同时承载、同里程异截面事件和接触丢失/再建立。报告接触位置、力、面积、峰值与时间步收敛。
4. **速度设计**：原生库只初始化一次，按轮对/轨实体保存 result-element，连续时间步使用历史状态热启动；首先测量真实车道岔算例的 `calculate` 耗时和积分 RHS 调用次数。若在线开销太高，再对里程、横移、侧滚、法向接近量、三种蠕滑构建自适应稀疏表；在切换/轮缘/多斑区域加密，留出独立样本验证插值误差，超界时回到原生 CONTACT。表的配置和 CONTACT 二进制哈希随仿真结果保存。只有通过误差与耗时双门后才启用快速路径。

## 接入门

原生 DLL 能加载只是第一门；还需输出解析基准、网格收敛、实际 PRR/PRW 的接触点与力向、至少一个车辆短时积分的能量/反力及运行时间。所有门通过之后，才能在车辆算例里增加显式的 `contact_backend=CONTACT`。切换前保留原求解器，避免产生名称为 CONTACT、实际仍由当前简化公式计算的结果。

依据：[CONTACT 源码、Python 接口和 Windows 构建文件](https://github.com/eve70a/CONTACT)，[美国联邦铁路局关于 CONTACT module 1 与 module 3 的说明](https://railroads.dot.gov/sites/fra.dot.gov/files/2024-05/Friction_Modeling%201.pdf)。
