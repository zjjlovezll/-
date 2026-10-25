# 轴箱的转动约束：13.094 Hz 无阻尼模态从哪里来，怎么去掉

日期：2026-10-26
代码：`vehicles/CRH380A_M_axlebox.json`、`vehicles/CRH380A_M_axlebox_x.json`、`F:\velch_tmp\straight\case_straight_axlebox.json`（内联拓扑）
测试：`tests/test_axlebox_rotational_restraint.py`（4 项，含一条能复现缺陷的反向测试）

## 1. 现象

审查（D3）指出：轴箱加速度通道里有一个 **13.0 Hz、rms 9.3 m/s²、永不衰减**的分量，80 km/h 与 350 km/h 频率相同（所以是车辆模态，不是车轮转动），零不平顺算例里也有。它比这些实验要测的任何不平顺信号都大一到两个数量级——短波那一路的"信噪比"其实一直在量它。

先把它定死：

| 检查 | 结果 |
|---|---|
| 零不平顺、6 s、输出 500 Hz，逐 0.25 s 窗取 10–17 Hz 峰值 | t=0.12 s **9.181 m/s²** → t=5.87 s **9.074**，**剩 98.9 %** |
| 同一段跑接触占空比 | **1.0000**（八斑全程在载，不是脱空—落回） |
| 通道分解（同一段最后半窗） | 轴箱 z rms **6.7589**；**轮对 z rms 0.0016**；构架 0.0073；车体 0.0002 |

所以：轮对几乎不动、车体和构架不动，**只有轴箱自己在跳**，而且从第一帧就跳、不衰减。它不是我加进去的激励，也不来自轨道几何。

## 2. 定位：线性化里有一个 ζ = 0 的四重模态

`scripts/s9p_modal_audit.py` 用 `JacobianAssembler(dynamics).blocks(0.0, q, v)` 在平衡态组装 `A = [[0, I], [∂f/∂q, ∂f/∂v]]` 并求特征值（注意公开方法是 `blocks(t_s, q, v)`，`_blocks_at` 是内部的；第一次写错报了 `AttributeError: 'JacobianAssembler' object has no attribute 'blocks_at'`）。

86 坐标的系统里出现：

```
13.094 Hz  zeta +0.0000
13.094 Hz  zeta +0.0000
13.095 Hz  zeta +0.0000
13.095 Hz  zeta +0.0000
```

四重简并、阻尼严格为零。同频段其它模态都是正常阻尼的（12.005 Hz ζ 0.185、12.574 Hz ζ 0.033、15.30 Hz ζ 0.011），所以这不是"整体阻尼不足"，而是**某一个方向上刚度为零**。

按动能 `m·|u|²` 拆参与度（`F:\velch_tmp\mode_energy.py`）：

```
axlebox1L…4R.z    m = 48.2   |u| = 3.036e-3   每个 4.44e-4
八个轴箱合计占动能 97.6 %
```

即：八个轴箱**竖直平移**，其它一切几乎不动。

## 3. 根因：平移与转动恰好抵消，弹簧一点没被拉伸

查"有哪些力元碰这个坐标"（`F:\velch_tmp\box_z_path.py`）：

| 元件 | 刚度 / 阻尼 | 耦合 |
|---|---|---|
| `bearing_a1L_z` | **1.000e+08 / 0** | `wheelset1.z:+1, wheelset1.roll:−1, axlebox1L.z:−1, axlebox1L.roll:+1` |
| `primary_1L_z` | 1.176e+06 / 1.000e+04 | `bogie1.z:+1, bogie1.roll:−1, bogie1.pitch:+1, axlebox1L.z:−1, axlebox1L.roll:+1` |

两条元件的伸长量都是 `(轮对.z − 轮对.roll) − (轴箱.z − 轴箱.roll)` 这种 **z 与 roll 同号组合**。于是存在一个方向：轴箱竖直上移多少，就同时绕横向轴转多少，使这个组合**恒为零**——弹簧不伸长、阻尼不产生速度差、势能与耗散都是 0。

验证：给 `bearing_a*_z` 加阻尼没有任何效果（0 / 2000 / 20000 / 200000 N·s/m 四档，13.094 Hz 的 ζ **全都是 0.0000**），因为该方向上元件两端的速度差本来就是 0。

**这不是数值问题，是装配缺了一项约束**：Simpack 原模型用 `joint.type = 2`（转臂式关节）连接轴箱与构架，那个关节**有转动约束**；我们的节点表只有平移衬套（`arm_*_x` 13.7e6、`arm_*_y` 5.49e6）和一根本构架 yaw 弹簧，**绕横轴的转动约束完全没有**。缺了它，"转动"就成了自由方向。

## 4. 修法

在转臂关节处补上绕横轴的转动约束，八个轴箱各一根（`axis: "roll"`，轴箱 ↔ 所在构架）：

```json
{ "kind": "torsional", "name": "box_roll_1L", "axis": "roll",
  "stiffness": 1400000.0, "damping": 2000.0,
  "from": {"body": "axlebox1L"}, "to": {"body": "bogie1"} }
```

刚度不用猜：转臂衬套的横向刚度 `k_y = 5.49e6 N/m` 作用在约 `b = 0.5 m` 的力臂上，等效转动刚度 `k_y·b² = 1.37e6 N·m/rad`，取 **1.4e6**；阻尼取 2.0e3 N·m·s/rad（ζ ≈ 0.004 量级，只为了不让那个方向重新变成无阻尼）。

这一项同时写进两个车辆文件（`CRH380A_M_axlebox` 84 元件、`CRH380A_M_axlebox_x` 85 元件），并写进**算例自己的内联拓扑**——这是本轮踩到的第二个坑：`F:\velch_tmp\straight\case_straight_axlebox.json` 自带 `topology`（76 元件），**根本不读 `vehicles/*.json`**。第一次只改车辆文件时 `velch vehicle validate` 通过、算例毫无变化，因为跑的根本不是那份拓扑。

## 5. 验证

| 指标 | 修前 | 修后 |
|---|---|---|
| 12.5–13.7 Hz 内最低 ζ | **0.0000**（13.094 Hz 四重） | **0.0042**（12.620/12.621 Hz，成对） |
| 零不平顺 6 s 的 10–17 Hz 峰值 | 9.181 m/s²（首窗）→ 9.074（末窗，剩 98.9 %） | **0.020 → 0.000（剩 0.0 %）** |
| 接触占空比 | 1.0000 | 1.0000（未受影响） |

`scripts/s9o_long_track.py decay` 的末行现在是 `decay: first 0.020 -> last 0.000 (remaining 0.0 %)`。

回归测试 `tests/test_axlebox_rotational_restraint.py` 四项：元件存在且挂在转臂位置（轴箱 ↔ 该轴所属构架、axis roll、刚度与阻尼为正）；用轴箱体车辆线性化后 12.5–13.7 Hz 的最低 ζ > 0.003；**把八根元件删掉后同一窗口的最低 ζ < 1e-3**（这条让测试能像缺陷那样失败，而不是只断言"文件里有这个键"）；纵向车型带同样的八根。

## 6. 这一条改变了什么

- 短波/长波反演的所有"信噪比"口径此前都建立在一个 9 m/s² 的假信号之上：13.33 Hz 在 80 km/h 对应 **1.667 m** 波长，正好落在 (1.6, 3.2) m 带内，并以 −29 dB 渗进 (0.8, 1.6) m 带。这也解释了 S9-11/S9-12 为什么"重频带复原成标定值、轻频带一律 4–16 µm"——那个"串扰底线"就是它。
- 依赖同一份内联拓扑的实验（`s9f` 短波、`s9i` 高速短波、`s9j` 半径—纵向、`s9k`/`s9l`/`s9m` 随机谱）必须在修后的算例上重测，之前的数字按 `docs/RANDOM_SPECTRUM_INVERSION_2026-10-25.md` 的口径更正处理。

## 7. 不能证明什么

- 1.4e6 N·m/rad 是**等效值**，不是从 Simpack 挖出来的实测转动刚度；`not_verified` 里写明了这一点。
- 只补了绕**横轴**（roll）的转动约束。绕纵轴与竖轴的转动刚度仍只有 yaw 弹簧（2.0e6）与实际几何给出的部分，没有逐项标定。
- 13 Hz 消失不等于轴箱通道就"干净"了：236.5 / 373.7 Hz 一带仍有 ζ ≈ 0 的模态（它们属于接触/钢轨侧，见 `s9p` 的全表），只是不在这些实验的频带里。

## 8. 复算

```powershell
cd F:\ai道岔状态反演辨识\Velch
$env:PYTHONPATH="F:\ai道岔状态反演辨识\Velch\src"
python -X utf8 -m pytest tests\test_axlebox_rotational_restraint.py -q --basetemp F:\velch_tmp\pytest
python -X utf8 scripts\s9p_modal_audit.py F:\velch_tmp\s9o\audit_case.json --window 12.5 13.7
python -X utf8 scripts\s9o_long_track.py decay
```
