# 来源提供方与对象绑定

`<provider>/provider.yaml`保存提供方能力，`../source-bindings/<binding>/binding.yaml`保存对象、证券代码和币种映射。现有`research/sources`继续兼容；当同名旧来源不存在时，SourceDefinition会读取binding。不为每份PDF和每个日期复制提供方代码。

两类有界发现：

- `html_links`：抓取并归档目录HTML，按注册link_pattern和allowed_hosts发现文档；支持rel/class=next的数字页游标，标题及最近heading仅作定位线索，不推定报告期/公开时间。
- `date_window`：从注册日期模板生成指定起止期间的请求清单；它不是交易日历或来源覆盖证明。计划通过item_ids选择有依据的预期日期，失败请求单独记录。

URL模板支持year/page/date及从date派生的year/month/day/yyyymmdd/yymmdd；所有外部来源仍经过标准proxy/TLS、参数白名单、下载大小和归档权限检查。提供方允许域名约束同时应用于初始URL、重定向及最终URL。

共享工作流由`source_discover`、`acquisition_plan`、`acquisition_run`、`acquisition_status`提供。分页中断保存发现清单和游标；用resume_discovery_id继续。任务计划、追加事件、候选快照和审核记录保存在`data/outputs/research-records/acquisition/`，清除本地缓存后仍可恢复。

`acquisition_run`默认检查远程；显式reuse_archived=true才按相同origin_url复用已归档且摘要校验通过的版本，回执注明未检查远程修订。相同全市场原件可以由不同binding解析；原件单份存储，候选记录提取绑定，不能使用首次归档证券代码冒充其他证券。

固定市场解析器可自动产生候选，仍待明确审核；财务和经营候选由人工/AI依据原件提取。complete只表示计划选定文档/候选完成，精确研究覆盖和用途就绪另行评估。provider配置改变后旧归档状态仍可查询，新获取必须重新发现以绑定新配置。

429/Retry-After及可重试网络错误写入提供方级持久化冷却记录，跨绑定共享、跨克隆保留。没有后台调度器；到期后显式续跑，不绕过来源限流。

公开检索表单可声明 `request_method: POST` 与 `fixed_parameters`；请求仅发送已登记参数，调用方不能覆盖固定参数。对象的站内编号放绑定 `parameters`，同一 provider 可复用不同对象。`hkex-titles` 是这种配置的实例。发现清单保留原始链接标题、anchor title 与标题层级上下文；这些是来源线索，不自动转换成已核实报告期间。

标题检索可能返回非研究目标文件（例如 AGM poll results）。已选任务的未批准项可提交 `submissions[item_id].skip_reason`，要求明确人工理由，追加不可覆盖事件；终态为 `completed_with_skips`，不能当作资料全覆盖。已批准或已准入项不能跳过；再次研究被跳过资料时新建明确的选择任务。
