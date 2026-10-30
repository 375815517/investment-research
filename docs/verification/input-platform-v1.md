# 输入平台 0.1 验收记录

日期：2026-10-30。范围：[实施计划](../plans/input-platform-implementation.md)中的首版工程基建。本文区分本地离线验收、真实来源探测和待验证能力。

## 已通过

| 模块 | 实际验收与结果 |
| --- | --- |
| 工程底座 | Python 3.12.14，uv 锁定安装；独立 `/tmp` 虚拟环境再次安装成功 |
| 静态检查 | Ruff 检查和格式检查、mypy 全部通过 |
| 自动测试 | 65 项离线测试通过：core 19、connectors 24、CLI 11、AI 10、publication 1 |
| 构建 | domain、repository、engine、connectors、cli、ai 六包 sdist 与 wheel 构建成功 |
| CLI 闭环 | 合成行情和财务资料完成 17 步：导入、去重、候选、校验、财务复核、计划、入库、重复 NOOP、时点查询、索引重建；独立虚拟环境重复通过 |
| 数据保护 | 非法 OHLC、未知真实证券、行情候选覆盖原件、清单与数据不一致均阻断；候选/复核变更使计划失效 |
| 历史与恢复 | 历史模式过滤、A→B→C 连续修订、滚动窗口同源去重保留证据、多批次中断重放及失败连接器回执测试通过 |
| AI 文件工具 | 安装、NOOP、冲突保护、旧计划失效、断点恢复、卸载只删归属文件及链接重写测试通过 |
| 发布检查 | 显式路径清单检查，阻断无关暂存、legacy 修改和正式输入覆盖；不是自动发布服务 |

执行命令：`UV_CACHE_DIR=/workspace/.cache/uv bash scripts/check.sh`。干净环境检查使用 `UV_PROJECT_ENVIRONMENT=/tmp/investment-research-acceptance-venv` 锁定安装，再执行 pytest 与 demo。默认测试不联网、不调用模型。CI 配置已加入，但远程 CI 是否通过须查看后续真实运行结果。

当前工作区已生成 8 个 Codex Skill 投影，filesystem verified、source_current true。临时工作区中的 Codex 和 CodeBuddy 均得到同样的文件验证结果；30 份入口、规则、文档与投影 Markdown 的本地链接检查无缺失。原生发现和调用状态保持未验证。

## 小米与来源

用户已确认小米主证券为港股 **01810 / HKD**，确认记录位于 `data/inputs/companies/xiaomi/profile/2026-10-30-confirmed/` 与 `data/inputs/markets/securities/xiaomi-hk/2026-10-30-confirmed/`。这表示研究范围确认，不表示官方证券主数据已验证。

一次 Yahoo chart 网络探测取得 1810.HK 数据：响应元信息为 HKD、HKG、Asia/Hong_Kong；请求 2026-10-19 至 2026-10-24，返回 4 条日记录。这只能证明本次可访问及响应形态，不能证明完整交易日覆盖、长期可用或未复权口径。探测文件留在临时区，未纳入正式行情。

`research/sources/yahoo-chart/source.yaml` 明确归档许可 unknown，collect 按配置阻断。解析结果标记 provider-native，不冒充已核实的 unadjusted。**M2 真实小米行情准入尚未完成**；须核实来源归档条件、调整口径和数据覆盖，或登记满足条件的其他来源，不通过手工 import 绕过同一阻断。

## 可用范围与后续事项

- M0、M1：本地工程与固定输入合同闭环已验收。当前仅 daily-prices、financial-facts 两种可执行数据集合同；YAML 引用类型，不是动态规则语言。
- M2：连接器基础已验收；真实生产来源仍待上述条件完成。
- M3：AI 候选、证据定位字段与摘要绑定复核已实现；没有 OCR 或真实模型调用。reviewer 是登记字段，不是身份认证，语义真实性需实际核实。
- M4：Codex/CodeBuddy 的文件适配与离线测试通过；原生发现 unknown、实际调用 not_tested、Hook disabled。CodeBuddy 为实验性文件适配。
- M5：API、定时 worker、web、MCP 和自动 Git 发布是后续任务，未实现。

单批次以完整清单作为可见性边界；多证券多批次不承诺全有或全无。coverage 可以按时间及显式修订取版本，但没有完整交易日历和跨来源裁决。公开时间由导入者提供，不自动证明当时已公开。历史查询与预测回测仍须审查可知性。

演示数据仅在临时工作区，不进入真实企业档案。原有 legacy 删除保持未暂存，不属于本次变更。云环境保存的配置及旧外部安装脚本未自动改写，新工程安装方式以运行手册为准。
