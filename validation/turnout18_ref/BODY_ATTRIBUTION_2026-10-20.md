# 方案 A：轨体归属 + 换体迟滞（2026-10-20）

## 做了什么

两处改动，都写进算例文件，因此每次运行都自带它用的规则：

1. `rail_templates[i].bodies[j].y_window_m = [lo, hi]`
   —— 轨体横向准入窗（绝对里程坐标，m）。轨头顶面不在车轮踏面下方的轨体，
   无论量出的侵入多深都不承载。实现：`velch.vehicle.RailBody.accepts_contact_y`，
   在 `vehicle_solver._evaluate_patch` 找到接触后过滤。
2. `run.body_hysteresis: true`
   —— 每侧只允许一个轨体承载，且换体有迟滞：在位者必须先卸载到
   `BODY_SWITCH_RELEASE_M = 5.0e-5 m`（0.05 mm）以下，且挑战者比它深
   `BODY_SWITCH_MARGIN_M = 2.0e-5 m`（0.02 mm）以上，才换体。
   在位者完全失去接触则无条件交接。实现：`VehicleDynamics._attribute_bodies`。

新增测试 `tests/test_contact_bodies.py`：横向准入窗、在位者保持、卸载后交接。
`pytest tests` → **22 passed**。

## 实测（辙叉窗 69.0 m 起 0.05 s，前轴 79→83.9 m，全部 `numerically_checked`）

| 算例 | 右轨峰值 | 均值 | 脱空采样 | max 侵入 | 墙钟 |
|---|---|---|---|---|---|
| `out_attr_base_G`（基线） | 613 708 N | 55 967 | 65/101 | 0.932 mm | 65.1 s |
| `out_attr_gate736_plain` | 613 708 N | 55 967 | 65/101 | 0.932 mm | 60.1 s |
| `out_attr_gate736_hyst` | 626 447 N | 56 391 | 64/101 | 0.948 mm | 45.2 s |
| `out_attr_gate740_hyst` | **795 250 N** | 69 926 | 66/101 | 1.115 mm | 37.8 s |

- 736 mm 窗是**空操作**：实测心轨接触点本来就在 736.4–743 mm，从未低于 736。
- 迟滞把峰值**推高**：在位者（翼轨）多撑一会儿，交接时心轨更低，落差更大。

**结论：A 不是杠杆。** 613.7 kN → 613.7 / 626.4 / 795.3 kN。

## 为什么 A 不可能有效（决定性数据）

原始断面在辙叉段的轨体分割（`probe_frog_bodies.py`，每站 2 个体）：

```
   里程     心轨体 y_lo..y_hi  crown_y  crown_z      翼轨体(60TY1) crown_y  crown_z
 79.707    716..748         733    -2.76 mm        748..853        801    +0.00
 80.004    716..758         738    -1.31 mm        758..862        811    +0.00
 80.278    716..767         743    -0.06 mm        767..871        820    +0.00
 80.468    716..773         746    -0.05 mm        773..878        826    +0.00
```

- 翼轨（60TY1，头宽 104.4 mm）的轨顶确实在 z=0，但**轨顶横位在 801–820 mm**，
  早已越过车轮踏面的外侧倒角（LMA 断面 abs y 到 815.8 mm、该处轮面已低于轨顶 5.8 mm）。
- 车轮参考面在 746.5 mm，踏面有效承载带约 736–790 mm；这一段里**只有心轨**，
  而心轨轨顶在 79.707 m 处比翼轨低 **2.76 mm**，到 80.278 m 才升平。
- 所以 79.7–80.3 m 是一段真实的 2.7 mm V 形凹陷（≈4.8 mm/m），
  350 km/h 下要求 0.47 m/s 的垂向速度——这不是接触搜索的毛病，是**断面本身**的。

心轨在密贴状态下的轨顶应与翼轨顶面齐平（附注 9.5：辙叉钢轨组合型、心轨 60AT2、
短心轨后端滑动端）。当前断面里心轨低了 2.76 mm，说明这套特征断面取的是**心轨未
密贴/有害空间**的形态，而不是直向通过时的密贴形态。

## 下一步（方案 B）

把直向走行面的心轨降低值按密贴状态重建：79.13–80.28 m 心轨轨顶抬到 z=0
（与翼轨齐平），翼轨保留其刨切过渡；重建后要求：

1. 平直段静载仍为 59 680.6 N（不得漂移）；
2. 辙叉区右轨力落在 Simpack 的 27.7–135.0 kN 带内，且**不允许力归零**；
3. 轮对垂向行程与 Simpack 的 0.594 mm 同量级（当前 1.25 mm）。

## 产物

- 代码：`src/velch/vehicle.py`（`RailBody.y_window_m` / `accepts_contact_y`）、
  `src/velch/vehicle_solver.py`（`_attribute_bodies`、`BODY_SWITCH_*`）、
  `src/velch/model.py:106`（`RunSettings.body_hysteresis`）
- 脚本：`validation/crh380a_m/make_attr_cases.py`、`cmp_attr.py`、`probe_frog_bodies.py`
- 算例：`case_attr_frog_gate{736,740}_{plain,hyst}.json`
- 运行目录：`out_attr_base_G/`、`out_attr_gate736_plain/`、`out_attr_gate736_hyst/`、
  `out_attr_gate740_hyst/`
