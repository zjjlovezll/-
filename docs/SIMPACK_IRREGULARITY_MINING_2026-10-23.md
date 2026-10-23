# Simpack 里"轨道不平顺"是怎么装进模型的（齿轨模型取证）

> 取证对象：`H:\总的齿轨项目\总和1\总齿轨项目\齿轨项目刚性-直向-坡度_道岔-轨道不平顺\RACK_RAILWAY_VEHICLE - XNEW - M`
> （车型与轨道与我们不同，本文只取"安装方式"这一件事。）
> 方法：`spck` 是 ASCII 模型库，逐行 `key ( args ) = value ! 注释`，直接读文本，不反编译。

## 1. 结论一句话

Simpack 的不平顺 **不是**"改钢轨型面"，而是**轨道元素（Track）上挂一组"激励（Excitation）"**：
不平顺样本存在一个**输入函数集文件（`.tre`）**里，激励元素按里程读取该文件的某一列，再由轨道元素把
**横向 / 垂向 / 侧滚 / 轨距**四个分量叠加到轨道中心线（或每根钢轨）上。里程区间、淡入淡出也在轨道元素上给。

## 2. 三层结构与对应关键字

```
输入函数集（数据）      ifctnset.file ( $N_AAR5_T ) = 'AAR5_track_excit_Trc_1km.tre'
        ↓ 列选择
激励元素（读表）        excit.type ( $E_LAT ) = 109
                        excit.par ( 1, $E_LAT ) = $N_AAR5_T.$I_Lateral     ← 取哪一列
                        excit.par ( 2, $E_LAT ) = 0.0                      ← [m] 起始位置（0=原样）
                        excit.par ( 3, $E_LAT ) = 0.0                      ← [m] 结束位置
                        excit.par ( 7, $E_LAT ) = 0.0                      ← [-] 偏置
                        excit.par ( 9, $E_LAT ) = 0.0                      ← [-] 缩放（绕均值）
        ↓ 挂到轨道上
轨道元素（施加）        track.excit.lat  ( $Trk_STR ) = $E_LAT   ! EXC_TRACK_LATERAL
                        track.excit.vert ( $Trk_STR ) = $E_VER   ! EXC_TRACK_VERTICAL
                        track.excit.roll ( $Trk_STR ) = $E_ROL   ! EXC_TRACK_ROLL
                        track.excit.gauge( $Trk_STR ) = $E_GAU   ! EXC_TRACK_GAUGE
                        track.excit.type     ( $Trk_STR ) = 1    ! 0=关闭, 1=开启(本模型用 1)
                        track.excit.start    ( $Trk_STR ) = 30.0  ! [m] 起始里程
                        track.excit.end      ( $Trk_STR ) = 1000.0! [m] 结束里程
                        track.excit.fade.len ( $Trk_STR ) = 1.0   ! [m] 淡入淡出长度
```

**两套口径都存在**（同一个模型里可以同时看到）：

* **整条轨道四分量**：`track.excit.lat / vert / roll / gauge`（本模型的 `$Trk_STR`、`$Trk_SWITCH`、`$Trk_R300` 都用这套）；
* **每根钢轨分量**：`track.excit.left.lat|vert|roll`、`track.excit.right.lat|vert|roll`、`track.excit.gauge`
  （本模型的 `$Trk_STR_NoExt` 用了 `left.vert` 与 `right.vert`，其余为 `null`）。

**"null 就是没接"**：`$Trk_Track`（另一个轨道元素）里七个激励槽全是 `null`、`track.excit.type = 0`，
所以那个轨道不施加不平顺——这就是"同一模型里既能跑有激励、也能跑无激励"的开关方式。

## 3. 数据文件 `.tre` 的两种形态

| 形态 | 特征 | 我们怎么处理 |
|---|---|---|
| ASCII（用户生成器产出的那种） | 以 `header.begin` 开头，`data.type = 1`，`data.par(1..5)` 单位系数、`data.par(6) = 1` 逐行读，随后五列 `s, Δy, Δz, Δφ, Δg` | **直接支持**（读+写） |
| 二进制（Simpack 2021x 自己存的 `AAR5_track_excit_Trc_1km.tre`，56 044 B） | 以 `\x00\x00\x00\x08` 起头，浮点内嵌，无 `header.begin` | 检出即**明确拒绝**并提示"请在 Simpack 里另存为 ASCII / 用我们的生成器生成"，不猜格式 |

用户已有的 `H:\不平顺\tre.tre` 属 ASCII 形态，4096 行、0–1023.75 m、`dx = 0.25 m`，与上表一致。

## 4. 与我们的求解器怎么对应（重要）

| Simpack | 语义 | Velch 对应做法 |
|---|---|---|
| `Δy`（lateral） | 轨道中心线横向偏移 | 轨面 `y` 偏移（左右同号） |
| `Δz`（vertical） | 轨道中心线垂向偏移 | 轨面 `z` 偏移 |
| `Δφ`（roll） | 轨道侧滚（水平/三角坑） | 左轨 `+Δφ·(g/2)`、右轨 `−Δφ·(g/2)` 的差动抬高 |
| `Δg`（gauge） | 轨距变化 | 左轨 `−Δg/2`、右轨 `+Δg/2`（按我们的左右符号约定取反需实测确认） |
| `track.excit.start/end/fade` | 施加区间与淡入淡出 | 算例里同样给 `start/end/fade_m`，不做"全程施加"的默认 |
| `excit.par(9) Scaling` | 绕均值缩放幅值 | 算例里给 `scale`（便于做 0.5×/1×/2× 敏感性） |

**差异（必须写进文档，不能假装一样）**：Simpack 是把激励加到**轨道中心线/钢轨参考**上（几何在轨道元素内部处理），
我们是在**采样型面时把偏移叠加到型面点**。两者在"准静态几何"意义下等价，但在**长波与侧滚耦合**上不完全相同
（我们的接触会重新搜索接触点，Simpack 也做，但两者的接触离散不同）。差异用同一 `.tre` 跑同工况来量化，不靠断言。

## 5. 落地清单（Velch 侧）

1. `velch/irregularity.py`：`read_tre()`（ASCII，检出二进制即报错）、`write_tre()`、`columns()`（Δy/Δz/Δφ/Δg 取列）；
2. 算例新增块：
   ```json
   "irregularity": {
     "tre": "AAR5_track_excit_Trc_1km.tre",
     "start_m": 30.0, "end_m": 1000.0, "fade_m": 1.0, "scale": 1.0,
     "channels": ["lateral", "vertical", "roll", "gauge"]
   }
   ```
3. 施加点选在"型面采样"层（与求解器读轨面同一条曲线），并在旁挂 `simpack.json` 里记录
   `tre_sha256`、`start/end/fade`、`scale`、以及"与 Simpack 语义对齐的三条假设"；
4. 验收：`tre.tre` 读入再写出逐字节等价；同 `.tre` 下 `Δy/Δz/Δφ/Δg` 在 0 里程处的值与文件首行一致；
   衰减区间外激励为 0（淡入淡出按余弦或线性，需在文档写明选哪一种）。

## 6. 还没核对的两点（不编）

1. `track.excit.type` 的 **1 与 2 的差别**：本模型里 `$Trk_STR`/`$Trk_SWITCH`/`$Trk_R300` 用 1，
   `$Trk_STR_NoExt` 用 2，`$Trk_Track`/`$Trk_TEST` 用 0；从字段看不出来，需在 Simpack 界面确认
   （或对同一份 `.tre` 跑一次 1 与 2 对比结果差异）。
2. **淡入淡出的形状**：只有 `fade.len` 一个长度参数，未记录是线性还是余弦过渡。
