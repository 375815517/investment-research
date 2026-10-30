# 数据准备闭环的 AI 协作设计

范围：原始资料获取、整合、缺口补齐与准入；不执行指标、预测、复盘或定时任务。正式数据操作由共享 engine 实现，AI 层不复制缺口算法、来源映射、准入策略和写入逻辑。

多源数据沿用同一执行边界：需求与渠道覆盖先行，领域语义见 [多源规则](../rules/multi-source-inputs.md)。probe 不设自有数据集白名单或重新实现领域合同；将 dataset_id 原样交给 CLI，未知数据集由正式合同拒绝。

## 流程与责任

1. data-planning 读取能力与合同，调用 detect_gaps，区分可判断缺口与 unknown_expectation。
2. data-acquisition 通过 ensure_plan 固定需求、预期依据、来源和有界请求；已授权且可执行的计划交 ensure_apply。
3. data-review 处理需复核的候选及准入问题。ensure_apply 不自动批准 AI 提取；review_required 必须保留。
4. 获取/整理完成后重新 detect_gaps；只有复查满足期望才称为 complete。已有原件不等于结构化记录齐全。

CLI 和 engine 负责确定状态。Skill 解释状态，不把 blocked、unknown_expectation、historically_unavailable 或 review_required 改写为成功。现有 collection/prepare/validate/review/ingest 仍是执行组件和人工补录入口，不构成第二套流程。

## 实际验证与适配边界

`python -m investment_ai.probe` 只执行 capabilities 与 detect-gaps（默认）或 coverage（显式选择），记录所读 canonical Skills 摘要、请求摘要、CLI 退出码与结果摘要，保存到本机 `.research-local/ai-verification/`。该工具不触发 ensure_apply，不写正式 data，不安装宿主投影。它验证显式文件阅读路径和 CLI 操作协议；无法证明模型理解、原生发现、独立语义审核或后台调度。

真实 Codex 会话可以显式读取 Skill 后执行工具并保存该回执。应把‘本次显式调用已验证’和‘native discovery 未验证’分别报告。CodeBuddy 仍需实际宿主验收，不能复用 Codex 回执宣称支持。

## MCP 与 Hook 最小建议

当前 CLI 已能满足宿主工作，不增加第二条执行通道。将来确需 MCP 时，只将 capabilities、detect_gaps、ensure_plan、ensure_apply 和 operation status 映射到相同请求/响应合同，认证、调用超时和操作 ID 单独验收；不在 MCP 中实现存储规则。

当前 Hook 禁用。若宿主版本确认支持，再增加只读启动检查（doctor/能力检查），输出是否需同步 Skill 的提示；Hook 不自动采集、不 apply、不提交，也不承担唯一历史保护。关闭 Hook 后完整数据流程必须仍可运行。

## 验收

- 未提供可靠的交易日历/披露预期时返回未知，而不是编造缺失列表。
- 历史 live_observed 缺口明确不可通过今天补采修复。
- 计划固定摘要；输入改变后不得沿用旧计划。
- ensure_apply 返回需审核时，不以重复 apply 绕过复核。
- probe 使用实际安装 CLI、拒绝无协议 JSON、保留退出码，不能将合约错误包装成验证通过。
- 不创建投影或修改 native discovery 状态；最终同步由主执行者显式完成。

新资料类型尚无自动期望合同，因此 `--operation coverage` 验证实际读取调用，返回 available/missing 等原始状态并固定 completeness=not_assessed；不转换为 complete。默认 detect-gaps 仍由正式合同决定是否支持数据集，合同错误不能生成调用成功回执。两条路径都不执行写入或采集。
