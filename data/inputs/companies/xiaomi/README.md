# 小米集团研究数据入口

主证券：港股 01810，HKD；用户确认记录位于 [profile](profile/2026-10-30-confirmed/company.json)。证券行情权威存储在 [市场行情目录](../../markets/prices/xiaomi-hk/)，不在公司目录复制。

- [年度财务事实](financials/2024/)：2024 年合并报表收入、毛利、营业利润、年度利润，CNY 百万元；来自官方年度业绩公告 PDF 第 2 物理页。
- [披露需求与原件引用](reporting-calendar/2024/2026-10-30-observed/expectations.json)：本次所需字段，不表示全部财务项目已提取。
- [行情覆盖依据](../../markets/calendars/hkex/2026/2026-10-30-observed/expectations.json)：2026-10-19 至 24；公众假期和周六排除，4 个交易日。
- [真实执行验收](../../../outputs/research-records/data-platform-closure-20261030/real-data-acceptance.json)：缺口、补采、复核、重复执行和历史限制。

行情价格与成交量均为 provider-native，调整方法和成交量单位未核实，不能替代未复权价格/股数。资料公开时刻尚未形成精确证据，严格历史截止点查询排除不符合条件的记录。无指标、预测或投资结论。

## 上市以来行情

已补取 2018-07-09 至 2026-10-29 的来源原始日行情，默认查询2048条，与XHKG日历模型对比无缺日。港交所确认2023-07-17休市，来源占位值保留在原件和历史批次，查询通过有证据交易状态排除。

[全区间核验记录](../../../outputs/research-records/xiaomi-listing-history-20261030/verification.json) · [政策、财报、舆情与竞争资料同步计划](../../../../docs/plans/xiaomi-historical-information.md)

## 多源资料与市场观测

[市场观测](../../markets/observations/xiaomi-hk/)包含来源PE、股份、卖空成交与须申报淡仓。[财务](financials/)新增2025年报中2021–2025历史汇总，非当年原始发布版本。[公司声明](statements/)与[媒体报道](../../events/company/xiaomi/source-statements/)保留来源身份。

共享资料：[中国政策](../../policies/jurisdiction/china/facts/)、[全球手机行业](../../industries/smartphones-global/facts/)、[竞争声明](../../events/industry/smartphones-global/source-statements/)。这些关联表示研究阅读范围，不证明小米享有某项政策资格或受益。

[完整验收及5项缺口](../../../../docs/verification/xiaomi-multi-source.md)。各期记录不相加混用；自由流通比例、全市场多头比例等尚未取得可靠值。

最新覆盖与用途判断见[数据适用性验收](../../../../docs/verification/xiaomi-data-fitness.md)：2018–2025年报原件已归档，52条财务来源观测、22条市场观测；完整性与历史可知性限制分别说明。
