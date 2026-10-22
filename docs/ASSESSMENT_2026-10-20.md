# 标准评价指标（assess）：把仿真输出变成可判读的结论

日期 2026-10-20。`velch/ metrics.py` + `velch assess` 子命令，把任何一次运行的
`history.csv` 直接换算成铁路动力学报告要的三个指标，并按 GB/T 5599 客车限值判定。

## 用法

```bash
python -X utf8 -m velch assess <运行目录或 history.csv> \
        [--static-axle-load-n 210000] [--output assessment.json]
```

退出码：`0` 全部通过、`2` 超限或有错误。不加 `--static-axle-load-n` 时用本次运行
实测的平均轴重（`(P_L+P_R)/2` 的样本均值），这是诚实口径——它反映的是本模型的质量，
而不是外部假定值。

## 指标定义

| 指标 | 定义 | 默认限值 |
|---|---|---|
| 脱轨系数 | `Q/P = |F_y| / P`，逐采样逐侧取最大 | 0.80（客车） |
| 轮重减载率 | `ΔP/P̄`，`P̄ = (P_L+P_R)/2`，`ΔP = P̄ − min(P_L,P_R)` | 0.60 |
| 轮轴横向力 | `H = |F_y,L + F_y,R|` | `10 + P0/3` kN，P0 为静轴重 |

同时输出每根轴的 `P_L/P_R` 极值、左右两侧的 `active` 丢失采样数（=脱空计数），
以及 `verdict.checks[*].pass` 的逐项判定。

## 实测（`out_AB/case_AB_slab3`，辙叉窗 0.05 s）

```
axle   P_L min   P_L max   P_R min   P_R max     Q/P   side    dP/P     H kN  lost
   1     58.49     60.23     23.26    108.83   0.036  right   0.438     2.48     0
   2     59.45     59.92     29.31     91.75   0.039  right   0.341     1.18     0
   3     59.67     59.75     57.74     60.90   0.026  right   0.017     0.05     0
   4     59.50     60.05     55.01     64.96   0.028  right   0.041     0.26     0

PASS  derailment_coefficient     0.0389  (limit 0.8)
PASS  wheel_load_reduction       0.4382  (limit 0.6)
PASS  axle_lateral_force_n       2478    (limit 49760)
overall: PASS
```

信息量：脱轨系数只有 0.039（横力极小，符合“直向激励以垂向为主”的物理判断），
而轮重减载率 0.438 是真正接近限值的量——这正好是辙叉区轮载转移的直接后果，
也说明**后续反演最该盯的输出量是轮重减载率**，而不是峰值力。

## 产物

- `src/velch/metrics.py`：`AssessmentLimits`、`AxleAssessment`、`Assessment`、
  `assess_history()`、`mean_axle_load_n()`、`format_assessment()`
- `src/velch/cli.py`：`assess` 子命令
- `tests/test_metrics.py`（4 项）：已知行的解析校验、目录/CSV 两种入参、限值判定、
  缺列与缺文件的失败路径
- 全部 **64 项测试通过**
