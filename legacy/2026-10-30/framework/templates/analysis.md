# {{company}}：{{title}}

## 研究问题与结论

尚未形成结论。注明决策期限、信息截至日期和信心。

## 关键事实

将结构化数据写入 facts.csv；说明期间、单位、口径、原始来源与复核状态。

## 主营业务、竞争与海外

逐业务比较需求、份额、价格、成本、渠道与资本回报。

## 成长来源与情景

区分行业增长、份额变化、产品结构和新业务。详细假设写入 assumptions.md。

## 估值与价格隐含预期

核对股价时点、稀释股本、汇率和利润口径。没有数据时保留待验证，不填入假精确目标价。

## 反证与下一步

列出最可能推翻判断的证据、观察时间与来源。新观察追加 verification.md，后续结果写入 retrospective.md。
# 证据与计算交付要求

核心判断对应 claims.csv，列出事实ID、支持/反对证据和失效条件。facts.csv至少记录fact_id、metric、period、value、unit、source_id、locator、kind（disclosed/company_guidance）。保存inputs中的行情与证据版本；runs中保留parameters.json、results.csv、manifest.json。未来验证未到期，不填实际结果。

