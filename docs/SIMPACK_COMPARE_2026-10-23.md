# Simpack 与 Velch 的定量对照（前轮对，23.5–138.5 m）

**这一页只描述差异，不调参数。** 它回答"同一条轮对上，两条曲线的数字差多少"，不回答"谁对"。

## 出处

| | |
|---|---|
| Simpack 结果 | `F:\项目\CRH380A_纯刚性模型\database\database\mbs_db_substructure\CRH380A_M_Carbody.output\350.mat` |
| 文件 sha256 | `2924b964dc2682244359e14bdbac7962e66b3fc6994f8f348be75677c5f536e9` |
| 提取脚本 | `.tmp/extract_simpack_force.py`（读 HDF5 的 `timeInt/RS_result/SRS_S_F/SRS_S_WS_F/SRS_RWT_WS`） |
| 通道 | `ch_001 SumQ Sum of vertical rail forces`（前轮对垂向支反力之和）、`ch_003 s Position along track` |
| 采样 | 2401 点 / 0.5 ms / 1.2 s；`s` 覆盖 23.500–138.501 m |
| Velch 结果 | `F:\velch_data\validation\crh380a_m\out_full12_cap05\history.csv`（`case_full12_cap05.json`，DOP853，2401 帧） |
| 对照量 | `axle1_left_normal_n + axle1_right_normal_n`——与前轮对垂向支反力之和是同一个量 |
| 对照窗 | **23.5–138.5 m**（两侧都有数据的重叠段），0.05 m 等距网格，2301 点 |

## 数字

| 量 | Simpack | Velch | 比值 |
|---|---|---|---|
| 均值 | 120.32 kN | 119.35 kN | 0.992 |
| 最小 | 95.21 kN | 96.11 kN | 1.010 |
| **最大** | **194.29 kN** | **136.29 kN** | **0.701** |
| 相对均值的 rms | 4.83 kN | 2.90 kN | 0.601 |
| 主导频率 | 31.65 Hz | 37.19 Hz | — |
| 30–60 Hz rms | 11.17 kN | 6.93 kN | 0.62× |
| 150–250 Hz rms | 3.35 kN | 1.04 kN | 0.31× |
| 250–400 Hz rms | 2.20 kN | 1.63 kN | 0.74× |
| 差值（Velch − Simpack） | — | 均值 -0.97 kN，rms 4.57 kN | — |
| 最大偏差 | — | **-66.00 kN @ 80.00 m** | — |

## 六条读数

1. **静态水平几乎一致**：均值差 0.97 kN（0.8%），最小/最大包络的左边界（95.2 对 96.1 kN）吻合。
2. **峰值差 58 kN**：Simpack 194.3 kN、我们 136.3 kN，出现在同一段里程（80 m 附近的道岔区）。
3. **差值集中在道岔区**：最大偏差 -66.0 kN @ 80.00 m；整段 rms 只有 4.57 kN，说明**不是整体偏高偏低，而是几个尖峰**。
4. **三个频带全部偏小**（0.62× / 0.31× / 0.74×），150–250 Hz 最明显——与我们此前"30–60 Hz 带欠激励"的读法一致，但这里的量化更硬：**不是某个频带错，是整体能量不足、越往高频差得越多**。
5. **里程轴是对的**：允许把一侧整体平移时，最优位移只有 **+0.20 m**（rms 从 4.57 降到 4.36 kN）。所以差异不是配准误差，是模型差异。
6. **主导频率 31.65 对 37.19 Hz**：都在低频段，量级相当；真正的分歧在峰值的幅值，不在频率位置。

## 这页不能证明什么

- **不能证明"我们错、Simpack 对"**。Simpack 那一侧同样有一个标定过的翼轨抬升（+0.31 mm 是它自己模型里的量）；两者的道岔断面标定不是同一套。
- **不是同工况验证**：两侧共用同一里程定义与同一物理量，但车辆参数、接触律、轨道支撑的取值各自独立。
- **不构成标定**：本页没有改动任何默认值。要让峰值对齐，必须另立保真门并说明改了哪条物理。

## 复现

```powershell
python -X utf8 .tmp\extract_simpack_force.py     # -> F:\velch_tmp\simpack_front_wheelset.csv
python -X utf8 .tmp\compare_simpack.py           # -> F:\velch_tmp\simpack_compare.json
```

两个脚本都在仓库外（`.tmp/`），只读 Simpack 结果与已归档的 Velch 运行；没有重跑仿真。
