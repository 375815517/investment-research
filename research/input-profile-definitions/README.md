# 输入规格生成定义

`dual-company-v1.json`冻结已批准范围，生成工具只读取该定义、指标字典和已确认证券身份，**不读取已有观测来决定必需字段**。

```bash
uv run python scripts/build_input_profiles.py
```

输出位于`research/input-profiles/<profile-id>/v1.json`。重复同一请求幂等；改变已存在版本的需求会冲突，应显式升版并保留原需求和评估。年度和年末时点有明确默认边界；月度、中期/季度必须在定义中提供准确起止月日，不从自然年猜测统计窗口。

- 两家公司`annual-core`各28项×2018–2025八年=224个必需键：损益10项、资产负债12项、现金流6项（含购建资产现金支出）。不因某年未披露或未提取降低门槛。
- 两家公司`annual-valuation-dependencies`各24个键：加权平均基本/稀释股数，以及报告中相应年初的现金余额比较期；该包只是已定义依赖，不代表完整估值输入。有效发行股数、股类、价格/利润窗口和汇率仍要另外检查。
- 小米`operating-2024-2025`16个键：年度手机出货、12月全球/中国手机平板MAU、米家/AI助手/电视盒棒MAU、年末AIoT设备、年度汽车交付。维度由原披露语义定义，不将缺失补零。

财务原值允许不同数量级，比较/转换另需明确规则。来源固定小米各年度年报和腾讯官方报告渠道；当前使用原始、IFRS、CNY、合并集团维度，重述/其他范围不能无声替代。所有包以逐键状态与用途评估为准，生成成功不是数据已取得。

腾讯`operating-2024-2025`6个键：12月微信/WeChat合并MAU、手机QQ MAU、第四季度平均每日付费增值服务订阅数。最后一项按原脚注为季度平均，不保存成期末存量；2024Q1起口径变化保留在原件与basis中。

## 腾讯经营规格 v2 时间精度更正

`腾讯 operating v1`曾按12月完整窗口声明MAU需求；复核原始表头只有As at 31 December，不能证明窗口开始日。`tencent-operating-v2.json`保持相同两个年度、三项字段和总体维度，MAU改为期末披露的月活统计（period_measure/instant），不补造12月1日。第四季度平均每日付费订阅窗口仍明确为10月1日至12月31日。v1与首次核查保留，不静默改写；后续真实适用性以v2为准。

```bash
uv run python scripts/build_input_profiles.py --definition research/input-profile-definitions/tencent-operating-v2.json
```

## 年度原披露范围 v2 与季度逐字段规格

`dual-company-annual-v2.json` 生成两家公司 annual-core/v2，各 224 个必需键；v1 的 PPE-only 严格规格保留。v2 仍是每年 28 字段，只把 16 个公司年度的购建资产现金支出键改为对应原披露范围：小米 2018–2024 为 capital-expenditure-cash-payments，2025 为 property-land-intangible-cash-payments；腾讯 2018–2025 为 property-construction-investment-cash-payments（2024/25 原行包含预付款）。依据是各年度现金流量表原行及归档候选，不把混合项目强拆成 PPE。此规格用途为 source_description，未设置跨公司 capex 比较组；覆盖完成不代表可直接同比或生成因子。

`dual-company-interim-quarterly-v1.json` 独立声明季度、中期及九个月累计需求，不以当前提取到的字段裁剪分母。小米 Q1 为 2019–2026，腾讯 Q1 为 2018–2026；双方 H1、Q2 为 2018–2026，Q3、九个月累计和 Q4 为 2018–2025。小米 2018 H1/Q2 虽属上市前期间，上市后公开的资料仍保留；不要求尚未公开的 2026 Q3。

| 期间 | 每期必需字段 | 小米键数 | 腾讯键数 |
| --- | ---: | ---: | ---: |
| Q1 三表 | 27 | 216 | 243 |
| H1 三表 | 27 | 243 | 243 |
| Q2 单季损益 | 10 | 90 | 90 |
| Q3 单季损益 | 10 | 80 | 80 |
| 九个月累计三表 | 27 | 216 | 216 |
| Q4 单季损益 | 10 | 80 | 80 |
| 合计 | | 925 | 952 |

三表 27 字段为年度核心去掉购建资产现金支出；10 个损益字段包括收入、销售成本、毛利、经营利润、财务费用、所得税、净利润、归母利润、基本及稀释 EPS。存量键取准确季末/半年末，单季和累计流量保留不同起止日期。Q4 按年度业绩公告 IFRS，其他期间 IAS34。官方资料可能通过多个已登记渠道发布，因此不绑定单一 source_id；每键仍要求唯一匹配，冲突不得自动挑选。缺失归母、EPS、gross 财务费用等按缺口报告，净财务收入/费用不能替代 gross 需求；Q4 不用全年减累计隐式伪造 source_reported。

生成器支持字段显式 `years` 范围、规格或字段会计口径、规格来源限制；所有配置均版本化，变更已写出的同版本规格会被拒绝。以上命令同前，仅替换 `--definition` 路径。

### 报告渠道与公告渠道分开（季度 v2）

季度 core/v2 保持上述 925/952 分母，明确每个键的 source_id，取代 v1 的不限定渠道匹配。H1/Q2 正式中报固定 xiaomi-reports/tencent-reports；小米 Q1/Q3 为 xiaomi-results，Q4 2024 为先前归档的 xiaomi-2024-results、其余为 xiaomi-results；腾讯 Q1/Q3/Q4 至 2024 为 hkex-tencent-announcements，2025 起为 tencent-results。来源身份来自已登记官方归档渠道，不能因内容相同而重写文档身份。

另以 `dual-company-interim-announcement-v1.json` 生成两家 interim-announcement-core/v1，各 333 必需键（H1 243 + Q2 90），选择较早发布的业绩公告：小米 xiaomi-results；腾讯 2018–2024 hkex-tencent-announcements，2025–2026 tencent-results。两种资料分别审计，不叠加计算完成率，也不把不同披露日资料自动去重。旧季度 v1 保留，其无来源限定可能如实报告 ambiguous；所有版本 max_matches 均为 1。

## 年初现金与股本补充

`dual-company-opening-balance-v2.json` 明确请求当年1月1日的直接披露期初现金；旧v1前一年12月31日口径保留，不能以字段名“opening”把两个日期静默等同。两者均仅包含加权股数和现金的有限前置数据，不是完整估值输入认证。

`year-end-issued-shares-v1.json` 要求两公司2018–2025年末发行股数，以及小米2024–2025 A/B股类明细；2023小米股本冲突保留需求并隔离候选，不能用数量覆盖掩盖矛盾。
