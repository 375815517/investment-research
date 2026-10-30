---
name: data-acquisition
description: 按固定的补齐计划获取原件并整理候选数据，保留覆盖和失败记录，最后重新检查缺口。
---

先读 [输入基线](../../../docs/architecture/input-data-baseline.md)、[共同证据规则](../../rules/research-evidence.md)、[数据闭环约定](../../rules/data-completion.md)。行情细则见 [行情指南](../market-data-acquisition/SKILL.md)，文档细则见 [证据指南](../evidence-retrieval/SKILL.md)。

1. 使用 data-planning 获得 detect-gaps 结果和 `research data ensure-plan --request ensure.json --json` 的固定计划。检查其来源、对象、区间、期望依据、预估动作和阻断项。
2. 对当前任务已授权且可执行的计划，调用 `research data ensure-apply --request apply.json --json`；apply.json 只提交 plan_id。计划失效时重新规划，不自行编辑计划或自动换来源扩大范围。
3. 获取与整理结果分别判断。complete 需要随后缺口复查确认；partial、blocked、review_required 保留真实状态。已有原件但缺解析能力时进入处理任务，不重复下载冒充补齐。
4. 若需人工/宿主获取原件，使用已支持来源或浏览器取得文件后经 `research data import --request import.json --json` 归档；保存实际来源和时间。不直接写正式业务目录。
5. 对需要语义提取的资料，使用 `research data prepare --request prepare.json --json` 提交原文值、单位、期间、主体、定位和歧义。`research data validate --candidate-id <ID> --json` 返回需复核时交给 data-review；ensure 不自动批准 AI 候选。PDF 定位必须为 `pdf:page:N`（从1起的物理页码），excerpt 必须来自该页，并进入后续复核。JSON 行情必须从归档原件经固定解析器提取，不提交 AI 编写的 records 替代报价。
6. 中断先执行 `research operation status <ID> --json`；仅按真实 next_actions 续跑，结果未知先查回执，不反复 apply。
7. 用原需求再次执行 `research data detect-gaps --request gaps.json --json`。只有满足明确期望的复查结果才能称为数据准备完成；原件下载、格式正确和正式记录齐全是不同状态。

不自动提交或推送 Git，不触发指标、预测、复盘或定时任务。输出请求/计划、原件与整合批次引用、复查结果及仍未解决的缺口。

验收：重复补齐不产生重复事实；错误页面不能当作行情；需审核不能被重复 apply 绕过；部分范围成功与剩余缺口同时保留。
