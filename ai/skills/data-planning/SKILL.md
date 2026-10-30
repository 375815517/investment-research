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
