# Velch 0.4.26 发布说明

**发布日期**：2026-10-23

## 这一版多了什么

**节点表引擎**：车辆的刚体与元件可以写成数据（`layout.model = "v2-node"`），求解器不再
假设"四轴两转向架占 35 个坐标"。冻结的 35 坐标布局原样保留，`history.csv` 与重构前**逐位相同**
（sha256 `7bfbaa1c…8566ad88`，244 404 B）。

**两台新车型定义**：

| 文件 | 内容 |
|---|---|
| `vehicles/CRH380A_M_node.json` | 用节点表重述冻结的 30 个连接器，逐元件系数相同（差 0.000e+00） |
| `vehicles/CRH380A_M_6dof.json` | 上面的基础上装牵引拉杆、抗侧滚扭杆、二系横向减振器 |

后者是**新物理**：这三个元件的数值来自 Simpack 转向架子模型，`not_verified` 里写着它们
尚未与实测或 Simpack 输出标定。

## 怎么验

```powershell
python -X utf8 -m velch vehicle validate CRH380A_M_node
python -X utf8 scripts/verify_vehicle_ref.py      # 冻结基线逐位不变
python -X utf8 -m pytest tests/test_topology.py tests/test_topology_corpus.py
```

`pytest` 全仓 657 passed / 1 skipped；安装包冒烟 8 步全过。

## 仍然没有的

* 节点表与冻结基线的**轨迹等价**：峰值集合相同，但各轨归属轮换了，尚未收敛（如实记录在
  `docs/VEHICLE_TOPOLOGY_2026-10-23.md` §3）；
* 轮对纵向自由度、止挡、齿轮箱吊杆；
* 三轴转向架与铰接车的真实表；
* 与实测或 Simpack 输出的标定（`physics_validation_status` 仍是 `unvalidated`）。
