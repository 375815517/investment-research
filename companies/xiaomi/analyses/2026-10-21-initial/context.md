# 初始归档公共上下文快照

归档于2026-10-21。以下是当时实际保存的公共规则及公司资料，后续共享更新不回写此处。

## rules.md

SHA-256：b5efa27e4d9c5e435e7f269abbdf13e0a9549c4f0c24c98043c26b4be5df179e

# 研究规则

## 证据和口径

1. 优先公司原始公告、交易所文件、监管数据；行业研究采用有方法说明和明确日期的机构原文。
2. 每项关键数字注明原始链接、数据期间、单位、币种、范围，以及披露、复核或推断状态。
3. 出货量、销量、交付量、订单不可混用；营收、毛利、经营利润、调整后净利润、自由现金流分别判断。
4. 季度不能机械年化；上市公司指引、机构预测、自己的情景分开。
5. 记录价格的交易所、币种和采样时间；过期价格不得称为当前价格。收益率计算包含汇率、分红与摊薄的假设。

## 判断纪律

- 每个核心结论列出支持证据、相反证据、关键假设及失效条件。
- 先辨认竞争地位、资本回报和资金需求，再讨论估值。
- 公司成长、每股盈利成长和股东回报分别推导。优秀企业也可能因买价过高带来低回报。
- 不把多业务简单相加当作协同；观察获客成本、交叉购买、留存和资本占用的实际变化。
- 数据未复核时允许形成工作假说，必须保留状态，禁止升级成确定事实。

## 版本、验证与复盘

公司共享资料持续更新；每次分析独立保存，context.md 固化当时采用的公共上下文。已留档正文不覆盖；追加验证、纠错说明或新建研究。

复盘同时包含成功与失败，不用后来信息美化当时可得信息。把公司专用改进写回 shared/learnings.md，把跨公司改进写入 lessons.md，并说明适用边界。

本工具不执行买卖，不自动抓取网络行情。研究者自行补充和验证数据，维护个人决策记录。


## methodology.md

SHA-256：0ddae107512f3105191b22689d938be40e3ed310e82d9d48ab00a1b2cefd0da4

# 分析方法论

## 一、明确问题与时间边界

写出这次研究试图回答的单一问题、决策期限、信息截至日和无法获取的资料。先写可能推翻结论的证据，防止只检索支持材料。

## 二、理解收入与利润来源

按业务拆解收入 = 数量 × 单价；利润 = 收入 × 毛利率 − 费用。对平台业务另拆用户、时长、商业化率和监管约束；对制造业务另拆产能、渠道库存、折旧、营运资金与资本开支。

检查会计利润能否转为现金：经营现金流 − 维持竞争力所需的资本开支；明确现金流定义与公司口径差异。增长并非都创造价值，比较新增资本回报与资本成本。

## 三、竞争与海外

逐项比较目标客户、产品价格、性能、渠道、生态、成本与本地政策。市场份额必须采用同地区、同期间、同定义数据。海外收入增长拆为市场需求、份额、汇率、本地化产能和渠道变化；把关税、合规、售后与汇回风险纳入利润测算。

## 四、成长来源

按业务区分行业增量、份额提升、价格或结构改善和新业务。计算各项对收入、利润与现金流的增量贡献。验证高基数、低基数和收购影响。

## 五、估值与情景

使用保守、基准、积极三种情景，明确数量、单价、利润率、资本开支、股本和汇率。公司指引不等于一定实现，自己的假设不应伪装成一致预期。

- 复合增速 = (终值 / 初值)^(1 / 年数) − 1。
- 每股盈利 = 归属股东利润 / 稀释后股数；回购和股权激励都要计算。
- 企业价值法：企业价值减净债务及少数股东权益，再加独立估值的非经营资产；现金是否重复计入要核对。
- 分部估值适用于结构清晰的多业务公司；分部利润、集团费用和内部交易口径应一致。
- 现金流折现明确折现率和终值；终值占比过高时下调结论信心。

用敏感性检验找出决定结果的两个变量，再估计当前价格已经隐含何种增长。不能只说“估值比历史低”。

## 六、验证计划与复盘

每个重要假设对应一项待验证事项：指标、来源、观察日期、支持阈值、反证阈值、负责人或未认领。新公告出现后追加观察。复盘区分数据错误、模型错误、竞争误判、时间偏差和随机波动，再决定是否修改方法。


## companies/xiaomi/shared/README.md

SHA-256：4abc1616d13551c621ae7cc9414852fb51595e912f6bdb3f3652086609ebf963

---
name: "小米集团"
ticker: "01810.HK"
sector: "消费科技 / 智能汽车"
summary: "检验汽车、海外与高端化，能否转化为集团利润和现金流增长。"
---

# 小米集团研究项目

公共资料与本次分析分离。初始资料为历史整理，待逐条复核。


## companies/xiaomi/shared/profile.md

SHA-256：630e57e804b45b3ff6da0b0c082ab064274f14b0f79d980f29442e389aef97b7

# 公司概况

资料基准：本会话截至 2026-10-21 的研究整理；本次建库未重新逐条复核。

业务由手机、IoT 与生活消费、互联网服务及智能电动汽车 / AI 等组成。手机提供用户和渠道基础，互联网利润率较高，汽车承载收入扩张与资本消耗。多业务协同需要用交叉购买、获客成本和资本回报验证。

竞争对象按业务区分：手机为苹果、三星、华为、OPPO、vivo、荣耀与区域性的传音；家电为美的、海尔和格力；汽车为比亚迪、特斯拉、理想、零跑及鸿蒙智行合作品牌。联盟交付不能等同于华为整车收入。

海外需拆欧洲、印度、拉美、非洲等区域；已有手机渠道不直接等于汽车制造、认证、维修和金融网络。2027 欧洲汽车上市属于计划，须逐步验证落地。


## companies/xiaomi/shared/methods.md

SHA-256：a5c041e22aac156bb2907a83a7bbcf0b1f665677acd166d0b1e34125786cf00a

# 小米专用分析方法

## 分部增量毛利桥

收入增长率不足以判断质量。每季按手机、IoT、互联网、汽车 / AI 等计算营收 × 毛利率，比较新增毛利能否覆盖研发、渠道和管理费用。汽车 / AI 是合并分部，不能把其毛利直接当成汽车独立毛利。

## 手机高端化

同时追踪出货、财报 ASP、批发 ASP、高价段份额与毛利。不同机构 ASP 和财报确认口径不可互换；高 ASP 伴随低销量未必带来更高利润。

## 海外与生态

境外占比 = 境外收入 / 集团收入，拆解分子增长与境内分母下降。IoT 联网设备为存量、月活为活跃用户、出货为流量，不直接推出付费收入。汽车出海单列认证、关税、售后、零件和本地产能。

## 估值

消费电子、互联网和汽车分部估值要扣集团费用与资本占用；汽车用销量 × 单价构建收入，再推毛利、费用和现金流。不要把收入市销率当作利润已经实现。


## companies/xiaomi/shared/sources.md

SHA-256：1822a16d46b9895fa43a625eeb6f7333a6ad482fe99b09aee2f4bcd7759f9c66

# 常用数据源

初始来源收录于 2026-10-21，未在建库时重新访问。每次使用需补访问日、版本、页码和数据口径。

- [公司财报原文入口](https://ir.mi.com/static-files/b903a881-8143-44a3-b759-703653bbb043)
- [小米投资者关系](https://ir.mi.com/)
- [Omdia 行业研究](https://omdia.tech.informa.com/)
- [Counterpoint 研究](https://counterpointresearch.com/)
- [IDC 市场份额](https://www.idc.com/promo/smartphone-market-share/)

公司披露用于财务事实；行业报告用于同口径竞争比较。具体原始报告链接保存在首次分析的 sources.md。


## companies/xiaomi/shared/questions.md

SHA-256：fa9b04656304824decbaa6889405bc43ec00b76dd33e820930829b12f7a392d3

# 待验证事项

- [ ] 下一季手机毛利率是否恢复？以公司分部公告为准，若量价改善仍未增加毛利，反证高端化已兑现的判断。
- [ ] 汽车 / AI 分部收入增加能否带来经营亏损收窄？核对合并口径，不编造汽车独立利润。
- [ ] 海外收入增长是否来自真实销量、品类扩张还是汇率？补地区、币种和产品分拆。
- [ ] 欧洲汽车上市计划是否出现正式车型认证、定价、交付及维修网络？计划不记入已实现收入。
- [ ] 高端化与海外 IoT 能否提高集团现金回报？核对存货、应付款、资本开支及研发现金支出。


## companies/xiaomi/shared/learnings.md

SHA-256：e6d93c560746cbb87d178231e07631fea85a94a00afb27cde77e4975f042ff99

# 小米公司复盘

## 当前形成的方法约束

不能以汽车收入增长替代集团盈利增长；手机、IoT 和汽车毛利变化要合并核算。不能用手机海外用户数机械推算汽车销量。

## 待结果验证

现阶段结论属于工作假说，没有后续真实经营结果或投资收益验证。每季将实际值与各次分析的 assumptions.md 对照；同时保留失败情景和未兑现判断。


## 原研究证据

空间相对路径：research/xiaomi-competitors-overseas-2026-10-21.md

SHA-256：49e8e7ff779a6b293d4770a52ce5d890250b9a2b7fc80d1a630fce3323d8f404


## 文档工作台归档验证

以下仅验证资料系统，不构成财务数据复核。

# 研习工作台浏览器观察

观察日期：2026-10-21。观察对象为 apps/investment-research 1.0.0 当前源码，资料均运行在临时隔离副本，未从测试页面修改正式研究文档。

- 浏览器：Codex in-app browser；桌面视口1440×1000，窄屏390×844，默认窄面板也查看过。
- 总览与公司：查看公司卡片、研究时间线、共享资料、规则和待验证入口。真实资料副本显示2家公司、2次历史分析、10项待验证、34份文档。
- 创建分析：在小米页面创建“浏览器验证：竞争与利润”，确认跳转新report.md，显示草稿日期及7个文档标签。
- 追加验证：填写问题、观察、原始URL，提交后verification.md显示UTC时间、未解决状态及输入内容。
- 编辑公共文档：在公司专用方法保存“浏览器保存检查：按业务拆解增长。”，刷新后可见；独立启动另一个服务进程读取同一临时目录，修改和新增分析仍可见。
- 新增公司：创建“隔离测试公司”，进入独立公共资料页面，公司数从2变3；正式资料库没有该测试公司。
- 全文检索：搜索“按业务拆解增长”，返回刚修改的公司方法文档。
- 情景：基期1000、年增长20%、净利率8%、3年，页面实时显示营收1728.00、利润138.24、累计增长72.8%，与公式一致。
- 真实报告：查看小米历史快照，显示待复核、来源链接及正文；没有正文编辑按钮。事后复盘页面仍有编辑入口。
- 窄屏：总览及长报告documentElement的clientWidth与scrollWidth均390；导航和报告标签可横向滚动，正文及表格在内容区阅读。桌面展示左侧导航、公司卡片和正文侧栏。
- 失败与修正：早期测试临时目录经过macOS /var符号链接而被拒绝，夹具改为真实路径后通过；编辑器标签补充明确关联后测试完成。未测试多用户并发、复杂CSV、自动行情、真实交易或长期性能。
- 设计判断：信息按公司公共资料/每次研究/验证与复盘分层；日期及复核状态先于正文，文档下载和持久位置可见。上述可用性观察不代表用户满意或投资判断正确。
- 正式托管：Compiler检查通过，仅申请binding.loopback和workspace.read-write；未替用户批准，未安装或启动生产实例。

截图：/tmp/investment-overview.png（隔离真实资料副本的桌面总览）。


## 首次归档文件清单

- companies/tencent/analyses/2026-10-21-initial/assumptions.md ｜ SHA-256 759c94a771a81617822097652733b28744d6960381cc2912127b93da224ec010
- companies/tencent/analyses/2026-10-21-initial/context.md ｜ SHA-256 4b62efaaff910fe59eeca08c86666a8838f0481fec0c3305d4be25dc41d5e93f
- companies/tencent/analyses/2026-10-21-initial/facts.csv ｜ SHA-256 ae197fbc306816d61269d4951b04c48f9b7fa533d1874e278b906c38d7ae9e36
- companies/tencent/analyses/2026-10-21-initial/report.md ｜ SHA-256 8a1b12d86a28ab674543d23d3005f5b75275a73626596bd22444c1adbfe5bb03
- companies/tencent/analyses/2026-10-21-initial/retrospective.md ｜ SHA-256 b6484455650baeb0071c86def5d903a95484b3a9b0d919a8e31f10b629b63156
- companies/tencent/analyses/2026-10-21-initial/sources.md ｜ SHA-256 46008eaed98d70140175cb247f586e0e9ccc928e06391bb2cdad7890c0bbadc2
- companies/tencent/analyses/2026-10-21-initial/verification.md ｜ SHA-256 0aa54589e6204823e819acae7741530f52ae258ed8c141319fc18de564a4f656
- companies/tencent/shared/README.md ｜ SHA-256 6e7141b96c6f2940bff965cd0a153f52d884250f8e1cb89095c13dc29fd645b6
- companies/tencent/shared/learnings.md ｜ SHA-256 eb576be02e8d780bd91bc605135d567be7e51d129015ea75179ec87d56a10745
- companies/tencent/shared/methods.md ｜ SHA-256 34906b680d010830a7327b6a2a9594c7b7d8cc620bd58170f4b4e57e72420afc
- companies/tencent/shared/profile.md ｜ SHA-256 a986ba9acba2265192349c653317fc116221e6194789044f8bb5df03835d3610
- companies/tencent/shared/questions.md ｜ SHA-256 cf07f647fc5361975cfa692ebf632ad7c6407e8f048c581386c3c0138dd818c5
- companies/tencent/shared/sources.md ｜ SHA-256 0b5a6751c9611d6aaaf846bb5d4480a7a465a40200da643d6b528e91c24e19bc
- companies/xiaomi/analyses/2026-10-21-initial/assumptions.md ｜ SHA-256 88267cac42d25fdd2365582c22d81d267921f31f5079602a2233be55fc2e3bd2
- companies/xiaomi/analyses/2026-10-21-initial/facts.csv ｜ SHA-256 06c3981a175759e1bcded1023d04c9508d9efb0471b9240245db7287fbd5af17
- companies/xiaomi/analyses/2026-10-21-initial/report.md ｜ SHA-256 8ebdb57b308f0cecee51cd0105fcb971437d0bf372e3d43e6396e008efb566a0
- companies/xiaomi/analyses/2026-10-21-initial/retrospective.md ｜ SHA-256 b6484455650baeb0071c86def5d903a95484b3a9b0d919a8e31f10b629b63156
- companies/xiaomi/analyses/2026-10-21-initial/sources.md ｜ SHA-256 8054645ef6db95db768a52bec85a23a6021d7d84d48e0ae60a2eb70a24791cda
- companies/xiaomi/analyses/2026-10-21-initial/verification.md ｜ SHA-256 0aa54589e6204823e819acae7741530f52ae258ed8c141319fc18de564a4f656
- companies/xiaomi/shared/README.md ｜ SHA-256 4abc1616d13551c621ae7cc9414852fb51595e912f6bdb3f3652086609ebf963
- companies/xiaomi/shared/learnings.md ｜ SHA-256 e6d93c560746cbb87d178231e07631fea85a94a00afb27cde77e4975f042ff99
- companies/xiaomi/shared/methods.md ｜ SHA-256 a5c041e22aac156bb2907a83a7bbcf0b1f665677acd166d0b1e34125786cf00a
- companies/xiaomi/shared/profile.md ｜ SHA-256 630e57e804b45b3ff6da0b0c082ab064274f14b0f79d980f29442e389aef97b7
- companies/xiaomi/shared/questions.md ｜ SHA-256 fa9b04656304824decbaa6889405bc43ec00b76dd33e820930829b12f7a392d3
- companies/xiaomi/shared/sources.md ｜ SHA-256 1822a16d46b9895fa43a625eeb6f7333a6ad482fe99b09aee2f4bcd7759f9c66
