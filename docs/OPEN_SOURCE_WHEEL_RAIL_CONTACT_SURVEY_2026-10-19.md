# 开源轮轨接触算法调查（2026-10-19）

## Velch 当前问题

`src/velch/contact.py` 将轮下表面和轨上表面压成单值横断面，在公共横向网格上取最大近似侵入；每条候选钢轨仅保留一个接触点。法向力是输入有效半径的 Hertz 3/2 次幂加阻尼，切向力是两分量线性蠕滑需求的三次饱和。这可以做软件基线，但不能充分表示轮缘侧面、道岔接触轨切换、同一钢轨多斑接触、曲率相关接触斑、旋转蠕滑与非 Hertz 应力。

## 可参考源码

| 项目与源码 | 语言/许可 | 有价值的部分 | 使用边界与 Velch 角色 |
|---|---|---|---|
| [OpenVSD](https://github.com/wangjianbin123/OpenVSD)，[AEContGeo.cpp](https://github.com/wangjianbin123/OpenVSD/blob/main/AEContGeo.cpp) | C++ / GPL-3.0 | 几何约束接触点搜索、样条轮廓与车辆动力学组织；仓库引用 Wang 等 2023 接触点迭代论文 | 先研究其接触几何策略和失败处理。GPL-3.0 代码不能在未完成许可评估时直接复制进 Velch。仓库简述不足以证明它覆盖道岔多轨接触，需用实际轮廓验证。 |
| [CONTACT](https://github.com/eve70a/CONTACT)，[Python 接口目录](https://github.com/eve70a/CONTACT/tree/master/python_intfc) | Fortran + 接口 / Apache-2.0 | 轮轨接触位置、接触斑、非 Hertz 法向压力、切向应力、黏滑区；适合作为离线参考解和数值对照 | 当前 README 指出编译依赖 Intel Fortran/MKL；集成工作量较大。集中接触、小接触斑等适用前提需要核对尖轨/轮缘工况。优先用于基准，而非每个 Velch 积分步立即调用。 |
| [C_Normal_Tangential_Railway_Contact](https://github.com/criogenox/C_Normal_Tangential_Railway_Contact) | C++ / MIT | `normal_eq_elastic` 非 Hertz 法向近似、`tang_fastsim` FASTSIM 蠕滑力、`tang_spin_tabcon` 旋转蠕滑表格接口；仓库提供部分论文/CONTACT 对比 | 模块边界与 Velch 当前法向/切向接口接近。仓库规模较小，作者提供的精度声明还需独立重算，尤其是道岔截面、多接触斑与表格数据来源。 |
| [A_WRCC Wheel-Rail Contact Characterization](https://github.com/criogenox/A_WRCC-Wheel-Rail-Contact-Characterization) | Java / MIT | 刚性轮轨轮廓接触候选、接触角、滚动半径差与等效锥度 | 可借鉴独立接触几何表和轮径差输出；项目假设直线平行钢轨及单一截面，不能直接代替道岔随里程多轨搜索。 |
| [railfe2](https://github.com/Petr-Voltr/railfe2) | Python / MIT | 车辆—连续 Timoshenko 梁钢轨—轨枕/支承耦合，压缩型 Hertz 弹簧、静态/频域/时域求解 | 适合 Velch 后续轨道动力学层；其平面 x-z 模型不解决复杂横向轮缘/多轨接触几何。 |
| [Slippy](https://github.com/FrictionTribologyEnigma/slippy) | Python / MIT | 通用边界元法向接触、表面形貌和摩擦学计算；谢菲尔德大学用它研究轮轨界面 | 适合离线接触斑/压力/磨耗敏感性研究；通用表面求解器，需要自行解决道岔接触点定位和多体运动耦合。 |

这些是截至调查日期在项目主页/仓库中可核实的功能和许可信息。开源项目的 README 自述不等同于针对本模型的精度验证。

## 建议的借鉴顺序

1. **接触几何先行**：保留原始 PRR 点序和多值几何，按轮廓连续段与轨道实体分区搜索多个候选。为每个接触候选输出轮点、轨点、法线、间隙、接触角、所在钢轨/截面 ID；使用 OpenVSD 的几何约束和样条组织方式作参考。允许轮缘、踏面、基本轨与尖轨同时产生候选，不再用单个全局最大侵入量遮蔽其他斑。
2. **法向接触替换**：先比较现有 Hertz 简化式、等效弹性模型和 CONTACT 法向结果，形成对同一轮轨几何、载荷和材料的比较表。若多斑之间有明显弹性耦合，再考虑 CONTACT 类变分求解或其他显式多斑方案。
3. **切向力升级**：在明确接触斑尺寸、法向压力和三种蠕滑（纵向、横向、旋转）后评估 FASTSIM。现有三次饱和力可作为低成本基线；不要仅替换一个函数名就宣称实现 FASTSIM。
4. **轨道与反演接口**：借鉴 railfe2 的连续钢轨/支承组装，但保持接触几何和接触斑求解独立，以便刚性轨道、柔性轨道和状态反演共用。同一计算应记录每个接触斑载荷、位置、法向、蠕滑与活动轨 ID。

## 最小复核工况

- 标准轮/轨截面、不同轮对横移与侧滚：核对踏面—轮缘接触点连续性、候选数量和接触角。
- 同一基本轨、尖轨及两轨同时承载：核对轮载转移而不是只比较总轮轨力。
- 用户 H 盘 PRR 序列：对 52.894、53.892、55.290、66.621、69.224 m 的同里程异截面分别按前/后分支计算；先确定 Simpack 模型实际分支规则和坐标变换。
- 统一材料、载荷和蠕滑输入：比较 Velch、所选开源实现与可用的 CONTACT/Simpack 输出，记录单位、版本/提交号、轮廓哈希和误差定义。

## 采用结论

近期最适合进入 Velch 的研究路线是：**参考 OpenVSD 的几何搜索思想，自行实现道岔多候选接触几何；参考 MIT 许可的 C++ 法向/FASTSIM 模块升级接触力；以 CONTACT 作为高精度对照；用 railfe2 支持后续连续钢轨与支承层级。** 在真实模型坐标、同里程分支和接触斑基准未核实前，不把任何第三方结果直接标记为道岔物理验证。
