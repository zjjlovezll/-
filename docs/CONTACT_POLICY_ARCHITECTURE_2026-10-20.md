# 接触策略层：可插拔接口、首轮 A/B 结果与创新路线（2026-10-20）

## 1. 为什么要做这一层

之前每换一种接触想法（软最大、曲率刚度、阻尼律、斑平均）都要改 `find_graph_contact` 或
`evaluate_contact` 的内部，改完只能整体回退。现在把**三个决策点**各抽成一个具名策略，全部由算例
JSON 的 `contact` 段选择，默认值等于历史行为，所以：

* 任何旧算例一字不改仍按原样跑；
* 新想法是一次 A/B 开关，不是一次求解器改写；
* 外部标定（Simpack、试验台、SDITT）无论给常数还是逐点量，都只填参数，不动积分器。

代码：`Velch/src/velch/contact_law.py`（策略与纯函数）、`contact.py`（接进搜索与力）、
`vehicle_solver.py`（把 `case.contact` 传进每一体的搜索）。测试：`Velch/tests/test_contact_law.py`，
全仓 **42 项通过**。

## 2. 三个决策点

| 决策点 | 取值 | 含义 |
|---|---|---|
| `point_policy` | `argmax`（默认） | 硬最大值，历史行为 |
| | `soft_argmax` | θ 软加权重心：接触点随载荷连续滑动，最深节点换人时不再跳变 |
| `stiffness_policy` | `fixed_effective_radius`（默认） | `C = 4/3·E*·sqrt(R*)`，R* 由算例给一个常数 |
| | `local_circular` | 逐接触点由两侧型面曲率算 `R* = 4/Σ(1/R)`，轨顶凸、轮缘根部贴合，天然更软 |
| `damping_policy` | `fixed_coefficient`（默认） | `c·sqrt(δ)·v` |
| | `hunt_crossley` | `(3/4)·α·C·δ^1.5·v`，`α=(1−e)/((1+e)v_ref)`，阻尼与刚度、恢复系数绑定 |

另外两个可调量：

* `point_theta_m`：软最大宽度。**缺省不写 = 自适应** `θ = clip(1.0·b_Hertz, 2 µm, 50 µm)`，
  `b_Hertz = sqrt(2R*δ)`。这比 SDITT 固定 20 µm 更进一步：平滑尺度永远不超过真实接触斑，
  且 δ→0 时自动消失，所以静平衡不受影响（实测静载仍 59 680.6 N 级）。
* `ellipticity_correction`：`local_circular` 的椭圆修正因子，默认 1.0。圆形等效与精确椭圆解
  之间是一个有界因子，留给标定用，不改结构。

## 3. 首轮 A/B（辙叉窗 0.05 s，翼轨体，仅改 `contact` 段）

| 算例 | R1 峰值 | R2 峰值 | R1 均值 | 最大侵入 | 接触采样 | 轮心行程 | nfev | 墙钟 |
|---|---|---|---|---|---|---|---|---|
| base（R*=0.02, argmax, 固定阻尼） | **229.2 kN** | 217.4 | 59.0 | 0.486 mm | 67/101 | 0.440 mm | 13 781 | 19.7 s |
| soft（自适应 θ） | 232.5 | 223.0 | 59.1 | 0.490 | 67/101 | 0.440 | 16 373 | 28.5 s |
| soft_fixed_theta（θ=20 µm） | 230.5 | 219.6 | 59.0 | 0.488 | 67/101 | 0.440 | 12 701 | 21.2 s |
| local（曲率刚度） | 465.2 | 392.6 | 58.8 | 0.342 | 47/101 | 0.480 | 17 225 | 39.0 s |
| local_hc（曲率+恢复系数阻尼） | 388.3 | 370.9 | 60.4 | 0.336 | 52/101 | 0.456 | 17 825 | 40.4 s |
| combined（三者同开） | 389.9 | 357.3 | 60.4 | 0.331 | 52/101 | 0.450 | 50 693 | 115.5 s |
| Simpack 同段 | **128 kN** | — | — | 0.424 mm | 全时 | 0.594 mm | — | — |

**结论（必须照实说）**：

1. 软最大对峰值**中性**（229→232 kN），它确实消掉了接触点跳变，但这一段的力不再由"点选错"决定。
2. 曲率刚度把侵入从 0.486 压到 0.342 mm（**更接近 Simpack 的 0.12–0.424**），但峰值反而升到
   465 kN、接触采样掉到 47/101——刚度越大，弹得越狠，越容易脱空。这与之前把 R* 直接取 0.5407
   得到 717 kN 是同一个机制。
3. 恢复系数阻尼只把峰值从 465 拉回 388 kN，方向对、量级不够。
4. 三者同开 390 kN，但 nfev 涨到 50 693、墙钟 115 s——**组合并不划算**。

也就是说：三个借来的机制各自都实现了、都可复现，但**没有一个是这一段峰值的杠杆**。轮心行程
0.440 mm 已经小于 Simpack 的 0.594 mm，侵入 0.486 mm 已经与之同量级，剩下的差距全在"34/101 个
采样完全脱空"——而脱空的根因是走行面在 79.9–80.3 m 还有一个约 0.49 mm 的纵向凹坑（翼轨体只补掉了
其中一部分），不是接触律。

## 4. 因此下一步（已定位，不再猜）

翼轨体现在是**照抄原始断面**建出来的，而原始断面的翼轨冠随里程外移、在 79.9–80.3 m 让开走行带，
于是固定横位 753 mm 处仍低 1.3 mm。设计意图是**翼轨顶面在整段密贴区保持 z=0**（60TY1 轨头，附注
9.5），所以正确做法是给翼轨体建**合成冠面**：冠位按设计横移，但冠高恒为 0，横向 104 mm 头宽，
心轨按降低值曲线沉在它下面。这一步做完，0.49 mm 凹坑消失，才有可能谈"脱空归零、峰值进 130 kN
量级"。

## 5. 创新路线（在两者之上，不重复它们）

按"精度→速度"排序，每条都留了接口位：

1. **自适应 θ（已实现）**：把平滑尺度绑到真实接触斑，而不是固定 20 µm。下一步把 `scale` 与
   `θ` 做成随 δ 平滑变化的连续函数，并给出"力对几何台阶的 Lipschitz 上界"，用数值界替代经验值。
2. **局部椭圆修正**：`ellipticity_correction` 已留口。用 `Re_Radius`+`Par_Hertz` 的 β 表算精确
   (m, n)，把 `local_circular` 的 20–30% 圆等效偏差消掉，同时保持逐点连续。
3. **斑间去重**：`merge_contact_responses` 现在对相邻体的重叠渗透重复计力，按 SDITT 的
   `NF_STRIPES` Col 6–11 裁掉重叠区。这是多体情形下唯一还没修的正确性问题。
4. **解析雅可比**：接触力对 (y, z, roll) 的偏导有闭式，供 Radau/BDF 用，预计把隐式迭代次数压掉
   一半以上（当前 `combined` 的 50 693 nfev 就是隐式回退的代价）。
5. **仿射网格缓存**：同一体在相邻两站之间时，两侧型面的 y 列不变、只有插值权重变，因此
   `(网格, 两侧高度)` 可在区间入口算一次，之后每次只需一次加权和 + 一次 sqrt。这是把当前
   `find_graph_contact` 101 µs 压到 20–30 µs 的最直接手段，且**逐位等价**（可用 1e-12 断言回归）。
6. **(s, y) 查表**：在 5 已成立的前提下再上 2D 表，把接触搜索变成两次 `searchsorted` + 插值；
   预计单次 1–2 µs，总墙钟进入秒级。
7. **误差可控的 s-滞后评估**：型面沿里程缓变，接触几何可在粗 s 网格上算、用 Hermite 预测并以
   侵入误差限控制加密。这条能把"每步都重建几何"改成"每 N 步一次 + 预测"，是速度上的第二个数量级，
   且误差有界可验。

## 6. 产物

- `Velch/src/velch/contact_law.py`（新）：策略枚举、`adaptive_theta_m`、`soft_argmax_position`、
  `local_curvature`、`circular_equivalent_radius`、`hertz_stiffness_n_m_1p5`、
  `hunt_crossley_coefficient`。
- `Velch/src/velch/contact.py`：`ContactParameters` 新增 8 个可选字段（默认=历史行为）；
  `ContactGeometry` 新增 `stiffness_n_m_1p5`/`radius_star_m`/`half_width_m`；
  `_contact_on_span`/`find_graph_contact` 透传策略；`evaluate_contact` 用逐点刚度与阻尼策略。
- `Velch/src/velch/vehicle_solver.py`：`_evaluate_patch` 把 `case.contact` 的策略传进搜索。
- `Velch/tests/test_contact_law.py`（新）：14 项。
- `Velch/validation/crh380a_m/make_policy_cases.py`、`cmp_policy.py`：A/B 生成与汇总。
- 算例 `case_pol_{base,soft,soft_fixed_theta,local,local_hc,combined}.json`；
  输出 `out_pol/case_pol_*`（6 个，全部 `numerically_checked`，7 项门全过）。
