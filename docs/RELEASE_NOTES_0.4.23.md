# Velch 0.4.23 发布说明

发布日：2026-10-23　｜　和 0.4.22 的差别：**首页与证据地图指向三份可复算材料，发布序列成表**。

## 这一版改了什么

- 新增 `docs/RELEASE_SERIES.md`：23 个标签逐行列出，含"这一版解决了什么"，**由脚本生成**，
  并进了自动验收（`release-series` 第五步）。
- `README.md` 新增"这版凭什么可信"：一张表指向证据地图、发布序列、物理不变量。
- 证据地图新增分项「①b 发布物与标签一致」，与它的复核命令。

## 验证

- `pytest` **612 passed, 1 skipped**
- `auto_accept.py --skip-run` → ACCEPT（tests / doctor / contract / invariants / release-series）
- `packaging/smoke_test.py --readonly-acl` → ACCEPT（8 步）
