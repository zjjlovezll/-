# 降低值旋钮可用，但两条刚性路线都卡在同一处站表拼接

日期：2026-10-29（目标第 12 轮之后的第二次增量）
提交：本轮

## 一句话

「把降低值做成剖面深度偏置」这件事已经**在代码里成立并且加了守卫**（`z_offset_m` 逐点可加、不动横向坐标）；
但要在**刚性直向**两个区段上真正转这个旋钮，先得修一处**站表拼接**缺陷——刀尖区（约 53.7 m）与心轨区（约 103–116 m）
都会报同一个家族的错误：相邻两站的断面**没有共同的横向覆盖**。

## 一、旋钮（本轮的代码增量）

`profiles.py:120` 的 `z = raw[:,1] * z_scale_m * z_sign + z_offset_m`，而 `vehicle.py:394` 从算例的
`stations[].profile` 里读 `z_offset_m`。所以「injured 断面」= 设计断面 + 一个有符号的深度偏置，
**不需要新文件、不需要重建几何**。

`tests/test_lowering_offset.py` 三项把这件事钉住：

| 判据 | 结果 |
|---|---|
| +22.6 mm 偏置后每一点都恰好高 22.6 mm（atol 1e-12） | 通过 |
| 偏置**不动**横向坐标（`array_equal(y)`） | 通过 |
| 不给偏置时与显式 0 逐位相同（冻结算例不受影响） | 通过 |

为什么值得单独写测试：仓库里已经有四次「键名写错 → 被静默忽略」的事故（`align_to_track`、
`curve_rail_surface`、`(1−κy)`、横向速率），而旋钮失效的症状是**读数不变**，和物理结论撞在一起分不开。

## 二、算例的真实结构（本轮读出来的）

`scratch/s30/case_diverging_gauge.json`：

```
rail_templates: left  → stations 19001 个，s_m 30.0 .. 125.0
                right → stations 16664 个，s_m 30.0 .. 116.59，并带 event_branches
station 的键： id / s_m / profile{file, format, units, y_sign, y_offset_m, z_sign, z_offset_m?}
```

所以「心轨区（103.28–116.44 m）」**在算例里确实存在**，但它落在 right 模板的后段，而 right 模板在
这一段会切换不同的断面族（`event_branches`），这才是问题所在。

## 三、两条刚性路线的卡点（都是同一处）

| 尝试 | 读数 | 性质 |
|---|---|---|
| 直向刚性，起点 30 m，跑到刀尖区（53.7 m） | `graph slope limit at axle1_left/left:main …`（第 12 轮） | 窄切片被选中：`pen 3143.53 µm、lever_y +0.71535、slope 1.274` |
| 直向刚性，起点 95 m（把轴放到 105/102.5/87.5/85 m），想在 103–116 m 转旋钮 | `ProfileError: adjacent profiles have no lateral overlap`（本轮） | 静平衡阶段就抛：相邻两站断面的横向覆盖不相交 |

两者是同一件事的两面：**站表把不同来源、不同横向跨度的断面拼在一起**，而在拼接点附近
（a）纵向斜率无定义（`_station_derivative` 要求共同横向区间），或者（b）只落在窄／侧向切片上
被斜率门拒绝。

## 四、所以下一步是修拼接，不是再调旋钮

修法（按代价排序，均不触碰容差）：

1. **补齐共同横向区间**：拼接点两侧的断面统一重采样到 `[−0.0357, +0.0717]` 这类共同跨度上
   （图纸断面就是这个量级），拼接点前后各留 ≥0.5 m 的过渡；
2. **过渡段显式插值**：在拼接点前后 0.5–1.0 m 内按里程线性混合两族断面的 `z(y)`，让斜率连续；
3. 修完的判据：`dz_ds` 在 100–118 m 全程有限；起点 95 m 的静平衡残差 < 1e-5 N、八轮 0.625–1.6× 均载。

## 五、已经站得住的部分（不依赖上面那处修复）

- **柔性轨道路线上，降低值反演已经跑通**：尖轨 23.0 mm、心轨 23.0 mm，比值 1.0000 对真值 22.6 mm
  （−1.8 %）；`+0.268 mm` 剖面偏置 → `+0.268 mm` 载荷等效（1.01 %，第 208 轮）。
- **旋钮可用且有守卫**（本轮）。
- 冻结基线与七门不受影响：本轮只加测试与文档。

## 六、复算

```bash
cd F:/ai道岔状态反演辨识/Velch
PYTHONPATH=src python -X utf8 -m pytest tests/test_lowering_offset.py -q --basetemp ../scratch/pytest
PYTHONPATH=src python -X utf8 - <<'PY'   # 复现第三节第二行
import json; from pathlib import Path
raw = json.loads(Path(r"../scratch/s30/case_diverging_gauge.json").read_text(encoding="utf-8"))
print([(t["id"], len(t["stations"]), t["stations"][0]["s_m"], t["stations"][-1]["s_m"]) for t in raw["rail_templates"]])
PY
```
