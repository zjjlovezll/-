# 0.4.24：一台车只有一个定义

## 装什么

`Velch-0.4.24-win64.zip`（onedir，解压即用，双击 `启动 Velch.cmd`）。

## 这一版的新东西

**车辆数据库**：`vehicles/CRH380A_M.json`，算例里写一行 `"vehicle_ref": "CRH380A_M"`
就代替整块 `vehicle`。四条命令：

```powershell
python -X utf8 -m velch vehicle dir                 # 车辆库在哪
python -X utf8 -m velch vehicle list                # 逐车一行
python -X utf8 -m velch vehicle show CRH380A_M      # 整份文件
python -X utf8 -m velch vehicle validate CRH380A_M  # 只校验
```

**校验规则**（`velch vehicle validate`）：质量/惯性为正、一系二系九字段齐全且刚度阻尼非负、
左右轮对称、`provenance` 非空、`physics_validation_status` 必填、`layout` 必须是 v2 剖面。

## 验收：换了写法，一个数字都不许变

```powershell
python -X utf8 scripts/verify_vehicle_ref.py
```

同一算例跑两遍（内联 vs 引用），逐位比 `history.csv`：

| 项 | 结果 |
| --- | --- |
| `history.csv` sha256 | `7bfbaa1c…`（两遍相同，244 404 字节） |
| `result_status` | `numerically_checked` |
| 七项门 | 7/7 |
| VERDICT | **EQUIVALENT** |

另外，解析 `vehicle_ref` 会把车辆文件的 sha256 写进 `asset_hashes`，所以跑完再改车辆文件，
产物校验会失败——这台车被钉住了。

## 这一版**没有**解决

- 车辆拓扑仍写死在 `vehicle_solver.py`（2 转向架 × 2 轴 × 左右），6 轴机车/3 轴转向架/铰接车进不来；
- 自由度仍不全：轮对缺 `x`/`pitch`，车体与转向架缺 `spin`，全车无轴箱；
- 悬挂仍只有 `k_y/k_z/k_yaw`，无 `k_x`、无侧滚/点头刚度、无 6×6 交叉项；
- 界面里"选车 → 计算"尚未接线（下一步）；
- 与实测/Simpack 的物理标定仍未做，`physics_validation_status` 仍是 `unvalidated…`。

细节见 `docs/VEHICLE_DATABASE_2026-10-23.md`。
