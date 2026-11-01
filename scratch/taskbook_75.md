## 七十五、第 316 轮：覆盖性的两个读者

| 项 | 内容 |
|---|---|
| 触发 | 第 315 轮只在**门**里判覆盖；审计与门页仍只读 std，安静的 0.44 m 在它们眼里可引用 |
| 改法 | `window_coverage(meta)`（新归档读 `stationarity_covered`，老归档按 `min(窗口, duration×speed)` 与 `samples` 重算，允许一个间距）；`quotable = stationary and covered is not False` |
| 审计 | 每行多 `window_m/window_covered/window_span_m/window_expected_span_m/window_spacing_m/window_samples/quotable`；verdict 多 `window_declared/uncovered_window/not_quotable` |
| 实测 | 71 归档 / 69 平稳 / 2 隔离（60 km/h 那两趟）；声明窗口 3、没走到 2、不可引用 4；reading 归档覆盖 True（9.000 m）可引用，0.02 s 归档力安静但覆盖 False、不可引用 |
| 门页 | `_stationary_run` 返回 `quotable`（老报告回落 `stationary`）；`verdict()["not_quotable"]`；60 km/h 那行打印 `[withdrawn: this run is not quotable]`，数字不隐藏 |
| 未改 | 5 kN 阈值、一个间距的允许量、`stationary` 预注册判据；60 km/h 长跑（1.6 s ≈ 7 h） |
| 未做 | `Ω_obs` 主门三件待批准；心轨两体；100 km/h 的 G-REL/G-LOC |
