# Velch 0.4.35 发布说明

日期：2026-10-26

## 本轮结论

**车辆库与柔性轮对模态集现在真的在安装包里。** 之前 `packaging/Velch.spec` 只收集
`examples/` 与 `docs/`，所以打包版的 `velch vehicle list` 是空的——那读起来像"模型没做"，
实际是"没打包进去"。这一版补上 `vehicles/`（5 台 CRH380A 变体 + `index.json` +
`vehicles/modes/CRH3C_wheelset_fe.json` 1.85 MB 柔性轮对模态集），并修掉随之暴露的第二个问题：
PyInstaller 6 的 `datas` 落在 `_internal/`，而 `vehicle_db._root()` 只查了 `<安装目录>/vehicles`，
所以即使打包了也找不到。现在两个位置都查（与 `selfcheck.docs_roots()` 同一套做法）。

- `VELCH_VEHICLE_DIR` 仍然优先，指向自定义库不变；
- 新测试 `tests/test_vehicle_ship.py` 4 项：两种安装布局各一条、环境变量优先一条、
  模态集确实在库目录里一条（格式 `velch-wheel-modes/1`、33 阶）。

## 验证

- 全仓 `pytest`：813 passed, 1 skipped in 109.64s；
- 冻结版 `velch-cli.exe vehicle list` 列出 5 台车（35 / 38 / 38 / 86 / 90 自由度）；
- `velch-cli.exe vehicle validate CRH380A_M_axlebox` → `合法（字段、正负、左右对称、自由度剖面、出处齐全）`；
- 包体：onedir 198.8 MB（上一版 196.6 MB，多出的是 `vehicles/` 1.9 MB 与模态集 1.85 MB）、zip `Velch-0.4.35-win64.zip` 95.1 MB；
- `packaging/smoke_test.py --readonly-acl` → ACCEPT · 8 步 · 失败 0 · 跳过 0（`reports/packaging_smoke_20261026-094846.json`）；
- 冻结版实测：`velch-cli.exe vehicle list` 从 `_internal\vehicles` 列出 5 台车，`vehicle validate CRH380A_M_axlebox` → 合法；
- 冻结物理未动：静载门 59 680.5769 N / 65.47 µm、八接触峰值 89.68 / 170.61 kN、
  七项门 7/7、DOP853 逐位不变（`scripts/physics_invariants.py` → VERDICT: UNCHANGED）。

## 已知边界（与 0.4.34 相同）

- `physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`；
- 未做代码签名，首次运行会弹 SmartScreen；
- 语料（1.4 GB 算例集）仍不进包，靠 `VELCH_DATA_ROOT` 或标记文件指路。
