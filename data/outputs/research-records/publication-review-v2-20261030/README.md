# 年报公开日期复核（2026-10-30）

小米 2018–2025 年报的公开日采用发行人 IR 页面内嵌的 Euroland 公告列表。列表明确给出年报标题、展示日期与附件关联 ID；已保存官方响应原件，而非从附件 URL 或董事会批准日推测发布时间。

- 2018: 2019-04-08；2019: 2020-04-26；2020: 2021-04-26；2021: 2022-04-27。
- 2022: 2023-04-26；2023: 2024-04-25；2024: 2025-04-24；2025: 2026-04-28。
- 七份公告附件与此前归档原件 SHA-256 完全一致。2024 年附件 PDF 二进制不同，但 379 页逐页去空白提取文本完全一致；交换所附件也已归档，修订记录明确说明内容等价与二进制同一的区别。
- 日期按香港市场日历（Asia/Hong_Kong）解释，精度为 date。系统用下一日当地零点作为保守可用上界，`published_at` 仍为空；不把列表内部未明确定义时区的 epoch 当成准确发布时间。
- 修订保存在各原件旁 `metadata-revisions/`，没有覆盖旧 `document.json`；登记与当前首次观察时间均没有回填。

`pit-examples.json` 是实际 Repository/evidence_time 查询：每份年报在日期保守上界前不可用、上界起 historical_reconstruction 可用；同一历史时点 live_observed 不可用，因为系统当时尚未见到原件/登记修订。原始断言仍可用 revision_id=original 固定。`xiaomi-publication-revisions.json` 保存具体请求与结果；`evidence-imports.json` 保存证据原件引用；`attachment-identity-checks.json` 记录附件关联与哈希。

注意：自动门禁验证引用原件与摘录存在，不自动理解“日期与特定年报”的语义关联；以上关联由具名 AI reviewer 对官方列表、附件及目标原件核实。真实公开日不代表年度全文内容在报告年末已可知。

腾讯 2018–2025 年报使用 HKEX 正式 Title Search 返回的 `Release Time`、证券代码 00700、年报标题与 PDF 链接。同样只采用日期精度：2018 年报 2019-04-01；2019 年报 2020-04-02；2020 年报 2021-04-08；2021 年报 2022-04-07；2022 年报 2023-04-06；2023 年报 2024-04-08；2024 年报 2025-04-08；2025 年报 2026-04-09。列表虽展示分钟，本次不宣称精确到秒。七份链接 PDF 哈希完全一致；2023 年报二进制不同但全部 282 页去空白文本一致，对照 PDF 已另行归档。对应请求、哈希与 PIT 验证见 `tencent-*.json`。

HKEX 查询可复用：先用 `/search/prefix.do?lang=EN&type=A&name=00700&market=SEHK&callback=callback` 解析发行人内部 `stockId=7609`；向 `/search/titlesearch.xhtml?lang=en` POST 表单 `lang=EN, category=0, market=SEHK, searchType=0, documentType=-1, t1code=-2, t2Gcode=-2, t2code=-2, stockId=7609, title=ANNUAL REPORT, from=20190101, to=20261030`。须检查发行人、标题、日期范围、结果数及分页，不以内部 stockId 代替用户确认主证券。

两个文本等价案例已追加新修订版本：supporting_document_ids 同时绑定对照 PDF 与逐页规范化文本 SHA-256 比较报告；原修订保持不变。读取修订会验证 supporting 原件哈希，effective metadata_evidence_refs 暴露全部依赖供冻结包自动收集。见 supporting-evidence-revisions.json 与 equivalence-evidence-imports.json。比较报告明确为 AI 审核衍生证据，不伪装为发行人原文。

另补 2018–2026 双方中报：使用同一 HKEX 查询，标题换成 INTERIM REPORT、日期起点改为 20180101，小米 stockId 由证券代码 01810 精确匹配得到 190371。返回各 9 条；日期修订及三种 PIT 查询见 `*-interim-*.json`。中报正式全文的公开日期可能晚于半年度业绩公告，不能用后者时间直接回填前者全文。当前记录选择中报全文自身证据，不宣称最早业绩可知时间。

季度业绩公告公开日另行补证：腾讯 Q1/Q3 17 份与年度结果公告（含直接披露 Q4）8 份；小米 Q1/Q3 16 份与年度结果公告 8 份。腾讯复用已归档的逐年 HKEX 官方列表，用精确 href、已捕获 collection 的 final_url 与 SHA-256 绑定当前归档原件；完整收集凭据副本导入为具名 AI 派生审核证据并作为 supporting document。小米 IR 存量原件与新读取 HKEX 列表的 24 个对应附件逐份 SHA-256 完全一致。全部采用官方表格内 Release Time 的日期部分，日期精度保守上界规则不变。

季度结果与查询保存在 `*-quarterly-publication-revisions.json`、`*-quarterly-pit-examples.json`，未覆盖前述年报/中报 102 条查询。小米 2018 Q1 上市前未在当前 16 份目标中，2026 Q3 截至 2026-10-30 尚未见结果公告，均不伪造缺失历史。Q4 公告发布日期属于年度业绩公告自身，不等于后来正式年报 PDF 的发布时间。

半年度业绩公告版本：另补两企业 2018–2026 各 9 份 H1/Q2 公告原件的独立公开日。腾讯来自同一官方 HKEX 逐年列表及对应收集 URL/哈希；小米 9 份 HKEX 附件均与 IR 存量原件 SHA 完全一致。不能以正式中报的较晚出版日替代。新增 `*-h1-announcement-*.json`，54 条 PIT 检查通过；此前 249 条保留，总计 101 份研究源文档日期、303 条 PIT 查询。
