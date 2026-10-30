# 数据适用性评估：有限规则与研究判断

本次把“采集成功”和“可以分析”分开处理。领域合同为 `AssessInputsRequest`，共享执行操作为 `assess_inputs`；CLI/API/网页共用执行层。它不是投资评分、预测模型或无界事实核查器。实际通过的测试和小米结果见最新验收记录，本文解释规则及使用方式。

## 数据闭环新增一环

需求与用途 → 来源获取 → 原件归档 → 候选提取 → 校验与复核 → 正式入库 → coverage/audit → assess → 问题处理与再次评估。

`coverage` 回答当前查询可见哪些记录；`audit-inputs` 回答声明的最低样本需求是否满足；`assess-inputs` 回答这些样本用于所声明用途时有哪些确定性限制。三者不能互相替代。需求清单属于研究资产；实际评估结果、输入引用和改进记录属于研究记录，纳入 Git。修订追加，不能为了获得 complete/ready 删除原始需求。

## 请求与结果

`AssessInputsRequest` 继承 `AuditInputsRequest`，保留 requirements、knowledge_mode 和 information_cutoff，增加 purpose：

| 用途 | 含义与边界 |
| --- | --- |
| source_description | 描述归档来源实际提供的内容；不承诺来源主张独立属实 |
| historical_point_in_time | 在历史 cutoff 和 knowledge_mode 下判断可用性；不允许事后解释模式代替历史研究 |
| quantitative_comparison | 检查已知单位、价格基准、口径和股类冲突；无冲突也不等于全部语义等价已认证 |

调用前用 `research capabilities --json` 与 `research schema AssessInputsRequest --json` 检查当前安装版本。以已取得样本为例，复制 `research/coverage-policies/xiaomi-multi-source/acquired-samples.json` 的请求内容并增加 `"purpose": "source_description"`，保存独立请求，再执行：

```bash
research data assess-inputs --request assessment-request.json --json
```

历史用途必须同时选择 historical_reconstruction 或 live_observed，并提供带时区的 information_cutoff。历史重建允许今天补录有当时公开证据的资料；live_observed 还要求平台在当时已观察到。公开时间由导入者声明，过滤通过不能升级为历史发布记录已独立认证。

结果包含 status、purpose、scope、audit、observations、findings、dimensions、limitations、artifact_refs、next_actions。每条 finding 包含 code、dimension、severity、requirement_index 和 evidence_refs；next_actions 是需处理的问题代码，不是已执行补采动作。

- ready：所声明的有限用途未命中阻断或警告；不等于全历史齐全、经济真实性认证或可做所有分析。
- limited：存在需随分析展示的限制；不能隐去警告后当作无条件可用。
- blocked：样本需求未满足或存在该用途不允许的口径问题。可保留合格输入，不能宣称原任务已就绪。

## 已实现规则的覆盖

| 维度 | 确定性检查 | 仍需独立判断 |
| --- | --- | --- |
| 文件完整性 | 通过共享仓储读取并校验归档原件、批次摘要 | 网站身份、披露真伪、经济真实性 |
| 声明需求覆盖 | 使用 audit 的实际可见记录，缺最低样本即阻断 | 交易日历、报告全集、全网新闻/政策总体；full_history 与 source_population 保持 not_assessed |
| 时间 | 继承 cutoff 与知识模式筛选；未知发布时间提示 | 历史发布记录认证、重述与原始版本身份 |
| 可比性 | provider-native 价格/量、供应商PE、同指标混合单位/交易时段/股类/来源基础等提示或阻断 | 所有会计及统计定义的语义等价、公司行动、汇率和基准选择 |
| 来源可靠性 | 单源范围、多源独立性未知、文字记录仅为来源主张 | 独立交叉确认、转载根源、代表性与因果 |

数量化用途遇到未核实价格或量单位、供应商PE方法未标准化、混合计量基础、以文字声明替代数值样本时阻断。股份观测提醒核对同日同股类分母。缺需求始终阻断，不因其他维度表现好而抵消。没有主观综合质量分，避免把不同类型缺口平均掉。

## 小米当前用途判断

当前四个年度损益字段可以描述已核对的披露值，但不构成完整基本面数据。资产负债、现金流、归母利润/EPS、分部及历史原始发布版本都需另设需求；年度利润不能代替归母利润计算PE。行情来源口径尚未核实的部分不能直接宣称可计算可比总回报。少量政策、新闻和行业资料可支持有引用的来源描述，不能代表全网舆情或长期竞争格局。

须申报淡仓、卖空成交、买方成交、多头持仓不是同一总体。分布还需总体、计量单位、时间粒度、分箱/加权方法与披露门槛；总量记录不支持持仓分布。流通比必须说明自由流通、公众持股或已发行股本中的哪一种及对应股类。来源缺失与定义未定分开报告，不生成互补比例或伪精确数值。

## 系统化改进顺序

1. 证据/提取问题：隔离错误候选，核对原件并新增修订；归档数据不直接覆盖。
2. 口径问题：补来源定义、股类、期间和计量依据；未知值保留未知，不能凭显示格式猜单位。
3. 覆盖问题：先固定可信预期清单，再补期、补字段、补原始版本；无全集依据则保持覆盖未知。
4. 使用问题：在研究问题、数据需求和用途矩阵中记录阻断原因；有界子研究使用独立请求，不改变原任务验收要求。
5. 复查：执行同一 audit/assess、保存新结果与引用，记录已解除和仍存在的问题。

本轮新数据类的有界获取、准入、查询及适用性检查，不等于所有历史渠道自动发现、自动补采或语义独立核验已完成。AI 应遵循[共同适用性规则](../../ai/rules/data-fitness.md)，不得把未实现能力写成已运行结果。
