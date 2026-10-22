# validation/ 索引

这个目录是**测量与验证语料**，不是软件包的一部分（`src/` 只有 1.6 MB，这里 1.37 GB）。
软件不依赖它的存在：缺了它，`pytest` 里直接读 oracle 的少数用例会失败，UI 第①⑤屏会空，
但 `velch run` / `run-vehicle` 仍然能用，`--fast` 也不受影响。

## 现状（2026-10-22 实测）

| 项 | 数量 |
| --- | --- |
| 文件总数 | 14 607 |
| 体积 | 1.37 GB |
| `crh380a_m/out_*` 运行目录 | 208 |
| `crh380a_m/case_*.json` 算例 | 358 |
| `crh380a_m/*.py` 一次性脚本 | 223 |
| 顶层子目录 | `crh380a_m`（主力，CRH380A_M 过 18 号道岔）、`turnout18`、`turnout18_ref`（参考长文与判据） |

## 哪些进版本库，哪些不进

`.gitignore` 里只留**两个冻结 oracle**，因为测试与验收门要按值比较它们：

- `crh380a_m/out_A_final_law/` —— 静载门：每接触 **59 680.5769 N**、侵入 **65.47 µm**，
  2401 帧全部相同（它**只是静载门，不是动态基线**）
- `crh380a_m/out_full12_cap05/` —— 整车 1.2 s 动态基线：`axle1_right` 峰值 89.68 kN、
  `axle2_right` 170.61 kN（整程最大值）、最大侵入 551.9 µm、脱空 0 次

其余 208 个运行目录、`div_panel/`（6 189 文件 / 160 MB）、`smoothed/` 与 `smoothed_final/`
（各 176 MB）、`modes_scale_*.json`（最大 249 MB）都是**可再生产物**，不进库。

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

## 怎么把它搬出仓库（推荐，一次即可）

代码里没有任何硬编码路径：`velch.data_root` 按 **`VELCH_DATA_ROOT` → 仓内 `validation/`
→ 标记文件 `.velch-data.json`** 的顺序定位。搬家用标记文件最稳（对所有进程生效，
不用每次设环境变量）：

```powershell
Move-Item F:\ai道岔状态反演辨识\Velch\validation F:\velch_data\validation
'{ "data_root": "F:/velch_data/validation" }' |
    Set-Content F:\ai道岔状态反演辨识\Velch\.velch-data.json -Encoding utf8
cd F:\ai道岔状态反演辨识\Velch; python -X utf8 -m pytest tests -q --basetemp F:\velch_tmp\pytest
python -X utf8 -c "from velch.data_root import explain; print(explain())"
```

搬完 `explain()` 应报 `source: marker .velch-data.json`、`case_files: 358`。
**两个冻结 oracle 必须跟着一起搬**（它们就在 `crh380a_m/` 里，整体移动即可）。

## 验收门脚本

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 validation\crh380a_m\s2_analytic.py gate      # 六时刻解析雅可比门
python -X utf8 validation\crh380a_m\check_purity.py          # 右端纯度（必须严格 0.0）
python -X utf8 validation\crh380a_m\check_jacobian.py        # 有限差分参照物与步长
```
