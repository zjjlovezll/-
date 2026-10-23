# 轨道不平顺进求解器（0.4.31 前的功能层，2026-10-23）

> 目标：把 Simpack 里那套"激励 → 轨道 → 钢轨面"的不平顺，接到我们自己的求解器上，并且**证明**它接对了。
> 取证（Simpack 怎么装的）：`docs/SIMPACK_IRREGULARITY_MINING_2026-10-23.md`。

## 1. 接了哪些、没接哪些

| Simpack | 我们 | 说明 |
|---|---|---|
| `Δy` 横向 | ✅ | 左右轨同号横移 |
| `Δz` 垂向 | ✅ | 左右轨同号升降 |
| `Δφ` 侧滚 | ✅ | 左轨 `−Δφ·g/2`、右轨 `+Δφ·g/2`（水平/三角坑） |
| `Δg` 轨距 | ✅ | 左轨 `−Δg/2`、右轨 `+Δg/2` |
| `start/end/fade` | ✅ | 半余弦过渡（Simpack 形状未文档化，见 §4） |
| `excit.par(9)` 缩放 | ✅ | 算例 `scale` |
| 二进制 `.tre` | ❌ 明确拒绝 | 只认 ASCII，猜格式会静默改幅值 |
| `data.type ≠ 1` | ❌ 明确报错 | 只支持"横向/垂向/侧滚/轨距"五列这一型 |

## 2. 接在哪一层（这是关键决定）

**接在"型面采样"层，不接在"站位"层。**

站位之间隔着米级（辙叉算例右轨只有 79.131–150 m 的两端站位），而不平顺样本是 0.25 m 一个；
如果把不平顺烘进站位型面，等于把 0.25 m 的波动低通到米级——那正是"看起来接了、其实没接"的典型。
所以实现成 `irregularity.ShiftedSeries`：求解器每次向它要"某里程处的轨面"时，它在返回
`ProfileSample.profile` 上加 `(dy, dz)`，并把 `dz_ds` 加上 `d(dz)/ds`（数值差分，步长 1 mm）。
接触搜索本身一行没改——它照旧只看一个型面。

## 3. 验收（两条，都是硬判据）

### 3.1 零幅值必须与基线**逐位**相同

同一算例派生两份：`case_irr_zero`（`scale = 0.0`）与 `case_irr_full`（`scale = 1.0`），窗口 69–74 m、淡入 0.25 m。

```
基线      out_base_ref   history.csv sha256 1b9be8134d7767fb…  244 376 B   numerically_checked  门 7/7
零幅值    out_irr_zero   history.csv sha256 1b9be8134d7767fb…  244 376 B   numerically_checked  门 7/7
```

**两行 sha256 完全相同**——说明这条通道在"不该动的时候确实没动"（新增的字段、包装的 series、附加的
`dz_ds` 都没有污染数值路径）。这一条由 `tests/test_irregularity_case.py::test_zero_amplitude_reproduces_the_untouched_surface_exactly`
在型面层再钉一次（`np.array_equal`，不是 `allclose`）。

### 3.2 满幅值必须**等于**文件里记的值

`tests/test_irregularity_case.py::test_full_amplitude_shifts_each_rail_by_the_recorded_sample` 对左右轨、
多个里程逐个断言：

```
dz = Δz + sign·Δφ·(g/2)        dy = Δy + sign·Δg/2          （sign：左轨 −1、右轨 +1）
```

实测（左轨、69.5 m）：`Δz = 0.4298 mm`、`Δφ·g/2 = 0.0851 mm` → 测得 `dz = 0.3447 mm` ✔。
容差 1e-12 m（不是"看起来差不多"）。

## 4. 与 Simpack 的三处**已知差异**（写在这里，不藏）

1. **施加点**：Simpack 加在轨道中心线/钢轨参考上（几何在轨道元素内部处理），我们加在**采样轨面**上。
   准静态几何等价，但长波与"侧滚 × 轨距"的耦合路径不同，差异必须用同一份 `.tre` 跑同工况来量化。
2. **淡入形状**：Simpack 只有一个 `fade.len`，形状未文档化；我们选**半余弦**（C1、单参数）。若要严格对齐，
   需在 Simpack 里对同一份 `.tre` 做一次阶跃对比。
3. **波长带宽**：采样步长 0.25 m → 只能承载 **≥ 0.5 m** 的空间波长；这份 `tre.tre` 的带宽是
   **0.5–1023.75 m**，短波（<0.5 m）它本来就没有。做短波反演必须换生成器（见任务书 S3）。

## 5. 算例怎么写

```json
"irregularity": {
  "tre": "D:/data/AAR5_track_excit_Trc_1km.tre",
  "start_m": 69.0, "end_m": 74.0, "fade_m": 0.25,
  "scale": 1.0,
  "channels": ["lateral", "vertical", "roll", "gauge"]
}
```

- `tre` 相对算例所在目录解析，也可以给绝对路径；
- 文件会被记进 `asset_hashes`，所以**改了 `.tre` 会让产物校验失败**（这是有意的）；
- 实际施加的内容记在 `case.irregularity`：`source/sha256/samples/step_m/channels/start_m/end_m/fade_m/scale/
  wavelength_band_m/fade_shape/applied_at`，可随产物一起交付。

## 6. 一个已观察到的现象（不是缺陷，但要写下来）

在辙叉算例（`case_frog_N_strip05`，69–74 m）上，`scale=1.0` 与 `scale=0.0` 的**接触力峰值完全相同**
（170.65 / 208.75 kN、最大侵入 150.59 µm）。查证结论：该窗口里的接触已经**顶到侵入限值**
（`maximum_penetration_m`），力被限值截住，0.4 mm 的轨面起伏不足以改变峰值。
所以"零幅值等价"在这一窗口是**通过限值退化出来的**，不能当作灵敏度证据；
真正的灵敏度要在**正常侵入（50–150 µm）**的平顺断面窗口上测（如 80 m 以后那段）。
这一条已写进任务书 S3 的验收要求里。

## 7. 复算命令

```powershell
# 读文件、看带宽与各通道 rms
python -X utf8 -c "from velch.irregularity import read_tre; import json; print(json.dumps(read_tre(r'H:\不平顺\tre.tre').describe(), ensure_ascii=False, indent=1))"

# 两份派生算例（零幅值 / 满幅值）
python -X utf8 ..\.tmp\make_irr_cases.py

# 跑并比 sha256
python -X utf8 -m velch run-vehicle F:\velch_data\validation\crh380a_m\case_irr_zero.json --output F:\velch_tmp\out_irr_zero --fast
python -X utf8 -m velch run-vehicle F:\velch_data\validation\crh380a_m\case_irr_full.json --output F:\velch_tmp\out_irr_full --fast
python -X utf8 ..\.tmp\cmp_irr.py

# 测试
python -X utf8 -m pytest tests\test_irregularity.py tests\test_irregularity_case.py -q
```
