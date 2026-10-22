# Velch 0.4.19 发布说明

发布日：2026-10-23　｜　和 0.4.18 的差别：**评价屏把"这不是标定"写在判定上方**。

## 这一版改了什么

- ⑤ 评价屏顶部常驻一条黄色横幅：本运行不是标定，判定只在这套参数下成立，并指向
  `docs/BUGS.md`（O008）与 `docs/PHYSICS_INVARIANTS.md`。
- 横幅随卡片宽度换行（`wrap_with`），不写死宽度。

## 为什么值得发

这一屏会输出"通过"，而"通过"最容易被引用成"真实道岔安全"。边界必须在数字旁边，不能只在文档里。

## 仍然没有的四项

1. Simpack 横向布置的双侧导入（需要两条轨都有断面表的模型）。
2. Simpack 侧轴重/刚度/阻尼只作对照。
3. 没有代码签名。
4. `physics_validation_status` 仍未标定——**这条横幅说的就是它**。

## 验证

- `pytest` **583 passed, 1 skipped**
- `packaging/smoke_test.py --readonly-acl` → ACCEPT（8 步）
