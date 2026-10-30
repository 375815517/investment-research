# 可复用输入平台界面与协议验收

2026-10-30，在正式数据准入完成后重启 API 服务，使用实际仓库、浏览器与独立 CLI 对同一输入规格执行只读 `profile-assess`。下表反映当前声明范围，不等于完整财务研究、因子或预测可用。

| 规格 | 必需键满足数 | 用途状态 |
| --- | ---: | --- |
| 小米年度 core/v2 | 224 / 224 | ready，仅来源描述范围 |
| 腾讯年度 core/v2 | 219 / 224 | blocked |
| 小米季度、H1、九个月 core/v2 | 879 / 925 | blocked |
| 腾讯季度、H1、九个月 core/v2 | 919 / 952 | blocked |
| 小米 H1/Q2 公告 core/v1 | 327 / 333 | blocked |
| 腾讯 H1/Q2 公告 core/v1 | 321 / 333 | blocked |
| 小米经营 2024–2025/v1 | 16 / 16 | ready，仅声明经营字段 |
| 腾讯经营 2024–2025/v2 | 6 / 6 | ready，仅声明经营字段 |

缺项均明确为 missing，没有通过放宽匹配数量或同值去重掩盖 ambiguous。腾讯年度缺 5 个 gross 财务费用键；腾讯季度规格缺 33 个 gross 财务费用键。小米季度缺 22 个 gross 财务费用键和 Q4 归母利润、基本 EPS、稀释 EPS 各 8 个。公告规格缺少小米 6 个、腾讯 12 个 gross 财务费用键。净财务收入/费用保存在独立指标下，不能代替这些要求。小米年度 v2 购建资产支出保留原披露范围，不能推导为 PPE-only 或跨公司可比较。

八项 API 请求均返回 HTTP 200，界面显示实际用途状态和每个必需键。CLI 与 API 的总体状态、逐键匹配状态/数量、限制 findings 完全一致；ready 返回 CLI 0，blocked 返回 3。网页没有运行时错误；新的财务观测数据集禁用旧版自动补采入口。人工核对了缺项表及就绪经营表截图。

证据位于 [final-browser](../../data/outputs/research-records/dual-company-input-profiles-20261030/final-browser/acceptance.json)，同目录包含八份完整逐键评估和两张浏览器截图。规格及版本的定义见 [输入规格说明](../../research/input-profile-definitions/README.md)。宿主投影的文件校验不代表宿主原生发现或语义执行已验证；本验收仅覆盖实际浏览器、HTTP API 和 CLI。
