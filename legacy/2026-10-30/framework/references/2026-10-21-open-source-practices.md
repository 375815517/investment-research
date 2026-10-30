---
title: 投资研究开源实践：方法、组织与实现对照
date: 2026-10-21
status: research-note
scope: 官方资料与少量源码核对；未安装运行候选项目
---

# 投资研究开源实践：方法、组织与实现对照

## 判断与适用范围

本次比较的九个项目提供了值得借鉴的局部设计，但没有足够证据证明其中某一个完整系统比现有方案更符合本项目需求。建议保留“文档资产为权威、每家公司独立、每次分析留档、统一 Web 展示”，优先补强证据关联、计算复现、行业方法复用与预测复盘。它们能改善研究的可检查性；是否改善投资判断，需要另做持续评估。

本报告服务于个人长期基本面研究工作台的设计，不提供股票交易建议。资料于 2026-10-21 访问，取自官方文档、仓库、许可和少量公式源码。选择依据是能力互补，不以 GitHub 星数排序：金融数据平台、财务计算、分析 Agent、实验记录、文档出版各选代表。没有安装候选项目、调用收费数据、跑收益回测或测量速度；因此“适合借鉴”是结合当前需求作出的设计判断，“运行稳定”“预测有效”不在已验证范围。

当前实物仍是 `apps/investment-research/` 应用、`investment-research/` 文档、空间 `research/` 历史材料。上一轮提出的统一项目加公共 `web/` 尚未实施。以下目录是候选组织方案，不是已完成迁移。

## 1. 九个代表项目，分别学什么

| 项目 | 官方资料支持的能力 | 对我们的借鉴判断 | 不宜直接照搬的部分 |
|---|---|---|---|
| OpenBB ODP | 数据提供方、标准模型与调用入口分离；Python 和 REST 共用执行层 | 数据接入一次，报告、计算和 Web 读取同一标准结果 | 不把 ODP 开源后端等同于完整 Workspace 企业界面 |
| AKShare | 财经数据接口与接口说明；官方明确提示接口可能移除、存在数据风险 | 为中国及香港相关研究建立可替换的数据适配层 | 不能把接口返回值视为已核实公告，也不能假设永久免费稳定 |
| FinanceToolkit | 可读财务公式、财报和财务指标计算 | 统一公式、单位和定义，把计算从文字生成中分离 | 数据覆盖、供应商套餐与不同会计口径仍需处理 |
| FinRobot | README 描述确定性计算与 LLM 叙述分离、研究流水线和溯源设计 | 让模型组织证据和解释，关键数字由可复核程序生成 | 未验证其全部溯源保证、生产成熟度和实际投资效果 |
| TradingAgents | 分析角色、看多/看空研究者、交易与风险角色 | 提炼支持论点、反证、争议与裁决理由 | 角色数量不等于独立证据；交易执行不属于当前需求 |
| Qlib | Experiment 管理研究实验，Recorder 保存单次运行；提供 MLflow 实现 | 同一研究问题允许多个运行版本，保留输入、参数、指标和结果 | 量化预测与回测框架不替代企业竞争和经营研究 |
| Quarto | Markdown、计算、引用和多种出版输出；项目统一配置 | 报告数字与图表共用计算输出；Web 可重建 | 无需立即把全部 Markdown 改成可执行文档 |
| Quartz | Markdown 内容、元数据、搜索与反向链接，静态展示 | 共享展示模块按文件身份和引用构建跨公司视图 | 静态展示不直接提供现有编辑、冲突检查流程 |
| DVC | 流水线记录依赖、参数和输出，锁文件记录内容摘要 | 每次分析保存可读的输入—计算—结果依赖清单 | 现阶段不必引入大文件远端和完整流水线工具 |

上述事实依据：[OpenBB 架构](https://docs.openbb.co/odp/python/concepts/architecture)、[ODP 与 Workspace 边界](https://github.com/openbq-org/OpenBB)、[AKShare](https://github.com/akfamily/akshare)、[FinanceToolkit](https://www.jeroenbouma.com/projects/financetoolkit)、[FinRobot](https://github.com/AI4Finance-Foundation/FinRobot)、[TradingAgents](https://github.com/TauricResearch/TradingAgents)、[Qlib Recorder](https://qlib.readthedocs.io/en/latest/component/recorder.html)、[Quarto](https://quarto.org/docs/projects/quarto-projects.html)、[Quartz](https://quartz.jzhao.xyz/)、[DVC 文件格式](https://doc.dvc.org/user-guide/project-structure/dvcyaml-files)。

这张表不能按“功能数”加总评分。OpenBB 解决数据访问，Quarto 解决报告出版，TradingAgents 解决角色工作流，所处层次不同。我们的任务是选择组合边界，而不是用其中一个项目替代全部资产。

## 2. 实现方式：把可借鉴机制变成边界

### 2.1 数据提供方不是数据事实本身

OpenBB 的 provider 用输入模型、输出模型与转换/提取步骤适配不同数据源，执行结果还携带提供方和警告信息。这个机制适合借鉴为轻量接口：`获取原文 → 保存来源信息 → 标准化指标 → 质量检查 → 进入研究`。[官方架构](https://docs.openbb.co/odp/python/concepts/architecture)

建议公司 `shared/sources.md` 保存“哪里找、如何核对、覆盖哪些指标”；每次分析的 `sources.md` 保存“这次实际用了哪份文件、发布日期、页码、访问时间”。公共目录保存来源说明，单次分析保存具体证据，二者不能互相代替。AKShare 可作为候选数据入口，但公司的公告和交易所原文仍应承担关键财务事实的复核职责；这是本项目的证据策略，并非 AKShare 提供真实性保证。

标准化时保留原值和转换过程。例如原文“人民币百万元”转换为“人民币亿元”，应能同时看见原始数字、单位及转换倍数。缺失值、零值和“不适用”必须分开；不同网站若共同引用同一公告，不能计算成多份独立证据。

### 2.2 公式可读，计算过程可以重算

FinanceToolkit 作者将不同来源同名指标存在算法差异作为设计出发点，其估值源码把 EPS 写成独立计算函数，明确利润、优先股股息和平均股数输入。[设计说明](https://www.jeroenbouma.com/projects/financetoolkit)、[估值公式源码](https://github.com/JerBouma/FinanceToolkit/blob/main/financetoolkit/ratios/valuation_model.py)

建议我们的每个关键指标都记录四件事：定义、输入证据 ID、公式版本、结果。PE 要标明利润是历史、滚动还是预测，EPS 的股数是否稀释，人民币盈利与港币价格如何换算。采用一个透明公式仍不等于口径正确，必须先判断所用利润和股本是否适合本次问题。

FinRobot 当前 README 也明确提出财务计算和 LLM 叙述分离。本次只把它作为架构参考，未验证其宣称的所有计算和审计路径。对我们最小的应用是：报告中的表格从保存的 `results.csv` 读取，网页情景工具若改变假设，明确标为临时情景；保存时建立新运行版本，不覆盖历史结果。[FinRobot 设计说明](https://github.com/AI4Finance-Foundation/FinRobot)

### 2.3 每次分析与每次计算运行分开

Qlib 区分实验与单次运行，Recorder 可以记录参数、指标和产物。借鉴这个层次，一次“小米海外成长分析”可以有基准、降价、关税变化等多次计算；不必为每次改参数复制整份研究。[Qlib 实验记录](https://qlib.readthedocs.io/en/latest/component/recorder.html)

建议每个运行记录输入文件摘要、参数、公式版本、执行时间和输出摘要。DVC 的锁文件提供了相似的依赖追踪思路，但我们可以先用普通 YAML 清单实现。摘要能证明是否为同一份内容，不能证明来源真实；只有链接和摘要而没有可访问原件，也无法保证日后重算。[DVC 依赖与锁文件](https://doc.dvc.org/user-guide/project-structure/dvcyaml-files)

### 2.4 Web 是公共读取与编辑入口，发布结果是派生物

Quarto 项目共享配置并输出到独立目录；Quartz 将 Markdown 经过转换和过滤生成网站。两者都支持内容与展示产物分开。[Quarto 项目](https://quarto.org/docs/projects/quarto-projects.html)、[Quartz 架构](https://quartz.jzhao.xyz/advanced/architecture)

对应到当前项目：文件拥有研究内容，公共 Web 负责浏览、搜索、图表和受控编辑；编辑仍写回文件。生成的索引和图表可以重建。以后若支持静态发布，需单独决定发布哪些内容，不能把“部署可视化界面”理解成全部原始材料都已获准公开。

Quarto 的 `freeze` 是执行管理机制：全项目渲染可复用已保存的计算结果；单独渲染文件等情况有不同执行行为。它不能替我们冻结外部行情。金融研究仍需明确保存当时输入。[执行管理](https://quarto.org/docs/projects/code-execution.html)

## 3. 内容与分析方法：从报告集合变成可验证的判断积累

本节是对当前项目的改进提案，不是上述软件共同提供的现成功能。

### 3.1 四层复用：通用、行业、公司、单次分析

当前已有通用方法、公司共享资料和单次研究，建议补充行业层。通用层回答证据、时间、估值和复盘的基本规则；行业层解释不同商业模式应观察什么；公司层保存特有业务结构和问题；单次分析固定当时实际采用的版本。

| 层级 | 示例内容 | 更新方式 |
|---|---|---|
| 通用方法 | 来源优先级、现金流、估值口径、反证、复盘 | 方法升级注明原因；历史报告保留采用版本 |
| 行业方法 | 手机量价与渠道、汽车交付与资本占用、平台用户与变现 | 从多个公司案例验证，不把一家经验直接视为行业规律 |
| 公司公共资料 | 小米业务分部、腾讯特有指标、数据源、未解决问题 | 持续维护并注明生效时间 |
| 单次分析 | 研究问题、当时证据、假设、模型、判断与后续观察 | 已留档正文保留；纠错和后续验证追加 |

同一个行业方法可以被多家公司引用。同一份行业原始材料也可以复用；每次分析保存引用的版本和定位，不复制一份后任意修改。

### 3.2 为结论和反证赋予稳定身份

TradingAgents 的看多/看空研究流程启发我们保留对立解释，但角色辩论本身不保证证据独立。[官方角色说明](https://github.com/TauricResearch/TradingAgents)

建议用一个简洁的判断表，连接现有 `facts.csv`、`sources.md`、`assumptions.md` 和 `verification.md`。每条判断记录：判断 ID、支持事实 ID、反对事实 ID、关键假设、适用期限、反证条件、观察结果。无需先引入图数据库；表格和稳定 ID 就能表达关系。

例如“海外扩张能够提升利润”至少要分别回答：收入是否增长、毛利是否改善、本地营销和售后成本是否上升、营运资金是否增加。不能只用海外收入增长支持利润结论。反方审阅的输出应是缺失证据、不同口径和推翻条件，不能只形成另一篇语气悲观的文章。

### 3.3 从驱动到股东结果，分段推导

建议每份成长研究沿同一条顺序检查：业务数量与价格 → 分部利润 → 费用和税 → 资本开支与营运资金 → 股数与每股结果 → 买入估值隐含的预期。每一步都写明来源或假设。

以下只是研究问题示例，不是本次核实的公司经营结论：

| 研究对象 | 优先拆解的问题 | 需要防止的误推 |
|---|---|---|
| 小米手机 | 地区出货量、均价、产品组合、渠道库存 | 把出货增长直接等同终端需求或利润增长 |
| 小米汽车 | 交付、均价、单位成本、产能利用、售后、资本开支 | 把订单等同交付，把毛利转正等同现金流转正 |
| 小米海外 | 区域量价、汇率、税费、渠道和本地服务成本 | 用全球份额推断每个地区的竞争地位 |
| 腾讯 AI | 实际收入或效率贡献、推理成本、资本开支、折旧 | 把投入规模直接等同竞争优势或回报 |

同业比较应先建立可比范围，再选公司。按业务选择竞争对手和替代方案，统一期间、地区和指标定义；不能只比较集团总收入。估值再用敏感性和反向推导检验：当前价格需要哪些经营假设成立？哪两个变量足以改变结论？

### 3.4 复盘要能发现方法错误

当前规则已要求保留失败案例。建议进一步把当时预测值、区间、期限及实际结果关联起来，区分数据错误、公式错误、竞争误判、时间偏差和外部冲击。

先用可以观察的经营指标检验预测质量，例如下一期分部收入区间，而不是只用股价涨跌评价研究。报告里的“信心”如果是主观分级，应注明依据；没有校准样本时不要把 80% 当成统计准确率。若日后使用概率预测，可记录所有到期案例的覆盖率或概率评分，并保留样本量；本次没有此类实测数据。

## 4. 推荐组织结构与资产关系

统一项目边界值得保留。下面是渐进候选树；只有实际使用时才创建可选目录，避免为未来需求预先堆空目录。

```text
investment-research/
  README.md
  rules.md
  methodology.md
  lessons.md
  templates/
  research/                 # 工具与方法学习，如本报告
  playbooks/                # 可选：行业方法
  topics/                   # 可选：跨公司主题，引用原资料
  companies/
    xiaomi/
      shared/               # 公司持续更新资料
      analyses/
        <日期-主题>/
          report.md
          facts.csv
          sources.md
          assumptions.md
          verification.md
          retrospective.md
          context.md
          claims.csv        # 可选：判断与证据关联
          inputs/           # 按需保存可合法留存的原始输入
          runs/<运行ID>/    # 按需保存参数、结果、依赖清单
  web/                      # 候选公共模块，当前尚未迁入
```

目录只表达归属；元数据表达关系。建议保留稳定 `company_id`、`analysis_id`、`source_id`、`claim_id`、`run_id`。来源表记录数据期、发布日、采集日；报告记录信息截止时间；用 `supersedes` 指向被更新的旧研究。旧分析仍可阅读，不能让“最新”链接替换其历史输入。[Quartz 元数据作为机制参考](https://quartz.jzhao.xyz/getting-started/authoring-content)

不要现在就把同一张小表同时维护在 Markdown、CSV、YAML 三个地方。正文由 Markdown 拥有；需计算的数据由 CSV 拥有；YAML 只保存身份、配置和引用。Web 从这些文件生成视图。若未来建搜索库，它只保存可重建索引。

研究报告、计算输出和来源的关系建议为：

```text
来源文件/公告 → 标准化事实 → 假设与公式 → 计算结果 → 研究判断
                    ↘ 反对证据与待验证事项 ↗       ↓
                                  新观察 → 复盘 → 方法修订
```

这些关联使公共 Web 能回答“这条结论依据什么”“哪份来源修订会影响哪些判断”。知识图谱是否画成网络图属于后续展示选择，先把引用关系存正确。

## 5. 对当前项目的差距判断

本次读取了当前 README、AGENTS、rules 与 methodology。下面区分已有文档合同和待补机制；没有对全部源码作重新审计，不将“文档未提及”断言为“源码不存在”。

| 领域 | 当前已有合同 | 建议补充 |
|---|---|---|
| 文件权威 | Markdown/CSV 持久保存、Web 读取、可独立阅读 | 合并项目后仍保持生成物可重建，迁移时验证路径 |
| 研究复用 | 通用方法、公司 shared、每次 context 快照 | 行业方法和稳定引用版本 |
| 证据 | 来源、期间、单位、币种、验证状态要求 | 事实、来源和判断的 ID 关联及缺失检查 |
| 历史 | 留档正文、追加验证、复盘 | 原始输入与计算版本绑定，修订影响提示 |
| 估值 | 三情景、分部估值、敏感性规则 | 将实际参数、公式和结果共同保存并重算 |
| 质量 | 反证、失败案例、偏差分类 | 可量化的经营预测记录与到期评估 |

现有规则已经包含不少良好实践，优先落实可检查性，比再写一套相似规则更有价值。

## 6. 实施优先级和验收方式

| 次序 | 建议工作 | 最小试点 | 可观察的验收 |
|---|---|---|---|
| P0 | 补齐身份与证据引用 | 下一次小米分析中的三个核心判断 | 每个判断能追溯到事实、来源、页码或表格和反证条件；无依据项明确待核实 |
| P0 | 明确四层方法复用 | 一个手机行业方法和小米差异说明 | 更新共享方法后，旧分析的 context 和采用版本不变 |
| P1 | 保存可重算模型 | 一个业务分部的基准与压力情景 | 同一输入参数得到一致结果；报告与 Web 数字一致；缺失输入报错 |
| P1 | 连接来源变化与验证 | 人工模拟一份来源修订 | 能列出受影响判断并标记待复核，不自动改写历史结论 |
| P1 | 做三份研究的流程试点 | 三个独立研究问题，不要求三家公司 | 记录来源补齐时间、可追溯率、口径错误、重算成功率和复盘完成情况 |
| P2 | 试验出版与数据适配器 | 一篇计算密集报告、一个数据接口 | Quarto 导出数字一致；适配器失效有明确状态且保留旧数据 |
| 暂缓 | 全面 Agent 编排、DVC 远端、平台整体替换 | 等重复劳动或数据规模形成实际瓶颈 | 先测维护成本和新增收益，再决定是否采用 |

这些是验收设计，不是本次完成的功能或已测得的改善比例。数据接入方式、目录迁移和正式部署需要另一次实现工作；本次只增加方法调研资产。

## 7. 采用前仍需核实的事项

1. **香港上市公司覆盖。** 以小米和腾讯的几个关键指标实际调用候选接口，核对历史深度、单位、财报修订、复权和更新延迟。本次未调用，不能依据支持“股票”就推断覆盖充分。
2. **时点数据。** 供应商的最新修订历史数据，未必等于当时已公开的数据。历史研究要分别记录期间、首次公开时间和修订时间；回看旧研究时不能无提示混入后来资料。
3. **费用与数据使用条款。** 开源程序许可不等于数据可自由获取或再分发；需按实际供应商和选定套餐核实。本报告不作商业再分发的法律判断。
4. **维护和运行质量。** 本次没有锁定所有项目的发行版本或提交，也没有完整测试；GitHub API 元数据读取遇到限流，未据此编制维护活跃度排名。正式接入前固定版本，核对测试、依赖及相关问题记录。
5. **效果。** Agent 辩论、长报告和回测样例不能直接证明投资优势。是否改善研究质量，应以同样问题、同样来源范围和盲审标准比较；是否改善收益需要更长时间及适当基准。

### 许可核对记录

以下为访问日所读分支的仓库许可，不替代采用时对固定版本、依赖和数据条款的复核。没有复制这些项目的实现代码。

| 项目 | 核对到的许可 | 原文 |
|---|---|---|
| OpenBB | Apache-2.0 | [develop/LICENSE](https://raw.githubusercontent.com/OpenBB-finance/OpenBB/develop/LICENSE) |
| AKShare | MIT | [main/LICENSE](https://raw.githubusercontent.com/akfamily/akshare/main/LICENSE) |
| FinanceToolkit | MIT | [main/LICENSE.txt](https://raw.githubusercontent.com/JerBouma/FinanceToolkit/main/LICENSE.txt) |
| FinRobot | Apache-2.0 | [master/LICENSE](https://raw.githubusercontent.com/AI4Finance-Foundation/FinRobot/master/LICENSE) |
| TradingAgents | Apache-2.0 | [main/LICENSE](https://raw.githubusercontent.com/TauricResearch/TradingAgents/main/LICENSE) |
| Qlib | MIT | [main/LICENSE](https://raw.githubusercontent.com/microsoft/qlib/main/LICENSE) |
| Quarto | MIT | [main/COPYING.md](https://raw.githubusercontent.com/quarto-dev/quarto-cli/main/COPYING.md) |
| Quartz | MIT | [v5/LICENSE.txt](https://raw.githubusercontent.com/jackyzha0/quartz/v5/LICENSE.txt) |
| DVC | Apache-2.0 | [main/LICENSE](https://github.com/treeverse/dvc/blob/main/LICENSE) |

访问时 OpenBB 旧仓库地址重定向到 `openbq-org/OpenBB`，Quartz 官网显示 v5，DVC 旧仓库地址重定向到 `treeverse/dvc`。本报告按实际访问资料记录，不能把较早教程中的结构、许可或版本直接套入当前项目。

## 8. 建议采用的下一步

在下一份小米研究里先试行“核心判断—事实—来源—反证—计算”的完整关联，保留现有 Markdown/CSV 和公共 Web。试点通过后，再合并物理目录、抽出行业方法并扩展界面。优先让一份真实研究能够核对、重算和复盘，再决定引入哪些开源依赖。
