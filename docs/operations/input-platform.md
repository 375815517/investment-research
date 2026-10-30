# 输入平台运行手册

本手册保留首版入库流程，并在末节补充当前检测、补采、API和网页。先读 [输入基线](../architecture/input-data-baseline.md)；详细完成状态与限制见 [验收记录](../verification/input-platform-v1.md)。所有例子使用实际CLI，不包含尚未实现的 data plan 或自动Git发布命令。

## 安装与检查

要求 Python 3.12 和 uv。仓库根是工作区；包安装后也可从任意目录传入 `--workspace`。

```bash
uv sync --locked --group dev
uv run --locked research --json doctor
uv run --locked research --json capabilities
uv run --locked research --json schema DailyPrice
uv run --locked python scripts/demo_input_pipeline.py
```

云环境默认缓存路径不可写时，设置 `UV_CACHE_DIR=/workspace/.cache/uv`，不修改系统目录。离线演示创建并清理临时工作区，使用明确的 demo 标识，不写真实企业数据，不调用外部模型。

## 配置和合同

根 pyproject.toml 管理workspace与开发工具。工作区选择优先级为显式 `--workspace`、`RESEARCH_WORKSPACE`、从当前目录向上发现项目标记。业务合同不能通过环境变量覆盖。来源配置仅引用环境变量名称，不保存认证值。

当前 DailyPrice、FinancialFact 等结构以 investment_domain 中类型为唯一可执行来源，`research/datasets/` 描述并引用模型；没有通用YAML规则执行器。新增字段必须更新模型、schema、解析器与回归样例，不手工维护冲突的第二份字段schema。

## 统一数据流程

命令可使用 `--request request.json` 或 `--request -` 从标准输入读取对象。`--json` 保证标准输出为机器结果；退出码和 issues 一起判断。来源、候选和批次使用稳定ID，目标路径由公共服务计算。

```bash
research --workspace /path/to/repo --json data import --request import.json
research --workspace /path/to/repo --json data prepare --request prepare.json
research --workspace /path/to/repo --json data validate --request candidate.json
research --workspace /path/to/repo --json data review --request review.json
research --workspace /path/to/repo --json data ingest --dry-run --request candidate.json
research --workspace /path/to/repo --json data ingest --apply --request plan.json
```

以上文件名为用户实际请求文件，不是仓库已提供的数据。完整可运行样例是 scripts/demo_input_pipeline.py。import至少指定path/source_id，已核实的published_at必须带时区；未知可为空，严格历史时点查询会排除未知公开时间。

prepare指定document_id/dataset_id。日线由固定CSV解析器读取原件，不能用任意候选覆盖行情。财务数据通过records提交company_id、metric_id、期间、source_value/source_unit、currency、scope、record_kind、locator和excerpt；FinancialFact schema可通过命令导出。语义提取没有自动OCR或模型调用，必须复核，不因模型confidence高自动准入。

review指定candidate_id、reviewer、decision、notes；它是绑定候选摘要的复核登记，不是真实身份认证或独立审核证明。财务原文定位及口径仍需实际核实。计划和apply之间候选、复核或仓储版本变化会失效。

## 获取来源与失败

```bash
research --json source check --source-id <registered-source>
research --json data collect --request collection-request.json
```

source check只说明本地配置、连接器和认证引用状态；network未检查必须保持not_checked。HTTP CSV连接器固定类型和字段要求；公开网页/浏览器下载先走import，不能直接写正式行情。

Yahoo来源探测仅证明该时点可取得小米少量provider-native报价；历史调整口径与归档条件未核实，不作为已验收的未复权来源。遇到来源配置的归档阻断，不用import绕过同一限制。真实M2仍按验收记录标记部分完成。

## 查询与恢复

```bash
research --json data coverage --dataset-id daily-prices --subject-id xiaomi-hk
research --json operation status <operation_id>
research --json operation resume <operation_id>
research --json data index --rebuild
```

历史查询传information_cutoff与knowledge_mode：retrospective_explanation、historical_reconstruction、live_observed。当前覆盖按时点和显式修订返回有效来源版本；同源同业务键相同记录合并并保留批次、原件引用，不跨来源合并，不自动推断交易日完整度或择一替代冲突来源。公开时间由导入者提供，工具不能自动证明历史公开时点。

检查点位于.research-local，续跑根据已有结果工作；正式原件和回执独立归档。完整batch清单控制可见性，多个证券子批次不承诺全有或全无。Git提交与推送独立执行。

## 宿主初始化

```bash
research --json host inspect --host codex
research --json host plan --host codex --save
research --json host apply --plan-id <returned-plan-id>
research --json host verify --host codex
```

先安装CLI再使用setup Skill，避免循环依赖。Skills只维护在ai/skills，安装副本忽略；链接按投影位置重写。sync/repair/uninstall先生成计划，仍需apply；用户改动不会被覆盖。不要删除无回执文件来解决冲突。

filesystem、discovery、invocation分别报告；当前没有真实宿主发现/调用验收，CodeBuddy为实验性文件适配，Hooks disabled。不能仅根据复制成功宣称宿主原生支持。

## 工程检查与发布

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked pytest -m 'not network and not live_model'
uv build --all-packages --out-dir .research-local/dist
```

CI限定新工程和离线样本，不执行legacy旧代码。真实网络与模型检查另行运行，不纳入默认离线成功承诺。

发布时根据入库回执列出的路径选择性暂存。`scripts/check_publication.py --manifest paths.json`检查Git索引是否仅包含明确文件、是否覆盖输入历史或修改legacy；不自动暂存、提交或推送。该脚本是首版发布检查，不代替完整引用校验或服务器分支保护。现有无关改动保持未暂存。

## 数据平台闭环

最新验收见 [数据平台闭环记录](../verification/data-platform-closure.md)，范围与设计见 [本轮计划](../plans/data-platform-closure.md)。CLI、API、网页共享相同 Service。

```bash
uv run research data detect-gaps --request request.json --json
uv run research data ensure-plan --request request.json --json
uv run research data ensure-apply --plan-id <返回的计划ID> --json
uv run research-server --workspace /path/to/investment-research --port 8765
```

在运行服务的同一机器打开 `http://127.0.0.1:8765`。页面选择对象、数据集、来源、口径和有证据的预期清单，查看原件与整合记录、检测缺口及应用补采计划。服务默认仅本机，不包含公网认证部署；云环境本机地址不是用户电脑可直接访问的公网地址。

日行情需求示例（文件内容）：

```json
{"dataset_id":"daily-prices","subject_id":"xiaomi-hk","start":"2026-10-19","end":"2026-10-24","expectation_path":"data/inputs/markets/calendars/hkex/2026/2026-10-30-observed/expectations.json","source_id":"tencent-kline","price_basis":"provider-native"}
```

CLI 执行真实补采时在请求增加 `acquisition: {"source_id":"tencent-kline","parameters":{"param":"hk01810,day,2026-10-19,2026-10-24,20,"}}`；网页由已登记来源生成参数。每个计划最多一次来源获取，失败后报告剩余缺口；财务原件取得后进入待提取/复核，不自动批准。

新增JSON行情解析固定使用原件观察时点，保守排除观察当日及未来行情，不能在次日重解析时升级盘中样本。PDF locator 使用 `pdf:page:2` 等物理页号，excerpt必须匹配该页文本；这仅核对定位，不代替语义复核。当前查询默认 unadjusted，读取供应商原始口径需显式 price_basis=provider-native。

## 长区间行情回补

`scripts/backfill_price_history.py` 使用共享采集/校验/入库服务，按半年分窗以满足来源请求长度约束；响应超出请求范围或校验失败即阻断该窗口。每窗保存回执，失败窗口可单独重跑，已入库版本不覆盖。`collected`仅表示所有窗口获取入库成功，交易日完整性须另核对。

```bash
uv run python scripts/backfill_price_history.py --source tencent-kline --security xiaomi-hk --start 2018-07-09 --end 2026-10-29
research --json data coverage --request request.json
```

查询请求指定 `dataset_id=daily-prices`、`subject_id=xiaomi-hk`、起止日期及 `price_basis=provider-native`。本轮验证见小米入口。

有官方证据的休市记录位于 `data/inputs/markets/trading-status/<security>/<year>/<revision>/status.json`，合同为 `MarketClosure`。查询按信息时点读取并排除来源休市占位行，同时返回excluded及证据引用；原件与旧批次保留。零成交量本身不是休市证据，不能自动过滤。日期只有日级公开证据时，不伪造准确发布时间，历史模式下未知时间的排除记录不追溯生效。
