# 车体子模型：把 `CRH380A_M_Carbody.spck` 读成数字

> 文件：`G:\研究生\动力学\CRH380A_纯刚性模型\database\database\mbs_db_substructure\CRH380A_M_Carbody.spck`
> 大小 77 538 B · 627 条记录 · 12 个全局参数 · 1 个刚体 · 39 个力元条目
> 读取器：`velch/simpack_model.py`（`python -m velch.simpack_model <file>`）

## 一句话结论

车体的**质量与三个转动惯量我们本来就是对的**（四项与文件逐位相同）；这一轮补上的是
**它们的位置**（质心、参考点、定距、轴距）与**二系悬挂在车体一侧的锚点坐标**，
并把这些数字与求解器真正用的相对锚高之间的恒等式写成机器检查。

## 一、12 个全局参数（全部解出）

| 变量 | 值 | 含义 | 落在哪 |
|---|---|---|---|
| `$_CB_mass` | 34 934 kg | 车体质量 | `vehicle.carbody.mass_kg`（原值，已核对） |
| `$_CB_Ixx` | 113 200 kg·m² | 侧滚惯量 | `vehicle.carbody.roll_inertia_kg_m2`（原值） |
| `$_CB_Iyy` | 1 711 800 kg·m² | 点头惯量 | `vehicle.carbody.pitch_inertia_kg_m2`（原值） |
| `$_CB_Izz` | 1 615 300 kg·m² | 摇头惯量 | `vehicle.carbody.yaw_inertia_kg_m2`（原值） |
| `$_CB_CG_x` / `$_CB_CG_y` | 0 / 0 | 质心纵向/横向 | `geometry.carbody.cg_m` |
| `$_CB_CG_z` | −1.55 m | 质心高度（轨面下为负） | `geometry.carbody.cg_m.z` |
| `$_Carbody_Position` | 13.5 m | 车体参考点里程 | `geometry.carbody.reference_x_m` |
| `$_Bogie_Distance` | 17.5 m | 定距 | `geometry.bogies.distance_m` |
| `$_Bogie_Front` / `$_Bogie_Rear` | 22.25 / 4.75 | 前后转向架位置 | `geometry.bogies.front_x_m` / `rear_x_m` |
| `$_Wheelset_Distance` | 2.5 m | 轴距 | `geometry.bogies.wheelbase_m` |

文件里另有 `$F_FACC`（Type 5，`$M_Isys → $M_CB_BRF`）与 39 条力元条目，绝大多数是
`$S_F.*` / `$S_R.$S_WS_*` 的**子模型引用**——它们说明"车体下挂了哪些东西"，
参数本身在前转向架/后转向架子模型里（见 `SIMPACK_BOGIE_MINING_2026-10-23.md`）。

## 二、坐标约定（写进 `geometry.frame`，因为不写就一定会差一个偏移）

- **z：轨面为 0，向下为负**。Simpack 就是这么存的，我们原样保留——绝对高度可以直接抄，
  不需要在复制时加一个隐式偏移。
- **y：轨道中心线为 0，右正**。Simpack 模型对左右两侧存的是 `|y|`，所以每一侧的实际符号
  必须逐元件重导；这一点写在 `not_verified` 里，没有当成已知。
- **x：车体参考点**。本车是 13.5 m。

## 三、四条恒等式（机器检查，不看人眼）

`velch vehicle validate` 会把 `geometry` 与 `vehicle` 逐项对齐，任何一条不成立就拒绝加载：

| 恒等式 | 本车实测 |
|---|---|
| 车体质量 / 三个惯量：`geometry` 与 `vehicle.carbody` 相同 | 34 934 / 113 200 / 1 711 800 / 1 615 300 |
| `geometry.bogies.distance_m = 2 × vehicle.bogie_half_spacing_m` | 17.5 = 2 × 8.75 |
| 空气簧上表面 − 车体质心 = `secondary.upper_anchor_height_m` | −1.0 − (−1.55) = 0.55 |
| 空气簧下表面 − 构架质心 = `secondary.lower_anchor_height_m` | −0.8 − (−0.51) = −0.29 |

一系另外两条按 1 mm 容差比对：`$_AxleGuide_Damp_z = −0.322` 对
`primary.upper_anchor_height_m = −0.323`，`$_AxleGuide_Spr_z = −0.585` 对
`primary.lower_anchor_height_m = −0.585`。差 1 mm 是原模型自己的取整，不是我们抄错——
所以容差写的是 1 mm 并注明原因，而不是把它抹平。

## 四、记下来了但**还不解**的东西

这些数字进库、有出处、有校验，但求解器里没有对应的自由度或元件，所以本版结果与它们无关：

- 车体纵向自由度（x）与车体—转向架的点头/摇头耦合；
- 抗侧滚扭杆 1 000 000 N·m/rad（`$F_SS_AntiRollBar`）、牵引拉杆 7 880 000 N/m、
  二系横向减震器 17 150 000 N·s/m + 40 000 N/m、横向止挡（`$F_SS_Stop`）；
- 轴箱转臂节点 13 700 000 / 5 490 000 N/m 与四个 48.2 kg 轴箱体。

一句话：**车体现在是"数字齐全、装配留白"**。`physics_validation_status` 仍然是
`unvalidated_against_measurement_or_Simpack`。

## 五、这一轮改了什么、没改什么

- `vehicles/CRH380A_M.json`：新增 `geometry` 块（frame / carbody / bogies / primary /
  secondary / carbody_mounted）、`provenance.geometry`（两个 `.spck` 的 sha256 + 读取器名）、
  三条 `not_verified`；文件从 3 613 B 长到 7 225 B。
- `velch/vehicle_db.py`：新增 `_geometry_problems()`（八类自洽检查）、`vehicle show` 打印
  "车体几何 / 车体位置"两行。
- `tests/test_vehicle_db.py`：新增 6 项（自洽通过、四类矛盾被拒、报告含几何）。
- **结果逐位不变**：`scripts/verify_vehicle_ref.py` → `VERDICT: EQUIVALENT`，
  `history.csv` sha256 `7bfbaa1c…8566ad88`、244 404 B、`numerically_checked`、七门全 true
  （求解器只读 `vehicle` 块，`geometry` 是旁挂证据）。

## 六、复算

```powershell
$env:PYTHONPATH="$PWD\src"
python -X utf8 -m velch.simpack_model "<...>\CRH380A_M_Carbody.spck"
python -X utf8 -m velch vehicle show CRH380A_M
python -X utf8 -m velch vehicle validate CRH380A_M
python -X utf8 scripts\verify_vehicle_ref.py
```

## 七、仍然没有的

1. 车体与转向架的**装配**（上面第四节那些元件）——需要 Step 2 的节点表拓扑；
2. 实测数据侧的标定（`physics_validation_status` 未变）；
3. 左右侧 `|y|` 的符号约定逐元件重导（当前只记半宽，没有逐元件正负）。
