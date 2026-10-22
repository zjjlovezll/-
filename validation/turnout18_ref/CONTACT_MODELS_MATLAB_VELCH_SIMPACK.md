# 三个实现的轮轨接触对照：MATLAB(SDITT) / Velch / Simpack（2026-10-20）

## 1. MATLAB（`G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728`）怎么算

分三层，每层一个可搬的机制。

### 1.1 找点：按"正渗透区间"取点，再取软加权重心

`Extreme_Boundary.m:12-17`
```matlab
bools_start = (Ver_Dis(1:end-1,2)<0 & Ver_Dis(2:end,2)>=0);
bools_end   = (Ver_Dis(1:end-1,2)>=0 & Ver_Dis(2:end,2)<0);
for i = 1:size(Ver_Dis_start,1)
    p = Ver_Dis_start(i,1);  q = Ver_Dis_end(i,1);
    [~,pos] = max(Ver_Dis(p:q,2));          % 每个连通区间内取一个点
    Ver_Dis_2_postive(i,:) = [p+pos-1, Ver_Dis(p+pos-1,:), Ver_Dis_1(p+pos-1,2)];
end
```
即**一个连通的正渗透区间 = 一个接触点**，天然支持多点接触，也不会出现"两个体之间只能选一个"的全局 argmax。

`Quasi_Elastic_Correction.m:30-35`
```matlab
theta = 2e-5;                                              % 20 µm
fun_weight = exp((Elastic_pen(p:q,2)-pen_max)/theta);      % 软最大
dis_y = diff(Elastic_pen(p:q+1,1));
Ver_Pen_b(i,1) = sum(Elastic_pen(p:q,1).*fun_weight.*dis_y) ./ sum(fun_weight.*dis_y);
```
接触点不是 argmax，而是 **θ = 20 µm 的 soft-argmax 重心**——横位随渗透场连续滑动，不存在跳变。

### 1.2 归属：按型面横向范围判轨体

`Judge_i2_ConRail.m`：把接触点横位与各子轨型面的 `min(y)` 比较，落在哪条型面范围内就归哪个体（R1/R2/R3 分别为主轨、翼轨、心轨）。**用几何边界判，不用谁深谁赢。**

### 1.3 力：曲率导出的刚度 + 条带积分 + 每斑独立

`Re_Radius.m`
```matlab
R_yy_w = Con_wheel_2(:,3);                       % 滚动半径随横位
R_xx_w = interp1(...);  R_xx_r = interp1(...);   % 横向曲率半径
rou    = 4./(1./R_yy_w + 1./R_xx_w + 1./R_xx_r); % 等效半径 ρ
```
`Par_Hertz.m`
```matlab
beta = acos(rou./4.*abs(1./R_yy_w-1./R_xx_w-1./R_xx_r));
m = interp1(BGmn(:,1),BGmn(:,2),beta);  n = interp1(BGmn(:,1),BGmn(:,3),beta);
a1 = 0.1506e-3 * m .* rou.^(1/3);   b1 = 0.1506e-3 * n .* rou.^(1/3);
elastic_permeability_Unit = 3*(1-Vr^2)/(pi*Er*a1) * ellipticK(psi);  % 单位力柔度 [m/N]
Con_A = 1/2*1./R_yy_w;   Con_B = 1/2*(1./R_xx_w+1./R_xx_r);
```
`Multi_Con_250812.m:418`（单点 Hertz 口径）
```matlab
Normal_Force(:,5) = (Con_wheel_2_II(:,5) ./ elastic_permeability_Unit(:,1)).^(3/2);
```
即 **N = (δ / C_Hertz)^(3/2)，C_Hertz 由 β、ρ、m、n 从曲率算出**，不是给定的小半径。

`NF_STRIPES_230623.m:36-41, 292-315`（STRIPES 口径，51 条带）
```matlab
epsilon = n.^2 ./ Con_r ./ (1+(n./m).^2);        % 无量纲
h_0     = epsilon .* Con_wheel_2_II(:,5);        % 虚拟渗透基准
pen_j   = h_0 - gap_j;                           % 每带渗透
a_j     = sqrt(pen_j ./ A_cj);                   % 带半宽随渗透开方
K_j     = Er*(1+(n_j./m_j).^2).*dy ./ (2*(1-Vr^2)*n_j.^3);   % [N/m]
NF      = K_j .* pen_j;                          % 线性
```
线性的原因是带长 a_j ∝ √δ ⇒ 面积 ∝ √δ ⇒ 压力 ∝ √δ ⇒ 力 ∝ δ。

`NF_STRIPES_230623.m:52-117`：相邻斑的渗透区**互相裁掉重叠部分**（`limit_1 = 1e-3`，用单调起止点判断谁覆盖谁），避免同一块渗透被两个斑各算一次——这正是我们 `merge_contact_responses` 现在缺的。

## 2. 三个实现对照

| 维度 | MATLAB (SDITT) | Velch | Simpack |
|---|---|---|---|
| 接触点选择 | 正渗透区间内取极值 + θ=20 µm soft-argmax 重心 | 全局硬 argmax（每体一点） | 接触几何表 + 有界搜索窗 + 换体迟滞 |
| 多点接触 | 每连通区间一点，无上限 | 每轨体一点，力相加（重叠会重复计数） | 最多 5 斑/配对（`_1.._5`），斑由轮型面外侧向内侧编号 |
| 法向刚度 | 曲率导出（ρ, A, B, m, n → 柔度） | **固定 `effective_radius_m`** | 离散弹性切片，刚度为切片 Hertz 集成 |
| 法向力 | 单点 (δ/C)^1.5 或 51 条带 ΣK_jδ_j | C·δ^1.5，C=(4/3)E*√R* | 逐切片积分，`p_geo,max` 只作记录 |
| 渗透口径 | 虚拟渗透 h_0 = ε·δ_elastic（有界） | **真实刚性侵入**（数值量） | 切片渗透 ≤ `cont_disc_delta`(0.5 mm) |
| 阻尼 | `Type_Normal='STRIPES&ConDamp'` 有接触阻尼 | 固定 `1e6`，δ≤0 直接断力 | `fn.dref=1e5` + damping transition + standstill |
| 积分 | Park / Newmark（未真正实现 Co-Running） | DOP853 / Radau | SODASRT_2（BDF 1–5，32 线程） |
| 归属 | 按型面横向范围 | 按轨体窗口 + 迟滞 | GT 表 |

## 3. 为什么"算出来的力是对的"——三条判据

### 3.1 静态力根本不是接触律算出来的
ΣN = W 由质量决定。48 654 kg ⇒ 477.3 kN ⇒ 每轮 59.7 kN。任何连续、单调的接触律，只要解了垂向平衡，都给这个数。**所以"静载对"不证明接触律对。**

### 3.2 动态力由几何 + 惯性决定，接触律只决定侵入与接触斑
350 km/h 下轮子必须跟随走行面的斜率 ∂z/∂s；所需垂向加速度 a = v²·d²z/ds²。辙叉鼻端一步 1.01 mm/30.4 mm 的落差 ⇒ 需要 200 kN 级的力。**这条与我们 600 kN 的量级吻合，说明力本身是从几何算出来的，不是从力律算出来的。**

### 3.3 接触律的可检验量是"侵入—力"这一对，Simpack 自己给了标尺
用 Simpack 的逐时刻 (N, δ) 反算：

| 量 | 数值 |
|---|---|
| Simpack N/δ^1.5 中位 | **1.117e11**（p10 9.97e10，p90 1.29e11） |
| ⇒ 等效半径 `R* = (C/(4/3 E*))²` | **0.5407 m** |
| 曲率法（`Re_Radius` 口径，LMA+60 kg） | ρ ≈ 0.55–0.71 m ✅ 同量级 |
| Velch 用的 `effective_radius_m` | **0.02 m**（自编参数） |
| ⇒ 刚度比 | 我们软 **5.2 倍** |
| 静平衡侵入：我们 / Simpack / 按 R*=0.5407 预测 | 0.1976 / 0.0662 / **0.0659 mm** |

**最后一行是决定性的**：把 R* 换成 0.5407，静平衡侵入预测 0.0659 mm，Simpack 实测中位 0.0662 mm，差 0.5%。所以 Simpack 的接触律就是一条曲率导出的 Hertz 律，我们的 0.02 m 把侵入放大了 3 倍——这才是 1.3 mm 的几何坑被放大成 0.92 mm 侵彻、600 kN 冲击的算术原因。

## 4. 但"把刚度改对"并不能修好它（实测）

| 算例（辙叉窗，0.05 s） | 右轨峰值 | 最大侵入 | 有接触采样 | 墙钟 |
|---|---|---|---|---|
| 无翼轨体 + R*=0.02（软） | 596 051 N | 0.9197 mm | 36/101 | 65 s |
| **加翼轨体 + R*=0.02（软）** | **229 182 N** | 0.4858 mm | 67/101 | 19 s |
| 加翼轨体 + R*=0.5407（硬，正确刚度） | **716 807 N** | 0.3461 mm | 36/101 | **10.6 s** |

刚度改对之后侵入确实降到 0.346 mm（更接近 Simpack 的 0.12–0.34 mm），但**峰值反而升到 717 kN**：硬接触把轮子弹得更高（轮心 z 出现 +0.026 mm 的正值），脱空段从 4 段并成 3 段更长的段。

**结论：刚度不是杠杆，连续性才是。** 力由几何+惯性定，接触律决定的是"轮子被托住还是被弹开"。要让轮子被托住，必须让接触点连续、多点、有阻尼——这三件事 MATLAB 全都做了。

## 5. 取长补短的落地清单

1. **soft-argmax 接触点**（搬 `Quasi_Elastic_Correction`）：把 `find_graph_contact` 的 `argmax` 换成 θ 可配的 soft-argmax 重心，`y* = Σ y·w·dy / Σ w·dy`，`w = exp((pen−max)/θ)`。θ 默认 20 µm。这一条直接消灭 38 mm 横跳。
2. **每连通区间一点**（搬 `Extreme_Boundary`）：把已经写好但没接线的 `find_graph_contacts` 接进求解器，按 `pen>0` 的连通段分组，每组一点。
3. **斑间去重**（搬 `NF_STRIPES` 的 Col 6–11）：`merge_contact_responses` 现在把相邻体的重叠渗透各算一次，要按横向区间裁掉重叠。
4. **曲率导出刚度**（搬 `Re_Radius`+`Par_Hertz`）：在 `find_graph_contact` 里按接触点横位取轮/轨横向曲率半径，算 ρ、β、m、n、C，替换 case 里的常数 `effective_radius_m`；常数保留为回退。
5. **接触阻尼按 `fn.dref` 口径**（学 Simpack）：小侵入段给非零阻尼，δ≤0 用过渡而不是硬断。
6. 保留 Velch 自己的长处：单文件、无 MATLAB 依赖、7 项数值门、逐运行 manifest、多进程 7× 并行、表化后 ~1 µs 的接触查表。

验收：辙叉窗右轨峰值进入 Simpack 的 1.3 倍以内（≤170 kN）且不出现完全脱空，平直段静载仍为 59 680.6 N。
