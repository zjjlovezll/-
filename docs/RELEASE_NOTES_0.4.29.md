# Velch 0.4.29 发布说明

**发布日期**：2026-10-23

## 这一版多了什么

| 元件 / 参数 | 作用 |
|---|---|
| `bump_stop` 新增 `transition_m` | 止挡的 C1 过渡段：力与斜率在接合处连续，代价是线性段抬高 `k·T/2`（默认 0，即保留 C0 折角） |
| 新元件 `force_table` | 逐点录入的力-位移曲线（可选力-速度曲线），段内线性插值与割线斜率 |

`force_table` 的实际用途：空气簧的载荷-高度曲线、台架测出的减振器力-速度曲线、磨损后的刚度退化——
都能直接当数据录进来，不必先拟合公式。

## 怎么验

```powershell
python -X utf8 -m pytest tests/test_elements_tables.py
python -X utf8 -m pytest tests
python -X utf8 scripts/verify_vehicle_ref.py
```

`pytest` 全仓 687 passed / 1 skipped；`verify_vehicle_ref.py` 仍 `VERDICT: EQUIVALENT`；安装包冒烟 8 步全过。

## 仍然没有的

* 间隙/阀门切换处**没有事件检测**（靠积分器自己缩步；`transition_m` 只是让人可以显式抹平）；
* 元件**没有内部状态**，滞回（减振器阀片、干摩擦黏滑）还没有；
* 空气簧的**气室容积/温度**物理没有，只有曲线；
* 与 Simpack 元件的逐条对照报告。
