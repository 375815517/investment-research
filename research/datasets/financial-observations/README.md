# 维度化财务观测

合同唯一机器定义为`investment_domain.FinancialObservation`，可用`research schema FinancialObservation --json`查看。正式记录分区：`data/inputs/companies/<company>/financials/<year>/<batch>`。

共享指标字典约束货币、每股、存量/流量、期间与分部；原始披露值与转换值分开。

沿共享prepare/validate/review/ingest流程；只有明确复核后的候选可以准入，原件和旧批次不覆盖。精确需求与比较组见research/input-profiles及决定004。
