# 003：多源资料与市场观测的有限合同

状态：已实现。日期：2026-10-30。用户授权将政策、财报、新闻、行业竞争及市场核心数据入库，并核查框架完整性；不新增投资预测或因子模型。

## 工程决定

保留 domain → repository/connectors → engine → CLI/API/web 的依赖分层。engine 的 `datasets.py` 集中维护四个受支持数据集的模型、业务键、对象、日期与分区；应用不复制判定逻辑。每类数据均经原件→候选→结构/证据检查→必要复核→计划→入库→查询。

新增 DocumentFact：来源声明，不是平台推断。批准需明确 `statement_consistency_checked`，防止“原文有某句话”被当成“AI摘要必然正确”。新增 MarketObservation：有限字段清单、类型单位、股类、来源口径、时间精度和分母证据；不使用可任意塞值的万能字段表。

HTML保留原字节；脚本/样式不作为陈述证据。PDF保留物理页定位，增加fonttools以支持部分年报字体解析。固定解析器与Agent候选均走相同复核流程，不能靠parser身份跳过金融语义。

## 输入基线增量

沿用共享原件与独立回执，新增业务分区：

- `markets/observations/<security>/<year>/<batch>/`：市场来源观测。
- `policies/<subject_type>/<subject>/facts/<year>/<batch>/`：共享政策陈述。
- `industries/<subject>/facts/<year>/<batch>/`：行业报告陈述。
- `companies/<subject>/statements/<year>/<batch>/`：公司/公司竞争声明。
- `events/<subject_type>/<subject>/source-statements/<year>/<batch>/`：媒体报道及其他已归类来源陈述，包括本轮industry主体的competition_statement。

这不是移动历史目录的迁移。旧文件保持原路径，业务身份及引用稳定；后续若合并行业竞争陈述分区需显式迁移，不悄悄重写已有批次。公司入口链接共享政策和行业资料，不复制原件。

## 时间、修订与证据

来源日期 observed_date 不编造时分；精确时刻 observed_at 统一UTC，避免同瞬间不同offset重复。按时刻筛选日期使用UTC日，按纯日期保留来源日期。当前统计快照仅代表抓取时看到的值，实际财务生效日未知必须写入basis。

比例的分母引用是实质输入：原件哈希、公开/获取时点都参与查询资格，未来或未知公开分母不能进入旧截止点。供应商回溯PE表不证明该值当时已被发布。不同口径不静默合并，修改须新增版本。

## 完整性与当前边界

`audit_inputs` 对明确的 requirements 做只读核查，范围是 `declared_sample_requirements`。市场缺失值不计满足；minimum_records不是全网覆盖率，多个转载不能冒充多个独立证据。完整查询校验批次和原件摘要。

新类支持候选复核与需求核查，尚无自动全网发现/全历史调度。当前来源配置中有固定报告端点，新增历史期仍需注册或明确请求；此版本不是通用历史文档爬虫。完整舆情分布、股东多空分布、历史每日估值与精准流通分母仍受来源可用性约束。具体缺口必须随验收呈现，不能改成“下一阶段”后声称本目标全部完成。
