# 第 8、9 条门：起点与平稳性（第 314 轮）

七条数值门回答的是"积分器做对了吗"。它们在这一轮之前**同时**放行了一趟"起点没坐稳"的运行：60 km/h、0.54 s 那趟前轴右轨法向力在 **0–207.75 kN** 之间摆（std **34.75 kN**），七门依然 **7/7**。原因不是门写错了，而是那七条里**没有一条**读起点状态或力的历程。

所以这一轮**加**两条门（不加门不减门的最低要求是不替换任何既有判据），并把状态从二值改成三值。

---

## 1. 第 8 条：`launch_balance`（起点）

读两个数，都是座椅（`_seat`）已经给出的：

| 量 | 门限 | 来源 |
|---|---|---|
| `vertical_preload_residual_n` | ≤ **0.1 N** | 与既有 `vertical_preload_residual` 同一条限 |
| `spin_relative_max` = \|spin·r − travel\| / travel | ≤ **1e-3** | 与既有 `spin_tracking` 同一条限 |

两条都是**已经在用的**门限，没有新拍的数字。

**为什么模态残差不进这条门**：第 312 轮我拍过一个 `LAUNCH_MODAL_RESIDUAL_N = 0.1`，实测是 60 km/h **106.74 N**、80 km/h **101.45 N**；把沉降轮数从 80 提到 **400**，`|modal|` 与残差**逐位相同**（1.2471e-03 m / 101.45 N）。它是 `_settle_modal_coordinates` 与 `_seat` 交替的**不动点性质**，不是某趟运行的缺陷，也与速度无关。把一个没人标定过的数字变成门，就是"发明容差"，所以它**只上报**（占轮载 0.170 % @80、0.179 % @60），要不要紧由第 9 条门回答。

## 2. 第 9 条：`stationarity`（平稳性）

定义（**第 314 轮末尾收紧过一次，见第 9 节**）：只在算例**声明了读数窗口** `run.stationarity_window_m` 时产生；在该窗口内（按前轴里程取样）八个轨法向力的标准差取最大者，门限 **5 kN**。窗口内少于 3 个样本 ⇒ 直接失败，不允许"没量到就算过"。

第一次的写法是**整段记录**的 std，被自己的闸门否决了：冻结基线在头 0.015 s 里把 **53.88 kN** 从 `stock` 搬到 `switch`（合法的尖轨转移），整段 std 必然几十 kN。

这个 5 kN 不是我挑的，是它两侧都有实测：

| 类别 | 实测 std | 出处 |
|---|---|---|
| 振着的那趟 60 km/h（0.54 s） | **34.75 kN**（0–207.75 kN） | 第 310 轮撤回的那趟 |
| 新路径 60 km/h（0.02 s） | **0.103 kN**（最大跨度 0.439 kN） | 第 313 轮 |
| 新路径 80 km/h（0.02 s） | **0.096 kN**（最大跨度 0.417 kN） | 第 313 轮 |
| 静下来的 100 km/h | **0.51 kN**（56.35–62.11 kN） | 第 310 轮 |
| 有的凸起算例（60 µm） | 0.20–0.80 kN | 第 311 轮审计（63 个归档） |

⇒ 5 kN 在**振着的 34.75 kN 之下 7 倍**、在**最吵的安静趟 0.51 kN 之上约 10 倍**，中间是空的。测试把两侧都钉住（`test_the_threshold_sits_in_the_measured_gap`），所以"把常量往正在失败的那趟挪一点"这条路两侧都被堵。

## 3. 状态从二值改三值

一条"起点没坐稳"的运行不是数值错误，把它记成 `numerical_gate_failed` 会让人去查积分器。所以：

| `result_status` | 条件 |
|---|---|
| `numerically_checked` | 九条全过 |
| **`physical_gate_failed`** | 只有 `launch_balance` / `stationarity` 失败 |
| `numerical_gate_failed` | 其余（数值）门里有失败 |

`gates` 字典仍然是一个 `all_passed` 的开关，任何下游读它都不用改。

## 4. 一个开关"能关掉门"就不再是门

第 312 轮我把起点报告挂在 `run.report_launch` 后面（默认 `False`）。这一轮改成：**起点报告无条件计算**，`report_launch` 只决定它**打印/写档案**与否。理由很直接：一个用设置就能关掉的检查，等于没有。

顺带把档案补全：`meta.json` 现在也带 `result_status`、`failed_gates`、`max_rail_force_std_kn`、`stationary_force_std_limit_kn` 和 `launch`（此前 `launch` 只在 `index.jsonl` 的行里，而"描述一趟运行"的文件是 `meta.json`）。加这一段时我自己的补丁把 `summary` 变量插到了 `main()` 里而不是 `write_archive()` 里，`NameError` 当场暴露——由测试 `test_a_run_archived_after_the_gates_carries_all_nine` 抓住。

## 5. 实测（本轮）

```
scripts/s172_run_case.py --set speed.kmh=60
  one_set_straight-060.00kmh-0.0200s-500us-69281ee8: frames 41  gates 9/9  wall 57.0 s
  launch_balance: True   stationarity: True
  window 56..65 m, samples 41, max rail std 0.103 kN
  launch |modal| 1.2431e-03 m, modal residual 106.74 N (0.179 %), preload 8.40e-08 N, spin 0.000e+00

scripts/s172_run_case.py --set speed.kmh=80
  one_set_straight-080.00kmh-0.0200s-500us-a18815bb: frames 41  gates 9/9  wall 17.4 s
  window 56..65 m, samples 41, max rail std 0.0962 kN
  launch |modal| 1.2471e-03 m, modal residual 101.45 N (0.170 %)
```

对照（同一套判据，用归档自己的序列重算）：

```
one_set_x46-060.00kmh-0.5400s-500us-83e727fc   max rail std 34.75 kN  ->  stationarity False
                                              (status would be physical_gate_failed)
```

## 6. 对已有归档的影响（不追溯改写）

已经落盘的归档保留它们自己的门记录：它们当时只有 7 条，`result_status` 仍是 `numerically_checked`。**门不能追溯清理旧文件，它只防止新的再产生。** 所以第 310 轮对 60 km/h 那一行的**撤回继续有效**，恢复仍然要一趟 ≥1.6 s 且过平稳性——这一轮没有跑它。

## 7. 边界

1. 第 9 条读**输出样本**：`output_step_s = 5e-4` 时 0.02 s 只有 41 帧，短窗的 std 本身有抽样误差（这是它作为"起跑即静"的粗筛，不是精细判据）；
2. 5 kN 是**实测分离度**，不是从某个物理容差推导出来的；换算例（更多轨、更多模态、更长窗）要重新测这个分离度才能沿用；
3. 只在本算例（234 维、`local_compliant`、直向）验证；曲向、实测反演（`Ω_obs`）未动；
4. 冻结物理未动：59 680.57685863 N / 65.4661 µm，`freeze_baseline --check` 见提交；
5. 七条数值门的定义一个字没改。

## 8. 复算

```bat
python -X utf8 scripts/s172_run_case.py --set speed.kmh=60
python -X utf8 scripts/s172_run_case.py --set speed.kmh=80
python -X utf8 -m pytest tests/test_launch_gates.py tests/test_spin_control.py -q
```

测试里 `test_gate_nine_separates_the_ringing_archive_from_the_quiet_pair` 直接读三个归档的
`series.npz`，不依赖任何本轮写入的数字，因此归档被重写时它会跟着变。

## 9. 这一条第一次写宽了：整段 std 把合法事件判成"没静下来"（已改）

第一次提交闸门给的是 **REJECT**（`reports/auto_accept_20261101-185212.json`）：`tests` 562.14 s 里 **4 failed / 1357 passed**，`end-to-end` 的 frog 冒烟回了 `physical_gate_failed`。逐项量下来，错的是判据，不是那些算例。

**1）基线算例为什么"不平稳"**（`examples/vehicle_v2/case.json`，2 m/s、0.015 s、31 帧、只走 30 mm）：

```
status physical_gate_failed   failed ['stationarity']
max rail std 53.877 kN   （axle1_right_switch 53.877，axle1_right_stock 23.595）
```

它带的正是**尖轨 lowering 的基线几何**：30 mm 行程里轮载从基本轨**合法转移**到 `switch` 体，`axle1_right_switch` 从 0 起跳。整段 std 几十 kN 是这个算例的**本分**，不是抖动。

**2）"首 10 %"也救不了它**——这一族 14 个归档里首 10 % 确实分得更好（≤0.72 kN 对振着的 7.94 / 10.11 kN），但那是 `one_set` 家族（准静态直向）的实测，不能外推到带事件的道岔算例。

**3）因此把适用域收紧，而不是放宽阈值**：第 9 条只在算例**声明读数窗口**时产生。没有声明 ⇒ 不产生该门 ⇒ `numerically_checked`，即"没有声明就没有主张"。这与 `spin_tracking` 只在有伺服时出现是同一条约定（`test_a_constant_profile_adds_no_gate_and_no_metric` 一直钉着它）。

**4）配额写进了 setup 端口**：`setups/one_set_straight.json` 声明 `stationarity_window_m: [56.0, 65.0]`，配套两个几何端口 `start_x_m: 46.0` / `seat_start_m: 40.0`——因为算例默认从 40 m 起跑（前轴 50 m），**到不了** 56 m 的窗口。第一次跑就是这样：窗口 0 个样本 ⇒ 门失败（这正是"窗口没量到不许算过"的行为，而不是 bug）。`--set reading.window_m=none` 可以显式撤掉主张。

**5）改后实测**：60/80 km/h 都 **9/9**（窗口内 41 个样本、max std 0.103 / 0.0962 kN），基线算例 **8/8**、`stationarity` 不出现、`result_status = numerically_checked`。

**这一条要记住的是**：我上一轮用"整段 std"去判"起跑即静"，是在**同一条数据上换了一把更钝的尺子**；尺子自己的第一次读数就把冻结基线判成失败，这是它该被否的信号，不是它被判得太严。
