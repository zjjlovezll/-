from pathlib import Path

path = Path(r"F:\ai道岔状态反演辨识\Velch\docs\SPEED_2026-10-20.md")
text = path.read_text(encoding="utf-8")

addition = """## 1.6 复核后修正：每站混合已经是现成的，L2 没有余量

读完 `profiles.py` 的实现后，1.5 的前提要更正：区间缓存 `_interval_cache` 里已经存了每站的
`zA`、`zB`，每次调用只做一次标量混合 `z = (1-f)*zA + f*zB`——也就是说“按站缓存 + 标量混合”
早就实现了，混合本身约 2 µs，不是瓶颈。

于是 L2 的余量重新评估：

- 混合：已最优。
- 曲率数组按站缓存再混合：理论精确，但窗口拟合只有约 25 µs/斑，且要先拿到 `f`，需要把
  `blend_weight` 透传三层；收益接近噪声，风险（再动一次热路径）不划算。
- 真正的大头仍是每次调用重建合并网格 + 两次 `np.interp` + 斜率差分，这部分**依赖当前轮对的
  横向位置**，本质上不能跨调用复用。

结论：**L2 作为“接触表”没有可观余量**。要再往下压，只能改离散化（已验证会让辙叉窗结果
跳变，不可接受），或者换算法层：L4 解析 Jacobian + 隐式积分（把 nfev 降一个量级）、
L6 GPU 批量。据此把路线表调整为：跳过 L2 与 L3，直接做 L4/L6 与阻尼定标。

"""

marker = "## 2 量到的、被否掉的提速手段"
assert marker in text
path.write_text(text.replace(marker, addition + marker, 1), encoding="utf-8")
print("ok")
