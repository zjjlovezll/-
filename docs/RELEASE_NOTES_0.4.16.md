# Velch 0.4.16 发布说明

发布日：2026-10-23　｜　和 0.4.15 的差别：**Simpack 导入的拒绝开始带结构化数字**。

## 这一版改了什么

- `SimpackCaseError` 新增 `detail` 字段；`simpack-case --import-lateral` 因轨距变化被拒时，
  CLI 输出的 JSON 里多一个 `detail` 对象（`code/gauge_mm/other_side_stations/both_sides_possible/ways_out`）。
- 只有"有数字"的失败才带 `detail`；目录不存在之类的失败保持原样。
- 文档：`docs/SIMPACK_IMPORT_2026-10-22.md` 第十节补 JSON 样例；`docs/BUGS.md` 的 O008 记为
  "已说明 + 机器可读"，并写明什么条件下才能真的导入两侧。

## 为什么这条值得发一版

O008 的结论原来是散文：**"这个模型左轨只有 2 站，所以两侧一起导入不可能"**。散文没法被脚本使用，
于是每次有人问"能不能两侧导入"都得重新读一遍句子。现在它是 `detail.both_sides_possible == false`
加 `detail.other_side_stations == 2`——脚本、MCP 工具、界面都能直接分支。

## 仍然没有的四项

1. Simpack 横向布置的双侧导入（需要换一个两条轨都有断面表的模型）。
2. Simpack 侧轴重/刚度/阻尼只作对照。
3. 没有代码签名。
4. `physics_validation_status` 仍未标定。

## 验证

- `pytest` **568 passed, 1 skipped**
- `packaging/smoke_test.py`（默认 7 步 / 加 `--readonly-acl` 8 步）→ ACCEPT
