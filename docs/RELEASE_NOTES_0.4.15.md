# Velch 0.4.15 发布说明

发布日：2026-10-23　｜　和 0.4.14 的差别：**只读安装从"文档里说一句"变成冒烟测试的一步**。

## 这一版改了什么

| 改动 | 影响 |
|---|---|
| 冒烟测试新增第 8 步 `readonly-acl`（`--readonly-acl` 开启） | 复制安装目录、禁写、验证「仍能算 + 自检说得出原因 + 不崩」 |
| `selfcheck` 的可写目录检查不再被 `agent_home()` 的异常打断 | 只读安装下给出 `[FAIL] 可写目录` 与 `VELCH_AGENT_HOME` 的指路，而不是 traceback |
| 文档补三处 | `docs/PACKAGING`（怎么跑第 8 步）、`docs/SELFCHECK`（只读安装的预期输出）、`docs/BUGS`（O009 关闭） |

## 只读安装的实测结论

在被禁写的副本里：

- `run-vehicle --fast` **正常产出** `manifest.json`（安装目录只读不妨碍计算）；
- `selfcheck` **退出码 2**，`[FAIL] 可写目录`，提示把 `VELCH_AGENT_HOME` 指到可写目录；
- 界面（Tk）**仍然可用** —— 这一条是被试出来的：用 `(W)` 禁写会让整个 GUI 报
  `Can't find a usable init.tcl`，因为 `(W)` 包含 SYNCHRONIZE，而 Tcl 用它打开库目录。

所以：解压到只读目录也能算、也能开界面，只是 agent 级功能（派生算例、作业目录、revision 账本）
需要 `VELCH_AGENT_HOME` 指向可写位置。

## 仍然没有的五项

1. Simpack 模型的横向布置未导入（该模型左轨只有 2 站，单侧导入等于改轨距，被闸门拒绝）。
2. Simpack 侧的轴重、刚度、阻尼只作对照，不写进算例。
3. 没有代码签名。
4. ~~只读安装目录的 ACL 步骤仍需手工~~ → **本版自动化**（第 8 步）。
5. `physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`。

## 验证

- `pytest` 全绿（见 `docs/CHANGELOG_DOCS.md` 状态表）
- `packaging/smoke_test.py` 默认 7 步 ACCEPT；加 `--readonly-acl` 后 **8 步 ACCEPT**
- `scripts/auto_accept.py --skip-run` → ACCEPT
