# Velch 0.4.30 发布说明

**发布日期**：2026-10-23

这一版没有新物理，只把"做到哪一步"变成可查的两页：

* `docs/ELEMENT_CATALOGUE_2026-10-23.md` —— 七个元件与 Simpack 的对照表、39 个真实力元的判读、
  以及**明确没搬的六类**（内部状态、事件检测、空气簧气室、约束类、USUB、求解器内部）；
* `docs/GOAL_STATUS_2026-10-23.md` —— 五步目标各自的完成度、证据命令、剩余差距。

代码上的变化只有一处：`velch vehicle list` 现在会打印每台车**用了哪些元件、各几个**，
（`elements.inventory` / `describe_inventory`），并有测试保证目录文档覆盖全部元件类型。

验证：全仓 pytest 全绿；`verify_vehicle_ref.py` 仍 `VERDICT: EQUIVALENT`；安装包冒烟 8 步全过。
