# 对象与来源映射

每个binding包含binding_id、provider_id、subject_id，以及适用的security_id、source_symbol、currency或benchmark_id。公司身份、证券身份和指数身份分别保留。变量只用于注册URL模板，不承载任意调用者URL或认证值。

同一提供方可绑定多个已确认研究对象。来源格式变化在connectors中处理；通用任务、准入和查询不允许公司特判。归档许可、下载范围及参数边界由provider统一规定。

`parameters` 可绑定提供方使用的对象标识，例如 HKEX `stockId`；它与 provider 的固定检索参数共同进入请求，禁止运行时覆盖。它不等同于主证券交易代码，须由来源公开映射核实。共享原件按内容哈希只存一份，提取候选仍记录当前 `parser_source_id`，避免用最早归档对象的解析范围错误地处理后续对象。
