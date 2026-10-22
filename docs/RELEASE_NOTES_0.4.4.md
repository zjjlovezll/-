# Velch 0.4.4 发布说明（2026-10-23 凌晨）

0.4.3 之后只有一处用户可见的改动：**被拒绝时，报错会告诉你换个里程换到哪里。**

## 变了什么

`velch-cli.exe simpack-case … --x-start 75.0` 现在会这样说：

```
the imported surface sits +11.24 mm against the template's at 79.867 m, beyond the 8.0 mm this run
can plausibly seat (measured here: 5.18 mm seated, 11.91 mm did not). Those stations are
switch/blade surfaces rather than one running surface.
The nearest start that measures within 3 mm is 72.7 m (worst 1.24 mm).
Or use --keep-profiles, or pass --allow-surface-drop and read the run before quoting it
```

- 候选起点来自模型自己的站位里程，且必须保证 `起跑 + 车速 × 时长` 不越出模型覆盖；
- 一个合格窗口都没有时，明说 `No window in this model measures within 3 mm of the template`；
- **只是建议**，不会替你改 `--x-start`。

## 为什么不能承诺"换过去就能跑"

60.0 / 65.0 / 70.0 m 三档的冠部高度与模板差不到 0.1 mm，静平衡仍然失败——转辙区的断面**形状**
逐站在变。这一条是 0.4.3 就写明的 O008，0.4.4 没有改变它，只是把"往哪换"从空话变成具体里程。

## 验证

- `pytest` **503 passed, 1 skipped**。
- `packaging/smoke_test.py` → ACCEPT（自检 / 跑算例 / 缺语料 / 中文空格路径）。
- 提交闸门 `verdict: ACCEPT`；物理数值未动。
