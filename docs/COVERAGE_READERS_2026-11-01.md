# 覆盖性有两个读者：审计与门页（第 316 轮）

第 315 轮把"窗口有没有走到"写进了**门**（`stationarity_gate(..., covered)`）。但读过同一批归档的还有两个地方：`scripts/s164_stationarity_audit.py`（说哪些归档可以引用）与 `scripts/s156_gate_page.py`（说哪一行可以引用）。它们当时只知道 **std**，所以一档安静的 0.44 m 在它们眼里仍然是"可引用"。这一轮补上第二个条件，并且**不动**那条预注册的力判据。

## 1 两个条件，故意分开

```
stationary  <=>  max over rails of std(normal force) < 5 kN        （第 310 轮，未改）
covered     <=>  span >= (high - low) - spacing                    （第 315 轮，本轮到读者）
quotable    <=>  stationary and covered is not False
```

`covered` 允许**一个采样间距**的欠额：站表把窗口切成等距格点，任何运行都不可能同时把样本放在窗口两端。`stationary` 单独保留，是因为它是第 310 轮预注册的那条，改它等于改结论；这一轮只是**再加一个独立条件**。

## 2 审计：从自己记录里重算，才判得了老归档

`window_coverage(meta)` 的顺序是：新归档直接读 `stationarity_covered`（第 315 轮起写入）；老归档用 `min(窗口长度, duration × speed)` 作 span、`span/(samples-1)` 作间距重算。这样**第 315 轮之前的归档也能被同一条谓词判**。

`audit()` 的每一行因此多了六个字段（`window_m / window_covered / window_span_m / window_expected_span_m / window_spacing_m / window_samples`）与一个判决字段 `quotable`；`verdict` 多了 `window_declared`、`uncovered_window`、`not_quotable`。

## 3 实测（71 个归档）

```
runs 71   stationary 69   quarantined 2
  quarantined: one_set_x46-060.00kmh-0.0200s-500us-83e727fc
               one_set_x46-060.00kmh-0.5400s-500us-83e727fc
declared a window: 3    never reached it:
  one_set_straight-060.00kmh-0.0200s-500us-69281ee8
  one_set_straight-080.00kmh-0.0200s-500us-a18815bb
not quotable: 4
```

`one_set_reading-080…-0.4050s`：`window_covered True`、`span 9.000 m ≥ expected 8.9889`、`quotable True`。
`one_set_straight-080…-0.0200s`：`stationary True`（力确实安静）、`window_covered False`（0.44 m）、**`quotable False`**。

**这就是这一轮的意义**：同一个归档，力判据过、覆盖判据不过，于是它从"可引用"变成"不可引用"——而两条判断都是单独的、可复算的。

## 4 门页：数字还打印，但要标出来

`_stationary_run` 现在返回 **`quotable`**（老报告没有这个键时回落 `stationary`），`gates_quotable` 因此跟着收紧；`verdict()` 增 `not_quotable`；`physical_by_speed` 每项带 `quotable`，打印时：

```
  60 km/h physical error at 5 % share: +0.267 m -> OUTSIDE the 0.20 m tolerance  [withdrawn: this run is not quotable]
  80 km/h physical error at 5 % share: +0.423 m -> OUTSIDE the 0.20 m tolerance
 100 km/h physical error at 5 % share: +0.420 m -> OUTSIDE the 0.20 m tolerance
```

**不隐藏那 0.267 m**：它是这台机器上真实算出来的数，只是没人可以用它下结论。藏掉数字会让下一个人以为那一行不存在。

## 5 边界

- 只对**声明了窗口**的归档生效：71 个里 3 个申报、其中 1 个真覆盖；其余 68 个没有主张，`covered` 记 `None`、不参与判决（"没有声明就没有主张"）。
- 60 km/h 的**长跑**没有重跑（1.6 s ≈ 7 h）；它的两趟归档仍是"力振着"，与覆盖性无关。
- `stationary` 的 5 kN 与 `covered` 的一个间距都**没有放宽**；这一轮只增加"两者都成立才算可引用"。
- `unsettled_modal`（`modal_decay > 0.5`，含 100 km/h bump 的 2.164）仍是诊断列，不是判决。

## 6 复算

```
python -X utf8 scripts/s164_stationarity_audit.py
python -X utf8 scripts/s156_gate_page.py
python -X utf8 -m pytest tests/test_stationarity_audit.py tests/test_gate_page.py -q
```

第一条给出上表的三行 verdict（`runs 71 / stationary 69 / quarantined 2`、`declared a window: 3`、`not quotable: 4`）；第二条把 60 km/h 那行标成 `[withdrawn]`；第三条 11 passed。
