# Velch 0.4.28 发布说明

**发布日期**：2026-10-23

## 这一版多了什么

**非线性力元通道**，以及第一批两种非线性元件：

| 元件 | 参数（单位） | 力律 |
|---|---|---|
| `bump_stop` | `stiffness`（N/m）、`gap_m`（m）、`preload_force`（N） | 自由行程后顶住 |
| `damper_blowoff` | `low_speed_damping`、`high_speed_damping`（N·s/m）、`blowoff_speed`（m/s） | 速度超阈值后阀门打开 |

求解器的 `Connector` 现在可以携带 `law`：力、局部斜率（进雅可比）、势能三者都来自同一个力律，
并且由测试互相钉住（势能导数 = 力、dF/dδ̇ = 阻尼）。

## 怎么验

```powershell
python -X utf8 -m pytest tests/test_elements_nonlinear.py
python -X utf8 scripts/verify_vehicle_ref.py
```

`pytest` 全仓 676 passed / 1 skipped；`verify_vehicle_ref.py` 仍 `VERDICT: EQUIVALENT`（冻结基线
逐位不变）。安装包冒烟 8 步全过。

## 仍然没有的

* 间隙/阀门切换处**没有事件检测**——斜率跳变会让积分器自己缩步，慢但诚实；
* 元件**没有内部状态**，所以减振器的滞回环、摩擦的黏滞都不在（下一层工作）；
* 空气簧、查表力、力表达式；
* 与 Simpack 元件的逐条对照报告。
