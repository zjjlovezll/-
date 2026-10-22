# Velch 0.4.11 发布说明（2026-10-23）

## 这一版装的是什么

onedir 目录包：`Velch.exe`（窗口版）+ `velch-cli.exe`（命令行）；双击 `启动 Velch.cmd` 进入界面。

## 相对 0.4.10

1. **冒烟测试从 5 步变 6 步**：新增 `agent-contract`——用冻结版 `velch-cli.exe` 依次跑
   `agent doctor`、`agent manifest`、`agent call {"tool":"capabilities"}`，要求工具数 ≥12、
   `capabilities` 在位、`parameter_count == 72`。这补上了"源码里契约测试全绿、但装出来的那份没验过"
   的空档。
2. **与 Simpack 的定量对照报告**（`docs/SIMPACK_COMPARE_2026-10-23.md`）：同一物理量
   （前轮对垂向支反力之和）在 **79.0–138.5 m** 重叠段逐点比较。均值差 −0.97 kN（0.8%）、
   峰值 194.29 对 136.29 kN（**差 58 kN，同在 80 m 道岔区**）、整段差值 rms 4.57 kN 而单点最大
   偏差 −66.0 kN、三个频带 0.62×/0.31×/0.74×、允许平移时最优位移仅 +0.2 m（里程轴配准正确）。
   **只描述不调参**，且写明"这页不能证明谁对"。
3. 修掉一个假 skip：`test_ui_simpack_dialog.py` 每例新建并销毁 Tk root，第 4 次构造抛 TclError
   就把"显示正常"误判成"没有显示"。改为模块级共享 root → 该文件 8 项全跑，全仓只剩 1 个有明确
   理由的 skip（`no VELCH_SIMPACK_MODEL set`）。

## 验证

- `pytest` **534 passed, 1 skipped**
- `velch.ui --selftest`：7 屏 / 0 报错 / 退出码 0
- 冒烟 **6 步 · 失败 0 · 跳过 0**（含新增的 agent-contract）
- 物理未动：静载门 59 680.5769 N / 65.47 µm、八接触峰值 89.68 / 170.61 kN、七项 manifest 门、
  DOP853 逐位等价

## 仍然没有的

1. Simpack **横向布置**（双体交接）：该模型只在一条轨上有变断面（右 236 站 / 左 2 站），两侧一起
   导入无从做起（O008）。
2. Simpack 的数只作对照值；写进算例的物理量仍由人显式给出。
3. 无代码签名；卸载 = 删目录；只读安装的 ACL 步骤仍手工（O009）。
4. `physics_validation_status` 仍为 `unvalidated_against_measurement_or_Simpack`——对照报告描述差异，
   不构成标定。
