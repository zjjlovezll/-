# 直向刚性算例：四个缺陷，一段 10 m 的干净运行

日期：2026-10-29（目标第 13 轮）
脚本：`scripts/s72_straight_stock_baseline.py`（接一个新的刚性算例跑基线）、`scripts/s73_straight_pair.py`（把左右两侧拼成同一根直向）

## 一句话

直向刚性算例里挡路的不是一处，而是**四个互相独立的缺陷**；修掉其中三个之后，
**刚性直向第一次跑出 0.45 s、7/7 门、八轮 0.979–1.051× 均载**（40 → 50 m）。

## 一、四个缺陷（都带实测）

| # | 缺陷 | 症状 | 处置 |
|---|---|---|---|
| 1 | 原算例是**侧向道岔**：右侧站表从 30 m 起就往 +y 弯，40 m 处轨距中心已偏 0.475 m | 8 根轨与车轮错开，静平衡只有 4/8 轮着地 | 用 `s73` 把左右两侧重建成**同一根直向**（尖轨体保留） |
| 2 | 左右**断面族不同源**：左 `Profile_Mileage_JBG.prr`、右 `jbg-20200418-R.prr` 的横向跨度不同（1.4994 m vs 1.5376 m） | 拼接点报 `ProfileError: adjacent profiles have no lateral overlap`；刀尖区 53.7 m 报 `graph slope limit`（`pen 3143.53 µm、lever_y +0.71535、slope 1.274`） | 左侧改成右断面的**镜像**（同族同跨度） |
| 3 | 左右**轨顶高不同**（右 +0.000072 m，左 −0.0 m；`jbg` 参考点就是高出 72 µm 的那个截面） | 载荷左右不均（实测 1.29× / 0.71×） | 右侧整体下移 0.00 µm（按**两轨顶高相同**定义轨顶） |
| 4 | `s73` 的**缓存键只含文件名**，不含变换 | 镜像后的左断面取到了未镜像的轨顶偏移，右侧轨顶被放到 **+0.76713 m**（应为 +0.75325，差 13.88 mm = 2×6.94 mm），对称算例又退回 4/8 | 缓存键改成 `(file, y_sign, z_sign, format)` |

第 4 条是这一轮最值得记的：**它只在"镜像 + 缓存"同时出现时发作**，而症状（4/8 轮、单侧约 2×）和
第 1、2 条完全一样，光看数字分不出来。修完后两侧轨顶实测：

```
left : crown y -0.75325  z +0.000072   n 1001
right: crown y +0.75325  z +0.000072   n 1001
```

## 二、跑出来的那一段（40 → 50 m，0.45 s，80 km/h）

| 量 | 实测 |
|---|---|
| 坐标数 | 35（纯刚体），8 根轨，每根 1 个 body，尖轨轴右侧多一个 `right:blade`（50.578–57.304） |
| 静平衡残差 | **1.492e-08 N** |
| 七门 | **7/7**（`solver_completed / finite_states_and_forces / vertical_preload_residual / penetration_within_case_limit / friction_bound / no_edge_limited_active_contact / translational_action_reaction`） |
| 八轮末帧份额 | **0.979 – 1.051×** |
| 单斑峰值 | 65.458 – 65.720 kN |
| 里程 | 走了 **10.000 m**（40 → 50 m，正好停在尖轨起点 50.578 m 之前） |

## 三、还没解决的（都在 50.578 m 之后）

1. **起跑里程必须在 40 m 附近**：同一个算例从 80 / 95 / 105 m 起跑都在静平衡阶段报
   `no seed converged; xtol`。轨道几何在 40 m 与 95 m 处完全相同（左右都是均匀断面），所以这不是形状问题，
   而是静平衡在该里程上找不到解——**未定位**，下一步先量这三个起点的逐行残差。
2. **尖轨区仍会触发斜率门**（第 12 轮在 53.7359 m 处，`pen 3143.53 µm`），这一轮没有重测。
3. **心轨区（103.28–116.44 m）**还没跑到：从 40 m 起跑需要 3.0 s 仿真。

## 四、复算

```bash
cd F:/ai道岔状态反演辨识/Velch
PYTHONPATH=src python -X utf8 scripts/s73_straight_pair.py
PYTHONPATH=src python -X utf8 scripts/s72_straight_stock_baseline.py \
  --case ../scratch/s73/case_s40_run.json --start 40 --duration 0.45 --output-step 5e-4 --out ../scratch/s72
```
