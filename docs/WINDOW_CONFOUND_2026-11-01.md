# 采样密度不是那 16 % 的来源（2026-11-01，第 300 轮）

> 第 299 轮把同一段九米在 80 与 100 km/h 上各反演一次，幅值差 **16.11 %**（66.2 对 56.6 µm）。
> 当时留下一个替代解释：两趟**采那九米的密度不同**——80 km/h 输出步长 11.11 mm、100 km/h 13.89 mm，
> 且 100 km/h 那一趟只存在 0.33 s（对 80 的 1.00 s），每米可用样本少一半。
> 如果估计器对"同一趟抽得粗一点"就给出不同幅值，那这个差与速度无关。本轮把这一个混淆项测掉。

## 一、预注册（跑之前写死在 `scripts/s153_window_confound.py` 的 docstring 里）

```
H1         16.11 % 的差是采样密度造成的
证伪判据    把 80 km/h 抽到 100 km/h 的站位步长（stride 2, 13.89 mm）或更粗（stride 3, 20.83 mm），
           拟合幅值相对 stride 1 的移动 < 3.0 µm —— 也就是待解释的 9.6 µm 缺口的 1/5 以下
读数        stride 1 / 2 / 3，同一窗口 56–65 m、同一条律、同一批起点
判决        两次移动都在 3.0 µm 内 ⇒ H1 被否，跨速度比较不必在同一步长上重做
```

为什么是 3.0 µm：缺口 9.6 µm 的三分之一以上才能算解释；而 3.0 µm 本身也只有 22 µm 绝对门的 1/7，
所以即便真有这个量级的采样敏感性，对门也无害。

## 二、读数（`scripts/s153_window_confound.py`，零新仿真）

```
speed 80 km/h, same window 56-65 m, same law, same seeds
  stride 1  samples 2001 (11.11 mm)  A 66.22 um  centre 58.514 m  p95 6.25 um  usable 369
  stride 2  samples 1001 (13.89 mm)  A 65.36 um  centre 58.540 m  p95 5.71 um  usable 185
  stride 3  samples  667 (20.83 mm)  A 67.15 um  centre 58.489 m  p95 7.16 um  usable 123

amplitude shifts vs stride 1: stride 2 -0.86 um, stride 3 +0.93 um
notional cross-speed gap 9.6 um, tolerance 3.0 um
VERDICT: decimation moves the amplitude by less than 3 um, a fifth of the 9.6 um gap
         -> H1 REJECTED (sampling is not the explanation)
```

两次移动是 **−0.86 µm（−1.3 %）** 与 **+0.93 µm（+1.4 %）**，都只有缺口的 **1/9 量级**；
中心位置几乎不动（58.514 / 58.540 / 58.489 m），p95 在 5.7–7.2 µm 之间。

## 三、这说明什么、不说明什么

**能说**：80 km/h 那一行的幅值**不是**采样密度的产物；把它抽到 100 km/h 的步长（甚至更粗）
仍给出 65.4–67.2 µm。因此第 299 轮的 **16.11 % 差不能归给"窗口长度/采样密度"**，
它是这两个速度之间、在这段几何与这套律下**真实存在的差**。

**不能说**：① 没有指出那 16 % 的物理来源（这一步只排除一个候选，不提供新机理）；
② 没有证明估计器对采样不敏感这件事对其它窗口/其它速度也成立——只测了 80 km/h × 三个步长；
③ 60 km/h 仍缺（它 0.02 s 就要 3.2 min ≈ 10 min/模拟秒，0.54 s 匹配窗口 ≥1.6 h，仍在算）；
④ 100 km/h 的 **定位漂 0.42 m** 与 **相对分箱 2.34 %** 仍未解释。

## 四、一条工程事实（顺手记下）

`stride` 是**只读**选项：`load(..., stride=1)` 与归档逐位相同（测试钉住 `times[1] == plain.times[2]`、
`len(decimated) == (len(plain)+1)//2`、`stride=0` 必须 `SystemExit`）。它不改归档、不改律、不改座椅。

## 五、复算

```bash
cd Velch
python -X utf8 scripts/s153_window_confound.py
python -X utf8 -m pytest tests/test_window_confound.py tests/test_cross_speed.py -q
```

产物：`reports/load_split_inversion_2026-10-31/window_confound.json`（三档读数、逐档移动、判决）。
