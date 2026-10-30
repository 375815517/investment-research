# AI 工作入口

本仓库根目录就是投资研究工作空间。先读 [README.md](README.md)，再读 [架构文档](docs/architecture/research-workspace.md)，按当前任务进入相关目录。

- 当前具备公共包、CLI/API/网页、检测补采和宿主文件适配；能力和限制以 capabilities、运行手册与[最新验收](docs/verification/reusable-input-platform.md)为准。worker、MCP和Hook未实现。
- AI 负责理解、假设与研究组织；确定性计算、版本保护与正式登记由执行系统承担。研究资产提供方法，输入数据与研究产出分别保存。
- 代码、方法、输入数据与研究产出均纳入 Git；遵循 [Git 数据管理约定](docs/operations/git-data-management.md)。正式数据保存到 `data/`，不可只保存在本地数据库、缓存或外部服务；历史正式记录修订时新增版本。
- `ai/` 统一维护协作规范、Skills、Hook 和宿主适配；`ai/skills/` 是权威 Skill 源。多宿主使用工具生成投影，禁止多份方法各自维护；文件适配工具已实现，宿主发现与实际调用另行验证。
- `legacy/` 保存原项目，是待逐项迁移的历史资料。其规则和机器绝对路径不作为当前根规范；不得覆盖历史报告、原始证据和计算快照。
- 应用入口放 apps/，共享实现放 packages/，研究定义放 research/；数据按业务主题与成果分类，资料单份归档并通过引用关联。
- 新增实现遵循架构边界，保护用户改动，完成与变更相称的验证。提交和推送按当前任务授权执行。

研究前读取 [数据设计](docs/architecture/research-data-design.md) 与 [共同证据规则](ai/rules/research-evidence.md)。按任务显式读取 ai/skills/market-data-acquisition、evidence-retrieval 或 impact-research 中的 SKILL.md；当前宿主自动发现尚未验证。

输入路径与归属以 [输入数据结构基线 v1](docs/architecture/input-data-baseline.md) 为唯一合同。原件集中归档，企业入口只引用共享资料；不另建 subjects 或 listings。首次建档须由用户确认主证券；本次已确认小米港股01810/HKD和腾讯港股00700/HKD，确认记录已保存，不重复询问。已登记有限范围的provider-native行情与官方财报；未复权/量单位及历史公开时间仍需核实，不能混同口径。

实现任务先读 [运行手册](docs/operations/input-platform.md) 和 [验收记录](docs/verification/input-platform-v1.md)。新代码检查范围为packages、apps/cli、ai/tooling、tests；不运行legacy。只暂存本任务明确文件，不夹带已有legacy删除。

新增document-facts和market-observations须复核，前者批准须statement_consistency_checked。市场比例不能用不明分母拼接。audit-inputs的complete仅指声明样本满足，完整请求仍有未取得字段，数量以最新审计为准；不得删需求使其变complete。历史时刻统一UTC，纯来源日期保留精度。

研究前按用途运行assess-inputs并遵循[适用性规则](ai/rules/data-fitness.md)。不能用样本计数通过替代全历史完整性；年度资料按年逐字段检查。新取得原件与旧报告分别保留，不追写既有正式记录。

可复用输入层按[决定004](docs/decisions/004-reusable-input-contracts.md)组织。research/metrics与input-profiles为语义/需求权威；新v2观测需字典校验和语义复核，原件时间修订只追加metadata-revisions。精确profile审计不是因子有效性认证。
