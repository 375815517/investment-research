# 决定004：可复用输入合同与稳定组织

日期2026-10-30，用户批准A–F实施范围。维持apps/packages/research/data/ai顶层结构，不另设第二工作空间或事实库。

- domain定义合同，engine组织准入、覆盖、转换和任务；repository负责不可覆盖文件与版本；connectors隔离提供方差异；apps不实现计算规则。
- financial-facts v1继续可读，financial-observations v2同属companies/<id>/financials；operating-observations置companies/<id>/operations；新批次不移动或重写旧批次。
- corporate-actions属markets/corporate-actions，benchmark-prices属markets/benchmarks；指数点位和股票货币报价分开。
- research/metrics/<metric>/vN.json与research/units定义单一权威语义；research/input-profiles/<id>/vN.json保存精确输入需求；旧coverage-policies保留兼容样本审计，不冒充精确需求。
- source-providers保存提供方能力，source-bindings保存对象映射；旧sources兼容，不为每份下载文档复制引擎代码。原件按内容单份归档，候选另保留提取binding身份。
- 原件公开时间更正追加metadata-revisions；原始document.json不改。事件期间、公开可知和系统首次观察独立，历史重建与实时模式分别选择。
- v2业务键使用显式语义字段和dimensions；自由说明basis不是另开一条同源业务记录的理由，修改说明需显式修订。旧market-observations键保持历史兼容，不暗中迁移。
- 输入包、转换记录、采集任务及恢复证据归入data/outputs/research-records；本机索引/缓存非权威，干净克隆应可验证和恢复。
- 统一Service operation只作路由，新算法分别在profiles/transforms/bundles/acquisition/temporal模块。新公司不能作为引擎条件分支。

工程通过、数据覆盖和某用途ready分别报告。外部源缺失不造零，未完成的A–F事项不能只因写了说明就标完成。
