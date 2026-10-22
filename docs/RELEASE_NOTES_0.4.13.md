# Velch 0.4.13 发布说明

发布日：2026-10-23　｜　和上一版（0.4.12）的差别：**把"凭什么可以发布"变成三份可复算的东西**。
界面与求解器一行没改——这一版是证据版。

## 这一版新增了什么

| 新增 | 怎么用 | 它回答什么 |
|---|---|---|
| `scripts/physics_invariants.py` | `python -X utf8 scripts/physics_invariants.py --no-run` | 物理数值有没有动（归档 2401 帧 + 一次现跑，退出码 0/2） |
| `docs/physics_invariants.json` | committed 参考值 | 漂移比较的基准，随发布一起走 |
| `scripts/evidence_map.py` → `docs/EVIDENCE_MAP.md` | `python -X utf8 scripts/evidence_map.py --check` | 六个分项各自**跑出来的最近结果**（不是"应该通过"） |
| `docs/SIMPACK_COMPARE_2026-10-23.md` | 阅读 | 与 Simpack `350.mat` 的逐点、逐频带对照 |
| `B025` 修复 | 自动 | 短记录（70 样本 / 2 kHz）下带通滤波不再抛 `Filter not stable` |

`evidence_map.py` 带 `--with-run` 时，⑤ 那一行会真的把 Simpack 模型导入、裁决、跑完：

```
geometry_readable = True、missing_profile_references = 0、profile_references = 238
seats: true（8 个接触、最大侵入 65.47 µm）
现跑 numerically_checked、门 7/7、nfev 116
```

导出的八个接触各 59.68 kN、最大侵入 65.47 µm，与模板算例的静载门（59 680.5769 N / 65.47 µm）
是同一个数——这不是巧合，是"导入几何之后静平衡仍然解到同一个平衡点"。

## 与 Simpack 的对照（摘要）

重叠段 79.0–138.5 m（2301 点），前轮对垂向支反力之和：

| 指标 | Velch | Simpack | 比值 |
|---|---|---|---|
| 均值 | 119.35 kN | 120.32 kN | 0.99 |
| 最小 | 96.11 kN | 95.21 kN | 1.01 |
| 最大 | 136.29 kN | 194.29 kN | **0.70** |
| rms（对均值） | 2.90 kN | 4.83 kN | 0.60 |
| 主导频率 | 37.19 Hz | 31.65 Hz | — |
| 30–60 Hz rms | 6.93 kN | 11.17 kN | 0.62 |
| 150–250 Hz rms | 1.04 kN | 3.35 kN | 0.31 |
| 250–400 Hz rms | 1.63 kN | 2.20 kN | 0.74 |

允许平移时最优位移只有 **+0.2 m**（rms 4.57 → 4.36 kN），所以**里程轴配准是对的**，差异是模型
差异（我们的接触斑更窄、高频更少）。这页不能证明谁对，也不是同工况验证，更不能当标定依据。

## 仍然没有的五项（和上一版相同）

1. Simpack 模型的**横向布置**未导入（该模型左轨只有 2 站，单侧导入等于改轨距，被闸门拒绝）。
2. Simpack 侧的轴重、刚度、阻尼**只作对照，不写进算例**。
3. 没有代码签名（首次运行会有 SmartScreen 提示）。
4. 只读安装目录（`C:\Program Files\Velch`）的 ACL 步骤仍需手工跑一遍（O009）。
5. `physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`：
   与 Simpack 的差异已量化，但**没有做标定**。

## 验证清单（这一版实测）

- `pytest` **552 passed, 1 skipped**（skip 是"没有设 `VELCH_SIMPACK_MODEL` 时不跑真模型那条"）
- `scripts/physics_invariants.py --no-run` → `VERDICT: UNCHANGED`
- `scripts/evidence_map.py --check` → 通过
- `packaging/smoke_test.py` → **ACCEPT · 6 步 · 失败 0 · 跳过 0**
- 安装包：onedir，两个 exe（`Velch.exe` 界面 / `velch-cli.exe` 命令行与 MCP）

## 怎么启动

双击 `启动 Velch.cmd`，或直接跑 `Velch.exe`。第一次打开如果没有算例，界面会告诉你
`VELCH_DATA_ROOT`、两个标记文件路径和标记 JSON 的写法——照抄即可。
