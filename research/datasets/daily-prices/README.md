# 日行情与来源口径

结构唯一来源为 `investment_domain.DailyPrice`，可通过 CLI schema 导出；本目录描述业务语义，不手工复制第二套机器 schema。

| 字段 | 含义 |
| --- | --- |
| security_id | 已确认证券的稳定 ID，不是公司简称 |
| trading_date | 该市场交易日期 |
| open/high/low/close | 同一交易时段、币种和明确标记口径的价格 |
| volume | 来源成交量；单位未知不自动当股数 |
| currency | 三字母币种 |
| volume_unit | shares 或 provider-native（单位未核实） |
| price_basis | unadjusted 或 provider-native（调整方法未核实） |
| session | 当前只接受 regular-final |

数值使用 Decimal，要求有限且价格大于零、成交量非负、OHLC 顺序成立。CSV 不接受未知列。详见[兼容扩展决定](../../../docs/decisions/002-source-observations-and-coverage.md)。来源、原件版本和时间资格由采集/文档/批次记录关联。

供应商原生 quote 不因没有使用 adjclose 就默认是未复权价。Yahoo/Tencent 原始观测明确标为 provider-native。查询默认 unadjusted，必须显式选择 provider-native 才返回该类观测；不能满足未复权需求。完整交易日覆盖、公司行动与正式收盘需结合可信来源核实；初版结构检查不能替代这部分事实验证。合成样例不构成真实证券资格确认。

原始响应在 source-files，实际行情在封版路径中，以 daily-prices.csv 和 batch.json 成对登记。
