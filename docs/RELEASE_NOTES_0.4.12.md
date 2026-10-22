# Velch 0.4.12 发布说明

## 这一版新增：物理不变量复算门

`scripts/physics_invariants.py` 把"物理数值不变"变成可执行的检查：从归档的 1.2 s 运行
（不重跑）读八接触峰值、最大侵入、脱空样本、辙叉窗的 rms/主频/三频带，再跑一次 0.05 s
的 `--fast` 现算，与 `docs/physics_invariants.json` 里的参考值逐项比对。

- 归档参考值：整程峰值 **170.61 kN**（`axle2_right`）、前轴右轨 **89.677 kN**、最大侵入
  **551.89 µm**、脱空 **0** 采样、辙叉窗 `rms 9.126 kN` / 主频 `57.14 Hz` / 三频带
  `5.677`、`1.75`、`2.25 kN`、七门 `7/7`、`numerically_checked`。
- 容差：峰值/侵入 ±1.0（kN / µm）、窗口 rms ±0.2 kN、主频 ±1.0 Hz、频带 ±0.2 kN、脱空必须完全
  相同；现跑要求 `numerically_checked`、八接触俱在、七门无失败。
- 已接进提交前闸门（`scripts/auto_accept.py` 第四步，0.2 s），每次提交都会验。

细节见 `docs/PHYSICS_INVARIANTS.md`。

## 顺带修复

- **B025**：`velch.inverse.bands.bandpass` 在 70 样本的短窗上会抛
  `ValueError: Filter not stable due to sum(a) == 0`（上边缘贴 Nyquist）。现在失败时依次收窄
  上边缘重试（0.999 → 0.97 → 0.90 × Nyquist），长记录结果逐位不变。
- 文档索引覆盖到全部 74 篇，并有测试在标题漂移时失败。

## 怎么装

1. 解压 `Velch-0.4.12-win64.zip` 到任意目录（**不要**放进 `C:\Program Files` 之类只读位置）。
2. 双击 `启动 Velch.cmd`，或直接 `Velch.exe`。
3. 语料（`validation/crh380a_m`）不随包发布；设置 `VELCH_DATA_ROOT`，或在
   `%LOCALAPPDATA%\Velch\.velch-data.json` 写 `{"data_root": "F:/velch_data"}`。
4. 命令行：同目录 `velch-cli.exe`（`--help`、`run-vehicle`、`agent doctor|manifest|call`）。

## 验证记录

- `pytest` 544 passed, 1 skipped（skip：未设 `VELCH_SIMPACK_MODEL`）
- `python scripts/auto_accept.py --skip-run` → 四步全 PASS
- `python scripts/physics_invariants.py` → **VERDICT: UNCHANGED**
- 打包冒烟 6 步全过（selftest / cli-run / missing-corpus / unicode-path / readonly-install /
  agent-contract）

## 仍然没有

1. 横向布置：只有单侧断面表时导入会改变轨距，默认拒绝（`--import-lateral` 需显式放行）。
2. 与 Simpack 的对照只到"逐点差异报告"（`docs/SIMPACK_COMPARE_2026-10-23.md`），不是标定。
3. 包未签名（首次运行会有 SmartScreen 提示）。
4. 只读安装的 ACL 情形仍需人工按 `docs/PACKAGING_2026-10-22.md` 末尾步骤验一遍（O009）。
5. `physics_validation_status` 仍为 `unvalidated_against_measurement_or_Simpack`——本版没有改
   任何默认物理参数，也没做标定。
