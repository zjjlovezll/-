# Velch 0.4.25

发布日：2026-10-23

## 这一版做了什么

车体不再只是四个数字。`CRH380A_M.spck` 的车体子模型被读成数字，记进车辆定义的 `geometry`
块：质心 (0, 0, −1.55 m)、参考点 13.5 m、定距 17.5 m、轴距 2.5 m、二系悬挂在车体与构架两侧的
锚点、抗侧滚扭杆 / 横向止挡 / 牵引拉杆的位置与刚度。质量与三个惯量与此前逐位相同（读回来验证的
是"我们原本就是对的"）。

`velch vehicle validate` 会用恒等式检查这些几何与求解器真正使用的相对锚高是否自洽（例如
−1.0 − (−1.55) = 0.55），不自洽就拒绝加载。

## 没有变的东西

结果逐位不变：`scripts/verify_vehicle_ref.py` → `VERDICT: EQUIVALENT`，
`history.csv` sha256 与 0.4.24 相同。几何块是旁挂证据，求解器只读 `vehicle` 块。

## 仍然没有的

1. 车体纵向自由度与车体—转向架耦合；抗侧滚扭杆、牵引拉杆、横向减震器、横向止挡、轴箱体
   都还没有装配进求解器（Step 2 的节点表拓扑是前提）。
2. 实测数据标定：`physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`。
3. 左右侧 `|y|` 的符号约定尚未逐元件重导。

## 怎么验证

```powershell
$env:PYTHONPATH="$PWD\src"
python -X utf8 -m velch vehicle show CRH380A_M
python -X utf8 -m velch vehicle validate CRH380A_M
python -X utf8 scripts\verify_vehicle_ref.py
python -X utf8 packaging\smoke_test.py --root dist_installer\Velch --data "F:\velch_data\validation" --readonly-acl
```
