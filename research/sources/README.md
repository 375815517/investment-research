# 数据来源定义

实际来源使用 `<source_id>/source.yaml`。当前实现支持显式注册的 `http-csv-v1`：返回标准 CSV 的 HTTP(S) 来源；未接通任何真实证券供应商。浏览器/用户取得文件可通过统一 `research data import` 导入。

最小配置如下，仅为说明，不是已接通的数据源：

```yaml
source_id: example-prices
name: 示例行情来源
connector_id: http-csv-v1
dataset_id: daily-prices
url: https://example.invalid/prices.csv
allowed_parameters: [symbol, start, end]
required_columns: [security_id, trading_date, open, high, low, close, volume, currency]
timeout_seconds: 15
max_bytes: 10000000
max_attempts: 2
retry_delay_seconds: 0.25
archive_permissions: unknown
known_limitations: [未验证接口与历史覆盖]
# auth_env: RESEARCH_PROVIDER_TOKEN
```

获取前须确认归档许可，并明确设为 `allowed`。认证只引用环境变量名，使用 HTTPS Bearer 头；不支持 URL 内嵌密钥。默认继承环境代理与 TLS 校验。配置限制重试、超时、响应大小和参数，禁止任意脚本连接器。`source check` 不联网，只报告配置、实现、认证变量是否存在；网络可达和业务覆盖仍是未检查。

响应只做 CSV 格式及声明列检查；原件通过统一 import 归档，随后 prepare/validate 进行业务校验。不能把 acquired 状态当成已入库或完整覆盖。原件包含多只证券时也只归档一次。

暂未支持：供应商特有 JSON 字段映射、分页、长期调度和真实来源健康监控。新增这些能力必须增加显式实现与离线样本测试。

### 公开报告与有限研究采集

`http-document-v1` 只接收有 PDF 文件标识及末尾标记的原件，原件仍通过共享 import 归档。
`extract_pdf_page(path, page)` 使用 pypdf 按从 1 开始的 **PDF 物理页**提取文本；
扫描件空页不补写文字，须走另外审阅的 OCR 流程。打印页码与物理页码不能混用。

`archive_permissions: research-only` 表示用户授权本项目为研究获取公开原文，必须同时填写
`usage_basis` 说明依据。这不是来源方开放许可，也不授权再分发。`restricted` 仍阻止采集；
已知的来源限制不能由用户研究授权覆盖。`unknown` 表示尚未完成用途判断，需先调查记录，
不意味着网络失败或者永久禁止研究。真实公开来源的当前用途与未确认事项记录在各 source.yaml。

`tencent-kline-v1` 保存 JSON 原件，并提供 day 分支的来源观测值。响应 MIME 有时为 text/html，
因此该适配器根据完整 JSON 结构判断，真正 HTML 错误页仍拒绝。成交量单位与历史复权口径
尚未核实，候选显式标记 unverified/provider-native，不将其转换为未复权标准日线。
