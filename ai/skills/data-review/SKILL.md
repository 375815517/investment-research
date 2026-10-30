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
