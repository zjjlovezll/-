# 接触半宽不是缺失的那个坐标（2026-10-31，第 280 轮）

> 第 279 轮把候选从四个减到一个：**σ 只依赖该站一个标量间隙**。最自然的"第二个坐标"是接触半宽——它在
> 过渡带上实测变化 1.30×（5.75 → 7.47 mm，第 254 轮），而且 `s99` 从第 270 轮起逐帧逐轨归档了
> `contact_half_width_m`。所以这一轮直接问：**把半宽加进去，六分量剖面的 floor 会掉到 0.02 吗？**

## 一、预注册

```
标定集  两峰、三峰（已归档）
留出集  六分量随机（已归档）
读法A   用归档半宽的残差修正（只标定在标定集上）⇒ 留出 floor ≤0.02
读法B   残差与半宽偏移的相关系数 ≥0.5
判决    任一条成立 ⇒ 半宽是缺失坐标；两条都不成立 ⇒ 缺失的不是半宽，逐站假设要从接触层重推
```

## 二、读数

```
run                           usable  law floor      db range (mm)  corr(r,db)
one_set_twopeak                  469     0.0133   -0.747 ..  1.025      -0.102
one_set_threepeak_obs            469     0.0427   -1.473 ..  1.250      -0.042
one_set_random                   381     0.1314   -1.473 ..  1.025      -0.447

width correction fitted on calibration: -0.02516 share per mm
held out one_set_random: before 0.1314  after 0.1193  gain   9.2 %   target 0.02
VERDICT: the width does not explain the spread of the residual: removing it changes the held-out floor
         by less than 30 %, so the missing physics is not the contact width and the per-station
         assumption itself has to be re-derived from the contact layer
```

三条读数：

1. **半宽的动态范围很小**：相对未加凸起那趟只变 **−1.47 … +1.03 mm**。它确实随抬升变化，但幅度不足以
   解释 10 倍的 floor 差；
2. **残差与半宽不相关**：两峰 **−0.102**、三峰 **−0.042**；六分量 **−0.447**（中等、而且**负号**——
   半宽变大时残差偏小），离读法 B 的 0.5 门都没到；
3. **留出修正只买到 9.2 %**：用标定集拟合的斜率（−0.0252 share/mm）修正留出集，floor **0.1314 → 0.1193**，
   离 0.02 差 **6 倍**。

## 三、一次差点犯的错（写进记录）

第一版把"两坐标律"实现成**用三参数 logistic 替换实测律**，得到"M2 0.1102、M3 0.1796"，看上去
"宽度也不管用"。但那不是公平的检验：**同一个 logistic 在标定集上就只有 0.1047 / 0.0744**，而实测律是
0.0133 / 0.0427——**替换底座本身把误差放大了一个数量级**，那样得出的任何关于半宽的结论都是关于 logistic
的结论，不是关于半宽的结论。已改成"保留实测律、只加一条宽度修正项"的留出检验，并把 logistic 结果降为
**附录**（`crude_logistic_appendix`，明确写"不能用来判定宽度"）。

## 四、所以缺失的是什么

半宽被排除之后，剩下的候选只有一类：**逐站独立假设本身**。也就是说，叠加上去之后，某站的份额不再只由
该站的间隙决定——它依赖周围一段的几何（轮在隆起的坡上时，法向方向、接触点横向位置、两侧法向力分配都会变）。
这不是"再加一个坐标"能修的，必须回到接触层：**逐站真解两体 Hertz（真实接触宽度、真实轮心高度）**，
即第 278 轮列的路线 (a)。

## 五、能说 / 不能说

**能说**：在这条种子六分量剖面上，把**归档的接触半宽**作为第二个坐标（只用标定集拟合修正、留出集检验），
floor 只从 **0.1314 降到 0.1193（−9.2 %）**，残差与半宽的相关系数为 **−0.447**（两峰 −0.102、三峰 −0.042）；
因此**半宽不是缺失的那个坐标**。

**不能说**：① 不能说"逐站假设一定错"——只排除了半宽这一条；
② 不能说路线 (a) 一定能到 0.02——未做；
③ 不给任何随机剖面的幅值数字（`G-RES` 仍 0.02，第 277 轮三门仍 FAIL）；
④ 只测一条种子剖面、单速度、单侧、直向。

## 六、复算

```bash
cd Velch
python -X utf8 scripts/s137_width_coordinate.py
python -X utf8 -m pytest tests/test_width_coordinate.py -q
```

产物：`reports/load_split_inversion_2026-10-31/width_coordinate.json`（逐运行 floor、db 范围、相关系数、
宽度修正斜率、留出前后 floor 与增益、附录 logistic、判决）。
