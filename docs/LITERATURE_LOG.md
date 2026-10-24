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
