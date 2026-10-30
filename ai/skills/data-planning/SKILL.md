---
name: data-planning
description: 围绕原始与整合数据需求检查工具能力、来源及有证据的期望范围，识别可补齐、未知、阻塞和需处理的缺口。
---

先读 [输入基线](../../../docs/architecture/input-data-baseline.md)、[共同证据规则](../../rules/research-evidence.md) 和 [数据闭环约定](../../rules/data-completion.md)。本流程只处理数据准备，不执行指标、预测、复盘或定时任务。

1. 执行 `research doctor --json`、`research capabilities --json`。只有工具实际声明并接受的合同才可执行；缺少 detect_gaps/ensure 能力时报告版本缺口。
2. 固定对象、数据集、区间、知识模式和截止点。读取已有主证券确认，不重复询问。样本保留 demo 身份，不能混入正式数据。
3. 检查所需的交易日历或财务披露/字段预期是否有可追溯依据；`expectation_path` 由程序校验。不能按周一至周五猜交易日，不能凭经验假定公司某日应披露某字段。无可靠预期时允许查询返回 unknown_expectation。
4. 调用 `research data detect-gaps --request gaps.json --json`。请求由当前 schema 定义，包含 dataset_id、subject_id、start、end 和期望依据；如适用还需 source_id、price_basis、information_cutoff、knowledge_mode、as_of。price_basis 默认 unadjusted；来源仅能保证原生报价时显式使用 provider-native，禁止为达到齐全而改称未复权。
5. 分别报告：已可用、可获取缺口、已有原件待整理、待审核、来源阻塞、预期未知、历史不可补救。只把可执行缺口交给获取流程，不把未知范围写成零条缺失。
6. 需补齐时使用 `research data ensure-plan --request ensure.json --json` 固定需求与来源动作。acquisition 是显式有界请求，参数必须来自来源合同；不扩展到全站、全市场或未知时间范围。

交付缺口结果、期望依据、计划 ID、阻断原因与下一步。计划不等于数据已齐全。正式路径由工具决定，不在 Skill 拼接路径。

验收：没有可靠日历时报告未知；财报原件存在但必要字段未整合时报告处理缺口；live_observed 的历史未持有信息不能通过今天下载变成当时已知。

## 多源输入约束

遵循 [多源输入与金融口径](../../rules/multi-source-inputs.md)：先固定需求清单与逐渠道覆盖，再获取和复查。付费、不可取得、未检索与覆盖未知不能改写为无数据或已完成。来源陈述、已核实事实和AI推断分开；PE、股类、卖空成交和须申报淡仓按各自定义保存，不能用 `1-short` 推导多头比例。

## 新资料数据集的执行边界

`document-facts` 与 `market-observations` 使用 `prepare → validate → review → ingest`，以 `coverage` 读取已准入记录，再人工核对原始有限需求清单；目前不支持这两类的 detect-gaps/ensure 自动完整性判断。不得将 coverage 的 available 解释为全量完整，不得为套用 ensure 把新资料伪装成 financial-facts。

DocumentFact 只允许 source_assertion，表示来源陈述；管理层目标、政策预期、传闻和AI推断不能标为已实现事实。MarketObservation 只接受 source_reported：`not_disclosed` 需来源证据、null 值和 missing_reason；平台没找到资料应记渠道缺口，不能伪造来源未披露记录。实际字段以 schema 为准，所有新类均需复核。来源PE不代表本平台计算估值。

有限需求清单可调用 `research data audit-inputs --request requirements.json --json`：请求包含 requirements 数组，每项 dataset_id、subject_id、start、end 及 minimum_records（默认1），可按 source_id、metric_id、document_kind 或 price_basis 筛选；历史模式在顶层声明 knowledge_mode 和 information_cutoff。该操作仅检查声明的样本/记录需求，不能证明全网渠道完整；市场 null 值不满足数值需求，不能把取得缺失说明算取得值。渠道未得原因仍单独保存。

## 数据适用性检查

遵循[数据适用性规则](../../rules/data-fitness.md)。先固定问题、用途、期间及所需维度，再查看 coverage、执行有限需求 audit-inputs，随后用同一需求调用 assess-inputs；实际命令与 schema 以 capabilities 为准。source_description、historical_point_in_time、quantitative_comparison 分别评价，不把 ready 泛化为所有研究均可用。报告限制及未覆盖的人工检查，保留原始需求与缺口。详细[设计与请求示例](../../../docs/plans/data-fitness-assessment.md)。

新闻/政策样本数不是全网完整率，四个损益字段不是完整基本面，须申报淡仓不是全市场多空分布。口径未知、缺历史公开时间或匹配分母时，不让 AI 补造数值；补采后重新评估并保存新结果。

## 精确规格与可复用执行

按[可复用输入规则](../../rules/reusable-inputs.md)执行。优先使用已登记输入规格进行 profile-audit/profile-assess；原件、待提取、待复核、已准入和用途就绪分别报告。发现/任务/修订/冻结操作以当前 capabilities 和 schema 为准，所有写入经共享执行服务，不由AI直接改正式数据。
