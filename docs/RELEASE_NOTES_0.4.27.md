# Velch 0.4.27 发布说明

**发布日期**：2026-10-23

## 这一版多了什么

**力学元件库 `velch/elements.py`**：元件变成"类型 + 参数表"，不再只有两种原语。

| 元件 | 参数（单位） |
|---|---|
| `spring` | `stiffness`（N/m）、`preload_force`（N） |
| `damper` | `damping`（N·s/m），允许没有刚度 |
| `spring_damper` | `stiffness`、`damping`、`preload_force` |
| `bushing` | `stiffness`、`damping`、`cross_stiffness`（非对角项，按主方向分解） |

参数缺项或越界会报出元件名、参数名与单位；未知类型会列出已知类型。

## 怎么验

```powershell
python -X utf8 -m pytest tests/test_elements.py
python -X utf8 -m pytest tests/test_topology.py tests/test_topology_corpus.py
```

`pytest` 全仓 669 passed / 1 skipped；冻结基线与节点表仍逐元件系数相同（差 `0.000e+00`）。
安装包冒烟 8 步全过。

## 仍然没有的

* 非线性元件（止挡、卸荷阀、库仑摩擦）——求解器目前只有线性行结构；
* 空气簧（刚度随高度变化）；
* 与 Simpack 元件表的逐条对照报告；
* 节点表与冻结基线的轨迹等价（峰值集合相同、归属轮换，见 `docs/VEHICLE_TOPOLOGY_2026-10-23.md` §3）。
