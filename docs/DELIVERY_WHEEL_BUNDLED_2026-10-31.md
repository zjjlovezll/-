# 让库随包走：轮子从 463 KB 变成 3.64 MB（2026-10-31，第 289 轮）

> 上一轮的第五道门判了 **FAIL**：轮子 104 个条目、`vehicles/` 一个都没有。
> 这一轮不搬 8.6 MB 进 `src/`，而是**在构建时**把库复制进 wheel，并让解析器优先看包内——
> 于是同一道门转 **PASS**，而且已经在"装到仓库外"的副本上跑通了交付算例。

## 一、做法（三处改动，都不动冻结物理）

| 位置 | 改动 |
|---|---|
| `setup.py`（新） | `class build_py(_build_py)`：`super().run()` 之后把 `<repo>/vehicles` 复制到 `build_lib/velch/_internal/vehicles`；库不在就 `SystemExit`（宁可构建失败，也不产出缺库的轮子） |
| `src/velch/vehicle_db.py` `_root()` | 先看 `<package>/_internal/vehicles`，**存在就用**；源码树里这个目录不存在，所以原来的"往上找仓库 `vehicles/`"逐位不变 |
| `.gitignore` | 忽略 `src/velch/_internal/`（若有构建期残留，不进 git） |

为什么不是"把库搬进 `src/`"：那会让仓库多 8.6 MB 的**副本**，且两处会漂移（断面改了要记得改两份）。
构建期复制只产出一个**产物**，与 `build/` 同性质。

## 二、轮子读数（前后对照）

| 量 | 第 288 轮（无 hook） | **第 289 轮** |
|---|---|---|
| 大小 | 463 065 B | **3 644 764 B** |
| 条目 | 104 | **413** |
| `_internal/vehicles` 下文件 | 0 | **309** |
| 其中 `sections/*` | 0 | **295** |
| `D-WHEEL` | **FAIL** | **PASS** |

## 三、装到仓库外再跑（这才是"能不能离开这台机器"）

```
site_m9/velch                            ← 安装位置
vehicle_dir: …\scratch\site_m9\velch\_internal\vehicles   exists: True
resolve_asset('lib:turnouts/CN60-1100-1_18/sections/jbg-20200418-R.txt')  -> 文件存在, portable: True
```

再用**安装副本**（不是仓库）把交付算例跑一遍：

```
case from install: turnouts/straight_one_set.json
seat residual: 2.748e-08 N
frames: 41   gates: 7 / 7   dimension: 234
```

`2.748e-08 N / 41 帧 / 7 门 / 234 维` 与仓库里那趟**逐项相同** ⇒ 安装产物给的是同一件事，不是"能 import"而已。

## 四、五门现状

```
[D-ASSETS]  1368 refs / 295 files / 0 missing / 0 absolute   -> PASS
[D-PATHS]   0 absolute                                       -> PASS
[D-SMOKE]   0.020 s  41 frames  residual 2.748e-08 N  7/7    -> PASS
[D-SUMMARY] coverage match  band surface match               -> PASS
[D-WHEEL]   3644764 B  entries 413  library 309  sections 295 -> PASS
VERDICT: the package carries everything it needs and reproduces its own headline
```

## 五、能说 / 不能说

**能说**：本仓库构建出的 wheel **自带** 295 个断面、3 张里程表、2 个道岔算例与车轮型面；装到仓库外后
`lib:` 解析落在**包内**（`velch/_internal/vehicles`），交付算例在安装副本上座椅残差 `2.7e-08 N`、0.02 s
41 帧、七门 7/7、234 维，与仓库读数逐项一致。

**不能说**：① 这不是"干净 venv 安装"的完整证据——本机 `venv` 无 setuptools、系统 temp 坏死，
安装用 `pip install --target` + 宿主 numpy 完成；② 轮子只装了**道岔库与算例**，外部语料
（`F:/velch_data` 里 368 个旧算例）仍不在包内；③ 断面几何没有任何变化，冻结基线照旧 UNCHANGED。

## 六、复算

```bash
cd Velch
TEMP=../scratch/tmp_m9 python -m pip wheel --no-deps --no-build-isolation -w ../scratch/wheel_m9 .
python -X utf8 scripts/s144_delivery_check.py --write
python -X utf8 -m pytest tests/test_delivery_check.py -q      # 6 项
```
