# AI 协作入口与能力状态

仓库根目录是工作空间；本目录维护单份规则、Skills 和宿主适配。执行与存储规则由公共程序实施，不能依赖宿主提示词或 Hook 作为唯一保障。

| 目录 | 作用 | 当前状态 |
| --- | --- | --- |
| rules | 证据、时间、来源身份与核实规范 | 已有共同规则 |
| skills | 三个核心数据流程、领域指南及安装维护流程 | 可显式读取，使用 CLI 能力发现 |
| adapters | 宿主配置、目标位置和支持边界 | Codex 文件适配；CodeBuddy 实验性文件适配 |
| tooling | 计划、投影、回执、同步、修复和卸载 | 已实现，离线文件级验收 |
| hooks | 可选宿主生命周期增强 | 禁用，未实现 |

核心流程：[规划](skills/data-planning/SKILL.md) → [获取整理](skills/data-acquisition/SKILL.md) → [核验入库](skills/data-review/SKILL.md)。专门问题参考行情、证据检索和影响研究指南；影响推断不是输入事实。

初始化按 [工作空间设置](skills/workspace-setup/SKILL.md)，后续维护按 [维护指南](skills/workspace-maintenance/SKILL.md)。生成的宿主 Skill 副本不提交，安装回执保存在 .research-local。实际宿主是否自动发现并调用 Skill 需要在对应宿主验证，文件校验通过不代表已经完成该验证。
