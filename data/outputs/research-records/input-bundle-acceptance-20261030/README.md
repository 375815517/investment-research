# 真实输入包冻结、恢复与故障验收

本轮使用公共 Service 操作 `normalize_inputs → freeze_inputs → verify_bundle`。规范化目标为 `units`，源观测不改写。

| Profile | 行数 | 规范化 | 适用性 | 新目录新进程恢复 |
|---|---:|---|---|---|
| market-window-sfc-2025-2026 | 36 | normalized | limited | verified |
| xiaomi-operating-2024-2025 | 16 | normalized | ready | verified |
| tencent-operating-2024-2025 | 2 | blocked | blocked | verified |

每个包均从 manifest 复制正式证据、元数据、批次、转换记录、Python 源码及锁文件到独立 `/tmp/investment-input-recovery-*` 目录；不复制 `.research-local`、原工作区缓存或 `.git`。子进程断言 engine 和 repository 来自复制目录，再校验原件 hash、源码 hash、转换重放。依赖解释器使用当前锁定环境，未宣称离线重新安装依赖。

对三个恢复目录分别注入：原始附件字节篡改、转换源码变动、缺失原件。三类故障均返回 blocked；逐一还原后均 verified。故障只发生在临时复制件中，原仓库证据不变。

腾讯初次经营 profile 的月份起止与来源 As At 口径不一致，四个 MAU key 缺失，规范化正确阻断；该包作为失败状态可复现的负例保留，未缩小预期分母。

这是正式文件复制恢复验收，尚不等于最终提交的 `git clone` 验收。冻结 hash 绑定当时全部 Python 源码；后续代码变动应建立新包，不能修改旧包的 hash 来绕过检查。最终提交后由主流程进行真实克隆验收。

详情、bundle ID、隔离目录、转换值及每次故障回执见 `acceptance.json`。

## 腾讯修正版正例

腾讯经营 v2 按原件 As At 使用 instant，保留 period_measure 和活跃账户维度，不虚构月初。6/6 条观察规范化成功、适用性 ready；新目录新进程恢复 verified。原件篡改、实现篡改、缺失原件均阻断，还原后 verified。旧 v1 阻断包保留为负例。

修正版 bundle：`inputs-4dbaad558621ccc449f56f4859b536ce`。

## 后续源码保全

开发继续修改实现后，旧包在当前工作区验证按预期阻断。已从上文临时恢复目录按原 SHA-256 找回全部四个包的确切实现（每包 44/45 个文件），去重归档到正式 `implementation-files/`，并建立独立 companion manifest，不修改旧 bundle。详见 `legacy-implementation-preservation.json` 与 `legacy-preserved-verify.json`。当前四包均 `implementation_recoverable=true`；实际重放仍须在隔离环境恢复对应源码及锁定依赖，不能将此状态说成当前版本验证通过。
