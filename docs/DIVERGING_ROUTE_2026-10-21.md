# 曲向（diverging route）装配 — 阶段 1 记录（2026-10-21）

## 1. 目标与验收

把 18 号道岔**曲向**接进 Velch 并跑出与直向可比的工况。验收门（目标 `goal-e940d288` 第 1 条）：

- 直/曲两套轨件序列都由数据装配，不手填断面；
- 车体沿 `layout=diverging` 的路径走，横移速度进入蠕滑；
- 冻结 oracle 不变（静载 59 680.577 N、静平衡 65.5 µm）；
- 测试全过（本阶段结束时 256 项）。

## 2. 几何权属：形状是测出来的，位置是设计值

这是本阶段最重要的一条边界，写在这里以免以后被误读：

| 量 | 来源 | 可核验性 |
|---|---|---|
| **钢轨断面形状** | SDITT `07(009)` 库的 `.prr`（`qjbg` 曲基本轨 / `qjg_cgyg` 曲尖轨 / `cxg` 曲辙叉） | 逐点来自文件，0 处手填 |
| **断面横向放置** | 库文件各自的 y 带中心 → 归到标准半轨距线 | 由文件算出 |
| **线路中心线 y(s)** | 图纸设计半径 **R = 1100.7175 m**（客专线(07)009 DXF 实测标注），自尖轨尖端 50.578 m 起 `y = (s-s₀)²/(2R)` | 设计值，非测量 |

**为什么位置不能来自库文件**：每个 `.prr` 在自己的零件坐标系里，`qjbg` / `qjg_cgyg` / `cxg` 的带中心漂移分别是 +72.0 / +34.2 / +29.4 mm；若直接串起来，路径会先升到 +72 mm 再掉回 +38 mm 再升到 +67 mm —— 非单调，物理上不成立。库内真正的放置数据在 `BasePro.ND`（28×8 单元）与 `AbaqusInput.mat`，后者在本机**缺失**。因此位置改用图纸半径，并在文档里明确标注。

## 3. 新增代码

- `Velch/src/velch/paths.py`：`PathTrack(stations_s_m, y_m)`，`at()` / `slope_at()` / `lateral_velocity_m_s()` / `span_m` / `summary()`；`load_path()` 接受字典或点列；`PathError`。表外恒为 0，站点必须严格递增。
- `Velch/src/velch/vehicle.py`：`VehicleCase.path: PathTrack | None = None`（末尾带默认值），加载器 `load_path(raw.get("path"))`。
- `Velch/src/velch/vehicle_solver.py` `_evaluate_patch`：`path = self.case.path`；`lateral_extra = path.at(x)`；`lateral_rate = path.lateral_velocity_m_s(x, speed)`；轮位 `wheel_lateral_offset_m + lateral_extra`，横向速度 `wheel_v_y_m_s = v[wh] + lateral_rate`。
- `Velch/tests/test_paths.py` 9 项（表外为 0、插值、坡度、`speed*slope` 与中心差分一致、非单调拒绝、长度不匹配拒绝、非有限拒绝、两种输入形式等价、`span/summary`）。

语义约定（写进代码注释）：**算例的 path 表达在钢轨参考系里**，所以"轮位偏移"与"钢轨放置偏移"同时含 path 项、在钢轨系内互相抵消；路线曲率对动力学的真实作用只剩**蠕滑**（横移速度）与断面本身。

## 4. 装配与产物

`Velch/validation/crh380a_m/build_diverging_case.py`：

- 5 mm 站位网格（默认 30–125 m），按里程选件：`qjbg`(≤60.943) → `qjg_cgyg`(50.578–100) → `cxg`(103.280–116.590)；
- 两道 pass：先在有件的站位算出 `y_offset = 0.753 + y(s) − 带中心`，再对全网格**线性插值偏移**（跨 100.0→103.28 的 163 mm 断口），保证相邻站位横向仍然重叠；
- **左右轨都要跟着 path 走**：左轨用直向 `Profile_Mileage_JBG.prr` 的外形、偏移 `−0.753 + y(s)`；
- 产物 `case_diverging_R1100.json`：8 条轨（2 模板 × 4 轴）、右轨单一 `main` 体 16 664 站位、`path` 45→1979 mm。

## 5. 三道诊断（都把失败原因钉死了）

1. **只移右轨、不移左轨** → 静态平衡 `hung-bogie branch — the lightest contact patch carries only 0.0 N while the heaviest carries 119 277.1 N (even share ~59 662 N)`。左轮被带走 0.13–0.17 m，脱离左轨。
2. **只移轮、不移轨** → 同样 0 N / 119 kN（对称的反向错位）。
3. **两者同移**（现方案）→ `probe_div_alignment.py` 逐轨核对：左右各 8 个接触的横向重叠 **71.7 / 72.4 mm**，与平直段一致。

诊断工具留在 `probe_div_alignment.py`（打印每条轨的 `x / path / 轨带 / 轮带 / 重叠`）。

## 6. 已知近似与限制

- **单一体**：曲向的尖轨区（50.578–60.943）实际有 `qjbg` 与 `qjg_cgyg` 两条轨并排承载，本版每站只取一件，未做"基本轨→尖轨"的多体交接。直向的辙叉区已有 `main/point/wing` 多体，这套机制可复用。
- **左轨断面**用直向基本轨，库里没有"曲左轨"。
- **放置**用设计半径，未用库内 `BasePro.ND`（且 `AbaqusInput.mat` 缺失），因此曲向的横向位置是设计重建而不是复现。
- 路径的绝对偏移在大里程处到 +2 m（R=1100 的几何结果），只用于取坡度，不参与接触几何。

## 7. 复现

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 validation\crh380a_m\build_diverging_case.py --span 30 125
cd validation\crh380a_m
python -X utf8 make_window_case.py case_diverging_R1100.json div 50.0
python -X utf8 probe_div_alignment.py case_div_diverging_R1100_0p05s.json
python -X utf8 -m velch run-vehicle case_div_diverging_R1100_0p05s.json --output out_div_0p05s
```

## 8. 状态

- 装配 ✅、路径接线 ✅、对齐诊断 ✅、256 项测试 ✅。
- 0.05 s 窗口（前轴 60.00→64.86 m，跨 60.943 m 的 `qjbg→qjg_cgyg` 交接）已跑完，`numerically_checked`。

## 9. 直向 vs 曲向（同一里程窗、同车同速 350 km/h）

| 指标（前轴） | 直向 `out_thru_0p05s` | 曲向 `out_div_0p05s` | 变化 |
|---|---|---|---|
| 右轨峰值 | 61.8 kN | **102.5 kN** | +66 % |
| 右轨最小 | 56.6 kN | **18.0 kN** | −68 % |
| 右轨均值 | 59.7 kN | 56.0 kN | −6 % |
| 左轨峰值 | 60.1 kN | 68.0 kN | +13 % |
| 脱空采样 | 0 | 0 | — |
| 轮对垂向行程 | 0.011 mm | **0.082 mm** | 7.5× |
| 最大侵入 | 0.074 mm | 0.090 mm | +22 % |

物理上说得通：60.94 m 处右轨从曲基本轨交接到曲尖轨，断面带中心变化约 60 mm，叠加 `y(s)` 带来的横向蠕滑（该站 `slope = 0.0086`，即 0.86 % 横移率），右轨瞬时卸载到 18 kN 又加载到 102.5 kN，而直向在同一个窗口几乎无波动（0.011 mm）。**这是本阶段第一个可用的曲向结论**，也是后续与 Simpack/实测对照的起点。

限制照旧：单件轨道（无基本轨→尖轨交接双体）、左轨用直向断面、位置按设计半径重建。下一步先做**尖轨区双体交接**（把 `qjbg` 与 `qjg_cgyg` 同时放进 50.578–60.943，复用直向辙叉那套 `main/point/wing` 机制），再进阶段 2。

## 10. 双体交接（进行中，未通过）

目标：把 `qjbg`（曲基本轨）与 `qjg_cgyg`（曲尖轨）在 50.578–60.943 并排放进同一侧，让轮载自然交接。装配已做成（`build_diverging_multi.py`，`stock` 6189 站 + `switch` 9885 站，各站横向重叠 71.7–72.9 mm，与平直段一致），但**静态求解仍未通过**，逐层排到两个具体缺陷：

1. **基本轨台肩槽吞轮**。曲基本轨轨头为让尖轨落座而被切出约 **22.6 mm** 深的槽。单件合并断面不会选到它（轮落在轨顶），一旦 `stock` 独立成体，接触搜索把槽底当"最深点"，实测侵入 **16.06 mm / 64.0 kN**（`probe_div_statics.py`）。
   已写 `prepare_seat_clip.py` 把低于轨顶 0.5 mm 的部分抬平（实测抬升 22.59 mm，节点数保持 1001 不变）；但重算的**纵向梯度 `dz_ds` 在 60 m 处仍非有限**，求解器以 `ProfileError: longitudinal profile derivative is undefined at the contact point` 拒绝运行——原因是各站断面来自不同 PRR 文件、节点网格不共形。
2. **种子垂向状态偏低**。探针显示后转向架（40/42.5 m、纯 JBG、path=0）也有 **0.897 mm** 侵入、前转向架 16 mm，同一条车呈 0.8 mrad 俯仰——说明复用的 `initial_state` 与新几何不匹配，不是断面问题。左轨四个轴全部报无接触（`geometry = None`），与右轨被压 16 mm 相洽。

两条待办按顺序：①用**合并序列**（`ProfileSeries` 的公共网格）而不是逐站 CSV 重建双体断面，使 `dz_ds` 良定义；②按新几何**重新解一次静态种子**，不要沿用源算例的 `initial_state`。

## 11. 阶段①验收（四量齐全）

`velch assess` 对同一里程窗（前轴 60.00→64.86 m、350 km/h、101 样本、静态轴重 119 371 / 119 497 N）的判定：

| 指标 | 直向 `out_thru_0p05s` | 曲向 `out_div_0p05s` | 倍数 |
|---|---|---|---|
| 接触力峰值（右轨轴1） | 61.79 kN | **102.48 kN** | 1.66× |
| 接触力谷值（右轨轴1） | 56.63 kN | **18.00 kN** | — |
| 脱空采样（`lost`） | 0 | **1**（轴2 右轮 0 N） | — |
| 脱轨系数 Q/P | 0.031 | **0.232** | 7.5× |
| 轮重减载率 ΔP/P | 0.038（PASS） | **1.000（FAIL）** | — |
| 轮轴横向力 H | 0.47 kN | 9.84 kN | 21× |
| 有效接触斑数 | 8 | 8 | — |

判定：直向 `overall PASS`；曲向 `FAIL`（轮重减载率 1.000 > 0.6），脱轨系数 0.232 远低于 0.8 限值。物理上说得通：60.943 m 交接处右轨瞬时完全卸载，随即被顶到 102 kN。

**冻结 oracle 未被扰动**（`check_static_gate.py`）：`flat_static_stiff` 与 `flat_static_soft` 均为峰值/谷值 **59 680.5769 N**、侵入 **65.47 µm**（hertz 65.47 µm、沉降 0.00 µm、脱空 0）。测试 **256 passed**。
