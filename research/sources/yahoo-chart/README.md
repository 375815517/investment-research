# Yahoo Finance chart 候选来源

已在本环境对 `1810.HK`、2026-10-19 至 2026-10-24 的有限区间进行公开接口探测，返回 4 个交易日期，币种 HKD、场所 HKG、时区 Asia/Hong_Kong。这个观察只证明检查时该请求有响应，不证明完整历史覆盖或长期可用。

连接器 `yahoo-chart-v1` 保存 JSON 原件并提取 `indicators.quote` 的来源原生数值。未使用 `adjclose`，但这仍不证明其历史拆股处理完全符合未复权定义。因此候选固定为 `price_basis: provider-native`，当前 `daily-prices` 的严格未复权合同会拒绝正式准入。

来源归档权限尚未核实，配置 `archive_permissions: unknown`，常规 collect 会明确阻断。已有公开探测原件可用于单独记录来源研究证据；不得把这个示例视为归档或再分发许可。真实自动采集前需核实来源约定、调整口径、日历和公司行动覆盖。

拟定参数：`symbol`（例如 1810.HK）、`period1`/`period2`（Unix 秒，结束边界按供应商约定）、`interval: 1d`、`events: div,splits`。security_id 由应用请求传入，不写死为小米。该来源配置可以用于其他已确认标的，不另建公司专用连接器。
