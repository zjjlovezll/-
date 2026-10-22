# CRH380A_M 刚性模型真实 Simpack 验证记录（2026-10-19）

## 判定

`G:\研究生\动力学\CRH380A_纯刚性模型\database\database` 可以用作 **Simpack 刚性车辆与轮轨几何基准**。已在 F 盘任务副本上完成 Simpack 2021x 的 0.05 s 和 1.2 s 时间积分，获得可追溯的 SBR。Velch 目前只能直接导入轨截面目录，尚不能把 `CRH380A_M` 的完整车辆拓扑和力元导入其求解器，因此本记录 **不表示 Velch 与 Simpack 动力学吻合**。

## 输入与模型检查

- 从 G 盘只读复制 256 个 `.spck/.prr/.prw/.trc/.obj` 输入到 `simpack-mcp-2021x/validation/CRH380A_M_2026-10-19/database/database`。逐文件 SHA-256 核对无遗漏、无差异，见 [副本校验](../../simpack-mcp-2021x/validation/CRH380A_M_2026-10-19/copy_hash_audit.json) 和 [复算脚本](../../simpack-mcp-2021x/validation/CRH380A_M_2026-10-19/verify_source_copy.py)。G 盘模型与历史结果未改动。
- 入口 `mbs_db_substructure/CRH380A_M_Carbody.spck` 引用前后转向架、轮对；Simpack MCP 读到 21 个刚体、21 个运动副、79 个力元、4 个轮轨接触、8 个轮轨副、4 个轮对、4 根轨、11 个轨道对象、279 个代换变量。模型设定 `$_Speed=350 km/h`、结束时间 `1.2 s`。源入口 SHA-256 为 `ab291570643d582781bc6ae420df9ffa463f3b186eb2ac50cde318f673f48172`。
- 轮对使用 `LMA.prw`。轮对模型引用 238 条轨截面记录，指向 233 个唯一 PRR；均可定位并解析，里程范围 0–150 m，10 处同里程有不同截面。见 [Velch 目录](../diagnostics/crh380a_m_track_catalog.json)、[Velch 文件审计](../diagnostics/crh380a_m_database_audit.json) 和 [Simpack MCP 轮廓审计](../../simpack-mcp-2021x/validation/CRH380A_M_2026-10-19/profile_audit.json)。Velch 在 50.578 m 等位置需显式指定 `before/after`，不可自动平均。

## 真实 Simpack 基准

| 项目 | 0.05 s 短工况 | 1.2 s 完整工况 |
|---|---:|---:|
| MCP 任务号 | `c2a3fdc4fe9448b0a3489c9c9c8f263c` | `a47bc7d9e48f40b08628147bfab5c3f4` |
| 求解器退出码 | 0 | 0 |
| 求解日志 | `successfully finished` | `successfully finished` |
| 结果文件 | `model.output/350.sbr` | `model.output/350.sbr` |
| 时间点 | 101 | 2401 |
| 时间范围 | 0–0.05 s | 0–1.2 s |
| 标量通道 | 4877 | 4877 |

完整工况 SBR 的 SHA-256 为 `fa4fdc814c3208922e5d44d7016426a9a0816458b3dfec6b0150944e0942c87d`。 [结果摘要](../../simpack-mcp-2021x/validation/CRH380A_M_2026-10-19/result_summary.json) 与 [复算脚本](../../simpack-mcp-2021x/validation/CRH380A_M_2026-10-19/summarize_case.py) 记录了通道路径、数值范围和同里程截面位置。完整工况前 101 点与短工况在时间、车体 X、前轮对 X、前轮对左右轮轨力 Z 四类通道上逐值相同。

完整工况中，车体 X 由 13.5 增至 130.1671295，前轮对 X 由 23.5 增至 140.1671295；位移约 116.6671 个模型长度单位，与 350 km/h 的设定相符。前轮对 X 经过 50.578 m 的插值时刻约为 0.278515 s，并经过全部 10 个同里程双截面位置。前轮对左、右轮轨力 Z 通道范围分别为 34364.13–90716.28 和 27672.40–134969.88 **结果数值单位**。Simpack Post QSA 未在这些结果通道暴露单位；未独立核对力元坐标系、正方向和单位前，不把这些数字标为 N，也不把 X 坐标越过截面里程等同于实际接触点经过该截面。

完整工况日志含 300 条轮廓预处理警告（陡斜率点被移除）和 16 条低蠕滑参考速度警告，无 `ERROR:`，求解成功。警告必须保留：轮廓经 Simpack 预处理后可能与原始 PRR 点列不完全相同，Velch 对比时需核对处理后几何与接触算法。历史 `CRH380A_M_Carbody.output/*.sbr` 未纳入基准，因其模型来源和工况不能仅凭文件名确认。

## MCP 修复与复查

- MCP 轮廓解析已覆盖数据库的 `wheel_rail_profiles` 目录；本地复算得到 238 引用、233 唯一文件、0 错误、10 个同里程警告。此前常驻 MCP 服务在未重启状态下仍按旧代码报“缺失”。
- MCP CLI 结果发现已按 `model.output` 中实际 `.sir/.sbr/.mat` 文件查找，解决本模型输出名为 `350` 时把退出码 0 误标为失败的问题。Simpack Post 的空查询参数也已修复。常驻 MCP 服务尚需重启才能加载这些改动；以上两个任务在旧进程中的 `state=failed` 是结果发现误报，求解器日志、退出码与结果文件证实求解完成。
- MCP 测试：`python -m pytest -q --basetemp .pytest_tmp_crh380a_suite`，50 项通过。输入副本 SHA-256：256/256 匹配。结果时间轴严格递增，四个对照通道长度一致。

## 下一道验证门

1. 提取 `CRH380A_M` 的质量、惯量、悬挂刚阻尼、接触配置、初始状态和各力元坐标系，建立到 Velch 自由度的显式映射；不能映射的元件单列。当前 `Velch run-vehicle` 接受其自有 JSON 案例，`inspect-simpack-track` 只导入轨截面目录。
2. 核对 10 处同里程截面的 Simpack 切换语义，以及 PRR 预处理后几何与 Velch 使用点列的差异。
3. 在同一车辆参数、轮轨几何、速度、坐标系、接触算法与输出采样下，比较位置、轮轨力和事件时刻，并给出误差指标；在完成前不宣称 Velch 动力学验证通过。
