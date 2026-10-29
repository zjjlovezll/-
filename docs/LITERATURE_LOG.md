# 文献日志（任务书要求：碰到具体问题才查，登记 DOI/URL 与"它解决了什么"）

## L1 频域方法对非线性系统的适用范围

- **问题**：S5 用"单带激励的复数响应"当线性算子，四带叠加误差 61–213 %。
- **来源**：Arsenio, *Adaptive …*（MIT，学位论文），第 30 页："Frequency domain methods may not be applied
  directly to nonlinear systems because frequency response functions cannot be defined"
  <http://www.ai.mit.edu/projects/mars/pubs/ThesisArsenio.pdf>
- **它改变了什么**：不再试图证明"我的 H 应该线性"，改用最佳线性近似（BLMA）+ 失真电平，见 `docs/S5_BLMA_2026-10-24.md`。

## L2 多正弦激励与随机相位平均（BLMA 的标准做法）

- **问题**：如何在存在非线性时仍得到一个可反演的频域算子。
- **来源**：Weiss 等，多正弦谱线设计与辨识（South Wales 存档）
  <https://pure.southwales.ac.uk/ws/portalfiles/portal/2109606/M._Weiss_2003_2059431.pdf>
- **它改变了什么**：H 的每一列改为 6 组随机相位的相干平均，并把真实相位对齐后取均值。

## L3 轴箱加速度用于轨道短波识别（工程侧佐证）

- **问题**：短波（0.05–1 m）到底该看哪个量的信号。
- **来源**：①SVMD 机理驱动的钢轨波磨检测，*Meas. Sci. Technol.* 2024
  <https://beta.iopscience.iop.org/article/10.1088/1361-6501/ad56ae/meta>；
  ②剑桥：30–1000 mm 波长段是波磨主战场
  <https://api.repository.cam.ac.uk/server/api/core/bitstreams/51c2a99b-3745-4280-96bb-7cec4e3642c1/content>；
  ③Warwick 2024 学位论文：振动法检测轨道问题的综述
  <https://wrap.warwick.ac.uk/195458/1/WRAP_Theses_Jin_2024.pdf>
- **它改变了什么**：确认 0.1 m 带是"该被看到"的物理量，问题只在于衰减与失真，不是选错了观测量。

## L4 不假设线性的反演路线（数据驱动）

- **问题**：若线性不可加，主流做法是什么。
- **来源**：GWO–CNN–LSTM 反演轨道纵向不平顺（*铁道建筑* 系列，DOI 10.13238/j.issn.1004-2954.202210240004）
  <https://openurl.ebsco.com/EPDB%3Agcd%3A5%3A30898853/detailv2>
- **它改变了什么**：给出了 S5 之外的第二条路（时域/数据驱动），但没有被本轮采用——任务书要求 S5 的 Tikhonov 结果，先把它做到底。

**使用规则（写在这里以免将来滥用）**：文献只用来决定"方法该怎么量、结论能说到哪"，不作为数值证据；
本仓库所有数值证据必须在 `docs/` 里可复算（脚本 + 输出），文献条目只出现在本文件。

## L5 加速度反演垂向不平顺的**公开精度基准**与它需要的额外传感器（最重要的一条）

- **问题**：我们的标定误差 65 %（合成、两带、0.1 mm、350 km/h）到底算失败还是常态？
- **来源**：Dai, Xu, Li, Liang, *Vertical track irregularity identification based on a detrending
  numerical integration algorithm with vehicle acceleration measurements*, MSSP 235 (2025) 112958,
  DOI 10.1016/j.ymssp.2025.112958（用户提供的 PDF）。
- **它给了什么**：① 用**轴箱或构架**加速度、内嵌去趋势的数值积分（参数自适应 VMD + 粒子群调四个积分参数），
  在 0.1–100 m 波长、200 m 线、**30/50/70 km/h**、200 Hz 采样下，估算垂向不平顺的 **RMSE = 1.25–2.42 mm**
  （表 4：40 km/h 轴箱 2.19 / 构架 2.42；60 km/h 1.76 / 1.67；80 km/h 1.49 / 1.74）；
  ② 激励用 **AAR 4 级**谱；③ 结论里明确 **< 0.1 m 与 > 100 m 两端退化**；
  ④ 只用构架加速度时 **< 10 m 明显偏离**；
  ⑤ 关键一句：长波之所以能拿回来，是因为**激光位移计直接测了车体↔轴箱相对位移 `dr`**，
     这条通路"绕过了 VMD 与数值积分"。
- **它改变了什么**（三条，都会改我们的下一步）：
  1. **口径**：这个领域的绝对精度是**毫米级 RMSE**，信号本身也是毫米级 → 相对误差几十个百分点是常态。
     我们把 65 % 当成"方法失败"是不公平的；该报的是"在该幅值下的绝对 RMS 误差"，并给出信号自身的 rms 作分母。
  2. **缺的那件东西是传感器，不是估计器**：他们拿到长波靠的是**相对位移**通道。这与我们 S4/S7c 的
     "加速度没有低频、短波被衰减 1/6330"完全一致 —— 加一条相对位移观测，比再换一版估计算法更有效。
  3. **速度域不对等**：他们 30–70 km/h、200 Hz；我们 350 km/h（0.1 m ↔ 972 Hz）。他们那条
     "速度越高、< 0.1 m 偏差越大"的趋势正好跨过我们的工作点 —— 所以我们的短波段更难，不是我们实现差。

## L6 联合估计（不平顺 + 支承刚度）的框架与"误差由模型保真度决定"

- **问题**：常数 `H` 不成立（S5）之后，替代框架是什么；以及误差到底受 SNR 还是受模型限制。
- **来源**：Han, Li, Cheng, *Joint estimation of railway ballasted track irregularities and stiffness
  using dual Kalman filter strategy and dynamic vehicle-track model*, 2026, CC BY（用户提供的 PDF）；
  关键词里明确写着 onboard measurement + **axle box acceleration (ABA)** + model updating。
- **它给了什么**：双重 Kalman 并联估计垂向几何与支承刚度；刚度更新用 **ABA 在 P2 共振区**的谱特征；
  数值研究扫 SNR 与降采样（2–3 kHz 是常规巡检采样，被降到 300 Hz 做压力测试）；
  结论是"在很宽的 SNR 范围内稳定"，**SNR 的影响有限**；插值主要影响刚度、几乎不影响几何；
  **恢复出的空间波长分辨率约 0.3 m**；并自陈弱点是"依赖物理模型精度，模型失配会带来几何估计偏差"。
- **它改变了什么**：① 我们 S5 的结论"残差 1e-11、误差 136 %、加多少平均都不降"与它的"SNR 影响有限、
  误差由模型保真度决定"是同一件事的两个说法 —— 我们的 65 % 属于**偏置**，不是噪声，这一点被独立印证；
  ② 联合估计（把刚度/参数当作状态一起估）是常数 `H` 的正当替代，且不需要线性化到"一个矩阵"；
  ③ 他们报的空间分辨率 0.3 m 给了我们一个可比的"波长下限"参照。

## L7 前向代理：分支 Fourier 神经算子把车-轨耦合算 32× / 263×

- **问题**：非线性反演要几十次到几千次正演，成本是否可接受。
- **来源**：Wang, Sun, He 等, *A branched Fourier neural operator for efficient calculation of
  vehicle–track spatially coupled dynamics*, CACAIE 2025, DOI 10.1111/mice.13367（用户提供的 PDF）。
- **它给了什么**：PINO-VTSCD 用**两个分支**（一个出车体响应、一个出构架/轮对/钢轨响应）做物理约束的神经算子；
  相对 L2 误差 **4.96 %**（比 CNN-GRU 的 11.7 % 低 57 %）；相对传统车-轨耦合模型**加速 32×**，
  批量 4800 个工况时 **263×**；训练参数取 CRH380 的 80 %–120 % 范围。
- **它改变了什么**：它把"每次反演要跑很多次正演"变成可承受的，正是 S5 之后非线性/迭代反演的前置条件；
  但注意两条：代理误差 4.96 % 会直接进入反演偏置，且它的训练域是 ±20 % 参数，
  **不能拿它去替代我们已冻结的物理**，只能当"候选搜索/初值"用，最终仍由真求解器确认。

## L8 实测数据 → Simpack 场景：曲率与缓和曲线的提取方法

- **问题**：实测反演时，横向响应里混着线形（曲线、超高、缓和曲线），我们的横向通道在直线对称工况下
  被垂向激励驱动 17× —— 到了曲线段几何会成为主项，怎么把它分离出来。
- **来源**：Cleven, Moser, Corves, *A methodology for scenario generation of railway high-speed tracks
  based on measured data for use in multibody simulation*, RWTH Aachen / Siemens Mobility（用户提供的 PDF）。
- **它给了什么**：如何从实测信号里判定**圆曲线、直线、缓和曲线**的参数，并生成可直接用于 Simpack 的场景；
  用构架多条信号与实测对比来证明场景生成可用。
- **它改变了什么**：给出"先定线形、再谈不平顺"的处理顺序；这也是我们横向通道将来做实测反演时
  必须前置的一步（否则会把曲线当成"横向不平顺"）。

## L9 独立第三方道岔车-轨动力相互作用基准（ANSYS FE + VAMPIRE MBS）

- **问题**：我们的道岔峰值与频带除了 Simpack，还缺一个独立对照。
- **来源**：Blanco-Saura, Velarte-González, Ribes-Llario, Real-Herráiz, *Study of the dynamic
  vehicle-track interaction in a railway turnout*, Multibody Syst Dyn 43 (2018) 21–36,
  DOI 10.1007/s11044-017-9579-2（用户提供的 PDF）。
- **它给了什么**：用 ANSYS 时域 FE 轨道 + VAMPIRE PRO 多体车辆做**反馈式联合仿真**，
  专门研究转辙器尖轨与辙叉鼻端的垂向动载，扫了速度、簧上质量、轨道刚度、车辆特征频率四个参数。
- **它改变了什么**：提供了一个不依赖 Simpack 的第三方参数敏感性结论，可用来校验"辙叉窗峰值主要由
  几何台阶 + 簧下质量决定"这一条判断；也说明"轨道用 FE、车辆用 MBS"的耦合方式与我们不同（我们是一体求解），
  差异要写进对照报告而不是当成误差。

## L10 Koopman 综述（提升线性化的方法地图）

- **问题**：S6 的提升特征实验失败了，但当时样本量不足（8 个复参数、7 个样本），是否值得重做。
- **来源**：Durán-Siguenza, Minchala, Garza-Castañón, Zhang, *Control based on the Koopman operator:
  A comprehensive review*, J. Franklin Inst.（用户提供的 PDF）。
- **它给了什么**：提升字典的选择、数据需求、以及"线性只在提升空间成立"的适用边界。
- **它改变了什么**：暂时不改动 —— 复现 S6 的前提是先把**单幅值可复现性**做出来（那时留出误差 114.9 %，
  说明问题在实验设计不在模型形式）。这条只作为"重开时该查什么"的备查，不作为现在的行动项。

## L11 柔性轮对的接触点算法：**变形后踏面上的接触线法**（S8-3 下一个增量的直接依据）

- **问题**：S8-3 目前只把胎面位移折进"侵入深度"这一个标量，接触点仍在未变形型面上搜索、法向仍是刚体法向。文献里这一步到底怎么做？
- **来源**：Gao Hao, Dai Huan-yun（西南交大牵引动力国家重点实验室）,
  *Wheel-Rail Contact Point Calculation of Flexible Wheelset Base on Wheel-Rail Contact Line Method*,
  Applied Mechanics and Materials 105–107 (2012) 1284–1288, DOI 10.4028/www.scientific.net/AMM.105-107.1284；
  同组中文版见《铁道学报》2012(05)《柔性轮对轮轨接触点算法》。摘要已读，正文未读（付费）。
- **它给了什么**：给定轮对的位置**与变形**，对每一滚动圆上的点算出**变形后的法向量**及其在钢轨上的投影，
  由此构成"轮轨接触线"，再用**接触线与钢轨断面型面之间竖直距离最小**定位最终接触点；随后用单轮对刚柔
  耦合方程做动力仿真，并与刚性轮对对比，结论是柔性方法给出**更准确的接触点位置**，且会改变蠕滑。
  参考文献链同时给出了这一脉的经典工作：Baeza/Fayos/Roda/Insa（VSD 46(7) 2008, 647–659，柔性旋转轮对的高频
  车-轨动力学）、Kaiser & Popp（VSD 44 2006, 932–939，弹性轮对与弹性钢轨相互作用）、
  Popp/Kaiser/Kruse（Arch. Appl. Mech. 72 (2003) 949–961）、Arnold/Kaiser/Schupp（VSD Suppl. 41 (2004) 242–251）。
- **它改变了什么**：把 S8-3 的"下一个增量"从"要不要做"变成"照这个顺序做"——
  ① 法向由**变形后踏面的横向斜率**决定（我们现在用的是刚体法向）；
  ② 接触点位置按"竖直距离最小"在**变形后的型面**上重搜（我们现在固定在轮心正下方）；
  ③ 两者都会改蠕滑，而蠕滑是切向力的入口。
  这也是我在文档里写"本增量只补了深度一个标量"时所说的那半个缺口，现在有了可引用的算法出处。
- **没有改变什么**：它不提供数值算例（没有给出刚性/柔性的力差百分比），所以**不能**当作验收门；
  验收仍用陈嘉胤论文的 Ip1 87.92 → 84.74 kN、轴箱加速度 65.3 → 120.4 m/s² 那几条。

## L12 轮轨接触点/横向力的**算法**：几何最小距离、两点接触、共形接触（第 199–200 轮的缺口出处）

- **问题**：第 200 轮量到"接触平面倾角对横移不响应"（`d(n_y/n_z)/dy` 拟合 6.9e-16），
  由此横向力被 `W·tan τ = 11.9 kN` 封住；而型面采样间距 0.496 mm 让倾角成阶梯。文献里这一步的**标准算法**是什么？
- **来源（题录与可检索片段，正文多数未读）**：
  - Popovici 学位论文（U. Twente），*The contact point position was determined by simply calculating
    the minimum distance between the profiles in vertical direction*
    — https://ris.utwente.nl/ws/portalfiles/portal/6067963/thesis_R_Popovici.pdf#4#20#4
  - *A development of the 2-point Wheel-Rail Contact Algorithm*（韩国，题录可见）
    — http://koreascience.kr/article/CFKO201132164226150.pdf
  - *An innovative wheel rail wear model under conformal contact conditions*，Multibody Syst. Dyn.（2026）
    — https://link.springer.com/content/pdf/10.1007/s11044-026-10185-2.pdf
  - 道岔区接触位置研究（HAL 学位论文，含 diverging route 的 contact position 图）
    — https://theses.hal.science/tel-03687144v1/file/TH2022UEFL2016.pdf
  - 型面曲率的三点差分式 `R = -dy² / (z[i-1] - 2 z[i] + z[i+1])`（FRA/ROSA 文档）
    — https://rosap.ntl.bts.gov/view/dot/85182/dot_85182_DS1.pdf
- **它给了什么**：① 接触点定位的通行做法就是"**竖直距离最小**"，与我们 `find_patch_contact` 同源，
  所以方法层面我们没有走偏；② 型面的**斜率/曲率按相邻三点差分**取，意味着斜率在采样点之间**本来就是分段常数**——
  这正好解释了第 200 轮的阶梯；③ 两点接触（踏面 + 轮缘）有专门的算法文献，并且是**几何判定**，不是放宽容差；
  ④ 在轮缘/轨距角这种**共形**区，Hertz 不成立，需要条带/非 Hertz 接触。
- **它改变了什么**：把"倾角不响应"从"模型怪病"改判成**已知离散化 + 共形接触缺失的组合问题**，
  并且给出两条正路：把接触几何做成**对 (y, roll) 的 C¹ 插值表**（并输出 `dn/dy`），以及在共形区改**条带/非 Hertz**。
- **没有改变什么**：这些都是"怎么算"，**不提供**任何数值判据；验收仍是 `W·tan τ` 与 21 842.4 N 的对照。

## L13 切向力（蠕滑律）模型的比较与选用（横向力的另一半）

- **问题**：横向力 = 法向分量（几何）+ 切向蠕滑分量。第 200 轮量到我们的蠕滑只值 248 N/接触（`slip_lat≈11 mm/s`、
  `f22 = 5e5 N`），2 mrad 冲角约 1 kN/接触。文献怎么选切向模型、怎么归一化？
- **来源**：*Comparison of the Kalker table method from CONTACT, Kalker's FASTSIM and its modified version,
  and the Polach approximate function*（Wiley 2019，题录可检索）
  — https://onlinelibrary.wiley.com/doi/pdf/10.1155/2019/5279380 ；
  FRA 1989《A Comparison of Model and Field Test Dynamic Performance》里关于 Kalker 表
  "`τ_Y` 经 `F_N` 的 1/3 次幂归一"的说明
  — https://railroads.fra.dot.gov/sites/fra.dot.gov/files/fra_net/16275/1989_A%20COMPARISON%20OF%20MODEL%20AND%20FIELD%20TEST%20DYNAMIC%20PERFO.PDF
- **它给了什么**：切向模型（CONTACT 表 / FASTSIM / Polach）都**按 `μN` 归一**，因此**横向力的上限是 `μN`**，
  与法向几何无关；而我们的实现里 `f22` 是**固定刚度**（`linear_lateral = -f22·slip/v`），
  在正常蠕滑量级下只给出几百牛顿，离 `μN ≈ 23.9 kN` 差两个量级。
- **它改变了什么**：把"要不要换切向模型"变成可判定的问题——在 `slip_lat` 的实测分布上比较
  `f22·slip/v` 与 Polach/FASTSIM 的饱和曲线；若两者在 11 mm/s 与 44 mm/s 处相差 10 倍以上，
  则**必须**换模型（这是物理，不是调参）。**仍不得**靠提高 `f22` 把曲线变绿（已实测更早失败）。
- **没有改变什么**：不提供数值算据；且注意 FASTSIM/Polach 仍是**近似**，接触斑形状要用 L12 的几何。

## L14 道岔里"多根钢轨各自是独立体"该怎么组合（组合断面 → 分体 + 接触转移）

- **问题**：图纸里的 `JG_* / XG_* / YG_*` 是"基本轨+尖轨""翼轨+心轨"的**组合断面**（一条连续上表面，
  中间 V 形轮缘槽）。而在动力学模型里，基本轨与尖轨是**两根各自受扣件支承的轨**，轮载要在两者之间转移。
  该按"一个变截面体"还是"两个独立体 + 接触转移"来做？
- **来源**：
  - *Effect of the vertical relative motion of stock/switch rails on wheel–rail contact mechanics in switch panel
    of railway turnout*（Advances in Mechanical Engineering, 2018；以 **CN60-1100-1:18** 高速道岔为对象）
    — https://doi.org/10.1177/1687814018790659
  - *Further evidence that the counteracting lateral contact forces during the switch and crossing transitions
    are a kinematic phenomenon*（Chalmers 报告全文）
    — https://publications.lib.chalmers.se/records/fulltext/193610/193610.pdf
  - *Implementation of variable cross-section curved beam in train-turnout dynamic interactions*
    （Int. J. Mech. Sci., 2024）
    — https://www.sciencedirect.com/science/article/pii/S0020740324007033
  - 道岔钢轨组合三维实体建模（尖轨-基本轨、心轨-翼轨组合）专利 CN111339648B
    — https://patentimages.storage.googleapis.com/0e/47/2c/e3f81786fd82be/CN111339648B.pdf
  - 道岔断面随长度变化、左右轨不同的建模讨论（力学学报 2005）
    — https://pubs.cstam.org.cn/data/article/lxxb/preview/pdf/2005-369.pdf
- **它给了什么**：① 基本轨与尖轨之间有**竖向相对运动**，而且这个相对运动**改变接触力学**
  ⇒ 两者必须能各自竖移（各自一条竖向自由度 + 各自扣件刚度），不能并成一个刚体；
  ② 道岔转换区的**反向横向接触力是运动学现象**（接触点从一根轨换到另一根轨时几何上的必然），
  不是外加法向力 —— 这一条直接解释了我们 B045/B047 里看到的"左右反向"；
  ③ 另一条路是**变截面曲梁**（A、I 沿里程变），这正是 Abaqus 那份直向道岔模型的做法
  （每站 A=4.988e-3、I11=1.23e-5 等），但它不解决"两根轨各自支承"的接触转移。
- **它改变了什么**：把"组合断面怎么进模型"固定为 —— **按 V 形槽把组合断面劈成两条各自独立的轨体**
  （各带自己的 `y_window_m` 与里程窗口），轮载按"谁最深谁承载"转移；
  降低值就是两个 crown 的高差（图纸读出 14.000 mm → 0），**不需要**再写一条 z 偏移表。
- **没有改变什么**：不给任何数值判据；也不允许用"把两根轨并成一根"来消掉接触转移的困难。
