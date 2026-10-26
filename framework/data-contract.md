# 研究资料与数据合同

本项目以原件、Markdown、CSV、JSON 为持久资产，DuckDB 在内存中读取 CSV，不保存另一份权威数据。Web 作者源码仅在 apps/research-web/；可选部署包由 tools/build-web.mjs 生成到项目内 .build/research-web/。当前以文档项目交付，不托管应用。旧版历史分析保留，新的研究固定其采用的证据、参数和行情。

## 资料类型、格式和更新责任

| 类型 | 保存位置与格式 | 必填信息 | 更新策略 |
|---|---|---|---|
| 财报、业绩公告、监管披露 | companies/公司/sources/ 原始 PDF；register.csv 登记 | 来源ID、标题、URL、文件名、发布日期、数据期、页码约定、采集时间、SHA256 | 同一文件修订另存版本，不覆写旧原件 |
| 公司计划、业绩指引 | 原始 PDF/网页原文；facts.csv 标为 company_guidance | 目标发布日期、目标期限、阈值或区间、原话定位、采用版本 | 与实绩分开；后续目标修订追加新版本 |
| 行业研究报告 | 可合法留存的 PDF/HTML 原件；无下载权仅保存来源与短摘录 | 机构、方法、样本、地区、sell-in/sell-through、发布日、修订日 | 不复制付费全文；比较前统一范围，不以转载数量当独立证据数 |
| 提取文本与人工摘要 | 原件旁按需生成 .md；标记 extracted 或 analyst_note | 原件ID、提取方法、页码、人工复核状态 | 可重建；不得取代原件，OCR 数字需核对 |
| 结构化财务事实 | 每次分析 facts.csv，UTF-8、RFC4180 引号 | fact_id、metric、period、value、unit、source_id、locator、kind | 原值与口径保存；计划不进入实际业绩列，不对空缺填0 |
| 股价原始数据 | data/market/raw/ 提供方 JSON 原始响应；prices.csv 规范日线 | symbol、date、OHLC、volume、currency、adjustment、provider | 最近窗口重拉、按日期合并、保留更早日期；原始响应按日及摘要留档 |
| 公司与行业事件 | data/events.csv | event_id、event_date、title、source_id、source_url、time_precision | 事实事件与预期事件分开；未知时刻不伪造盘前/盘后 |
| 研究判断与假设 | report.md、claims.csv、assumptions.md | 判断ID、事实ID、反证、有效期；假设与公司计划分开 | 研究正文留档，后续观察追加 verification.md |
| 计算运行 | runs/运行ID/parameters.json、results.csv、manifest.json | 参数、单位、公式版本、引擎版本、输入/输出SHA256 | 固定输入重算，变化建立新运行；结果是派生物 |
| 复盘 | retrospective.md | 原判断时间、观察时点、实绩、误差原因、适用边界 | 历史公司计划复核不冒充本项目当时预测；未到期明确等待 |

本次实际归档小米三份官方 PDF、来源登记、320日窗口内的实际可用日线及事件。网页/行业材料以来源链接和限定摘录入档，不声称已下载全部原件。

## 时间和数字规范

日期用 YYYY-MM-DD；时间用带时区 ISO 8601。行情交易日按 Asia/Hong_Kong，财报期间与公告日期分别保存。来源确切上传日未知就写 unknown，不用访问日冒充发布日。报告 asOf 是信息边界；市场数据当前视图与报告 inputs/prices.csv 快照相互独立。

人民币百万元统一使用 CNY million，不能把千元直接当百万元。数量以辆、股、部注明；货币换算保留 FX 假设和日期。股本区分期末发行股数、扣库存股口径、EPS 加权股数、稀释股数。Non-IFRS 利润与 IFRS 利润分开，不将毛利当净利。

当前行情是腾讯财经未复权的日线，volume 按股保存。已对 2026-06-01 的 OHLCV 与 Yahoo 历史页交叉核对，单日一致不代表全部历史均已独立核实。更新器排除香港当地当天17点之前的未收盘日线；这不是完整交易所日历判断，停牌和节假日不补零。超过最后交易日的数据缺口由状态显示，不冒充实时。

## 更新、幂等和失败恢复

在项目自己的 Python 环境安装 requirements.txt（固定 DuckDB 1.5.6）后：

```bash
python tools/pipeline.py refresh
python tools/pipeline.py dashboard
python tools/pipeline.py calculate --analysis companies/xiaomi/analyses/2026-10-21-growth-evidence
```

refresh 拉取最新窗口，验证价格范围、日期、有限值及重复冲突后，原子替换当前 CSV。相同日期重复更新不增加行；供应商修订会更新当前序列，旧响应及研究快照保留。网络失败、空响应、畸形价格不写空表，status.json 保留最近成功日期和失败原因。并发刷新由独占锁拒绝；异常退出残锁需确认旧进程已停后人工处理，程序不擅自抢锁。

如果 CSV 已保存但 DuckDB 视图生成失败，资料仍有效，只需 dashboard 重建。Web 比较行情摘要，过期视图会提示；不为修复显示重新写原始资料。

本轮提供按需更新命令，不创建未约定频率的后台任务。常用选择是港股交易日收盘后更新；确定频率后可由调度器调用同一入口。Web 刷新页面读取最近已保存数据，页面自身不访问外网，也不触发交易。

## 事件对齐和计算边界

当前试点事件只有日期，采用披露日之后首个可用交易日作为观察首日；基准为披露日当日或之前最后收盘价。记录1日和5交易日价格变化。没有足够前/后窗口时留空，不填0，不回退到别的事件。对盘前已知时间的事件，后续应增加明确时刻和交易所日历规则；本轮不混入该语义。

这是观察窗口，不是因果估计：没有市场基准调整、行业对照或混杂事件控制。价格未复权，不等于含分红总回报；公司行动导致的跳变须另查原始公告。计划将来发生的日期不能冒充真实已发生事件。

## 证据链验收

每条判断引用存在的 fact_id；每项事实指向登记来源和页码；情景假设写参数文件；结果包含公式与输入ID；清单绑定输入、结果和计算脚本摘要。独立复盘案例用2025年3月汽车目标与2025实际交付对照。当前未来预测必须保留未到期状态。

数据接口依据：[腾讯财经日线入口](https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=hk01810,day,,,320,)。第三方接口没有本项目可确认的服务承诺，失效时保留文件，不能静默换数据口径。[DuckDB CSV 说明](https://duckdb.org/docs/current/data/csv/overview)支持显式字段类型；本项目使用该方式避免证券代码、日期和数字被自动误判。

## PDF展示与原件一致性

公共Web的PDF链接进入本地阅读器，图像与可提取文字均直接来自同一归档PDF。翻页使用PDF实际页序；事实表保留印刷页码，二者可能偏移。下载返回原件字节，不生成替代PDF。阅读器是可替换展示层，渲染缓存不是新权威。
