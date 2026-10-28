# 两点接触：把接触算法补齐，并量清它对曲线能力的影响

日期 2026-10-28。依据文献 L12（轮轨接触点／两点接触／共形接触算法）与 L13（Kalker、
FASTSIM、Polach 的切向律），把求解器的接触搜索从「一个斑」扩到「多个斑」。

## 1 为什么改

曲线的横向力预算在上一轮被量成三项（`CURVE_LATERAL_CAPABILITY_2026-10-28.md`）：

| 项 | 实测 | 占 21 842.4 N 需求 |
|---|---|---|
| 轨顶法向倾斜（`n_y/n_z = ±0.0250`，左右反号） | 每斑 ±1.49 kN，净 **+36.8 N** | 0.2 % |
| 蠕滑（`f22 = 5.0e5 N`，`slip_lat ≈ 11 mm/s`） | 每斑 ≈ +248 N，净 **+497 N** | 2.3 % |
| 位移到 ±0.5 mm 的带内上限 | **8 169.6 N** | **37.4 %** |

而真正让状态走掉的是：稳态框架平衡在 `f22 = 5.0e5 N` 下**不存在**（九颗种子全部 `xtol`，
`|r|max = 8.4124e+03 N`，`cond 1.505e+04`）。上一轮把「力不够」定在蠕滑尺度上；本轮先按
用户的指示，把文献里的**两点接触**补齐——因为它是「接触算法」这一层唯一还缺的东西，而且
它能解释文献里为什么曲线通过不需要把 `f22` 放大十倍。

## 2 改了什么（三处，都是结构性改动）

### 2.1 `masked_sample_around`（`Velch/src/velch/contact_search.py`）

```python
def masked_sample_around(sample, *, center_y_m, exclusion_m, drop_m=10.0) -> ProfileSample:
```

把已采样表面的主斑带**压到 10 m 以下**（`z[mask] -= drop_m`），于是普通的
`find_graph_contact`——用它**自己的策略**——去找下一个最深的瓣。用「挖井」而不是「删除」，
是因为 `np.interp` 要求横坐标单调增，删除会在缺口里插出一个**不存在的表面**。窗口内没有
采样点时返回**同一个对象**，这是「单斑算例逐位不变」的构造性保证，而不是运气。

### 2.2 两个判据（`Velch/src/velch/model.py`）

| 字段 | 默认 | 依据 |
|---|---|---|
| `contact_two_point` | `True` | 见 §3 |
| `contact_two_point_exclusion_m` | `0.012` | 胎面斑与轮缘根相距约 55 mm，同一胎面上的双极值相距 **8.06 mm** |
| `contact_two_point_min_slope` | `0.25` | 第二个**平**瓣是同一胎面的另一块，只有陡面才是第二个物体 |

三个字段都在 `__post_init__` 里校验（布尔、有限、正）。

### 2.3 求解器（`Velch/src/velch/vehicle_solver.py`）

- 主斑的 ~23 个关键字参数收进 `_contact_search_kwargs(...)` 一个字典——两个斑不可能各走一套策略；
- 力律抽成 `_contact_response(...)`（曲率属于线路的那段注释跟着它走）；
- 新增 `_second_contact(...)`：掩蔽主斑 → 再搜 → 拒绝 `penetration <= 0` → 拒绝间距 `< 排除窗` →
  拒绝 `|n_y/n_z| < min_slope` → 过 `body.accepts_contact_y` → 耦合倾角 → `_contact_response`，
  并要求 `active and normal_force_n > 0`；
- **坡度守卫按物理重新推导，而不是放松**：原来遇到陡法向立刻 `raise`；现在把陡斑收集起来，
  只有当该接触**没有任何一个斑是缓的**时才抛，且沿用一字不差的报错
  `graph slope limit at {rail}/{body}, x={x:.9g} m`。理由有实测：轮缘根分担载荷时
  `n_y/n_z = 0.7216/0.6923`（斜率 1.04）是**正常物理**；守卫要防的是「只有一个陡斑、胎面什么都没碰」。

## 3 三次测量的过程（默认值是被测出来的，不是选的）

| 版本 | 结果 | 结论 |
|---|---|---|
| 开，排除窗 8 mm | **动了冻结 oracle**：`test_oracle_frozen` 两条失败（ACTUAL `−0.00042` vs DESIRED `−0.000463`） | 不能这样上 |
| 同上，量病因 | `case_A_plain` 就座态：每根轨裂成两斑——**41 400.5 N @ y = −0.75277（154.86 µm）** + **18 298.0 N @ y = −0.74471（89.85 µm）**，相距 **8.06 mm**，都在同一轨顶 | 这是**一个**赫兹斑被型面自身的双曲率看成两个极值，不是胎面/轮缘 |
| 关 → 排除窗 12 mm → 再开 | 仍然裂（8 根轨 × 2，合并 59 698.462 N，竖向 −0.4496 mm） | 距离不够，必须加坡度判据 |
| 两个判据齐备 | `two_point=False`：每轨 1 斑，`59 680.5769 N`，竖向 `−0.4628 mm`，残差 `1.88e-08`；`two_point=True`：**逐位相同** | 默认翻回 `True`，`test_oracle_frozen` 3 passed |

`tests/test_two_point_contact.py` **5 项**：

1. `test_the_masked_surface_keeps_the_abscissa_and_invents_nothing` —— 横坐标单调、长度不变、
   窗内压深 >5 m、窗外逐位不变、空窗返回**同一对象**；
2. `test_the_search_can_be_turned_off_and_still_matches_the_frozen_anchor` —— 关掉时仍是静止锚（59 680.5769 N / −0.4628 mm）；
3. `test_the_two_point_search_reproduces_the_frozen_anchor_bit_for_bit` —— **开与关的状态、逐轨法向力 `assert_array_equal`**，且每轨只有 1 个承载斑；
4. `test_both_criteria_are_load_bearing_on_the_measured_artefact` —— 出厂判据下每轨 1 斑；
   把排除窗放到 4 mm、坡度门放到 0.002，就复现那个 artefact（每轨 2 斑）⇒ **两个判据都在承重**；
5. `test_a_lone_steep_contact_still_raises_the_slope_guard` —— 整体横移 12 mm 后只剩一个陡斑，
   仍然抛 `graph slope limit at …`，报文格式未变 ⇒ **守卫没有被放松**。

## 4 对曲线能力的影响：实现了，但在本曲线工况上是**惰性**的

`--curvature-force --duration 0.34 --radius 1100 --run-at 30 --seat-at 30`：

| 量 | 上一轮（单斑） | 本轮（两点接触开） |
|---|---|---|
| 就座 | 8/8，0.988–1.000× | 8/8，0.988–1.000× |
| 运行 | `numerically_checked` 1701 帧 7/7 | **完全相同** |
| 最大侵入 | 120.51 µm | **120.51 µm** |
| 末帧 `sum Fy` | −17 062.8 N（−78.1 %） | −17 062.7 N（**−78.1 %**） |
| 末帧转移 | +25 048 N | **+25 048 N** |

**原因是可以算出来的**：轮缘根在胎面以下约 23 mm，而这条曲线全程最大侵入 **0.12 mm（0.34 s）
到 0.28 mm（0.60 s）**，差两个数量级。所以两点接触在这条曲线上**永远不会触发**——
它不是那条缺的腿。

顺带否掉一条本来很自然的猜测：既然 `graph slope limit` 由轮缘触发，那么「放宽守卫」应当能救曲线。
实测不是——守卫是在**轮缘已经顶上**之后才响的，放开它只是让那次非法接触进入状态。这也正是
项目规则禁止的做法，本轮没有做。

## 5 结论

1. **接触算法已按 L12 补齐**：多斑搜索、两个判据、守卫按物理重推，冻结静止锚**逐位不变**（59 680.5769 N / −0.4628 mm / 残差 1.88e-08）。
2. **它不解决曲线**：在 R = 1100 m / 80 km/h 上两点接触不触发（侵入 0.12 mm 对 23 mm 的轮缘高度）。
3. 因此曲线的账单仍然是**横向力预算**：在带内（8/8 且每轮 ∈[0.625,1.6]×）最多给 8 169.6 N = 37.4 % 的需求；要凑满必须 ±59.66 kN 的倒载 = 物理倒载（±43.9 kN）的 2.7 倍，而那时四轮离轨、四轮双载。
4. 下一步仍是上一轮登记、**待授权**的那一项：把 `f11`/`f22` 放回 Kalker 尺度（`3.5e6` / `2.5e6` N）并保留 `μN` 饱和，预登记判据 8/8 在带内、`sum Fy ≥ 0.9×` 需求、0.34 s 内 7/7 门。若仍不过，曲线项按「系数标定不足以救曲线」写入降级路径。

## 6 复算

```bash
cd Velch && PYTHONPATH=src python -X utf8 -m pytest tests/test_two_point_contact.py tests/test_oracle_frozen.py -q
cd Velch && PYTHONPATH=src python -X utf8 scripts/s32_curved_station_table.py --curvature-force --duration 0.34 --radius 1100 --run-at 30 --seat-at 30
cd Velch && PYTHONPATH=src python -X utf8 scripts/s43_running_equilibrium.py --capability
```

## 7 边界

- 两点接触的**几何**只用了单滚动圆的踏面型面加轮缘；轮背/轮缘根的实际共形接触（L12 的 conformal 分支）没有建；
- 未验证「真两斑」在时程里的稳定性：本模型里没有找到能同时压住胎面与轮缘根的物理状态（横移 12 mm 时只剩轮缘一个陡斑），所以第 4 项测试用的是「出厂判据 vs 放松判据」的对照，而不是一段两斑时程；
- 该判据的排除窗（12 mm）与坡度门（0.25）都是按本车型/型面量的，换车或换型面必须重量。
