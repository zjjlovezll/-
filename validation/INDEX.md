# validation/ 索引

这个目录曾经和软件包同树：`src/` 只有 1.6 MB，`validation/` 有 1.37 GB。
**2026-10-22 傍晚已把主力语料搬出仓库**，本文件留在仓内充当路标。

软件不依赖语料存在：缺了它，少数直接读 oracle 的用例会 skip、UI 第①⑤屏会空，
但 `velch run` / `run-vehicle` / `--fast` 都不受影响。

## 现在在哪

| 东西 | 位置 | 体积 |
| --- | --- | --- |
| `crh380a_m/`（358 个算例 + 208 个 `out_*` + 223 个脚本） | **`F:\velch_data\validation\crh380a_m`** | 1 392 MB |
| `turnout18/`、`turnout18_ref/`（判据长文与参考） | 仓内 `Velch/validation/` | 15.7 MB |
| 位置声明 | `Velch/.velch-data.json`（`{"data_root": "F:/velch_data/validation"}`，不入库） | 40 B |
| 位置声明模板 | `Velch/.velch-data.example.json` | 40 B |

解析顺序在 `src/velch/data_root.py` 里只有一处实现：**`VELCH_DATA_ROOT` 环境变量 →
`.velch-data.json` 标记 → 仓内 `validation/`**。UI（`store.VALIDATION_DIR`）、agent
（`agent.core.case_root()`）与九个测试模块都问它，没有第二套硬编码。

自查命令：

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 -c "from velch.data_root import explain; print(explain())"
#   -> source: marker .velch-data.json / case_files: 358
```

## 语料构成（`F:\velch_data\validation\crh380a_m`）

| 项 | 数量 |
| --- | --- |
| 文件总数 | 14 431 |
| 体积 | 1 392 MB |
| `out_*` 运行目录 | 208 |
| `case_*.json` 算例 | 358 |
| 一次性脚本 | 223 |
| 顶层子目录 | `crh380a_m`（CRH380A_M 过 18 号道岔）、`turnout18`、`turnout18_ref`（已留仓内） |

## 哪些进版本库，哪些不进

**都不进。** 语料整体在仓库外，`git` 里只剩判据值与文档。
两个曾经的"冻结 oracle"随语料外移，它们的**判据值**仍钉在代码里：

- 静载门：每接触 **59 680.5769 N**、侵入 **65.47 µm**（`tests/test_oracle_frozen.py` 断言的就是这两个数）
- 整车 1.2 s 动态基线：`axle1_right` 峰值 89.68 kN、`axle2_right` 170.61 kN（整程最大值）、
  最大侵入 551.9 µm、脱空 0 次，对应目录 `out_full12_cap05`

**一个坑，写在这里免得再犯**：`out_*` 里有 10 个目录的时间序列是**常数**，只能当静载门用，
不能拿来挖动态/频谱结论——`out_A_final_law`、`out_final_strip1p2s`（侵入恒 197.6 µm）、
`out_final_patch1p2s`（恒 66.9 µm）、`out_A_1p2s`、`out_A_smoke_0p05s`、`out_C_smoke`、
`out_flat_A_135`、`out_curv_flat`、`out_V_base`、`out_W_base_frog`。
判断方法：`history.csv` 里某列 2401 帧标准差为 0。正确动态目录是 `out_full12_cap05`。

## 脚本（223 个）

一次性测量/探针脚本，按用途分批，**都没有纳入包**，入口写法是
`cd Velch && python -X utf8 validation/crh380a_m/<script>.py`：

- `probe_*.py`（约 48）——单点探针：接触连续性、多斑、描述符、模态、降阶
- `cmp_*.py`（约 22）——与 Simpack / SDITT 对照：频谱、整程、曲线
- `make_*.py`（约 21）——由模板生成算例（`case_derived_*`）
- `s2_*.py`（16）——隐式求解器阶段：`s2_analytic.py` 是对外验收门脚本（见下）
- `check_*.py`（约 9）——纯度、连续性、`check_jacobian.py`（有限差分参照物与步长噪声地板）

## 当初怎么搬的（已经做完，留档）

只搬了主力语料 `crh380a_m`，`turnout18*` 判据长文留在仓内：

```powershell
New-Item -ItemType Directory -Force F:\velch_data\validation
Move-Item F:\ai道岔状态反演辨识\Velch\validation\crh380a_m F:\velch_data\validation\crh380a_m
'{ "data_root": "F:/velch_data/validation" }' |
    Set-Content F:\ai道岔状态反演辨识\Velch\.velch-data.json -Encoding utf8
```

**踩坑**：PowerShell 5.1 的 `Set-Content -Encoding utf8` 会写 BOM，`json.loads` 读到
`\ufeff` 直接抛错、于是标记被静默忽略、回落到（此时已空的）仓内路径——表现出来是
"31 failed / 14 errors"，看起来像代码坏了。`data_root._root_from_marker()` 因此改用
`utf-8-sig` 读取，`tests/test_data_root.py` 里有一条专门钉住"带 BOM 也要能读"。

搬完的样子：`pytest` **389 passed**、`velch.ui --selftest` 退出码 0、`velch.agent doctor`
`ok: true` 且 `detail: 358`。

## 验收门脚本（现在在仓外）

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 F:\velch_data\validation\crh380a_m\s2_analytic.py gate   # 六时刻解析雅可比门
python -X utf8 F:\velch_data\validation\crh380a_m\check_purity.py       # 右端纯度（必须严格 0.0）
python -X utf8 F:\velch_data\validation\crh380a_m\check_jacobian.py     # 有限差分参照物与步长
```
