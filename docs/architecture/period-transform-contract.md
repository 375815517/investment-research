# 期间转换合同与确定性函数

本模块属于输入整合的底层计算，不产生投资因子，不修改来源事实。接口为 `investment_domain.period_transforms.PeriodTransformRequest` 与 `investment_engine.period_transforms.transform_period`。**尚未注册为 Service/CLI/API 操作**；调用方负责从版本化指标目录解析 `MetricDefinition`、核验来源附件和批次版本，然后调用纯函数。

## 累计值转单季

`method=cumulative_to_quarter` 接收同一起点、不同终点的两个累计 flow。后值减前值，余下期间必须为三个完整连续月份，允许非自然年度财政季度。同公司、指标及版本、计量单位及尺度、币种、范围、维度、会计准则、口径、调整和重述状态均须相同。不同尺度需先进行已定义的尺度规范化，不能隐式转换。

EPS、比率、MAU、加权平均股本及其他 period_measure 均不可累计相减。差值可以是负的财务流量；物理计数或指标定义不允许负数时，负差值阻断。未知重述状态也阻断。

## 两时点存量平均

`method=endpoint_average` 仅接受两个严格递增时点的 stock，采用 `(期初值 + 期末值) / 2`。输出明确标为派生 period_measure、`endpoint_interval`，不是来源披露的平均数，也不是按时间加权的平均数。不会把该结果自动写回原指标或计算周转率等因子。

## 身份与证据

结果的 `derived_id` 是内容 hash，包含方法版本、指标定义及定义 hash、两个原始输入全文及各自 hash、来源 ID、附件 ID/hash、输入版本、元数据修订版本、期间和派生值。改变任何输入版本或口径会产生不同派生身份。来源值保持原样；纯函数本身不读取网络或声称验证了附件真实性。

`tests/test_period_transforms.py` 覆盖正例、版本身份、不同期间/单位/币种/范围基础不兼容、EPS/MAU/平均股本禁差分、不可知值、负计数与存量/流量混用。真实数据平台的规范化和冻结验收记录仍单列于 `data/outputs/research-records/input-bundle-acceptance-20261030/`，不将本模块假称为已经接入应用操作。
