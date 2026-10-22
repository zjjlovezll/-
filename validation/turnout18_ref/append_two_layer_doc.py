"""Append the two-layer results (S1-f §8-9) and update the doc index status."""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]          # Velch/
DOC = ROOT / "validation" / "turnout18_ref" / "S1F_TRACK_LAYERS_2026-10-20.md"

SECTION = """
## 8. 两层轨道已落地并跑通（本节为实测，覆盖第 5 节的"待落地"）

`TrackKernel` 新增 `two_layer` 类型（每根钢轨 4 个自由度：`y_rail, z_rail, y_sleeper, z_sleeper`），
`LinearSupport` 新增 6 个带默认值字段（`sleeper_mass_[yz]_kg`、`ballast_k_[yz]_n_m`、
`ballast_c_[yz]_n_s_m`），旧算例不受影响。**56 项测试全过。**

算例（`validation/crh380a_m/make_two_layer_case.py`，0.6 m 枕距）：
`m_rail=121 kg`、`k_pad=25e6 / c_pad=20e3`、`m_sleeper=79 kg`、`k_ballast=12e6 / c_ballast=120e3`。

满 1.2 s（2401 采样，7/7 门过，`numerically_checked`，67 自由度，nfev 482 525）：

| 轨道模型 | 峰值 | 最小力 | 脱空 | 轮对行程 | 主频 | 30-60 Hz | 150-250 Hz |
|---|---|---|---|---|---|---|---|
| 刚体 | 158.04 kN | 3.02 | 0 | 0.5933 mm | 175.76 Hz | 1.183 | 6.402 |
| 单自由度 kz50/cz20 | 123.77 | 13.41 | 0 | 0.6012 | 36.65 | 2.507 | 0.408 |
| **两层（本次）** | **125.35** | **23.50** | **0** | 0.4741 | **545.61** | **0.380** | 0.480 |
| Simpack | 134.97 | **27.67** | 0 | 0.5944 | **31.65** | **4.839** | 1.088 |

**读法**：第一个目标达成——峰值 −7.1%、最小力 23.50 kN 与参考的 27.67 kN 最接近
（此前单自由度是 13.41）、且完全不脱空。**但频带没有达成**：主频 545.61 Hz 是轮对压在接触
弹簧上的振铃（`sqrt(1.5*C*sqrt(delta)/m_wheelset)/2pi`，C≈1.2e11、delta≈0.1 mm → 约 600 Hz），
它压过了 32 Hz 的轨道模态；30-60 Hz 反而从 1.183（刚体）降到 0.380。

## 9. 结论：缺的不是层数，是模态参与质量

32 Hz 模态确实存在，但它在接触点的参与质量只有 79 kg 的轨枕，而 121 kg 的钢轨坐在 25e6 N/m
的扣件上——轮对感受到的仍是"硬轨 + 小质量轨枕"，所以 32 Hz 那条振型的挠度小、接触力里看不
出来。参考解里 31.65 Hz 能主导，说明它的轨道在接触点有**大得多的低频参与质量**。

下一步（按可检验性排序）：

1. 给轨枕质量补上道床参与质量（道床锥体质量，通常 200-400 kg/枕），使 32 Hz 模态的接触点
   参与质量从 79 kg 提到 300 kg 量级——这是唯一能在不改判据的前提下把 30-60 Hz 抬起来的改动。
2. 抑制 545 Hz 振铃：接触阻尼目前在 `hunt_crossley` 口径下由恢复系数给定（e=0.5），可对照
   Simpack 的 `fn.dref=1e5` 做一次定标，而不是继续调 e。
3. 若 1 与 2 之后 30-60 Hz 仍不足，则说明参考解的低频内容来自我们尚未建模的轨下结构
   （轨道板/道床板），那属于 S1-g，不是轨道层能补的。
"""

CHANGELOG = """
## 2026-10-20 追加

- **S1-f 部分完成**（`validation/turnout18_ref/S1F_TRACK_LAYERS_2026-10-20.md`）：
  钢轨梁第一阶模态 131.9 Hz（`sqrt(k_pad/m_bay)`），结构上给不出 30-60 Hz；
  两层轨道（钢轨 + 轨枕 + 道床）已实现（`track_models.py` 的 `two_layer`，每轨 4 自由度），
  满 1.2 s 峰值 125.35 kN（参考 134.97）、最小力 23.50（参考 27.67）、0 脱空，
  但主频 545.61 Hz、30-60 Hz 带 0.380（参考 4.839）→ **力对了、频谱还没对**，
  下一步是轨枕参与质量（道床锥体质量）而不是再加层。
- 状态表：S1-a 完成、S1-c 完成（空结果）、S1-d 完成（部分有效）、
  S1-e 完成（静力柔度版本作废；钢轨自由度版本 123.60 kN）、S1-f 部分完成，
  S1-g 轨下结构（轨道板/道床板）与 S2/S3/S4 待做。
"""


def main() -> None:
    text = DOC.read_text(encoding="utf-8")
    if "## 8. 两层轨道已落地" in text:
        print("S1F doc already has section 8")
    else:
        DOC.write_text(text.rstrip() + "\n" + SECTION, encoding="utf-8")
        print(f"S1F doc appended -> {len(DOC.read_text(encoding='utf-8').splitlines())} lines")

    changelog = ROOT / "docs" / "CHANGELOG_DOCS.md"
    if changelog.exists():
        body = changelog.read_text(encoding="utf-8")
        if "S1-f 部分完成" in body:
            print("changelog already updated")
        else:
            changelog.write_text(body.rstrip() + "\n" + CHANGELOG, encoding="utf-8")
            print("changelog updated")


if __name__ == "__main__":
    main()
