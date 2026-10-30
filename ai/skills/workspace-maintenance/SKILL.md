---
name: workspace-maintenance
description: 同步、诊断、修复或卸载项目级宿主投影，保护用户改动和权威研究方法。
---

安装逻辑只由 ai/tooling 实现，不修改全局宿主配置。

- 检查：`research host verify --host codex --json`，区分源版本过期、目标被修改和宿主未验证。
- 同步：`research host sync --host codex --save --json` 生成计划，再用 `research host apply --plan-id <ID> --json` 执行。
- 修复：`research host repair --host codex --save --json` 只规划归属可确认的文件；出现 USER_MODIFIED 时保留文件并报告差异，不覆盖。
- 卸载：`research host uninstall --host codex --save --json` 生成删除计划，再用 `research host uninstall --plan-id <ID> --json` 执行。只删除回执中仍与生成摘要一致的文件，其他文件保留。
- 安装中断：重复 apply 同一保存的 plan_id 接续；若源文件已变或存在另一个待完成计划，报告冲突，不删除回执绕过保护。

不删除缺回执的宿主文件，不清理研究 data，不改写共同规则；修改方法应在 ai/skills 或 ai/rules 进行，然后同步投影。

验收：源升级可同步；已修改目标阻断；未管理文件不被卸载；中断后同一计划可继续。
