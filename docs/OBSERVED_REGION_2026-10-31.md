# 一次过车只能看见一条带，不是一张面（M4：Ω_obs 与覆盖率）

日期 2026-10-31。本轮把最终目标里那句"反演尖轨/心轨表面的整个三维面曲线"变成**可判定的数**，
并且拿到的是一个限制结论：**0.40 s 的单次过车只测量了轨头宽度的 26 %（5 mm 口径）/ 42 %（1 mm 口径）**，
按预注册口径属于 **contact band only**，因此任何结果里都不得使用"面"这个词。

## 一、判据（写在读数之前，见脚本 docstring）

```
cell       (站位 0.20 m) × (横向 1 mm，相对该站基本轨冠)
patch      一帧内某根轨的接触带 [y−b, y+b]
Ω_obs      至少被一个 patch 覆盖的 cell（按轨、按站位分别记）
Ω_design   该站冠下 HEAD_DEPTH 以内的走行面 cell，**只统计这次运行真的走过的站位**
coverage   Σ_轨 |Ω_obs ∩ Ω_design| / Σ_轨 |Ω_design|
```

- 主口径 **HEAD_DEPTH = 5 mm**（预注册：一个接触斑**可能**触及的头部范围）；
- 并报 1 / 2 / 10 mm 三个口径，因为判据对这个选择敏感，藏起来等于事后改阈值；
- 分母**只算走过的站位**——没走到某里程不是"横向没测到"，把它算进来会让覆盖率随运行时长变化。

读数口径（预注册）：

| coverage | 判定 |
|---|---|
| ≥ 0.90 | surface（可以说"面"） |
| 0.50 – 0.90 | contact-band surface（带状，须注明） |
| < 0.50 | **contact band only**（不许说"面"） |

## 二、实现与产出

- `scripts/s99_run_archive.py` 新增两列：`contact_lateral_m`、`contact_half_width_m`（帧 × 8 轨，
  **无接触帧写 NaN**——留空是信息，写 0 会读成"在 y = 0 处有接触"）。归档重跑一次：
  `straight_one_set-080.00kmh-0.4000s-500us-55d6fd49`，801 帧、七门 7/7。
- `scripts/s111_obs_region.py`：从归档的接触点与带宽重建 `Ω_obs`，与算例自己的走行面比。
- `tests/test_obs_region.py` 4 项：带宽中位数 16.0 mm（≠ 头宽 37.15 mm）、主口径覆盖率 0.257、
  覆盖率随分母深度单调不增、以及"要覆盖 90 % 至少需要 3 条横向偏移"这条算术。

## 三、实测（一组模型，80 km/h，0.40 s，801 帧）

```
visited stations 30.0 .. 59.0 m
band covered per rail per station 14.0 .. 17.0 mm  (median 16.0)

depth   head width   Ω_design   covered   coverage   per rail
  1 mm     37.15 mm     12 936     5 392     41.7 %   38.7 .. 44.7 %
  2 mm     48.11 mm     16 464     5 392     32.8 %   30.8 .. 34.7 %
* 5 mm     61.46 mm     21 000     5 392     25.7 %   24.3 .. 27.0 %
 10 mm     68.79 mm     23 520     5 392     22.9 %   21.5 .. 24.3 %

primary 5 mm -> 25.7 %  ->  contact band only
```

带宽 16 mm ≈ 2b（b ≈ 8 mm 的接触斑半宽）加上 0.14 mm 的横向漂移，也就是说**这一条带几乎就是接触斑本身的宽度**，
车没有在横向"扫"过轨头。

## 四、这个数意味着什么（三条，都能算）

1. **"三维面"在当前观测下不成立**。目标里"整个三维面曲线"必须改写为"接触带面 `z(s,y) | Ω_obs`"，
   否则一个正确的结果也会被一个做不到的定义拖成失败（这一条属目标修订，仍需用户确认）。
2. **要 ≥90 % 需要至少 3 条横向偏移**：`ceil(0.9 × 37.15 / 16.0) = 3`。三次过车若落在**不同横向位置**
   （不同超高/曲线、不同轮对磨耗、或有意的横移），才能把带拼成面；同一位置跑十次仍是 42 %。
3. **精度必须与覆盖率并列报**。同样的估计器在 Ω_obs 内的 p95 可以很小，但它回答的是"这条带上多准"，
   不是"这个轨头多准"。这就是任务书 M4 把覆盖率写成前置门的原因。

## 五、能说 / 不能说

- **能说**：单次 80 km/h 过车，接触带中位宽度 16.0 mm；按 5 mm 头部口径覆盖 25.7 %（1 mm 口径 41.7 %）；
  预注册判定 **contact band only**。
- **不能说**：不能把"反演出的接触带面"称为"尖轨表面"；不能把 Ω_obs 内的误差当成整面误差；
  不能由"多跑几次"直接得到面——必须换横向位置。
- **未做**：尚未设计"三条不同横向偏移过车"的算子（这是 M7 的输入端）；`Ω_obs` 的横向坐标目前相对
  **该站基本轨冠**，尖轨/心轨体的横向基准尚未并入（M3 已给出它们的几何，但 Ω 的基准切换还没写）。

## 六、复算

```bash
cd Velch
PYTHONPATH=src python -X utf8 scripts/s99_run_archive.py \
  --case vehicles/turnouts/CN60-1100-1_18/cases/straight_one_set.json \
  --speed-kmh 80 --duration 0.40 --note campaign=m4-obs-region
PYTHONPATH=src python -X utf8 scripts/s111_obs_region.py --write
PYTHONPATH=src python -X utf8 -m pytest tests/test_obs_region.py -q
```
