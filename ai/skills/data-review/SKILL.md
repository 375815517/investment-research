---
name: data-review
description: 核查原始与整合数据的证据和口径，处理待审核候选并准入，随后复查缺口是否真正关闭。
---

先读 [输入基线](../../../docs/architecture/input-data-baseline.md)、[共同证据规则](../../rules/research-evidence.md) 和 [数据闭环约定](../../rules/data-completion.md)。结构校验通过不等于语义正确，AI 置信度不作为准入依据。

1. 读取 ensure-apply 或 detect-gaps 的问题记录，区分 processing_required、review_required、blocked、unknown_expectation 和 historically_unavailable。未知/阻塞问题不能通过 review 的批准开关消除。
2. 使用 `research data validate --candidate-id <ID> --json` 查看实际检查。回到原件核对主体、期间、单位、合并范围，以及目标、来源声明和实际披露的区别。
3. 按 `research data review --request review.json --json` 登记核实证据、复核者、方式及结论。自我复核如实标记；没有证据不能写 approved。复核必须绑定实际候选摘要。
4. 通过 `research data ingest --candidate-id <ID> --dry-run --json` 检查写入计划；仅在满足数据集准入且授权范围内使用 `research data ingest --plan-id <ID> --apply --json`。内容改变使旧复核/计划失效时，重新校验和复核。
5. 再次执行 `research data detect-gaps --request gaps.json --json`，核对原需求范围是否完整。部分合格数据可以保留，但不能把整个请求称为 complete。
6. 记录整合批次、复核依据、复查结果、未决问题。工作区入库、Git 提交、远端同步分别说明；不自动提交，不使用无差别 git add -A。

验收：期望清单缺依据时仍然未知；只有PDF没有字段记录时仍有处理缺口；错误单位和计划值不能进入实际值；审核后修改候选不能复用旧批准。

## 多源输入约束

遵循 [多源输入与金融口径](../../rules/multi-source-inputs.md)：先固定需求清单与逐渠道覆盖，再获取和复查。付费、不可取得、未检索与覆盖未知不能改写为无数据或已完成。来源陈述、已核实事实和AI推断分开；PE、股类、卖空成交和须申报淡仓按各自定义保存，不能用 `1-short` 推导多头比例。

## 新资料数据集的执行边界

`document-facts` 与 `market-observations` 使用 `prepare → validate → review → ingest`，以 `coverage` 读取已准入记录，再人工核对原始有限需求清单；目前不支持这两类的 detect-gaps/ensure 自动完整性判断。不得将 coverage 的 available 解释为全量完整，不得为套用 ensure 把新资料伪装成 financial-facts。

DocumentFact 只允许 source_assertion，表示来源陈述；管理层目标、政策预期、传闻和AI推断不能标为已实现事实。MarketObservation 只接受 source_reported：`not_disclosed` 需来源证据、null 值和 missing_reason；平台没找到资料应记渠道缺口，不能伪造来源未披露记录。实际字段以 schema 为准，所有新类均需复核。来源PE不代表本平台计算估值。

有限需求清单可调用 `research data audit-inputs --request requirements.json --json`：请求包含 requirements 数组，每项 dataset_id、subject_id、start、end 及 minimum_records（默认1），可按 source_id、metric_id、document_kind 或 price_basis 筛选；历史模式在顶层声明 knowledge_mode 和 information_cutoff。该操作仅检查声明的样本/记录需求，不能证明全网渠道完整；市场 null 值不满足数值需求，不能把取得缺失说明算取得值。渠道未得原因仍单独保存。

批准 document-facts 时 review 请求必须显式设置布尔字段 `statement_consistency_checked: true`，前提是已回原文逐项核实 statement 与 excerpt 的一致性；不能仅在 notes 中写同名字串，也不能把此字段当自动勾选项。该确认只证明摘要忠实表达原文，不证明来源主张已独立证实。

## 数据适用性检查

遵循[数据适用性规则](../../rules/data-fitness.md)。先固定问题、用途、期间及所需维度，再查看 coverage、执行有限需求 audit-inputs，随后用同一需求调用 assess-inputs；实际命令与 schema 以 capabilities 为准。source_description、historical_point_in_time、quantitative_comparison 分别评价，不把 ready 泛化为所有研究均可用。报告限制及未覆盖的人工检查，保留原始需求与缺口。详细[设计与请求示例](../../../docs/plans/data-fitness-assessment.md)。

新闻/政策样本数不是全网完整率，四个损益字段不是完整基本面，须申报淡仓不是全市场多空分布。口径未知、缺历史公开时间或匹配分母时，不让 AI 补造数值；补采后重新评估并保存新结果。
