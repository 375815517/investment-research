# 小米与腾讯：2025 年 10 月、2026 年 10 月截至 29 日的监管市场输入

范围为小米 01810、腾讯 00700 的指定 HKD 柜台。这里只登记来源报告的输入值，不生成指标或预测，也不将卖空成交额、须申报淡仓解释为全市场多空持仓比例。

## 来源与预期清单

- SFC 官方汇总淡仓索引发现 9 个报告日期：2025-10-03/10/17/24/31，2026-10-02/09/16/23。每公司每期收集须申报淡仓股数和 HKD 金额，共 36 个精确键。原始 CSV 以单份归档供两个 binding 使用。报告日期是观察日，不是已证明的发布时间。
- HKEX 每日行情报告中的当日 `short_selling` 段，每公司每交易日收集卖空股数、卖空成交额、同柜台总成交股数、总成交额。严格排除随后 `adj_short` 前日调整段。预期 2025-10 共 20 日，2026-10 截至 29 日共 19 日，共 312 个精确键。
- HKEX 日期分母来自已有 XHKG 会话模型和政府假日、交易时段证据，完整日期见 `hkex-expected-sessions.json`。该模型不等于每一天异常停市的独立官方核实；若后续取得异常停市证据，应提交版本化清单修订，不能静默缩小分母。

## 执行证据与结果

`*-acquisition.json` 保存发现、任务及逐项取得情况；原始任务中的 HTTP 失败保留，不自动循环重试。仅对已经取得的 HKEX 4 日（2026-10-02、15、28、29）另建可用项审核任务。`*-reviewed.json` 保存对原始数字列的独立检查和审核，`*-final.json` 保存恢复准入状态。之前的 STALE_PLAN 是并行写入导致的仓库版本保护，后续串行恢复，不跳过准入门禁。

两家公司 SFC 的 9 期均完成正式准入；13 份独立 CSV/HTML 原件合计 87,761,242 bytes，由两个证券 binding 共用，详见 `shared-originals.json`。

本次正式核验结果：SFC **36/36** 个预期输入键齐备；HKEX **32/312** 个键齐备，缺 **280** 个键（35 个交易日 × 2 公司 × 4 字段）。2025 年 10 月全 20 日缺失，2026 年 10 月另 15 日缺失。两家公司可用的 4 日均已审核准入。

最终精确结果以 `coverage-summary.json`、`*-exact-coverage.json` 与 `*-purpose-assessment.json` 为准。所有缺期保留在预期 profile 内；不能将有限可取样本表述为完整月份。HTTP 失败表示本轮接口取得失败，不证明历史数据不存在，也不能推断未报告等于零。

## 稳定复用入口

- Provider：`research/source-providers/sfc-weekly/provider.yaml`、`hkex-daily/provider.yaml`。
- Binding：`research/source-bindings/{sfc,hkex}-{xiaomi,tencent}/binding.yaml`。
- 精确输入合同：`research/input-profiles/market-window-{sfc,hkex}-2025-2026/v1.json`。
- 固定解析器：`sfc-short-positions-v1`、`hkex-daily-turnover-v1`。
- 使用公共 `source_discover → acquisition_plan → acquisition_run → review → profile_audit/profile_assess` 操作；跨对象只切换 binding，不能将公司代码固化到解析器。
- `reuse_archived:true` 明确复用已归档版本，执行 hash 校验，降低重复下载；不声称检查过远端修订。

原始附件、索引证据、报告数字、任务事件、覆盖 profile 和检查结果均由 Git 跟踪。发布时间缺少证明的输入只能用于回溯说明，不能因为今天取得历史 CSV 就认定在过去已可知。
