# 第五道门：轮子里没有道岔库（2026-10-31，第 288 轮）

> 上一轮的交付自检有四道门，全过。但那是**在仓库里**跑出来的——它证明"仓库自包含"，
> 不证明"安装出去的东西自包含"。这一轮补上第五道门，结论是**不过**：
> 轮子 463 065 B、104 个条目，`vehicles/` 一个都没有。

## 一、怎么量的（三步，都可复算）

```bash
# 1. 建轮子（on-host，不走网络）
python -m pip wheel --no-deps --no-build-isolation -w ../scratch/wheel_m9 .
#   -> velch_turnout_dynamics-0.4.37-py3-none-any.whl   463 065 B

# 2. 装到仓库之外
python -m pip install --no-index --no-deps --target ../scratch/site_m9 \
    ../scratch/wheel_m9/velch_turnout_dynamics-0.4.37-py3-none-any.whl

# 3. 从别的目录解析一个 lib: 引用
python -c "from velch.assets import resolve_asset as r; r('lib:turnouts/CN60-1100-1_18/sections/jbg-20200418-R.txt')"
```

第 1 步的读数是关键：**`entries 104`，顶层只有 `velch/` 与 `velch_turnout_dynamics-…dist-info`**，
`vehicles/` 与 `velch/_internal/` 都不存在。轮子 463 KB，而道岔库本身 **8.6 MB**——即 **0.05 %** 的资产被装进去了。

第 3 步的报错（逐字）：

```
AssetRefError: cannot resolve asset 'lib:turnouts/CN60-1100-1_18/sections/jbg-20200418-R.txt':
  not found under any known root
  looked in F:\ai道岔状态反演辨识\scratch\vehicles
```

`looked in` 那一行还暴露了第二件事：装到仓库外之后，`vehicle_dir()` 指向的是**安装根的父目录**
（`…\scratch\vehicles`），而不是包里某个位置——它按包文件往上找仓库根，找不到就返回一个不存在的路径，
而且**不报错**。所以 `lib:` 失败时的提示会把用户指向一个与他无关的目录。

## 二、第五道门的判据（写进脚本，跑之前定）

| 门 | 内容 | 判据 | 今日实测 |
|---|---|---|---|
| **D-WHEEL** | 安装出去的轮子必须自带道岔库 | 轮内 `vehicles/`（或 `_internal/vehicles/`）下的文件 ≥ **295** | **0 ⇒ FAIL** |

设计决定：这道门**只看已有轮子、不自己构建**。构建需要可用的临时目录与离线 setuptools，那是**机器状态**、
不是**包状态**；把它塞进闸门只会让"构建失败"和"资产缺失"混成一条红。轮子放在 `../scratch/wheel_m9/`，
脚本 `--wheel PATH` 也可以显式指定。

## 三、五道门的现状

```
[D-ASSETS]  references 1368  unique files 295  missing/outside 0  absolute 0  -> PASS
[D-PATHS]   absolute references 0                                           -> PASS
[D-SMOKE]   0.020 s  41 frames  seat residual 2.748e-08 N  gates 7/7        -> PASS
[D-SUMMARY] coverage match  band surface match                              -> PASS
[D-WHEEL]   velch_turnout_dynamics-0.4.37-py3-none-any.whl 463065 B
            entries 104  library 0  sections 0                              -> FAIL
VERDICT: the package is not self-contained (see the failing line above)
```

⇒ **仓库自包含（4 条），安装产物不自包含（1 条）**。这一轮的判决句从"齐了"改成"不齐"，是这一轮的实质产出。

## 四、能说 / 不能说

**能说**：从本仓库**安装成轮子**会得到一个能 import、但没有道岔库的包；库里的 295 个断面、3 张里程表、
2 个算例都没有进轮子；`lib:` 引用在安装环境下**必然失配**，且报错会把用户指向安装根的父目录。

**不能说**：① 这不等于"打包不可能"——正解是让库随包走（把 `vehicles/` 作为包数据放进 `velch/_internal/`，
并让 `_root()` 在非源码布局下优先找它），本轮没做，因为那会复制 8.6 MB 进 `src/`，属于**改变仓库布局**，
需要你点头；② 未测 PyInstaller 打包产物（那条路已有 `_internal` 支持），本轮只测 wheel。

## 五、下一步（需要你选）

| 方案 | 做法 | 代价 |
|---|---|---|
| **P1（正解）** | 把 `vehicles/` 作为包数据装进 `src/velch/_internal/vehicles/`，`_root()` 加一条"包内优先"分支；`D-WHEEL` 转 PASS | 仓库多 8.6 MB（或加一个构建期复制步骤），`_root()` 改动需回归 |
| **P2（限定交付）** | 明确"交付形态 = 源码树 + `pip install -e .`"，`D-WHEEL` 标为 `NOT_APPLICABLE` 并写进 README | 无需改布局，但"pip install 就能用"这句话就不能说 |
| P3 | 只在 CI/打包脚本里复制资产，仓库不存副本 | 多一条构建路径要维护，本地装轮子仍缺库 |

我倾向 **P1**：它把"能安装"从口头变成门，且 `_rooot()` 已经为 PyInstaller 写过 `_internal` 分支，同一条路。
