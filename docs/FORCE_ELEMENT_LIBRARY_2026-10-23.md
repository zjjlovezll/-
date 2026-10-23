# 力学元件库

**日期**：2026-10-23 · **版本**：0.4.27

## 1. 这张图景

Simpack 真正强的地方不是求解器，而是**元件库**：弹簧、减振器、衬套、止挡、空气簧、扭杆、
摩擦、力表达式……每种是一个有参数界面、有单位、能报告力的"类型"，模型里只写"哪一类 + 几个
参数 + 连在谁身上"。我们在 0.4.26 之前只有一种写法：在代码里手写 `Connector`，或者在
`topology.elements` 里写 `axial`/`torsional` 两种原语。

`velch/elements.py` 是朝那个方向走的第一步：**元件类型表 + 参数表 + 参数校验 + 一个消费者**
（`topology` 在装配时调用它，求解器一行没改）。

## 2. 现在有什么

| 元件 | Simpack 对应物 | 参数（单位） |
|---|---|---|
| `spring` | Spring | `stiffness`（N/m，必填）、`preload_force`（N） |
| `damper` | Damper | `damping`（N·s/m，必填），**可以不写刚度** |
| `spring_damper` | Spring-Damper（并联） | `stiffness`、`damping`、`preload_force` |
| `bushing` | Bushing | `stiffness`、`damping`、`cross_stiffness`（如 `{"y-z": 1000}`） |
| `axial` / `torsional` | （旧原语，保留） | 与 0.4.26 相同 |

`bushing` 允许非对角刚度，做法是**对 3×3 刚度矩阵做特征分解**，把每个主方向变成一个普通的
轴向弹簧-阻尼。好处是求解器的行结构不变，代价是交叉项的"方向"被写成了主方向——所以报错时
会列出特征值，让"矩阵不正定"这种错误在装配阶段就暴露。某一主方向在两个刚体上都没有坐标时，
**跳过该方向而不是报错**（3 轴衬套装在没有 x 的刚体上，本来就该只有两个方向出力）。

## 3. 三条规矩

1. **元件只产生连接**（哪些坐标、系数、预载），不碰积分；装配路径与冻结布局共用一条。
2. **参数有单位与边界**，缺参数或越界报出元件名、参数名与单位，例如
   `element 'b' (spring_damper) needs 'damping' [N·s/m]`。
3. **新增一种元件 = 一个 builder + 一组测试**，不需要改求解器。

## 4. 怎么用

```json
{"kind": "spring_damper", "name": "secondary_b1_L_z",
 "stiffness": "$vehicle.secondary.k_z_n_m", "damping": "$vehicle.secondary.c_z_n_s_m",
 "preload_force": 85660.6, "direction": [0, 0, 1],
 "from": {"body": "carbody", "point": [8.75, 1.23, 0]},
 "to":   {"body": "bogie1",  "point": [0.0, 1.23, 0]}}
```

`"$vehicle.…"` 仍由拓扑先解析成数字再交给元件库——**Simpack 给的数只有一处**这条规矩没变。

## 5. 等价性没有回退

改造后 `vehicles/CRH380A_M_node.json` 与冻结布局的 30 个连接器仍然**逐元件系数相同**
（最大差 `0.000e+00`），全仓 `pytest` 669 passed / 1 skipped。元件库是"换了一种写法描述同样的
东西"，不是"改了一种算法"。

## 6. 下一步（按 Simpack 元件表往后搬）

1. `bump_stop`（止挡）：分段刚度 + 间隙，需要给求解器加**非线性**元件通道（当前只有线性行）；
2. `air_spring`（空气簧）：刚度随高度变化 + 阻尼，CRH380A 的二系就是它；
3. `damper_blowoff`（带卸荷阀的减振器）：速度分段；
4. `dry_friction`（库仑摩擦）/ `force_expression`（力表达式）；
5. 每种元件在 `vehicle show` 里报告"模型用了哪些类型、各几个"，与 Simpack 元件表逐条对照。
