# 可复用输入平台操作约定

本轮合同与目录边界见[决定004](../decisions/004-reusable-input-contracts.md)，性能及并发边界见[决定005](../decisions/005-input-platform-scaling.md)。所有操作复用 `Service`，CLI、API、网页不各写一套计算。

## 从研究需求开始

1. 确认研究对象及主证券，建立对象登记；本轮小米01810和腾讯00700已确认。
2. 选择或新建 `research/input-profiles/<用途>/vN.json`，明确每个必需的对象、期间、指标、维度、单位、版本和来源。分母来自研究需求及官方披露制度，不能根据已经取得的数据倒推。
3. 运行精确覆盖与用途评估；旧 `audit-inputs` 的样本数通过不替代此步骤。
4. 先查本地原件，缺字段则提取，缺原件才发现和采集。AI输出候选，平台执行合同、证据、复核、冲突和正式准入门禁。
5. 单位整理产生独立转换记录，随后固定输入包。`frozen` 表示版本固定；`verified` 表示可重放及摘要一致；两者都不等于研究用途 `ready`。

```bash
uv run --locked research --json data profile-audit --request research/input-profiles/xiaomi-annual-core/v1.json
uv run --locked research --json data profile-assess --request research/input-profiles/tencent-annual-core/v1.json
```

`--request` 为对应合同的JSON文件。通过 `research --json schema` 查询实际合同，不凭文档猜测字段。`normalize-inputs` 请求包含 `profile` 与 `target_scale`；`freeze-inputs` 请求包含 `profile`、可选 `transformation_ids` 和 `label`；`verify-bundle` 请求包含 `bundle_id`。

## 来源与任务

- `research/source-providers/` 定义提供方、受限参数、发现方式、固定解析器及访问边界。
- `research/source-bindings/` 把提供方映射到公司、证券或指数；年度及日期是任务参数。
- `source-discover` 保存有界发现清单，`acquisition-plan` 建立持久任务，`acquisition-run` 推进，`acquisition-status` 核查真实阶段。等待语义提取或复核的任务不能显示为完成。
- HTTP失败、空响应、模板页、解析改版、节流及重试时间分别保留。重复执行优先恢复已有原件和审核；正式写入冲突后重新规划，不强行覆盖。
- 单份原件可供多公司使用，提取绑定和原始归档来源分别保存。固定行情解析器不能被当成任意数据集解析器。

`data/outputs/research-records/` 中的任务及回执随Git保存；`.research-local/` 的缓存可删除重建。跨克隆恢复须携带完整Git资料；原件外部URL不代替原件字节。

## 财报提取与语义复核

`scripts/extract_report_candidates.py` 按版本化提取规格读取原件页码、行及列，保存规格、原件摘要、脚本摘要和候选。AI核实单位、期间、合并/分部、原始/重述、审计状态及原文定义；第二次复核绑定候选摘要。修改任何候选值或引用后重新复核，不能沿用旧摘要批准。

年报或中报出现季度栏目时，必须单独使用正确列和期间；中报现金流累计值不冒充第二季度值。每股盈利、活跃用户等不能未经定义直接相减。经营量使用人数、设备、车辆等明确单位，不能都存成货币。

正式财务值在 `data/inputs/companies/<公司>/financials/`，经营量在 `operations/`；规格和复核过程在 `data/outputs/research-records/`。指标定义在 `research/metrics/`，不存具体公司的实际值。

期间转换的底层合同与限制见[期间转换说明](../architecture/period-transform-contract.md)，尚未注册为CLI/API操作。

## 时间、状态与修订

`revise-metadata` 只追加公开时间断言，关联来源证据及辅助原件。日期精度以保守可用上界筛选；不把日期编成已知的精确发布时间。`historical_reconstruction` 可使用后来取得的历史证据，`live_observed` 还要求系统当时已观察和登记。

公司行动区分提议、批准、实施和取消；计划付款日已过去不证明已经支付。支付确认与声明建立明确依赖，不把另一份原件的事实混入单个引用。原件、来源重述及平台更正全部保留历史版本。

## 扩展与复验

新增公司优先增加登记、binding与需求定义；新增来源格式在connectors中加入固定适配器和负例测试；新增量纲或期间语义修改domain和字典并升级合同。不得在engine加入公司名称分支。

价格需求生成脚本 `scripts/build_market_history_profiles.py` 从固定交易日历生成逐日需求，参数包含对象、来源、数据集及币种。日历模型不证明个股未停牌，价格日期覆盖不证明复权、成交量单位或总回报口径。

```bash
bash scripts/check.sh
```

全工程测试、真实数据完整性、独立复核、干净克隆恢复及网页呈现分别验收。外部来源缺口保留原需求和失败原因；更换用途或放宽口径需创建新的显式需求版本。
