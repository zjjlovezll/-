# 物理不变量复算门

一句话：**"物理数值不变"这句话现在是可执行的**，不再只是发布说明里的一句承诺。

## 它做什么

`scripts/physics_invariants.py` 从两个互相独立的来源取数，与 `docs/physics_invariants.json`
里committed 的参考值逐项比较：

1. **归档**（不重跑）：`out_full12_cap05/history.csv` 的 2401 帧 —— 八个接触峰值、最大侵入、
   脱空样本数、78.8–82.2 m 窗口的 rms / 主导频率 / 三个频带、`manifest.json` 的
   `result_status` 与七项门。
2. **现跑**（`--fast`，0.05 s 的辙叉算例，约 4 s）：当前代码是否仍能跑出
   `numerically_checked` 与七门全过，以及它的首帧与八接触峰值。

判据：接触峰值 ±1.0 kN、最大侵入 ±1.0 µm、窗口 rms ±0.2 kN、主导频率 ±1.0 Hz、频带 ±0.2 kN、
脱空样本必须完全相同、首帧静载 ±1.0 N；现跑要求 `numerically_checked` 且七门无失败。

退出码 0 = 未移动，2 = 漂移。报告写到 `reports/PHYSICS_INVARIANTS_LATEST.md`（运行产物，不入库）。

## 为什么窗口数字用的是"朴素 FFT"

文档里引用的 **9.13 kN / 57.14 Hz** 来自 `validation/crh380a_m/bands_from_history.py`：去均值、
矩形窗、`2/N` 标度的直接 FFT。`velch.inverse.bands.band_metrics` 回答的是另一个问题
（5–999 Hz 滤波、裁掉瞬态、主频按 1/3 倍频程中心报），用它当参考会让参考值和文档互相矛盾。
所以复算门里保留"文档口径"，并把差别写在这里，而不是让两个数字并存。

## 三个容易踩的点

- **静载门的 59 680.5769 N 属于模板算例**（`tests/test_oracle_frozen.py` 钉住）。归档这次从
  13.5 m 起算，首帧是 **59 680.3756 N**；复算门比的是"归档自己的首帧"，不是那个常数。
- 辙叉算例的**首帧不是静载门**（它过辙叉，首帧一侧 37.1 kN），所以现跑只要求"能跑、门全过、
  八个接触都在"。
- 归档的 `manifest.json` 里 `result_status` 与 `gates` 在 **`summary`** 下一层；读顶层会得到
  `None`，门就变成瞎的。

## 顺带修掉的一个缺陷（B025）

`velch.inverse.bands.bandpass` 在**短窗**（70 个样本、2 kHz）上会让 scipy 抛
`ValueError: Filter not stable due to sum(a) == 0`——上边缘贴着 Nyquist；同样的滤波器在
2401 点长记录上正常。现在滤波失败会依次收窄上边缘（0.999 → 0.97 → 0.90 × Nyquist）重试，
长记录的结果逐位不变，短窗不再崩。`tests/test_physics_invariants.py` 里有一条 70 点用例钉住它。

## 怎么跑

```powershell
python -X utf8 scripts/physics_invariants.py            # 归档 + 一次现跑
python -X utf8 scripts/physics_invariants.py --no-run    # 只读归档（提交前闸门用这一档）
python -X utf8 scripts/physics_invariants.py --write     # 有意变更物理时重写参考值
```

`scripts/auto_accept.py` 已把它作为第四步（`--no-run`，约 0.2 s），所以每次提交都会验一次。
