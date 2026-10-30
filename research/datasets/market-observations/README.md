# 有口径的市场观测

供应商或官方报告的估值、股份、成交与淡仓观测；来源值不是平台计算的投资因子。

可执行合同唯一来源为 `investment_domain.MarketObservation`，用 `research schema MarketObservation --json` 导出。统一走 prepare → validate → review → ingest。结构与原文摘录匹配不代替语义复核。

观测时间必须二选一：来源纯日期 observed_date，或带时区时刻 observed_at（规范为UTC，日期筛选按UTC日）。采集快照必须在basis中明确，不冒充该统计值真实生效日。

| 类别 | 口径要求 |
| --- | --- |
| short_sale_volume/turnover | 股数/金额，交易流量；早盘与全日分开 |
| reported_short_position/value | 须申报淡仓股数/市值，监管申报群体；不是全市场净空头 |
| pe_provider/pe_ttm/pe_static | 保留供应商名称与利润口径；负PE不能被正数约束错误删除，供应商值不冒充平台重算 |
| issued_shares/free_float_shares | 股类和有效时点；授权股数、已发行股数、自由流通、公众持股和CCASS持仓不同 |
| 各类ratio | ratio/percent单位明确；分母定义、期间、市场、股类和原件必须绑定，未来分母不进入旧截止点 |
| volume/turnover | 分别为量与额；未核实量单位仅volume允许provider-native，不能用OHLC乘成交量造金额 |

`record_kind=source_reported`；不接收AI猜测或现场心算的比率。未知数据若来源明确未披露，可有证据地登记null/not_disclosed；本系统未找到来源应进入获取缺口清单，不伪造为来源声称未披露。多头比例不能由1减卖空比例得到。

业务键包含证券、时间、字段、basis、时段、单位、币种、股类与分母身份；来源隔离。相同瞬间不因时区不同而重复计数。无历史完整性基准的新类返回unknown，不将存在若干行视为时序齐全。
