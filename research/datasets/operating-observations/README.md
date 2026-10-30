# 经营观测

合同唯一机器定义为`investment_domain.OperatingObservation`，可用`research schema OperatingObservation --json`查看。正式记录分区：`data/inputs/companies/<company>/operations/<year>/<batch>`。

用户、出货、设备、交付等非货币量使用明确单位及产品/地区/统计总体；观察窗口未知时不补猜开始日期。

沿共享prepare/validate/review/ingest流程；只有明确复核后的候选可以准入，原件和旧批次不覆盖。精确需求与比较组见research/input-profiles及决定004。
