# 研究输入

权威合同：[输入数据结构基线 v1](../../docs/architecture/input-data-baseline.md)。当前为目录骨架，无已采集的正式小米数据或已确认主证券。

| 目录 | 保存内容 |
| --- | --- |
| source-files | 单份归档的来源原件及文档元数据 |
| collection-records | 每次获取的过程、结果、原件引用和缺口 |
| companies | 企业自身资料；企业 README 导航至共享信息 |
| industries | 行业分类、供需与产品事实 |
| markets | 证券、行情、日历、公司行动、基准、观察范围、外部预期、汇率 |
| macro | 宏观观测及发布版本 |
| policies | 政策条款、资格、阶段与有效期 |
| events | 事件时间、参与对象及证据引用 |

股票日线位置：`markets/prices/<security_id>/daily/<year>/<batch_id>/daily-prices.csv`。同目录附 `batch.json`。原始响应仍放在 source-files，不复制到企业或行情目录。

资料导航通过稳定 ID、时间与证据关联生成；可读名称和中文说明帮助检索，目录位置不替代数据身份。当前不生成虚构公司、数据源或数据集配置。
