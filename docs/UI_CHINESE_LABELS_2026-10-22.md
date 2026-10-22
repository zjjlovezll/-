# 界面中文命名规则（Velch UI）

这份文件只说一件事：**界面上的中文字是怎么来的**，以及新增一类数据时该在哪里给它起名字。
它不描述屏幕布局（看 `README.md` 的「界面」一节）、也不描述物理量含义（看对应的算例与文档）。

## 1. 三条原则

1. **界面的字面量用中文，数据的标识符保持原样。**
   按钮、标签、提示、图轴标题是人写的，一律中文。通道名 `axle1_right_normal_n`、运行目录
   `out_full12_cap05`、算例编号 `S_hc_e0.15_v0.5` 是**标识符**：它们要能被复制、grep、贴进命令行，
   翻译只会让它们不可用。所以做法是「标识符 + 中文解释」，例如
   `out_full12_cap05 · 2401 帧 · 155 通道 · 隐式 BDF · 门 7/7`。
2. **不认识的宁可不译。** 落在文法之外的通道回落到 `原始名 [单位]`，不猜。
   错的汉语词读起来像定义，比不译更坏。
3. **单位用国际符号。** `[N]`、`[m/s]`、`[rad]`、`[—]`（无量纲）。不写「牛」「米每秒」——
   工程表格里 SI 符号比汉字更省地方，也更好对表。

## 2. 通道标签从哪里来

唯一实现：`src/velch/ui/store.py` 的 `channel_label()` / `channel_short_label()` /
`channel_unit()` / `channel_group()`，全部**由通道文法推导**，不查表、不硬编码清单。

文法是 `所有者[_侧别]_量[_per_s]`：

| 通道 | 标签 |
| --- | --- |
| `time_s` | 时间 [s] |
| `axle2_right_normal_n` | 第2轴右轨 法向力 [N] |
| `axle1_left_active` | 第1轴左轨 接触状态 [—] |
| `axle4_right_penetration_m` | 第4轴右轨 侵入深度 [m] |
| `axle1_left_fy_n` | 第1轴左轨 横向蠕滑力 [N] |
| `axle1_z_m_per_s` | 第1轴 沉浮速度 [m/s] |
| `carbody_yaw_rad` | 车体 摇头角 [rad] |
| `track_mode12_m` | 钢轨 模态位移 12 [m] |
| `axle1_left_rail_z_m` | 第1轴左轨 钢轨垂向位移 [m] |

实现里三个容易踩的点，都已有注释与测试钉住：

- `_per_s`（速度）必须在 `_m` / `_rad` 之前匹配，否则每个速度都会被叫成位移；
- `..._active`、`..._normal_n` 把词写在**单位后缀里**，剥后缀会丢语义 → `_SUFFIX_QUANTITY` 捡回来；
- 柔性轨道把结构件写在侧别之后（`left_rail_y_m`）→ 先认结构件，再认方向。

## 3. 运行目录标签从哪里来

`store.run_label()`：`名称 · 帧数 · 通道 · 方法 · 门 n/N`，其后可能附 `（manifest 缺失）`。
名称永远排第一，因为两个运行只能靠它区分。

## 4. 新增一类数据时要做什么

1. 在 `store.py` 的 `_OWNER` / `_SIDE` / `_QUANTITY` / `_TRACK_OWNER` / `_SUFFIX_QUANTITY` 里加词；
2. 在 `tests/test_ui_labels.py` 的 `GRAMMAR` 表里加一行期望值；
3. 跑 `tests/test_ui_labels.py::test_every_real_history_column_is_translated` ——
   它会把两个真实 `history.csv` 的每一列翻一遍，**任何新通道没被翻译就会红**。

## 5. 怎么自查

```powershell
cd F:\ai道岔状态反演辨识\Velch
python -X utf8 -m velch.ui --selftest              # 7 屏 / 0 报错
python -X utf8 -m pytest tests -q                  # 415 passed
python -X utf8 ..\.tmp\ui_identifier_audit.py      # 纯标识符应只剩 2 条（数据目录名与秒）
```

改完界面**一定要看 stderr**：Tk 把回调异常打到 stderr 之后照样出图，
2026-10-22 的一次 `NameError` 就是这样"看起来正常"的。
