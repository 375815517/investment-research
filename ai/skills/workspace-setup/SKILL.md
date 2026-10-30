---
name: workspace-setup
description: 检查工作区并计划、安装和验证项目级宿主 Skill 投影，明确区分文件安装与宿主原生发现。
---

根目录始终是工作入口，权威 Skills 位于 ai/skills。首次引导不依赖本 Skill 已被宿主发现：按根 README 的锁文件安装步骤取得 research 命令。

1. `research doctor --json` 检查环境；`research host inspect --host codex --json` 检查文件状态。其他宿主使用对应 host 参数。
2. `research host plan --host codex --json` 仅查看计划，默认不修改任何文件。
3. `research host plan --host codex --save --json` 将可执行计划保存到忽略的 .research-local；读取计划中的冲突和变更。
4. 已授权安装且无冲突时，`research host apply --plan-id <ID> --json`。plan 与 apply 之间源或目标改变会拒绝执行，应重新规划。
5. `research host verify --host codex --json` 检查摘要。filesystem=verified 只证明文件与回执一致，discovery=unknown、invocation=not_tested 必须如实报告。

CodeBuddy 当前仅有实验性文件投影，未经实际宿主验证，不宣称自动发现成功。可以从根 CODEBUDDY.md 显式阅读 canonical Skills。Hook 尚未启用。

验收：只读计划零修改；重复 apply 为 NOOP；目标用户修改被保留；投影后的资源链接可解析。
