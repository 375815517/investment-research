# 数据集定义

每个实际接入的数据集建立 `<dataset_id>/dataset.yaml` 和 README.md，定义记录粒度、字段、业务键、单位、时区、来源选择、分区、修订与质量规则。来源定义与数据集定义是多对多关系。

本目录只保存定义，不保存观测或实际批次。具体字段要求见 [输入基线](../../docs/architecture/input-data-baseline.md)。目前未创建可执行 schema 或候选数据集配置。
