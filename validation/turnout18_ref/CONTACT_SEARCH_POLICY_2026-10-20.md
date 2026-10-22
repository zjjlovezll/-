# 接触搜索策略 A/B：三个"对标 Simpack"的结构性改动全部实测

日期：2026-10-20
算例基座：`validation/crh380a_m/case_frog_I_wing_0p05s.json`（翼轨连续体，0.05 s，前轴 79.0→83.9 m，350 km/h）
运行：`python -X utf8 -m velch run-vehicle <case> --output <dir>`
度量：`python -X utf8 validation/crh380a_m/minpen_report.py <history.csv>`

## 1. 改了什么（全部默认关闭，旧算例不受影响）

| 旋钮 | 位置 | 默认 | 作用 |
|---|---|---|---|
| `run.contact_seed_scope` | `model.py` `RunSettings` | `"body"` | `"rail"` 时同一侧所有轨体共用一个"轮子当前接触位置"种子，任何单步横移不得超过 ±半宽 |
| `run.body_hysteresis` | 同上 | `false` | 每侧只允许一个轨体承载，换体需在位者卸载到 <0.05 mm 且挑战者深 0.02 mm |
| `contact.duplicate_patch_window_m` | `contact.py` `ContactParameters` | `0.0` | 两个接触点横向距离小于该值时，只保留较深的一个，避免同一接触斑被两个轨体各算一次力 |

实现要点：`contact.py` 新增 `deduplicate_contacts()`（按侵入深度降序贪心保留，互斥半径外独立）；`vehicle_solver.py` 的 `_evaluate_patch` 在 `seeds` 里找不到本体的种子时回落到 `"__rail__"` 种子，`evaluate` 在归属之后调用去重。测试 `42 passed`（原 28 项 + 既有 14 项）。

## 2. 实测结果（0.05 s 辙叉窗，单次运行）

| 策略 | 右轨峰值 | 右轨均值 | 脱空采样 | 在载最小侵入 | 最大侵入 | 轮心行程 |
|---|---|---|---|---|---|---|
| I_wing 基座（无窗、无迟滞、无去重） | **229.2 kN** | 59.0 | 34/101 | 22.8 µm | 0.486 mm | 0.440 mm |
| + 钢轨级种子 5 mm + 去重 4 mm | 269.9 kN | 63.2 | 38/101 | 30.9 µm | 0.541 mm | 0.557 mm |
| + 上述 + 换体迟滞 | **627.9 kN** | 58.5 | 63/101 | 16.9 µm | 0.955 mm | 1.845 mm |
| Simpack 同一段（2401 点中的 78.8–82.2 m） | 127.8 kN | ~61 | **0** | **4.8 µm** | 0.433 mm | 0.594 mm |

## 3. 结论（与我上一轮的假设相反）

1. **钢轨级有界搜索没有帮助**（229→270 kN）。原因是：窗口只能限制"横移幅度"，不能凭空造出支撑力；当窗口内的所有候选侵入都为负时，代码按设计回落到全跨度搜索，于是窗口等于空操作，而限幅本身又拖慢了换体。
2. **换体迟滞显著变坏**（230→628 kN）。强制单一承载体意味着轮子必须跟着"被选中那个体"的纵向起伏走；我们的辙叉区两个体的起伏相位不同，锁死一个体反而放大动态侵入（0.486→0.955 mm）。
3. **斑间去重在当前几何下几乎不触发**（两体相距 30–40 mm，远大于 4 mm 窗），保留它是正确性保险，不是性能杠杆。
4. 因此"Simpack 用有界搜索 + 单斑承载"这一结构性解释**被实测否定**。它在本模型里不是收益来源。

## 4. 目前最好结果与差距的准确表述

- 起点 596 kN → 现在 **229 kN**（2.6×），脱空 65→34 个采样，最大侵入 0.920→0.486 mm。
- 与 Simpack 的剩余差距：峰值 1.8×，且我们是"间歇脱空 + 冲击"，它是"全程微侵入跟随"（最小 4.8 µm / 8.66 kN，从不归零）。
- 这个差别不能再用接触搜索策略解释（已试遍）；它落在"力在近零侵入处如何接合"这一层，而这一层我们与它的口径不同：我们是严格单边（δ≤0 即零力），它在 δ≈5 µm 处仍有 8.7 kN。

## 5. 三个旋钮的处置

三个都保留、默认关闭、写进算例 schema。理由：它们各自解决的是**正确性问题**（去重防重复计力、种子作用域防单步横跳、迟滞防抖振），而不是精度问题；在需要复现"单斑承载"假设的对比研究里仍然有用，但不应作为默认。

## 6. 复现命令

```bat
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 validation\crh380a_m\make_policy_case.py validation\crh380a_m\case_frog_I_wing_0p05s.json validation\crh380a_m\case_frog_K_railseed.json --half-width-mm 5 --seed-scope rail --dedupe-mm 4
python -X utf8 -m velch run-vehicle validation\crh380a_m\case_frog_K_railseed.json --output validation\crh380a_m\out_K_railseed
python -X utf8 validation\crh380a_m\minpen_report.py validation\crh380a_m\out_K_railseed\history.csv
```
