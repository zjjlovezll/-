# 柔性轮对移植：SDITT 的数据契约与我们的落点（2026-10-24）

用户指出的 SDITT 源码位置：`G:\研究生\SDITT-RW-FT-250728`（实际内容在下一层
`G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728`，2375 个文件）。
本文只做一件事：把"要借的那一层"的**数据契约**钉死，并说明本机缺什么。

## 1. 这份交付是 RW-FT，不是 FW

驱动 `SDITT_CR400_NoStrTIrr_250728_Face.m`（1296 行，GBK 编码）：

```
303: % InpPar.NM_FW = 31*1;         % RW-0；FW>0（任意一个大于零的数值）
304: InpPar.NM_FW = 0;         % RW-0；FW>0（任意一个大于零的数值）
```

柔性轮对那一行是**注释掉的**，实际 0 阶。所以包名 `SDITT-RW-FT` 就是它的配置：
**刚性轮对 + 柔性轨道**。柔性轮对的代码全在（14 个 `.m`），但没有随包提供模态数据。

同一驱动里轨道侧的配置：

```
111-112: InpPar.Type_Track = 'FT-Modal'          % 模态叠加法
192:     CutFreq_FT = 2000;
194:     InpPar.N_track = length(find(InpPar.ModeFreq.FT_All(:,2)<=CutFreq_FT));
164:     load Mat_FT_S8b.mat                      % 07(009) 齿轨道岔
168:     load Mat_FT_CN18_T4.mat                  % CN18（18 号道岔）—— 本机没有这个文件
```

## 2. 柔性轮对的数据契约（七个输入、两个产物）

`Load_ModeShape_FW.m:10` 把工作目录 `addpath` 到

```
E:\# Flex-Rigid-20200418\# FW_Rotation\ANSYS_FW_SDITT_220608_Mass21\Modes_RigidBeam_Mass21_6DOF_NRC_230506
```

（E: 盘在本机存在，但这个目录不存在。）它读的文件：

| 文件 | 内容 | 读法 |
|---|---|---|
| `NodePos_FW_SDITT_MASS21_220608.txt` | 节点坐标 | `fopen` + `textscan`（`:24`） |
| `ELIST.lis` | 单元—节点连接 | 14 列，`HeaderLines 5`（`:31-34`） |
| `HBFILE_FW_Free_MASS` | 稀疏质量阵 | Harwell-Boeing，`Load_HBFILE.m`（`:38`） |
| `HBFILE_FW_Free_STIFF` | 稀疏刚度阵 | 同上（`:39`） |
| `Modefile_FW_SDITT_220608_MASS21_FreqModal.txt` | 各阶频率 | `textscan`（`:55`） |
| `Modefile_FW_SDITT_220608_MASS21_Mode30.txt` | 振型（按阶分块） | 每阶一个 `Mode<k>.txt`（`:95`） |
| `NLIST_Trend_Lat.lis` | 节点分组（AxleBox_L/R、NRC、WBack、WOut、Tread_*） | `:178` |

产物（`Load_ModeShape_FW.m:277`）：

```matlab
save FW_SDITT_230506_Mass21_v2.mat Pos_Node Mass_FW Stiff_FW DOF_FW NM_FW ModeFreq ModeShape Ele_List Par_FW
```

也就是说 **`FW_SDITT_230506_Mass21_v2.mat` 是从上面那批 ANSYS 导出文件现场算出来的**，
不是必须原件。四个轮对位置写在脚本里：`Pos_Z = [0.436619, 0.42223, 0.436619, 0.42223]`（`InputStream` 段 `:162`）。

第二个产物 `Par_FW_Rotation.mat` 由**另一个工程**（`# FW_Rotation`）生成，本树里只有消费者
`Load_Rotation_FW.m:4-5`，没有生成者。它提供四个矩阵和一个力映射表：

```
Matrix_J, Matrix_E, Matrix_L, Matrix_G, Matrix_F_SumAll
Matrix_C = G*G + G*J - J*G - J*J - E          % Load_Rotation_FW.m:54-55
```

按截止频率切片：`bools = ModeFreq.FW(:,2) <= CutFreq_FW`，`NM_FW = nnz(bools)`（`:39-41`）。

## 3. 数学形式（移植时要实现的部分）

模态坐标的质量是**单位阵**：`Mlc(1:DOF_FW,1:DOF_FW) = diag(ones(...))`
（`Matrix_Vehicle_FW_230409.m:89`），刚体运动仍由 5 自由度 + `Mw/Jwx/Jwy/Jwz` 承担
（`:95-99`），6 阶刚体模态在 `Load_ModeShape_FW.m` 里被删掉（`NM_del = 6`）。所以：

```
q̈ + (2ζω) q̇ + ω² q + 2Ω G q̇ + Ω² C q = Φᵀ f
```

- `ω²` 来自 `ModeFreq`，`ζ` 按节径给（`DR_FW` 默认 1e-2，节径 0 用 1e-3，节径 ≥2 用 1e-4，驱动 `:329-333`）；
- `Ω = V/R0`（`Matrix_Vehicle_FW_230409.m:80`），`Klc += Ω²C`（`:133`）、`Clc += -2ΩG`（`:418`）；
- 接触点位置 = 刚体位姿 + Φ·q，在**变形并旋转**后的踏面节点上搜索
  （`Multi_Con_250812.m:138-155`：`Pos_FW = [0 Yw Zw] + (pos_ori + Defor')·A_WS`，侧滚/摇头角由 `WOut/WBack` 重建）。

## 4. 本机缺什么（已实测）

- `G:\研究生\SDITT-RW-FT-250728` 下 2375 个文件，文件名含 `FW` 的 **14 个，全部是 `.m`，0 个数据文件**；
- `Par_FW_Rotation.mat`、`FW_SDITT_230506_Mass21_v2.mat`、两个 `HBFILE_FW_*`、各阶 `Modefile_FW_*`、
  `NodePos_FW_*`、`ELIST.lis`、`NLIST_Trend_Lat.lis`：F:/G:/H:/E: 均搜不到；
- `D:\# Flex-Rigid-20200418`、`D:\# Projects` 不存在；`E:\# Flex-Rigid-20200418` 不存在。

结论：**能借方法与契约，借不到数字。**

## 5. 可以立刻借到的另一层：柔性轨道模态集

| 资产 | 大小 | 用途 |
|---|---|---|
| `Mat_FT_S8b.mat` | 983.63 MB | `07(009)` 道岔 Abaqus 模态集（ModeFreq / ModeShape / ModeShape_Mapping / Pos_Node / N_Node / DOF_Node / Type_SpaceIron） |
| `DR_S8b_v*_Crossing.txt` / `_WeldAcc.txt` | 各 0–10 KB | 逐阶实测阻尼比（按"典型/常值"两类） |
| `Mileage_prr_2.txt` | 0.00 MB | 里程—型面布置 |
| `Par_Vehicle_CRH380A_v6_RW.m` | 0.01 MB | 车辆参数，可用来交叉核对我们的车辆库 |

我们已经有 `ModalTrack`（`src/velch/track_models.py:39`）与 `TrackKernel`（`:111`，验到 3002 阶），
所以这一层是"换一份更细的模态集"，不是新能力。`Mat_FT_CN18_T4.mat`（18 号道岔）**不在包内**。

## 6. 移植计划（S8，五步，每步有判据）

| 步 | 内容 | 判据 |
|---|---|---|
| S8-1 | 模态坐标块：单位质量、对角 ω²、对角 2ζω；接入状态向量与列名 | 自由响应频率与解析解 `<1e-6`；零模态时与现有刚性结果**逐位相同** |
| S8-2 | Φᵀ 映射：悬挂力、重力、接触力 → 模态力 | 静态下模态坐标无变形；6 个刚体位移与刚性版**逐位相同** |
| S8-3 | 变形踏面接触几何：节点位移 + `A_WS` 旋转，接触点在变形面上搜索 | 模态为零时与现有 `contact_search` **逐位相同** |
| S8-4 | 旋转耦合：`Ω²C` 进 Jq、`-2ΩG` 进 Jv（并且进解析雅可比） | 中心差分 `<1e-6`；`Ω=0` 时退化为刚性；`Ω²C`/`-2ΩG` 单独置零各跑一次确认影响 |
| S8-5 | 整车 0.05 s 窗口对照刚性轮对与 SDITT 参考 | 低频一致；高频出现轮对弹性模态峰，峰位与 `ModeFreq.FW` 对得上 |

不依赖模态来源的部分：S8-1、S8-2、S8-4 的框架与判据。可以用**合成模态**（两阶 300/600 Hz
的解析模态）先把它做出来，等真模态到位只替换模态表。

## 7. 复算命令

```powershell
# 看柔性轮对代码是否在、数据是否在
$p='G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728'
Get-ChildItem $p -Recurse -File | Where-Object { $_.Name -match 'FW' } | Group-Object Extension
Get-Content "$p\SDITT_CR400_NoStrTIrr_250728_Face.m" -Encoding Default | Select-String 'NM_FW\s*=|Type_Track\s*=|CutFreq_FT\s*='
```

## 8. 边界

- 本文只记录契约与缺口，**没有**改动任何求解器代码，也没有改变冻结物理
  （静载门 59 680.5769 N / 65.47 µm、八接触峰值 89.68 / 170.61 kN、七门）。
- SDITT 那边的柔性轮对**从未在本机跑过**（数据不在），因此本文不含任何 SDITT 侧数值结论。
- 轮对模态的来源有三条路，按代价排：拷回 `# FW_Rotation` 那套 ANSYS 导出（最快）；
  在自己机器上用 ANSYS 按 `Load_ModeShape_FW.m` 的七个文件格式重导一次；用合成/解析模态只验框架。
