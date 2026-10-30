---
name: data-acquisition
description: 使用已声明的工具获取或导入原件，准备可核查候选数据，保留采集范围和证据。
---

先读 [输入基线](../../../docs/architecture/input-data-baseline.md) 和 [共同证据规则](../../rules/research-evidence.md)。行情细则见 [行情指南](../market-data-acquisition/SKILL.md)，文档细则见 [证据检索指南](../evidence-retrieval/SKILL.md)。

1. 执行 `research capabilities --json`，确认当前数据集、解析器和操作。获取能力缺失时不能报告采集成功。
2. 根据来源合同使用已支持接口，或由宿主工具取得文件。浏览器/人工下载文件同样通过 `research data import --request import.json --json` 进入归档；具体字段读取 schema，不自行拼正式存储路径。
3. 保存返回的 document、collection 和 operation 引用。检查实际取得范围、部分成功与失败；采集成功不代表结构化数据合格。
4. 调用 `research data prepare --request prepare.json --json`。稳定格式使用已登记解析器；AI 提取采用候选协议，保留原文值、单位、期间、主体、原文定位和歧义，不能把估计或目标登记成实际事实。
5. 调用 `research data validate --candidate-id <ID> --json`，把问题交给数据核验流程。原件保留，未通过的候选不直接入库。
6. 中断时使用 `research operation status <ID> --json` 检查真实状态；只有返回的 next_actions 明确支持续跑时调用 resume。不要重复执行结果未知的写入。

不在此步骤自动提交或推送 Git。输出原件与候选引用、覆盖、失败/歧义和下一步；大文件只引用，不全部填入聊天。

验收：重复导入原件不重复归档；多证券响应保留一份原件；错误页面不当作行情；AI 对单位不确定时保留待核实项。
