# 基准指数

合同唯一机器定义为`investment_domain.BenchmarkPrice`，可用`research schema BenchmarkPrice --json`查看。正式记录分区：`data/inputs/markets/benchmarks/<benchmark>/daily/<year>/<batch>`。

指数点位与股票货币报价分开，价格指数与全收益指数不互换；来源原始点位与自算收益分开。

沿共享prepare/validate/review/ingest流程；只有明确复核后的候选可以准入，原件和旧批次不覆盖。精确需求与比较组见research/input-profiles及决定004。
