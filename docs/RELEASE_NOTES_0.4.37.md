# Velch 0.4.37 发布说明

日期：2026-10-26

## 本轮结论

**包现在自带模型：3 个算例 + 298 个型面/不平顺资产（12.1 MB），解压即用，不需要任何环境变量。**
上一版只证明了"包里的柔性轮对算例能跑"，长波/短波那两条主线的算例还留在本机语料里；
这一版把其中最关键的三个（辙叉 0.05 s、整车 1.2 s、直线 0.4 s）连同它们引用的资产一起导出成
可移植目录 `portable/validation/crh380a_m/`，并打进安装包。

- 新增 `packaging/portable_models.py`：读语料 → 收集每个算例引用的型面/`.tre` → **按内容哈希去重**
  → 复制进 `profiles/` → 把算例里的引用改写成相对名 → 逐份 `load_vehicle_case` 验证。
  实测：298 个资产、12.1 MB，三份算例全部加载通过（35 / 51 坐标）。
- `data_root()` 新增随包语料发现：`<安装目录>/validation`、`portable/validation`、
  `_internal/portable/validation`、`_internal/validation` 依次尝试；环境变量与标记文件仍然优先。
- `packaging/clean_room_test.py` 增加第 3 步 **bundled-corpus**：白名单环境下 `selfcheck` 必须报
  `[PASS] 算例语料 3 个算例`，并用随包辙叉算例真跑一次 `numerically_checked`。

## 验证

- 干净机器验收（白名单环境、`LOCALAPPDATA` 重定向、中文含空格路径）→
  **ACCEPT · 6 步 · 失败 0**（`reports/clean_room_20261026-104641.json`）；
- `packaging/smoke_test.py --readonly-acl` → ACCEPT · 8 步（下一节数字见发布时实测）；
- 包体：onedir 211.2 MB、zip 98.5 MB（上一版 198.9 / 95.1 MB，多出的 12.3 MB 就是随包模型）；
- `pytest`：见本轮提交闸门（`verdict: ACCEPT`）；
- 冻结物理未动：静载门 59 680.5769 N / 65.47 µm、八接触峰值 89.68 / 170.61 kN、七门 7/7。

## 已知边界

- 随包的是**三份代表性算例**，不是全部 368 份；整套语料 916 MB（13 447 个唯一文件），
  全量随包会把 zip 推到 1 GB 量级。要别的小算例，用 `packaging/portable_models.py --target <目录>`
  从本机语料导一份出来，或把 `--data` 指向完整语料。
- `physics_validation_status` 仍是 `unvalidated_against_measurement_or_Simpack`；
- 未做代码签名，首次运行会弹 SmartScreen。
