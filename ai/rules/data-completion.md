# 原始与整合数据准备闭环

范围限于原始资料、标准化事实、资料关联和覆盖核实；本阶段不启动指标、预测、复盘、定时任务。输入目录遵循 [输入基线](../../docs/architecture/input-data-baseline.md)。

先按 [多源规则](multi-source-inputs.md) 固定需求清单与候选渠道。各类输入逐项复查；未知总体范围不能以有限样本称全量。

## 固定流程

`detect_gaps → ensure_plan → ensure_apply → detect_gaps`，CLI 使用连字符子命令。detect 是缺口判断，ensure-plan 固定需求和动作，ensure-apply 在同一合同下执行，最后的 detect 是完成验收。没有可验证期望时不计算伪完整率。

| 返回含义 | AI 应如何处理 |
| --- | --- |
| complete | 已满足工具明确检查的期望范围；报告范围与依据，不外推为全量完整 |
| partial | 保存已完成部分，逐项报告剩余缺口 |
| unknown_expectation | 缺可靠日历、披露或字段期望，先补依据；不能当成没有缺口 |
| processing_required | 已有原件但未形成所需整合数据；安排解析/提取，不重复下载冒充完成 |
| review_required / needs_review | 仍需证据与语义核实；ensure 不自动批准 |
| blocked | 按错误码报告来源、认证、口径或合同问题；不凭猜测绕过 |
| historically_unavailable | 当时实际未取得的信息不能由今天补采修复；保留历史缺口 |

具体状态可能位于 status、coverage 或 issues 中，应按当前 schema 读取，不用自然语言摘要替代机器状态。缺口报告不等于金融分析结论。

## 期望、计划与证据

- 证券身份采用已确认映射。交易日期须来自有证据的交易日历；不能简单排除周末后声称准确交易日。
- 财务/经营所需字段与披露期望须记录原件/合同依据；文件存在不等于字段覆盖，字段有值不等于已核实。
- ensure-plan 的 acquisition 必须明确 source_id 与有界 parameters。不得自动遍历所有来源、扩大日期或更换统计口径。
- plan_id 绑定请求、期望、来源与基准。发生变化后重新规划；不能在聊天中重新解释旧 plan_id 后继续执行。
- 未准入候选保留审核状态；不把外部观点、公司愿景或本项目推断变成实际观测。
- 最后复查与起始需求使用相同范围、知识模式和期望版本；如需改变需求，明确另立计划，不能缩小范围制造完成。

## 宿主验证

根入口、Skill文件存在、显式读取执行、原生自动发现、Hook触发分别验证。`investment_ai.probe` 仅记录显式读取与只读 CLI 调用；native_discovery 保持 not_tested。实际会话使用该路径可以报告‘本次 Codex 显式调用已执行’，不能外推为所有宿主版本均支持。

所有工具返回实际结果；无实现、无凭据、未知状态和失败须如实报告。不要为成熟、已授权的数据操作重复索要批准；实质对象或口径歧义才需要用户决策。

## 新资料数据集的执行边界

`document-facts` 与 `market-observations` 使用 `prepare → validate → review → ingest`，以 `coverage` 读取已准入记录，再人工核对原始有限需求清单；目前不支持这两类的 detect-gaps/ensure 自动完整性判断。不得将 coverage 的 available 解释为全量完整，不得为套用 ensure 把新资料伪装成 financial-facts。

DocumentFact 只允许 source_assertion，表示来源陈述；管理层目标、政策预期、传闻和AI推断不能标为已实现事实。MarketObservation 只接受 source_reported：`not_disclosed` 需来源证据、null 值和 missing_reason；平台没找到资料应记渠道缺口，不能伪造来源未披露记录。实际字段以 schema 为准，所有新类均需复核。来源PE不代表本平台计算估值。

有限需求清单可调用 `research data audit-inputs --request requirements.json --json`：请求包含 requirements 数组，每项 dataset_id、subject_id、start、end 及 minimum_records（默认1），可按 source_id、metric_id、document_kind 或 price_basis 筛选；历史模式在顶层声明 knowledge_mode 和 information_cutoff。该操作仅检查声明的样本/记录需求，不能证明全网渠道完整；市场 null 值不满足数值需求，不能把取得缺失说明算取得值。渠道未得原因仍单独保存。
