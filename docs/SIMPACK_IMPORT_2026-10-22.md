# 从 Simpack 模型算一个算例（2026-10-22）

本文件记录"软件可以读取 Simpack 的模型进行计算"这件事到底做到哪一步、哪一部分没有做、以及
为什么不做。所有数字都是本机实测，命令可复现。

## 一、读到了什么

用 `velch inspect-simpack-track` 读本机的真实 Simpack 数据库
`G:\研究生\动力学\CRH380A_纯刚性模型\database\database\mbs_db_substructure\CRH380A_M_Wheelset.spck`：

| 项 | 值 |
|---|---|
| 扫描模型 | 1 个 `.spck`（186 648 B，sha256 `c6157828…`） |
| 型面引用 | **238 条**（236 条 right / 2 条 left） |
| 唯一 PRR 文件 | **233 个**（`Profile_Mileage_JBG/R5/R10/…`） |
| 缺失引用 | **0** |
| 同里程多表面 | **10 处**（道岔转辙/辙叉区，同一里程两个承载面） |
| 里程跨度 | 0 – 150 m |
| `profile_set_sha256` | `caf3625fee9d947a3f80280788fad014bb3ed2f8b905a48c7812e5aa486a4bda` |
| `geometry_readable` | **true** |

每个引用都带 `rail` / `side` / `index` / `station_m` / `path` / `sha256`，所以"哪个型面文件在哪
个里程、属于哪根轨"是可追溯的，不是猜的。

## 二、怎么把它变成一个能跑的算例

新增 `velch simpack-case`（`src/velch/simpack_case.py`）：**几何从 Simpack 来，物理从你给的
模板算例来**。

```powershell
# 1) 读模型，产出目录（只读，不改模型）
python -X utf8 -m velch inspect-simpack-track <model>.spck --model-root <database> --output catalog.json

# 2) 派生算例：里程布置从模型来，物理（质量/悬挂/接触/容差）从模板算例来
python -X utf8 -m velch simpack-case --catalog catalog.json \
    --template validation\crh380a_m\case_A_final_law.json \
    --out case_from_simpack.json --side right --x-start 60 --duration 0.05 \
    --sample 60 --keep-profiles

# 3) 跑
python -X utf8 -m velch run-vehicle case_from_simpack.json --output out_simpack --fast
```

产出两份文件：算例本身，以及 `<算例>.simpack.json` 溯源旁挂（catalog 与 template 的 sha256、
里程跨度、每个站位的型面与 sha256、`from_simpack` / `from_template` / `not_imported` 三张清单）。

### 两种模式，两次实测

| 模式 | 型面来源 | 结果 |
|---|---|---|
| `--keep-profiles`（只导入**里程布置**） | 模板算例的 JBG 断面 | **跑通**：`result_status = numerically_checked`、七项门全 true、静载 **59 680.5769 N**、侵入 **65.47 µm**、BDF nfev 116 |
| 默认（导入模型**自己的断面**） | 模型里 233 个 PRR | **在静平衡阶段失败**：`vertical preload equilibrium failed: … the lightest contact patch carries only 0.0 N while the heaviest carries 119316.3 N` |

第一种模式证明"里程布置 → 站位表 → 求解"这条链路是通的，而且它复现的正是冻结静载门
（59 680.5769 N / 65.47 µm），说明导入过程没有动到已标定的物理。

第二种模式失败是**真结论，不是待修的 bug**：模型在道岔区同一里程给出不同承载面（10 处同里程
多表面），而 Velch 的 `ProfileSeries` 每个里程只能插值一个表面；再加上轮对初始横向位置
（`y_offset_m = 0.753`）是模板给的，模型自己的横向布置没有导入，于是车轮落在承载面之外、单侧
承担两倍载荷（119 316 N ≈ 2 × 59 662 N）。要修它必须做"按站位导入横向布置 + 双体（基本轨/尖轨）
交接"，这是已知未做的下一层，不是本次能顺手带过的。

`ProfileSeries` 的单表面限制在派生时被显式计数：`dropped_duplicate_stations = 10` 写进旁挂，
不悄悄丢掉。

## 三、明确不导入的东西

Simpack 侧的数**只能作对照值**（reference, not adopted），写进算例的数只能由人显式给出：

- 轴重、簧下质量、转动惯量（决定静载门 59 680.5769 N）
- 赫兹 `E*`、`R*`、接触刚度、蠕滑系数、摩擦上界（决定 65.47 µm 与 `friction_bound`）
- 一系/二系刚度阻尼、止挡间隙、`maximum_penetration_m`（决定 89.68 / 170.61 kN 峰值）
- 模态频率/阻尼比/振型 MAT、`Phi` 归一化与截断频率
- 预载与初始平衡、`rtol`/`atol`/`output_step_s`
- 任何从 `.spck` 文本里"推断"出来的数

旁挂里的 `not_imported` 清单就是这条规则的机器可读版本：
`rigid body dynamics`、`flexible (modal) track`、`solver settings`、`measured or reference results`。

## 四、派生时的两条硬规矩

1. **里程不位移**。早期实现把模型里程平移到 `--x-start`，结果右轨只覆盖 13.5–163.5 m，第一个
   车轮位置就在覆盖之外，静平衡报"单侧 119 357 N"。现在里程按模型原样导入，`--x-start` 必须
   落在模型自身跨度内（含 `travel_speed × duration` 的行程余量），否则直接拒绝并打印跨度。
2. **拒绝而不是猜**。catalog 不可读、型面文件消失、模板里该侧是分体结构、`x_start` 越界——四种
   情况都给 `SimpackCaseError` 与一句能照着改的话，绝不写半个算例出去。

## 五、测试

`tests/test_simpack_case.py`（10 项）：schema 不符、`geometry_readable=false`、按 side 过滤与排序、
同里程去重计数、里程不被位移、越界拒绝、`--keep-profiles` 的型面来源、旁挂的
`from_*`/`not_imported`、型面文件缺失、以及真实模型在 `VELCH_SIMPACK_MODEL` 下可读（未设置则 skip）。

## 六、下一步（按价值排序）

1. 按站位导入**横向布置**（模型里每根轨的 y 基准），这是默认模式能跑起来的前提。
2. 双体交接（基本轨 / 尖轨、翼轨 / 心轨），需要 `rail_templates[*].bodies` 与 `y_window_m` 的映射。
3. 结果对照：把 Simpack 的 `RS_result` 通道与 Velch 的 `history.csv` 按同一里程窗对齐，出
   `docs/SIMPACK_COMPARE_<date>.md`——只描述差异，不调参。
