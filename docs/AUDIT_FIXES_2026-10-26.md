# 2026-10-26 只读审查的七个缺陷与修法

代码审查工程师做了一轮只读审查（HEAD `a9f43c8`）。**七个缺陷里有两个属于"静默"级**：会算错数值，但不报错、不过不了任何一道门、也没有一条测试会红。这一页记下每个缺陷的触发条件、后果、修法与回归测试。

## 先纠正我自己的一个误判

我此前报告"`.tre` 不平顺在算例上完全不生效（缺陷）"。审查否证了它：**施加链路端到端完好**，`ShiftedSeries` 在 40.5125 m 处确实给出 +30.0 µm。真正的原因是**几何错配**——`x_start_m = 38` 时四根轴分别扫过 28.0–33.6 m 与 45.5–53.6 m（轴偏置 ±10 / ±7.5 m），而波磨带在 40–41 m，**没有任何车轮走到它**。把 `x_start_m` 改成 30，立刻出现差别（`max|ΔF| = 7.56e4 N`，逐位比较为 `False`）。

这类失败现在不再无声：装配完 `irregularity` 后会做一次里程区间求交，空交时发 `RuntimeWarning` 并把 `reach`（四轴区间 + 激励带 + `overlaps`）写进 `irregularity` 记录，因此也进了产物 sidecar。

## 七个缺陷

| 编号 | 位置 | 触发 | 后果 | 修法 |
|---|---|---|---|---|
| **B028** | `src/velch/track_models.py` `internal_force` / `potential_j` / `support_reaction` | 任一 `local_compliant` 算例且状态维数 ≠ 35（节点表 38 / 86 坐标） | 竖向支撑刚度、位能、功率全部读到错的位置 → **竖向等于无支撑**，横向仍正确，所以不崩、只算错 | 三处硬编码 `36 + 2*i` 一律改为 `self.offset + 2*i (+1)`；`offset=35` 时逐位不变 |
| **B029** | `src/velch/solver.py:73` | v1 求解路径 + 任何 `irregularity` 块 | 取 `rail.profiles`（从未被 `shift_rails` 包装）→ `.tre` **100 % 不生效、无报错** | 改为走 `rail.contact_bodies`（无则回落 `rail.profiles`），与 v2 `/vehicle_solver.py:513` 对齐 |
| **B030** | `src/velch/contact_search.py` 两处 LRU 键 | `geometry_policy = "cached_grid"` 且不平顺含 `lateral`/`gauge`/`roll`（`vehicle.py` 默认四通道全开） | 键里只有 `rail_z` 指纹、没有横向项 → 横向/轨距/超高被缓存吞掉，静默失效 | 键补 `rail_y[0]/[mid]/[-1]` |
| **B031** | `src/velch/uncertainty.py` `fold_non_negative` | 反演出负的带幅值 | `sqrt(x)**2` 是恒等式，方差一点没折 → 该分量变成"均值 0、σ 不变"，即**报告为确定等于 0**，后续 z 分数与覆盖率全错 | 折叠后半正态方差 `(1 − 2/π)·σ²`，测试同步改 |
| **B032** | `packaging/portable_models.py` `build()` | `--target` 手误指向非空目录 | `shutil.rmtree` 无条件删；语料不在版本控制里，删了不可恢复 | 只替换"空目录或含 `BUNDLE.json`"的目标，否则拒绝并说明 |
| **B033** | `src/velch/irregularity_gen.py` 通道循环 | 请求两个以上通道 | 三元表达式两个分支都是 `field.copy()` → 横/竖**完全相关（corr = 1.0）**，侧滚响应被系统性放大 | 每个通道独立随机相位（同 seed 仍逐通道可复现） |
| **B034** | 同文件 `generate()` 默认参数 | 无参调用 / CLI 缺省 | `step 0.05` 与 `shortest 0.05` 自相矛盾，必抛异常 | 默认 `step = shortest/2` |

另有一条只读提示（未改）：`assets.py` 的 `lib:` 前缀现在带包含性校验，`lib:../..` 不再能越出数据根；`data_root.py` 的 marker 提示名在 `BUNDLED_CORPUS` 生效时可能指错，属排障体验问题，未纳入本轮。

## 为什么这些能活这么久

B028 被 **O010 抢先挡住**：节点表车型在柔性轨道上静平衡本来就不收敛（38 与 86 坐标都失败），所以谁也没跑到"竖向无支撑"那一步看见错数值。**一旦 O010 修好，B028 会立刻变成静默错数**——这是本轮最重要的收获，也是它排第一的原因。

B029/B030 一条发生在 v1 旧路径、一条只在非默认 `geometry_policy` 下触发，都不在任何验收门覆盖范围内。B031 的错误恰好是"看起来更确定"，而不是更可疑。

## 回归测试

`tests/test_audit_fixes.py`（9 项，全部通过）：

- `offset ∈ {35, 38, 86}` 下 `internal_force` 的横向与竖向行都等于 `−k·q`（B028，两条）；
- 位能与 offset 无关（B028）；
- 两通道相关性 `|ρ| < 0.5` 且同 seed 逐通道可复现（B033）；
- 无参 `generate()` 能跑（B034）；
- `_irregularity_reach` 在"带在 40–41 m、轴扫 28–33.6 / 45.5–53.6"时报 `overlaps = False`，把起点改到 30 m 后报 `True` 并给出 `band_m`。

`tests/test_uncertainty.py` 里折叠那条同步改成半正态方差（B031）。

## 验证

```
pytest tests -q --basetemp F:\velch_tmp\pytest   → 838 passed, 1 skipped in 117.21s
```

冻结物理未动：`offset=35` 是唯一被冻结基线走到的分支，`self.offset + 2*i + 1` 与旧 `36 + 2*i` 逐位相同，因此静载门 59 680.5769 N / 65.47 µm、八接触峰值 89.68 / 170.61 kN、七项门、DOP853 轨迹都不受影响（`tests/test_oracle_frozen.py` 全绿）。

## 修完之后：`.tre` 与 PRR 两条路径等价（0.13 %）

把三个算例的 `x_start_m` 从 38 改成 **30**（让 axle1 从 40.0 走到 41.0 m），其余不变：

| 运行 | 444.4 Hz 处 \|a\|（轴箱垂向） | 该窗内力标准差 |
|---|---|---|
| 零不平顺 | 0.19213 m/s² | 247.8 N |
| **`.tre` 30 µm / 50 mm** | **0.87302 m/s²** | 36 636.2 N |
| **PRR 点集改写 30 µm / 50 mm** | **0.87186 m/s²** | 36 514.4 N |

两条施加路径相差 **0.13 %**，所以"改 PRR 点集"与"给 `.tre`"在这套求解器里是同一条物理，可以互相校验。
用本窗实测增益（29 101 (m/s²)/m）反演得到 30.0 µm（真值 30 µm，0.0 %）；用 80 km/h 标定常数
26 455 反演得到 **33.0 µm（+10.0 %）**——这与我上一轮报的 −44 % 不同，那个数字来自"`.tre` 空转"
的错配对照，已作废。

## 复算命令

```powershell
cd F:\ai道岔状态反演辨识\Velch
$env:PYTHONPATH="F:\ai道岔状态反演辨识\Velch\src"
python -X utf8 -m pytest tests\test_audit_fixes.py tests\test_uncertainty.py -q --basetemp F:\velch_tmp\pytest
# .tre 覆盖自检现在的样子（把起点放回 38 m 就会看到这条警告）
python -X utf8 -c "from pathlib import Path; from velch.vehicle import load_vehicle_case; load_vehicle_case(Path('F:/velch_tmp/prr/case_tre.json'))"
```
