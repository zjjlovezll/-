# 曲线走进哪一侧：四条被实测否掉的路，和一条还没被否的

日期：2026-10-27
状态：决策记录（四条否定均有实测数字，可直接复查）

这条记录存在的理由很具体：曲线这一件事，我在同一批错误方向上反复走过三次——先在车辆侧加离心力，再把轨面横移，
再把超高当成抬升，每一次都“看起来在推进”，直到实测把它打回来。把否定写下来，比把结论写下来更省时间。

## 一、力路由（`curve_geometry = false`）：能坐住，但只对平衡超高

`case_A_final_law` 改成 R = 1100 m、cant = 0.107 m、100 km/h、`curve_geometry = false`：

```
result_status  numerically_checked    gates 7/7
八接触载荷     59 652 … 59 708 N      （均分 59 662 N，每轮 1.00×）
```

0.107 m 正是理论平衡超高 `h_th = 1.5·v²/(g·R)`，所以“八轮等载”是物理，不是调出来的。
**但它只对平衡超高成立**：同一半径把 cant 设成 0、100 km/h，仍然 `graph slope limit`。
结论：力路由保留，作为“车速与超高已知时的快速验算”，**不能**当作曲线过岔的唯一路径，
因为它把轨面当直的，接触几何与真实曲线不同。

## 二、轨面横移（`CurveSeries`）：否掉，量级差两个数量级

`CurveSeries` 把采样后的轨面按 `Δy = (s−origin)²/(2R)` 横移。R = 1100 m、cant = 0、80 km/h、x_start 60 m：

| 轨面 | 车辆状态 | `axle1_left` | `axle1_right` |
|---|---|---|---|
| 直 | 任意 | 0.0 kN | 0.0 kN |
| 曲 | 对齐（y = +45.5 mm，yaw = +0.0095） | **150 690.0 kN** | 0.0 kN |
| 曲 | 只加 yaw（y = 0） | 78 785.2 kN | 0.0 kN |
| 曲 | 只加 y | 150 689.6 kN | 0.0 kN |
| 曲 | **车保持直（y = 0，yaw = 0）** | **78 786.2 kN** | 0.0 kN |

两个读数说明一切：

1. **车不动、只横移轨面就出现 78.8 MN**：如果两侧框架一致，车不动应该仍是 0；
2. **车同向移 45.5 mm 后反而升到 150.7 MN**：同框架下应抵消，实测是叠加。

所以采样后的 `profile.y_m` 与车辆 `y` **不在同一个框架**里（`contact_search.py` 里 `rail_y = rail_y_m + rail_profile.y_m`
说明 `profile.y_m` 是绝对坐标，模板中心在 −0.753337 m）。把它横移等于把“坐标系”当成“几何”改。
现状：`curve_geometry` **且** `curve_rail_surface` 才启用，默认关闭。

## 三、超高当抬升：否掉，`5b67cb7` 起改成真正的转动

早先把 `curve_cant_m` 写成左右轨的高差（纯平移），结果是车轮顶到轨距面根部。现在：

- 几何路由：`RolledSeries` 把采样断面绕自身中心线转 `φ = asin(cant/gauge)`（107 mm / 1.493 m → 0.0717 rad）；
- 但**旋转断面不足以平衡曲线**：真正的平衡超高靠“车架跟着轨道平面一起倾”，重力在轨道平面内出现分量抵消 `m v²/R`；
  本模型重力始终沿世界 z 轴，于是车轮必须自己提供全部横向力 `48654 × 27.78² / 1100 ≈ 34 kN`，任何轨顶圆角都给不出这个接触角。
  实测：断面已转动，R=1100/cant=0.107 仍 `no seed converged; gtol termination condition is satisfied`；同一算例走力路由则 `numerically_checked`。
- 因此几何路由对非零超高**拒绝**，并写明原因（不是收敛问题，是重力方向问题）。

## 四、`align_to_track`：曾经是一个不存在的开关

代码里一直用 `getattr(case.run, "align_to_track", False)` 读它，而 `RunSettings` 从来没有这个字段，
所以它恒为 `False`——前几轮所有“按道岔设计线对齐”的运行，真正生效的都是 `curve_geometry`。
字段现在正式存在（默认 `False`）。对齐本身是**对的**：`case_diverging_R1100` 在 69 m 处读出
中线 **+0.159525 m**、切线 **+0.015833 rad**，与解析值 0.154 / 0.0167 吻合。

## 五、还没被否的那条：曲率放在车辆侧

- 站表本身已经是弯的（道岔曲股就写在站表里），不需要改轨面；
- 车辆侧已有横向位移与偏航，蠕滑里已有 `(1−κy)` 与 `Δv_x = ∓vκb`（`contact.py` 的
  `slip_x = travel·(1 − κ·lever_y) + spin·lever_z`，并有 `rel=1e-12` 的测试钉住 `curved − straight = −κvb`）；
- 缺的是**坐得住**：把车放到设计线上之后，静平衡仍然停在 `xtol`，且左轨四个斑、右轨零个。

所以下一步不是再加一项物理，而是**把静平衡的问题问对**：现在未知量只有 y/roll（几何路由再加 yaw），
而真实需要的是“车架随轨道平面倾斜”这个自由度。要么把 `roll`/`yaw` 扩成整车的姿态未知量，
要么引入车架倾角作为显式未知量——这是下一轮要量的东西，不是猜的。

## 六、复查命令

```powershell
cd F:\ai道岔状态反演辨识\Velch
$env:PYTHONPATH="F:\ai道岔状态反演辨识\Velch\src"
python -X utf8 .tmp\s12c_gauge_centre.py      # 中线与对齐
python -X utf8 .tmp\s12e_alignment_parts.py   # 第二、三节那张表
python -X utf8 .tmp\s12d_z_only_seat.py       # 只解 z 时的 150 690 kN
python -X utf8 -m pytest tests/test_curve_series.py tests/test_rail_roll.py tests/test_curve_seat.py -q --basetemp F:\velch_tmp\pytest
```
