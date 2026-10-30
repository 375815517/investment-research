# 有证据的来源陈述

政策、新闻、行业报告、竞争与公司声明；记录来源说了什么，不把它升级为平台独立确认的因果事实。

可执行合同唯一来源为 `investment_domain.DocumentFact`，用 `research schema DocumentFact --json` 导出。统一走 prepare → validate → review → ingest。结构与原文摘录匹配不代替语义复核。

资料类别限定 policy、news_report、industry_report、competition_statement、company_statement。保存主体类型/ID、事件日期、可选生效区间、来源声明、定位与原文。批准需 `statement_consistency_checked: true`；核验声明是否忠于原文，不证明来源主张必然真实。HTML排除脚本和样式后核对可见文本，PDF使用物理页定位。

共享政策不复制到公司目录，也不能据泛行业政策直接登记小米受益。行业出货不等于零售、订单不等于交付、转载不构成独立来源。当前数值型行业资料保留在有证据陈述中，尚无统一行业数值表合同。

新类不使用行情交易日完整性：coverage说明已登记记录，audit-inputs仅检验明确样本需求；未实现全网政策/新闻完整性或无界自动发现。
