# 20 mm 等效半径退役：模型终于在自己写的 oracle 上运行（B048，选项 A）

## 一、缺陷

`case_A_plain.json` 用 `contact.stiffness_policy = "fixed_effective_radius"` +
`effective_radius_m = 0.02`，把 Hertz 的 `N = C·δ^1.5` 评在一个 20 mm 的球上。在接触点按断面
实际拟合得到

```
R_wheel = 1273.65 mm      R_rail = 295.27 mm      1/R* = 1/R_w + 1/R_r  →  R* = 0.5501 m
```

即**声明的半径比几何锐 12–27 倍**。后果不是小数点：同一个 59.68 kN 被压到 **197.62 µm**，
而这个项目从第一天起写的 oracle 是 **65.47 µm**；`dδ/dy` 正比于曲率之和，于是**横向响应
被放大 12 倍**——前四轮"接触点被钉住"追的就是这件事。

## 二、决定（用户选 A）

改默认 + 重新冻结基线。理由：65.47 µm 本来就是文档里写的那个数，197.62 µm 才是例外。

## 三、改了什么

| 位置 | 改动 |
|---|---|
| `src/velch/contact_models.py:73`、`contact.py:83`、`contact_search.py:43/556/778` | `stiffness_policy` 默认 `fixed_effective_radius` → `local_circular` |
| `src/velch/vehicle_solver.py:_settle_modal_coordinates` | `rounds` 12 → 20，docstring 写明让步因子从 ~0.5 变到 **0.755/次**（接触更硬），12 次不再达标 |

算例 JSON 里的 `effective_radius_m = 0.02` **保留不动**：这样改动只有一行、可复核；它现在
只是不生效的声明（测试里显式写回 `fixed_effective_radius` 仍能复现 197.62 µm）。

## 四、实测（`case_A_plain`，80 km/h，座椅残差 4.1e-08 N）

| 量 | 20 mm 声明 | 拟合曲率（现在） |
|---|---|---|
| 法向力 | 59 680.5769 N | **59 680.57685863 N**（不变） |
| 贯入 | 197.62 µm | **65.4661 µm** ← 文档 oracle |
| `R*` | 0.020 m | **0.55010 m** |
| `C` | — | 1.12670e11 N/m^1.5 |
| 轮对 `z` | −4.628e-4 m | **−3.30578e-4 m**（高 132 µm） |

也就是说：**力一位未动，深度回到它一直在文档里的值，车只高 132 µm。**

## 五、测试（5 个文件，全部过）

| 文件 | 改动与理由 |
|---|---|
| `tests/test_oracle_frozen.py` | `ORACLE_VERTICAL_M` → `-3.3057783604e-04`，注释写清"力不变、深度变" |
| `tests/test_two_point_contact.py` | 同一常数 |
| `tests/test_effective_radius.py` | 首条改为断言"出厂算例现在就是 `local_circular`、命中文档 oracle"，并保留一条显式 `fixed_effective_radius` → 197.62 µm（证明旋钮还在、只是不生效） |
| `tests/test_modal_deformation.py` | 台阶 20 µm → 5 µm；力律断言从"常数 C 的比值"改写为 **`F = C(y)·δ^1.5` 按实测 C 与实测深度**，因为 C 现在随接触位置变 |
| `tests/test_modal_assembly.py` | 靠上面 `rounds` 20 复绿（残差 2.05 N / 1722 N = 1.2e-3 → 达标） |

`test_modal_deformation` 改写时量到的分解（5 µm 踏面位移）：**C 降 1.19 %、δ 升 1.21 %、
合力升 0.62 %**，而常数 C 的算术会预测降 1.8 %——这条正是"20 mm 时代假设 C 是常数"的证据。

## 六、基线重新冻结

```
straight_rigid     numerical_gates 7/7   7.9 s   295809cb24c8e24b   (was 06928c9db944796d)
straight_flexible  numerical_gates 7/7   5.2 s   7b1daef7e80664ac   (was ab81290f5924c3a5)
```

基线变更是**预期的**（波形随接触律变），而冻结的**力**没有动。曲线算例本来就声明
`local_circular`，所以 B045 与曲线判定的数字**不受本次改动影响**。

## 七、这次没有解决的

1. **横向注册**：诚实刚度下 1 mm 横移卸载 45 %（`test_effective_radius` 第 3 条），这是下一个
   阻塞；
2. **B045**：曲线路由 `lever_y` 越出轨头；
3. 直向所有历史数字（含降低值反演在 20 mm 下得到的那批）**需在诚实刚度下重测**。

## 八、复算

```bash
PYTHONPATH=src python -X utf8 -m pytest tests/test_effective_radius.py -q
PYTHONPATH=src python -X utf8 scripts/freeze_baseline.py            # 重写基线
PYTHONPATH=src python -X utf8 scripts/freeze_baseline.py --check    # 之后必须 UNCHANGED
```
