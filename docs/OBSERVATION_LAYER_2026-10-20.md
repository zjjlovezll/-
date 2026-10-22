# 观测量层：仿真对仿真 + 实测对模型（2026-10-20）

## 1. 为什么先做这一层

反演需要三样东西按顺序落地：**观测量 → 可辨识性 → 估计器**。观测量层是地基，它同时要服务两条完全不同的路径（用户 2026-10-20 明确要求两者同时展开）：

| | 仿真对仿真（Velch vs Simpack） | 实测对模型 |
|---|---|---|
| 对齐轴 | 里程 `x`（两边都有） | 时间 + 事件锚点（实测没有里程通道） |
| 第一批通道 | 轮轨法向力、接触点横位、几何侵入 | 轴箱加速度、轨腰应变（轮轨力测不到） |
| 不确定性 | 数值噪声（可忽略） | 传感器 + 安装 + 通道标定，必须进权重 |

这两条路径的差异只应存在于**对齐与权重**，不应该分叉求解器。所以做成一层独立模块。

## 2. 落地的两个模块

### `src/velch/io/history.py` — 带类型的 history 契约

`schema = "velch-history-v1"`。此前 `metrics.assess_history` 靠字符串切片猜列名（`axle1_right_normal_n` 是不是力？单位是什么？），等于把写盘命名变成了隐式公共契约。现在：

- `Channel(name, unit, kind)`，`kind ∈ {time, state, velocity, force, moment, contact, flag}`；
- `classify(name)` **匹配不到就抛**，不静默默认——把米和牛搞错比抛异常危险得多；
- `HistoryTable` 支持 `select / where / __getitem__`，越界带明确报错；
- `read_history(path)` 可直接传运行目录（自动找 `history.csv`），并校验：列数一致、全有限、有 `time_s`。

**写盘器不动**：`vehicle_solver.save_vehicle_result` 保持逐字节不变，因为冻结 oracle（`out_final_full1p2s`、`out_A_final_law`）的回归依赖它的输出字节。`write_history` 只用于派生/合成表。

实测：`out_final_full1p2s/history.csv` 读回 2401 采样、123 通道，kinds = `[contact, flag, force, state, time, velocity]`。

### `src/velch/inverse/observation.py` — 配对与残差

- `ChannelSpec(name, unit, role, sigma, frame)`：`role="data"` 进目标函数，`role="check"` 只做事后核查；`sigma` 是该通道自身单位下的 1σ，残差按 `1/sigma` 加权，这样 0.5 kN 的力通道和 0.02 g 的加速度通道可比；
- `ObservationSet`：一组共享同一轴的通道 + `provenance`，支持 `from_history`（自校验单位）、`from_csv`（实测导出，列名自由）、`subset`、`only(role)`；
- `align(predicted, observed, strategy)`，三种策略：
  - `station`：两侧都带 `axle1_x_m`，在等里程点上配对，**不外插**（预测只覆盖部分里程时只保留交集）；
  - `time`：插值到观测时间栅格；
  - `event`：把预测时间轴平移 `event_time_s − event_anchor_s` 后再按时间配对——实测没有里程通道时的唯一做法。

单位不一致、通道集合不一致、轴非单调、缺锚点，全部 fail-closed。

## 3. 在真实产物上的验证

`validation/crh380a_m/demo_observation.py`：

### 分支 A：仿真对仿真（真实数据）

| 项 | 值 |
|---|---|
| Velch 侧 | `out_final_full1p2s`，2401 采样 |
| Simpack 侧 | `350.mat` 的 `SRS_S_R/SRS_S_WS_F/SRS_RWP_R/{_Pair.ch_008, _1.ch_010}` |
| 配对样本 | 2041（交集，不外插） |
| 零点残差 rms | **10.55 kN** |
| 数据自推的最优里程偏移 | **−0.65 m**（rms 8.90 kN） |
| 辙叉窗 78.8–82.2 m 峰值 | Velch **121.83 kN** / Simpack **127.84 kN** |
| 辙叉窗 max\|残差\| / rms | 75.47 / 33.39 kN |

结论只写到这里：**配对层可用，残差已量化，但残差不解释**（它是模型差 + 时序差 + 轨道模型差的混合体，归因在精度分解文档里）。

### 分支 B：实测口径（事件锚定）

用 `axle1_z_m` 的二阶差分造一个加速度通道（−31.2…32.8 m/s²），把“实测”设成同一条序列但时间轴平移 **+20 ms**：

| 项 | 值 |
|---|---|
| 直接按时间配对 max\|残差\| | **62.4 m/s²** |
| 事件锚定后 max\|残差\| | **0.000 m/s²** |

这证明锚定能精确恢复已知时移。**它不是模型一致性的证据**（观测序列来自预测本身），脚本输出里也这样写了。

## 4. 一处口头结论的更正

此前多处笔记写“Simpack pair 的 `ch_008` 是转向架参考里程，轮对 x = s + 17.5”。实测否定：`s` 本身已是轮对里程（6.0…122.667 m 与轮对行程等长），加 17.5 会把辙叉窗口整体错位 17.5 m，导致“峰值只剩 63 kN”的假象。正确做法是**由数据求偏移**（`best_station_shift`，本轮得 −0.65 m），不要硬编码。

## 5. 这一层**没有**做什么

- 没有做可辨识性（`coverage` / `separating_excitation` 两个字段留给下一层）；
- 没有真实实测数据——仓库里没有道岔实测记录，`from_csv` 只用合成导出验证过；
- 没有决定“哪些参数进优化向量”。

## 6. 下一步

1. **冻结 oracle 回归**（架构师的步骤 0）：把 `out_final_full1p2s` / `out_A_final_law` 的 manifest 关键量与若干采样的 history 做成断言，让后续每一步拆分都有等价性护栏。
2. **可辨识性层** `inverse/identifiability.py`：对每个候选参数给 `jacobian`、`coverage`（结构上是否影响任何输出）与 `separating_excitation`（当前工况是否激励它），输出可优化子集；对照组 = 仿真对的力通道，实测组 = 加速度/应变通道。
3. **实测通道契约**：定 `ChannelSpec` 的推荐清单（轴箱加速度三向、轨腰应变、位移计），以及事件检测（辙叉鼻端、尖轨转换、应变峰）的接口。

## 7. 复现

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 -m pytest tests -q --basetemp F:\velch_tmp\pytest   # 82 passed
cd validation\crh380a_m
python -X utf8 demo_observation.py                                  # 上表
```
