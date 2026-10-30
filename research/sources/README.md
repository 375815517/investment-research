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
