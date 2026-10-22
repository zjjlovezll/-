# Velch 0.4.14 发布说明

发布日：2026-10-23　｜　和 0.4.13 的差别：**第一次运行不再靠猜**。界面与求解器一行没改。

## 新增：`velch selfcheck`

```
velch-cli.exe selfcheck
```

六项，中文输出，每条失败都写着怎么补：

| 检查 | 通过条件 |
|---|---|
| 版本与发布说明 | 当前版本有对应 `docs/RELEASE_NOTES_*.md`（冻结包里查 exe 旁的 `docs/`） |
| 算例语料 | 目录里有 `case_*.json`；**显式设了 `VELCH_DATA_ROOT` 却为空算失败** |
| Tk 界面库 | `tkinter` 可导入 |
| 绘图库 matplotlib | 可导入（缺只警告：④⑥⑦ 屏降级为文字） |
| Simpack 模型 | 设了环境变量时路径必须存在（没设只警告） |
| 可写目录 | `.agent` 可建、可写、可删 |

退出码：0 = 可以启动（可能有可选项未满足），2 = 有必须修的东西。

本机实测：

```
[PASS] 版本与发布说明   0.4.14，发布说明在位
[PASS] 算例语料      358 个算例，位于 F:\velch_data\validation\crh380a_m
[PASS] Tk 界面库     tkinter 可用
[PASS] 绘图库 matplotlib  可用
[WARN] Simpack 模型  未设置 VELCH_SIMPACK_MODEL / VELCH_SIMPACK_ROOT
[PASS] 可写目录      ...\.agent 可写
结论：可以启动，1 项可选未满足（上面标了怎么补）。
```

## 冒烟测试多了一步

`packaging/smoke_test.py` 现在 **7 步**：selftest / cli-run / **selfcheck** / missing-corpus /
agent-contract / unicode-path / install-dir-untouched。新增那步要求冻结版 `selfcheck` 退出码 0、
`[FAIL]` 一个都没有、`[PASS]` 至少 4 项（版本、语料、Tk、可写目录对一个能跑的包不是可选项）。

## 仍然没有的五项

1. Simpack 模型的横向布置未导入（该模型左轨只有 2 站，单侧导入等于改轨距，被闸门拒绝）。
2. Simpack 侧的轴重、刚度、阻尼只作对照，不写进算例。
3. 没有代码签名。
4. 只读安装目录（`C:\Program Files\Velch`）的 ACL 步骤仍需手工（O009）。
5. `physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`（差异已量化，未标定）。

## 验证

- `pytest` **562 passed, 1 skipped**
- `scripts/auto_accept.py --skip-run` → `verdict: ACCEPT`（tests / doctor / contract / invariants）
- `packaging/smoke_test.py` → 7 步全 PASS
