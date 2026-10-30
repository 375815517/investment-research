# 公司行动

合同唯一机器定义为`investment_domain.CorporateAction`，可用`research schema CorporateAction --json`查看。正式记录分区：`data/inputs/markets/corporate-actions/<security>/<year>/<batch>`。

公告、除权、生效、支付日期分开；proposed/approved/effected/cancelled必须明确，提议不能视为已实施。

沿共享prepare/validate/review/ingest流程；只有明确复核后的候选可以准入，原件和旧批次不覆盖。精确需求与比较组见research/input-profiles及决定004。
