# 研习 · AI 协同投资研究工作空间

长期研究企业、行业与市场，持续积累资料和行情；通过可追溯的分析、预测、评估和复盘，改进研究方法、因子与模型。

整个仓库根目录就是人和 AI 的工作入口。AI 提供理解与研究组织，平台执行明确口径的计算并保存事实，可视化呈现同一结果。

## 从这里开始

- [架构与目录合同](docs/architecture/research-workspace.md)：本次确定的目标、三层架构、方法与执行边界、数据组织、多宿主适配和协作。
- [Git 数据管理约定](docs/operations/git-data-management.md)：数据目录、历史版本、云端与服务器同步、恢复规则。
- [AI 工作入口](AGENTS.md)：当前工作范围与阅读规则。
- [旧内容暂存说明](legacy/README.md)：历史研究、数据与旧代码的保留位置。

- [输入数据结构基线 v1](docs/architecture/input-data-baseline.md)：正式目录、原件归属、主证券和历史时点规则。
- [研究数据与 AI 检索设计](docs/architecture/research-data-design.md)：行情、实体关系、事件影响、知识记录与实施顺序。
- [研究证据规则](ai/rules/research-evidence.md)：所有研究 Skills 共享的证据约束。

- [实施计划](docs/plans/input-platform-implementation.md)：模块、依赖和分期验收。
- [运行手册](docs/operations/input-platform.md)：安装、CLI、数据与宿主适配。
- [验收记录](docs/verification/input-platform-v1.md)：实际通过项和未完成范围。

## 当前状态

已实现首版 Python workspace、CLI、原件归档、候选校验/复核/入库、状态与索引、HTTP来源基础和宿主文件适配。离线样例仅用于验收，真实小米数据源、宿主原生调用、完整历史版本解析和API/worker/web的状态见验收记录。

| 目录 | 用途 |
| --- | --- |
| `ai/` | 共同规范、Skills、Hook、宿主适配与初始化工具 |
| `apps/` | 网页、API、CLI 与后台任务入口 |
| `packages/` | 领域合同、研究执行、外部接入和数据访问实现 |
| `research/` | 数据集合同、研究规则、来源、指标、因子、模型与流程定义 |
| `data/inputs/` | 企业、行业、市场、宏观、政策和事件资料 |
| `data/outputs/` | 企业/行业/市场研究、指标值、预测、评估、复盘与研究记录 |

输入与成果均纳入 Git。原件集中在 `data/inputs/source-files/`，采集记录在 `collection-records/`，整理结果放在具体业务目录；每次研究的输入版本清单保存在 research-records，完整目录见架构文档。数据库和索引仅作为可重建的查询缓存。大文件可按需使用 Git LFS，目前尚未配置。

目标体验是克隆后能理解项目，初始化后能运行离线示例，配置数据来源后能持续采集和研究。当前不能把目录已建立视为这些能力已经可用。

## 快速验证

```bash
uv sync --locked --group dev
uv run --locked research --json doctor
uv run --locked python scripts/demo_input_pipeline.py
```

演示使用临时工作区的合成数据，不写正式研究档案。完整检查使用 `bash scripts/check.sh`。
