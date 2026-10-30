# 财报直接披露事实

结构唯一来源为 `investment_domain.FinancialFact`，配置仅引用该模型。AI 或人工提交候选后须验证原件定位，并完成绑定候选摘要的语义复核；并非 JSON 合法即可入库。

候选字段为 company_id、metric_id、period_start、period_end、source_value、source_unit、currency、scope、record_kind、locator、excerpt。source_unit 仅接受 units/thousands/millions/billions；scope 区分 consolidated/standalone；record_kind 当前仅接受 reported_actual。

本合同保留原文数值与单位，不擅自把累计变单季、目标变实际或把分部重新分类。期末早于期初、无穷数值、指引和估计身份不符合此合同。其他经营/政策/预期应另定义专用合同，不能塞入财务事实表。

当前原文自动检查以可读取文本证据为主；PDF/OCR 的页码和表格语义仍需专门提取器及人工/Agent 核实，不宣称已自动完成全部财报解析。
