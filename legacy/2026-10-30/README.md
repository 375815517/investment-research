# 研习 · 投资研究

以证据形成判断，以持续跟踪验证判断，通过复盘积累研究方法。当前作为独立 Git 项目维护，项目根目录为 `/Users/zhuqiang/Dev/investment-research`。文档、数据与 Web 源码统一归属本仓库；尚未接入新的 Oriel Workspace。

## 从这里开始
- [研究规则](framework/rules.md) · [分析方法](framework/methodology.md) · [数据规范](framework/data-contract.md) · [公共经验](framework/lessons.md)
- 行业方法：[手机](industries/smartphones/methodology.md) · [汽车](industries/automotive/methodology.md) · [平台](industries/platforms/methodology.md)
- 公司：[小米](companies/xiaomi/knowledge/README.md) · [腾讯](companies/tencent/knowledge/README.md)
- [小米成长研究](companies/xiaomi/analyses/2026-10-21-growth-evidence/report.md) · [小米历史研究](companies/xiaomi/analyses/2026-10-21-initial/report.md)
- [开源实践调研](framework/references/2026-10-21-open-source-practices.md)
- [目录迁移记录](docs/migration.md) · [Oriel项目与应用升级诉求](docs/oriel-project-app-proposal.md)

## 内容归属

```text
framework/          通用规则、方法、数据规范、经验、模板与参考研究
industries/         按行业组织的公共方法（有资料再增加来源和数据）
companies/<公司>/
  knowledge/        公司概况、专属方法、数据源、待验证事项和经验
  sources/          外部证据原件及登记
  data/             动态行情、原始响应、事件和展示结果
  analyses/<研究>/  独立报告、事实、假设、冻结输入、计算、验证与复盘
apps/research-web/  项目内唯一的可视化应用源码
tools/             采集、计算、校验与可选打包工具
docs/              项目组织决定、迁移与后续交接
```

公司知识可持续更新；每次分析保留当时上下文与输入。历史报告、原始PDF和计算记录不因目录迁移改写；历次分析内部路径暂时保持，避免破坏证据链。旧研究正文归入analyses，不当作外部原始来源。

## 数据与计算

在项目根建立本地Python环境，安装requirements.txt中固定版本的DuckDB后：

```sh
python tools/pipeline.py refresh
python tools/pipeline.py calculate --analysis companies/xiaomi/analyses/2026-10-21-growth-evidence
python tools/test_pipeline.py
node --test apps/research-web/test.js
```

refresh显式更新动态行情；calculate读取对应分析的冻结输入。没有自动更新定时任务。PDF/Markdown/CSV/JSON是文件资产，DuckDB读取分析，计算结果和显示视图可以重建。

## Web模块

当前以项目优先，退出旧应用托管；Web源码保留，应用不是项目的唯一入口。需要本地开发预览时，在项目根执行：

```sh
node apps/research-web/server.js --library-root "$PWD"
```

可选 `node tools/build-web.mjs` 只在 `.build/research-web/` 生成包，不写Default/apps，不安装或启动应用。Oriel的项目默认应用和引用关系待后续升级，不采用“复制并纳管”建立第二份研究资产。
