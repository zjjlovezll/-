# 整体目标：完成度与差距

**日期**：2026-10-23 · **版本**：0.4.30

一页回答"这个任务做完了吗、还剩什么"。每个"已完成"都能指到一处可复跑的检查。

## 1. 五步目标

| 步骤 | 状态 | 证据（自己跑一遍） | 还剩什么 |
|---|---|---|---|
| ① 代码稳定 | **已完成** | `python scripts/auto_accept.py --skip-run`（tests / doctor / contract / invariants / release-series 全过）；687+ passed | 无阻塞项；`contact.py` 已从 1573 行拆到 384 行 |
| ② bug 清完 | **已完成（账本归零）** | `docs/BUGS.md`：B001–B025 全修，O 系列剩 O005（设计约束）、O008（模型缺左侧断面）；界面「已知问题」窗口直接列出 | O001（语料探测启发式）按设计保留、O005 是刻意不自动映射 |
| ③ UI 美观可读 | **已完成** | `tests/test_ui_layout.py`（7 屏 × 1.0/1.3 两档量按钮是否被裁）、`tests/test_ui_readability.py`、字号 Ctrl+= / Ctrl+- / Ctrl+0 | 只有"更好看"的空间，没有已知读错 |
| ④ 安装包 | **已完成** | `dist_installer/Velch-0.4.30-win64.zip`（约 94 MB）；`packaging/smoke_test.py --readonly-acl` → ACCEPT · 8 步 · 失败 0 | 无签名（需要证书）；只读安装的 ACL 步骤已自动化 |
| ⑤ 读 Simpack 模型算 | **已完成（几何 + 整链）** | `inspect-simpack-track` → `simpack-case`（裁决 seats/不 seats）→ `run-vehicle --fast` → `numerically_checked`；`docs/SIMPACK_IMPORT_2026-10-22.md`、`docs/SIMPACK_COMPARE_2026-10-23.md` | 横向布置不可双侧导入（模型左轨只有 2 站）；与 Simpack 结果只做同窗口数值对照，不是同工况验证 |

## 2. 元件库（后加的一项）

| 能力 | 状态 |
|---|---|
| 弹簧 / 减振器 / 并联 / 衬套（含交叉刚度） | 已完成（0.4.27） |
| 非线性通道（力律 + 工作点雅可比 + 势能） | 已完成（0.4.28） |
| 止挡（含 C1 过渡段）、卸荷阀减振器 | 已完成（0.4.28 / 0.4.29） |
| 查表力元（空气簧曲线、台架曲线） | 已完成（0.4.29） |
| 带内部状态的元件（滞回） | **未做**，需要扩展状态向量 |
| 事件检测 | **未做**，靠积分器缩步 |
| 约束类元件（万向节/齿轮/皮带） | **未做**，架构级 |
| 与 Simpack 元件逐条对照报告 | 已完成到"槽位判读 + 映射表"，缺"台架上两条曲线叠图" |

## 3. 物理可信度（必须一直跟着说）

* `physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`：**没有**做真实道岔的标定；
* 与 Simpack 的对照是同一个 1.2 s 窗口的数值并排（均值 120.32 vs 119.35 kN、峰值 194.29 vs 136.29 kN），
  差异来自模型与断面，**不能**据此说谁对；
* 冻结基线（静载 59 680.5769 N / 65.47 µm、八接触峰值、脱空 0）由
  `scripts/physics_invariants.py` 每次提交前自动复算，动了就红。

## 4. 下一步真正有价值的三件事

1. 把 `CRH380A_M_Wheelset.spck` 读完（轮对/轴箱/一系定位的完整几何），让"车辆数据库"覆盖到轮对级；
2. 元件内部状态 + 事件检测（滞回与间隙的物理，需要求解器配合）；
3. 真实道岔的标定：拿实测轮轨力反演接触刚度/阻尼，把 `physics_validation_status` 从 `unvalidated` 推进一步。
