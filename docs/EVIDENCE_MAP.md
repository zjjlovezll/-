# 证据地图：这一版凭什么可以说「可以发布」

由 `scripts/evidence_map.py` 生成——里面的结果都是**跑出来的**，不是抄来的。`tests/test_evidence_map.py` 会检查这里引用的每个文件都还在、每条命令都能解析，所以这一页没法悄悄过期。

- 当前提交 **`d519c28`**
- 标签 23 个：`v0.4.6`、`v0.4.7`、`v0.4.8`、`v0.4.9` …
- 全仓测试 **608 passed, 1 skipped**

## 逐项证据

| 目标分项 | 凭什么 | 复核命令 | 最近一次结果 |
|---|---|---|---|
| **① 代码整理与稳定** | 架构规则、`TODO/FIXME` 计数、文档索引与版本一致性都由测试守着 | `python -X utf8 -m pytest tests/test_architecture_rules.py tests/test_docs_index.py -q` | **21 passed, 0 skipped**（exit 0）<br>期望：全绿；索引覆盖 `docs/*.md` 每一篇；`__version__` 有对应发布说明 |
| **② 全仓 bug 清理** | 缺陷账本归零：已修记 B 编号，仍开记 O 编号并写明理由 | `python -X utf8 scripts/auto_accept.py --skip-run` | `ACCEPT` — tests PASS、doctor PASS、contract PASS、invariants PASS（exit 0）<br>期望：四步全 PASS（tests / doctor / contract / invariants） |
| **③ 界面美观与可读性** | 截断由布局测试量出来，不是靠看图；对比度由主题测试算出来 | `python -X utf8 -m pytest tests/test_ui_layout.py tests/test_ui_scale.py -q` | **13 passed, 0 skipped**（exit 0）<br>期望：7 屏 × 100%/130% 无被裁控件；`contrast_violations() == []` |
| **④ 安装包** | onedir 双 exe（窗口版 + 控制台版），装完能双击运行，并在包内跑一次真实算例 | `python -X utf8 packaging/build_installer.py && python -X utf8 packaging/smoke_test.py` | `ACCEPT` · 8 步 · 失败 0 · 跳过 0（`packaging_smoke_20261023-081858.json`）<br>期望：冒烟 6 步全 PASS：selftest / cli-run / missing-corpus / agent-contract / unicode-path / install-dir-untouched |
| **⑤ 读取 Simpack 模型** | 只读几何导入（catalog → case），导入后由静平衡决定能不能算 | `python -X utf8 -m velch inspect-simpack-track <db>/substructure/<x>.spck --model-root <db> --output catalog.json` | 未设置 `VELCH_SIMPACK_MODEL`/`VELCH_SIMPACK_ROOT`（本机未挂模型；细节见文档）<br>期望：`geometry_readable = true`、`missing_profile_references = 0`；派生算例 `seats: true` 后跑出 `numerically_checked`（加 `--with-run` 才跑这一段） |
| **物理数值不变** | 复算门：归档 2401 帧 + 一次 `--fast` 现跑，与 committed 参考值比较 | `python -X utf8 scripts/physics_invariants.py` | `UNCHANGED`（整程峰值 170.61 kN），exit 0<br>期望：VERDICT: UNCHANGED |

## 证据文件与最后一次改动

| 文件 | 内容 | 最后改动 |
|---|---|---|
| [`docs/ARCHITECTURE_2026-10-21.md`](../docs/ARCHITECTURE_2026-10-21.md) | 分项 1 的细节 | `b73a932 2026-10-22` |
| [`docs/CHANGELOG_DOCS.md`](../docs/CHANGELOG_DOCS.md) | 分项 1 的细节 | `d519c28 2026-10-23` |
| [`tests/test_docs_index.py`](../tests/test_docs_index.py) | 分项 1 的细节 | `3289507 2026-10-23` |
| [`docs/BUGS.md`](../docs/BUGS.md) | 分项 2 的细节 | `d519c28 2026-10-23` |
| [`scripts/auto_accept.py`](../scripts/auto_accept.py) | 分项 2 的细节 | `20aa168 2026-10-23` |
| [`tests/test_ui_layout.py`](../tests/test_ui_layout.py) | 分项 3 的细节 | `03cea5d 2026-10-23` |
| [`tests/test_ui_scale.py`](../tests/test_ui_scale.py) | 分项 3 的细节 | `e7c1c49 2026-10-23` |
| [`docs/UI_READABILITY_2026-10-22.md`](../docs/UI_READABILITY_2026-10-22.md) | 分项 3 的细节 | `db27a6b 2026-10-23` |
| [`docs/PACKAGING_2026-10-22.md`](../docs/PACKAGING_2026-10-22.md) | 分项 4 的细节 | `03cea5d 2026-10-23` |
| [`packaging/smoke_test.py`](../packaging/smoke_test.py) | 分项 4 的细节 | `03cea5d 2026-10-23` |
| [`packaging/Velch.spec`](../packaging/Velch.spec) | 分项 4 的细节 | `ab90767 2026-10-22` |
| [`docs/SIMPACK_IMPORT_2026-10-22.md`](../docs/SIMPACK_IMPORT_2026-10-22.md) | 分项 5 的细节 | `c05bac1 2026-10-23` |
| [`docs/SIMPACK_COMPARE_2026-10-23.md`](../docs/SIMPACK_COMPARE_2026-10-23.md) | 分项 5 的细节 | `12cea65 2026-10-23` |
| [`src/velch/simpack_case.py`](../src/velch/simpack_case.py) | 分项 5 的细节 | `c05bac1 2026-10-23` |
| [`docs/PHYSICS_INVARIANTS.md`](../docs/PHYSICS_INVARIANTS.md) | 物理不变量 | `20aa168 2026-10-23` |
| [`docs/physics_invariants.json`](../docs/physics_invariants.json) | 物理不变量 | `20aa168 2026-10-23` |
| [`scripts/physics_invariants.py`](../scripts/physics_invariants.py) | 物理不变量 | `20aa168 2026-10-23` |

## 这道门怎么进提交

`Velch/.githooks/pre-commit` → `scripts/auto_accept.py --skip-run`（约 44 s：测试 43 s + doctor + 契约 + 不变量）。启用一次即可：

```powershell
git config core.hooksPath .githooks
```

`python scripts/auto_accept.py`（不加 `--skip-run`）会再加一步端到端：派生算例 → 真跑 0.05 s → 读 manifest。安装包另有 `packaging/smoke_test.py` 六步，跑的是**冻结后的 exe**。

## 不在这张表里的东西

- 与实测数据的标定：没有同一道岔的实测与模型配对，`physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`。
- 与 Simpack 的定量关系只到**逐点差异报告**（`docs/SIMPACK_COMPARE_2026-10-23.md`），不改任何默认值。
- 包未签名；只读安装的 ACL 情形需按 `docs/PACKAGING_2026-10-22.md` 末尾人工验一遍（O009）。
