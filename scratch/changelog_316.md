## 第 316 轮 — 覆盖性也要给两个读者看：审计与门页

第 315 轮把"窗口有没有走到"写进了门，但同一批归档还有两个读者：`s164_stationarity_audit.py`（说哪些归档可引用）与 `s156_gate_page.py`（说哪一行可引用）。它们只知道 std，所以一档安静的 0.44 m 在它们眼里仍是"可引用"。这一轮补第二个条件，**不动**预注册的力判据。

- `window_coverage(meta)`：新归档读 `stationarity_covered`，老归档用 `min(窗口长度, duration×speed)` 与 `span/(samples-1)` 重算，允许**一个采样间距**的欠额；`quotable = stationary and covered is not False`。
- 审计每行多六个窗口字段与 `quotable`；`verdict` 多 `window_declared` / `uncovered_window` / `not_quotable`。
- 实测 **71 个归档、69 平稳、2 隔离**（仍是那两趟 60 km/h）；**声明窗口 3 个、没走到 2 个、不可引用 4 个**；`one_set_reading-080…-0.4050s` 覆盖 `True`、span `9.000 m`、可引用；`one_set_straight-080…-0.0200s` 力安静但覆盖 `False`、**不可引用**。
- 门页 `_stationary_run` 改返回 `quotable`（老报告回落 `stationary`），`verdict()` 增 `not_quotable`，打印把 60 km/h 那行标 `[withdrawn: this run is not quotable]`——**数字仍打印，不隐藏**。
- 边界：只对声明窗口的归档生效（3/71），其余 `covered = None` 不参与判决；60 km/h 长跑未重跑；5 kN 与"一个间距"都没放宽。

文档 `docs/COVERAGE_READERS_2026-11-01.md`；测试 `tests/test_stationarity_audit.py` 增一项（两份清单、四个不可引用、reading 归档可引用、0.02 s 归档安静但不可引用）。
