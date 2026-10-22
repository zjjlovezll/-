# 第一次运行先跑自检（`velch selfcheck`）

发布出去之后，"打不开"通常是五件事之一：没有语料、没有 matplotlib、没有 Tk、Simpack 路径随
工程目录一起搬走了、或者程序没有可写目录。这条命令把这五件事各自问一遍，**并且每条失败都告诉
你怎么补**。

```
python -X utf8 -m velch selfcheck          # 源码树
velch-cli.exe selfcheck                     # 安装包（控制台版；窗口版没有 stdout）
```

实测输出（本机，2026-10-23）：

```
Velch 自检（这台机器上这份程序能不能干活）

[PASS] 版本与发布说明         0.4.13，发布说明在位
[PASS] 算例语料            358 个算例，位于 F:\velch_data\validation\crh380a_m
[PASS] Tk 界面库          tkinter 可用
[PASS] 绘图库 matplotlib  可用
[WARN] Simpack 模型      未设置 VELCH_SIMPACK_MODEL / VELCH_SIMPACK_ROOT
        Simpack 模型      → 要读 Simpack 模型时再设置；只跑 Velch 自带算例可以不管这一项
[PASS] 可写目录            F:\ai道岔状态反演辨识\Velch\.agent 可写

结论：可以启动，1 项可选未满足（上面标了怎么补）。
```

## 三种结论与退出码

| 结论 | 退出码 | 含义 |
|---|---|---|
| 全部通过 | 0 | 六项都满足 |
| 可以启动，N 项可选未满足 | 0 | 缺的东西只影响部分功能（例如没装 matplotlib 时 ④⑥⑦ 屏降级为文字提示） |
| N 项必须修 | 2 | 缺的东西会让核心功能不可用（没有 Tk、语料路径被显式指错、可写目录不可写） |

## 为什么"显式指错的语料"算失败，而"根本没配"只算可选

`VELCH_DATA_ROOT` 一旦设了，用户就是在说"语料在这里"。若那个目录里没有 `case_*.json`，是配错
了；而完全没设时程序会依次查标记文件与安装目录，找不到只说明这是全新安装——那是正常状态，
打印查找顺序即可（`data_root.hint()` 已经这么做了）。这条区分有测试钉住：
`tests/test_selfcheck.py::test_missing_corpus_is_a_failure_that_carries_the_hint`。

## 它刻意不做的事

- **不读 1.4 GB 语料的内容**，只数 `case_*.json`——自检要在语料挂错时给出答案，不能自己也卡住。
- **不 import 求解器**（`vehicle_solver`/`contact`/`jacobian`），所以在一个装坏的包上也能回答。
- **不猜**：Simpack 那一项只检查路径是否存在，不打开 `.spck`（那是 `inspect-simpack-track` 的事）。

## 只读安装（`C:\Program Files\Velch`）下的预期输出

```
[FAIL] 可写目录  读不到也建不了程序状态目录：PermissionError …\.agent
       可写目录  → 把 VELCH_AGENT_HOME 指到可写目录（例如 %LOCALAPPDATA%\Velch\agent）
结论：1 项必须修，0 项可选。
```

界面与命令行仿真**仍然可用**（实测：只读副本里 `run-vehicle --fast` 正常产出 manifest）。只有 agent 级功能（派生算例、作业目录、revision 账本）需要 `VELCH_AGENT_HOME`。
