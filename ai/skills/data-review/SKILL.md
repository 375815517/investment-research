---
name: data-review
description: 核实候选数据的证据、单位与期间，通过统一校验和计划入库，保留阻断项与复核依据。
---

先读 [输入基线](../../../docs/architecture/input-data-baseline.md) 和 [共同证据规则](../../rules/research-evidence.md)。结构校验合格不等于语义真实，模型置信度不作为准入依据。

1. 使用 `research data validate --candidate-id <ID> --json` 获取实际检查结果。区分阻断、警告、覆盖不足和需语义复核。
2. 回到候选引用的原件与具体位置。确认来源声明/实际值身份、主体、期间、单位、合并范围与数据集口径。缺失信息不补猜，冲突不静默平均。
3. 对需要复核的候选，用 `research data review --request review.json --json` 登记证据、复核者、方法和结论。按 schema 填字段。自我复核如实标记，不声称独立审查。
4. 用 `research data ingest --candidate-id <ID> --dry-run --json` 查看写入计划。确认批次、路径、版本、覆盖与阻断项。禁止直接编辑 data/ 以绕过校验。
5. 对已授权且符合准入规则的计划，调用 `research data ingest --plan-id <ID> --apply --json`。候选、合同或计划变化时重新校验和必要复核，不复用旧批准。
6. 保存入库文件清单和回执。工作区入库、Git 提交、远端同步分别报告；提交推送遵循当前任务授权，不使用无差别 git add -A。

输出准入结论、复核范围、入库引用，或未解决事项及所需证据。没有独立复核能力时明确限制。

验收：计划值不会进入实际值；复核后的候选变动使旧计划失效；不合格批次不能入库；部分覆盖如实显示。
