# 元件目录与 Simpack 对照

**日期**：2026-10-23 · **版本**：0.4.30

这张表回答一个问题：**Simpack 的力元，我们搬到哪一步了。** 每一行都指得出一处代码和一条测试；
"没有"的行也写明为什么没有，而不是留白。

## 1. 已经能用的元件

| 我们的 `kind` | 参数（单位） | Simpack 对应物 | 力律 |
|---|---|---|---|
| `spring` | `stiffness`（N/m）、`preload_force`（N） | Spring（type 6 的刚度半） | 线性 |
| `damper` | `damping`（N·s/m） | Damper（type 6 的阻尼半） | 线性 |
| `spring_damper` | `stiffness`、`damping`、`preload_force` | Spring-Damper（type 6） | 线性并联 |
| `bushing` | `stiffness`、`damping`、`cross_stiffness` | Bushing（type 5，三向刚度 + 交叉项） | 特征分解成三个主方向 |
| `bump_stop` | `stiffness`、`gap_m`、`transition_m`、`preload_force` | Bump Stop | 自由行程 + 止挡（`transition_m` 给 C1 过渡） |
| `damper_blowoff` | `low_speed_damping`、`high_speed_damping`、`blowoff_speed` | 带卸荷阀的减振器 | 两段阻尼 |
| `force_table` | `points`（m→N）、`rate_points`（m/s→N）、`preload_force` | 空气簧载荷-高度曲线、台架测的减振器曲线、查表力元 | 分段线性，斜率=割线 |
| `axial` / `torsional` | `stiffness`、`damping`、`preload_force` | 直连（无独立 Simpack 类型） | 线性，节点表早期写法，保留兼容 |

七个"具名"元件 + 两个旧别名，参数表在 `src/velch/elements.py` 的 `PARAMETERS`，
装配在 `topology.axial_spec` / `torsional_spec`，力律与雅可比在 `Connector.law`。
测试：`tests/test_elements.py`、`tests/test_elements_nonlinear.py`、`tests/test_elements_tables.py`。

## 2. 从真模型里读到的元件（CRH380A 转向架）

`CRH380A_M_Bogie.spck` 里 39 个力元，按"参数槽位签名"判读（文件本身只写一句 `! Type`）：

| 槽位 | 个数 | 我们搬成什么 |
|---|---|---|
| type `5`（名义力 + 三向刚度/阻尼/间隙） | 12 | `bushing`（`$F_PS_JOINT_*` 轴箱转臂节点） |
| type `6`（名义长度 + 刚度 + 阻尼） | 16 | `spring_damper` / `damper` / `spring` |
| type `{ 6 }`（只有刚度） | 4 | `spring`（二系垂向减振器在 Simpack 里只有刚度，没有阻尼） |
| type `13`（绕 α/β/γ） | 1 | 抗侧滚扭杆 → 目前用 `torsional` 两根等价近似 |

这些数字与逐条参数都在 `docs/SIMPACK_BOGIE_MINING_2026-10-23.md`。

## 3. 明确没有搬的东西（都不是"以后再说"，是"现在做不到"）

| 缺什么 | 为什么 | 代价 / 出路 |
|---|---|---|
| **带内部状态的元件**（减振器阀片滞回、干摩擦黏滑） | 我们的元件是"力 = f(当前位移, 当前速度)"的代数函数；滞回需要元件自带状态量，并让积分器把状态一起积分 | 需要扩展状态向量与雅可比；在那之前只能用 `force_table` 的力-速度曲线近似（无滞回环） |
| **事件检测**（过间隙、阀门开关、脱空再接触） | 现在靠积分器自己缩步，`bump_stop.transition_m` 只是让人能显式抹平拐角 | 慢但诚实；真正的解是事件函数 + 重起步，那是求解器层的工作 |
| **空气簧的气室物理**（容积、温度、附加气室） | 我们只有"载荷-高度曲线"这个黑箱 | `force_table` 能复现曲线，但换工况（不同载荷、不同激励频率下的动刚度）不保证 |
| **约束类元件**（万向节、齿轮副、皮带） | 我们靠广义坐标把约束消掉了；要支持任意链式机构得改成约束方程 + 拉格朗日乘子 | 架构级改动，不是元件级 |
| **User Routine（USUB）** | Simpack 允许塞任意用户代码，既闭源也不可复现 | 不可能搬；如果用户的模型依赖它，只能重写成等效元件 |
| **求解器内部**（DAE 形式、线性代数、变量步长策略） | 那不是元件库 | 不搬，也不再声称"逐比特一致" |

## 4. 验收口径（为什么不比"结果逐比特"）

每个元件算"搬对"的判据是**特性曲线等价**：单自由度台架、同参数、同激励，出力-位移 / 力-速度 /
滞回环与 Simpack 画在一张图上。测试已经这么写（止挡的分段、卸荷阀的两段、查表的割线斜率、
势能导数 = 力、端到端雅可比与中心差分 < 2e-4）。

整车的判据是**不变量不移动**：`scripts/physics_invariants.py` 与 `scripts/verify_vehicle_ref.py`，
后者要求派生/引用算例的 `history.csv` 与冻结基线**逐位相同**。
