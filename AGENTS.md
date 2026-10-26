# 研习项目工作约定

本项目是独立 Git 仓库，根目录为 /Users/zhuqiang/Dev/investment-research。尚未接入 Oriel Workspace；既有 Default 任务属于历史记录，不复制其状态，也不借用旧 Claim 执行新工作。用户明确要求接入时再使用受支持入口。
先读README.md、framework/rules.md、framework/methodology.md和framework/data-contract.md，再读目标公司knowledge及具体analyses。

长期资产只有这一份：framework通用、industries行业、companies公司。公司公共知识在knowledge；每次分析独立留档，固定当时输入、上下文和假设，不用新行情改写旧结论。

历史报告、PDF、冻结CSV、计算参数/结果/manifest保持可追溯；新增研究按framework/templates与已有analyses格式创建。原始证据与研究者撰写的历史报告不得混同。

Web作者源码只在apps/research-web；tools/build-web.mjs只写本项目.build/research-web。当前不正式托管，不能重新创建Default/apps投资研究副本。原来的shared、playbooks等链接由阅读模块兼容解析，新内容一律使用新路径。

迁移或新建路径前核对项目内消费者；不在旧 Default 空间另建研究资产副本。Oriel升级诉求在docs/oriel-project-app-proposal.md，仅记录待转交，不代表已发出。
