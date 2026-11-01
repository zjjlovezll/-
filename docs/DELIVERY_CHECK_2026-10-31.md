# 交付自检：这包东西能不能离开这台机器（2026-10-31，第 287 轮）

> M9 的第一件不是打包脚本，而是**让包自己回答"我齐不齐"**。
> `scripts/s144_delivery_check.py` 读三个交付算例、解析每一处断面引用、对文件取 sha256、
> 座椅规范算例、积分文档里那个 0.02 s、再把交付总表重算一遍——四条门全过才打 `PASS`。

## 一、四条门（跑之前写死）

| 门 | 内容 | 判据 |
|---|---|---|
| **D-ASSETS** | 三个交付算例引用的每个断面都在**仓库内**、且有 sha256 | 缺失/越界 0 个 |
| **D-PATHS** | 交付算例里没有绝对路径（`G:\…` / `F:\velch_data` / `C:\…` / `/home/` / `/mnt/`） | 绝对引用 0 个 |
| **D-SMOKE** | 规范一组模型算例座椅后积分 0.02 s | 座椅残差 ≤1e-5 N 且**已产生的每条门都通过**：第 314 轮起规范算例是 **8 条**（七条数值门 + 无条件计算的 `launch_balance`；`stationarity` 只在算例声明读数窗口时产生，本算例不声明） |
| **D-SUMMARY** | `deliverable_summary.json` 仍等于从存档报告重算的结果 | 覆盖率与带面逐键相等 |

## 二、实测

```
cases           3
[D-ASSETS]  references 1368  unique files 295  missing/outside 0  absolute 0  -> PASS
[D-PATHS]   absolute references 0  -> PASS
[D-SMOKE]   0.020 s  frames 41  seat residual 2.748e-08 N  gates 7/7  -> PASS
[D-SUMMARY] coverage match  band surface match  -> PASS
VERDICT: the package carries everything it needs and reproduces its own headline
```

`1368` 条引用收在 **295** 个文件上（同一份断面被上百个站位重复引用，所以引用数远大于文件数）；
`41` 帧是 `0.02 s ÷ 5e-4 s` 的输出步长，与第 241 轮记录一致。

## 三、为什么这四条值得单独做

1. **绝对路径是这一路最容易复发的一类错**：第 260 轮的 `s123` 报告路径一度写到 `ROOT.parent`，
   `git add` 直接报 `outside repository`；第 272 轮的变体算例靠**绝对路径**才被 `resolve_asset` 接受。
   两件事都说明"路径能不能搬"必须由代码判，不能由人记。
2. **算例丢 cited 文件是静默的**：`straight_one_set.json` 右轨三个体各引用 160/76/65 个站位文件，
   少一个只会在某个里程上静默变成"没有接触"。
3. **冒烟必须跑，不能只看文件在不在**：七门里 `vertical_preload_residual` 与
   `no_edge_limited_active_contact` 都会在几何错位时变红，而文件齐全时几何完全可能错位。

## 四、能说 / 不能说

**能说**：在这台机器上，三个交付算例的**全部断面引用都在仓库内**、无绝对路径、字节可核（295 个 sha256），
规范一组模型算例座椅残差 `2.7e-08 N`、0.02 s 积分 41 帧、**8 条已产生的门全过**（第 314 轮起；
`stationarity` 需要算例声明读数窗口，规范算例不声明，因此不计入），且交付总表与存档逐键一致。

**不能说**：① 这不是**全新机器安装测试**——本机已装 numpy/scipy 与这个 checkout，`pip install .` 后
的干净环境未验；② `F:\velch_data\validation\crh380a_m` 里那 368 个**旧算例**仍在本机之外（`velch selfcheck`
会报 `算例语料` 一项），本轮只保证**道岔库与一组模型算例**自包含；③ 三条带面的 `Ω_obs` 仍是 55.4 %，
覆盖率边界没有因为这一轮而改变。

## 五、复算

```bash
cd Velch
python -X utf8 scripts/s144_delivery_check.py --write     # 四条门 + 写 manifest
python -X utf8 -m pytest tests/test_delivery_check.py -q  # 4 项，约 19 s
```

产物：`reports/surface_deliverable_2026-10-31/delivery_manifest.json`（1368 条引用的路径与 sha256、四条门、
冒烟读数、判决）。
