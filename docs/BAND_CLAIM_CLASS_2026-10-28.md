# 带幅值必须带"标定谱类"：从约定变成构造约束

日期 2026-10-28 · 代码 `src/velch/inverse/verdict.py` · 产物 `reports/inversion_synthetic_2026-10-28/`
· 测试 `tests/test_verdict_calibration_class.py`（9 项）

第 195 轮测到：同一振幅水平下，一条 24 谐波随机记录在每个频点的响应比一根纯音低
**1.14–1.78 倍（1.2–5.0 dB）**，而把纯音振幅加大 8 倍只让 `|H|` 变 **0.17 %**。
所以标定算子不是"频率的函数"，而是**"谱类的函数"**：幅值数字脱离它被标定的激励谱类就没有意义。

这句话如果只写在文档里，下一个人一定会忘。本轮把它变成**构造性约束**。

## 1 规则

`LayerResult` 一旦满足下面两条，就**在构造时抛错**，而不是等到有人去读文档：

1. 状态是 `passed`；
2. `metrics` 里出现任何**带幅值声明**键（`band_amplitudes_um` / `band_hit_rate` / `band_errors_db`）。

此时 `metrics["calibration_class"]` 必须存在且四个字段齐全：

| 字段 | 含义 |
|---|---|
| `harmonic_count` | 谐波数（谱类） |
| `band_edges_m` | 波段上下界 |
| `rms_um` | 每带 rms |
| `crest_factor` | 峰值因数（标定记录的实测值） |

报错文案直接写清理由，并引用第 195 轮的数：

```
layer L3_inversion claims a band amplitude (band_hit_rate) without a declared calibration class;
missing ['harmonic_count', 'band_edges_m', 'rms_um', 'crest_factor'].  A calibrated operator is only
valid inside the excitation class it was calibrated on: a 24-harmonic record and a pure tone at the
same rms differ by 1.2-5.0 dB per band, so an undeclared 'within 2 dB' is not a claim.
```

**规则是单向的**：`failed` 的层可以在没有谱类的情况下报带幅值。理由是失效路径**不是声明**，
把降级路径堵死只会逼人去绕过规则（第 4 项测试专门钉住这一条）。

## 2 这一轮真正被跑通的产物：一条带谱类的判决

`scripts/s40_band_verdict.py` 读第 194 轮（同类标定）与第 195 轮（单音标定）写出的两个 JSON，
**不手抄任何数字**，组出一份 `Verdict`：

| 层 | 状态 | 关键数 |
|---|---|---|
| L0 准入 | passed | 直向、70.3206 km/h、补片 42.5–45.5 m、步长 2.5 mm、通道 `axle1_z_acc`、8 条预测 |
| L1 配准 | **skipped** | 单通道对单轨，没有第二通道可配 |
| L2 标定 | passed | 同类 **6/8**、单音 **3/8**；`\|H_tone/H_record\|` 中位 1.555 / 1.142 / 1.676 / 1.776；振幅扫描 **0.17 %** |
| L3 反演 | passed | `band_hit_rate = 0.75`，**附完整谱类** |
| L4 不确定度 | **skipped** | 只有两个种子，覆盖率会是关于样本的声明 |
| L5 验收 | **failed** | 8 条里 6 条进 2 dB，未达 8/8 |

```
measurement_validation_status = not_evaluated
```

`not_evaluated` 是正确结果，不是漏填：这条路是**合成自洽性检验**，不对实测做任何声明。
这也顺带验证了第 1 项的派生规则（L5 失败且 `detected: False` → `not_evaluated`；
`detected: 3` → `detection_only`）在新约束下没有被破坏。

`bands.csv` 16 行 = 2 种子 × 4 带 × 2 估计子，列 `seed, band, estimator, truth_um, recovered_um,
error_db, within_gate`。

**可复算性**：`reports/` 被 `.gitignore` 忽略，而两个源 JSON 原本只在 `../scratch` 里，所以
`reports/inversion_synthetic_2026-10-28/inputs/` 保留了它们的副本，脚本优先读 scratch、读不到就读这份。
把 scratch 挪走后重跑，输出逐项相同（已实测）。

## 3 谱类的实测值（不是设定值）

| 量 | 实测 |
|---|---|
| 每带 rms | **8.000 / 7.999 / 7.997 / 7.999 µm**（四条带都被归一到 8 µm） |
| 整条记录 rms | 种子 1030 **16.578 µm**、种子 1031 **15.487 µm** |
| 峰值 | 37.771 / 47.170 µm |
| 峰值因数 | **2.278 / 3.046** |

两点必须说清：

1. **8 µm 是每带，不是整条记录。** 四条带叠加后整条 rms 是 15.5–16.6 µm，
   前几轮文档里"8 µm rms"指的是**每带**，这里明确写下来。
2. **峰值因数归种子决定，不属于谱类常量**（2.28 vs 3.05，相差 34 %）。所以谱类里存的是
   **标定记录**的实测峰值因数，测试记录的实际值另列 —— 不假装它不变。

## 4 这条规则改变了什么、没改变什么

**改变**：任何"带幅值 ±2 dB"的通过结论，现在**必须**同时给出谱类；没有谱类的通过结论
连对象都构造不出来。这正好补上第 2 项要求里"幅值只能用带限幅值表述"缺的那一半 ——
**谁在什么激励下标的**。

**没改变**：`measurement_validation_status` 仍然只由验收层派生、仍然只有那一处可写
（第 1 项已落地并有源码扫描守卫）；6/8 与 3/8 这两个数都还在，并列报告。

## 5 边界

- 谱类只描述了四个量（谐波数、波段、每带 rms、峰值因数），**没有**描述相位分布、带内谱形、
  频谱倾斜 —— 这些在同类标定里被"同一种生成器"隐式固定住，一旦换生成方式必须重标；
- 只测过"多音 vs 单音"这一对，没有分离谐波数与带宽各自的作用；
- 合成路线，无实测真值。

## 6 复算

```bash
PYTHONPATH=src python -X utf8 scripts/s40_band_verdict.py     # 读 s38/s39 的两个 JSON（scratch 或 inputs/）
PYTHONPATH=src python -X utf8 -m pytest tests/test_verdict_calibration_class.py -q
```
