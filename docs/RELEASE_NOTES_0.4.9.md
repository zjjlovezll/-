# Velch 0.4.9 发布说明（2026-10-23）

## 这一版装的是什么

与 0.4.8 相同的 onedir 目录包：`Velch.exe`（窗口版）+ `velch-cli.exe`（命令行），双击
`启动 Velch.cmd` 或在资源管理器里双击 `Velch.exe` 都能进入界面。

## 相对 0.4.8 的四处修复

| 编号 | 问题 | 现在的行为 |
|---|---|---|
| B024 | 没挂语料时 ① 屏五个按钮被挤到 94 px（打包版首启必然触发） | 空态提示按卡片宽度折行，按钮恢复完整宽度 |
| — | 界面按钮可能被裁而无人知道 | `tests/test_ui_layout.py` 逐屏量"分配宽度 vs 所需宽度"，1.0/1.3 两档、有/无语料两种环境 |
| — | `tests/conftest.py` 靠扫源码文本决定哪些用例跳过 | 模块显式 `pytestmark = pytest.mark.corpus`（12 个），文本扫描只作兜底；漂移由 `test_corpus_marker.py` 拦住 |
| — | 选实测 CSV 时列是"默默猜"的 | 状态栏报出选中的里程列/力列、还剩几个候选，可下拉改；`x` 不再把 `max_force` 抢成里程列 |

## 0.4.8 起就有的横向布置（本轮仍未变）

`simpack-case --import-lateral` 会把每站冠部横向位置写进 `y_offset_m`，但**默认拒绝**：
只导一侧等于改轨距（实测右轨 −73.78…+102.99 mm、左轨 0 站），超过 5 mm 就抛错并报出
`changes the gauge by +103.0 mm at 80.911 m`。要放行必须显式 `--allow-gauge-change`。
横向布置的正解是双体交接（基本轨/尖轨各自一个 body），仍未做，登记在 O008。

## 验证

- `pytest`：**528 passed, 1 skipped**（有语料）；**389 passed, 140 skipped**（无语料，0 失败）
- `velch.ui --selftest`：7 屏 / 0 报错 / 退出码 0
- 冒烟五步（`packaging/smoke_test.py`）：自检、CLI 实跑、缺语料提示、中文+空格路径、安装目录不被改写
- 闸门：每次提交跑 `auto_accept --skip-run`，`verdict: ACCEPT`

## 仍然没有的

1. Simpack 的**横向布置**（双体交接）未导入——单侧导入会改轨距，故默认拒绝。
2. Simpack 的数只作**对照值**，写进算例的每个物理量仍由人显式给出。
3. 没有与 Simpack 结果的定量对照报告。
4. 无代码签名（Windows 会提示"未知发布者"）；卸载 = 删目录。
5. `physics_validation_status` 仍为 `unvalidated_against_measurement_or_Simpack`。
