---
name: data-planning
description: 将研究需求转换为对象、数据集、期间和来源缺口；在获取前检查实际工具能力与输入合同。
---

先读 [输入基线](../../../docs/architecture/input-data-baseline.md) 和 [共同证据规则](../../rules/research-evidence.md)。本 Skill 组织工作，程序承担字段、路径和准入判断。

1. 执行 `research doctor --json`、`research capabilities --json`。不把配置存在当成来源已接通，不调用 capabilities 未声明的能力。
2. 明确对象、期间、信息截止点及三种知识模式之一。首次实际企业建档按基线确认主证券；已有确认直接读取。离线样本必须保留 demo 身份。
3. 使用 `research schema --help` 获取合同查询方式，读取真实 schema。使用 `research data coverage --request request.json --json` 查询已支持数据集的覆盖。业务时间和公开时间分别处理。
4. 产出数据需求清单：对象、所需数据集、期间、来源候选、已有覆盖、缺口、可执行步骤和未实现能力。来源选择不应隐式改变统计口径。
5. 可用来源交给数据获取流程；缺连接器时明确记录接入任务，或使用宿主已有工具取得原件后通过统一 import 导入。不临时绕过归档写 data/。

输出是计划与可执行请求，不是虚构数据或预测。数据集字段和质量规则只引用 research/datasets，不在本 Skill 重复定义。

验收：来源未配置时报告缺口；缺少历史预期时不声称能判断超预期；历史重建不冒充当时实时采集。
