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
