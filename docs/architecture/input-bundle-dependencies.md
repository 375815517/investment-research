# 输入包的精确定义依赖

`InputRequirementProfile.definition_refs` 可声明生成该需求所依赖的日历、对象注册或其他定义文件。最多 256 个唯一引用，每个路径最多 512 字符，必须是 `research/` 或 `data/inputs/` 下的相对文件路径；拒绝路径穿越、反斜线、空段、控制字符和符号链接。来源原件与 document metadata 也可逐文件显式声明。声明的文件不存在时冻结阻断，不能静默略过。

冻结会自动固定每条实际 v2 财务/经营观察所对应的 `research/metrics/<metric_id>/v<metric_version>.json`，并按该定义再次检查观察的单位、期间和维度。必须存在对应字典和 `research/units/scales.json`；v2 输入不能退回“无定义也接受”。旧 financial-facts 合成测试环境没有这些目录时保留兼容；真实工作区存在尺度目录时仍固定其文件。

所有声明和自动识别的依赖进入 bundle 的逐文件 SHA-256 清单。验证只读取冻结的具体文件，不扫描整个研究目录、不把无关新文件加入旧包，也不以当前新数据替换原输入。修改指标字典、尺度文件或声明的交易日历将导致 `verify_bundle` 返回 blocked。

本接口不自动发现日历生成的隐藏依赖。profile 作者必须列出真实使用的日历规则及原件证据，而不能仅写一个未存档的网址。字段缺省为空不代表不存在外部依赖。

已生成的旧输入包保持不可变，不补写新字段或重算旧 hash；采用该依赖机制的正式验收应重新冻结建立新包。软件源码变动同样需要建立新冻结版本。

## 未提交实现的保全

新冻结在保存 manifest 的同时，把实际 Python 源文件、`pyproject.toml` 和 `uv.lock` 的原始字节按 SHA-256 去重归档到 `data/outputs/research-records/implementation-files/<sha>/source.txt`；每条 implementation 清单增加 `archive_ref`。即使冻结时工作区含未提交修改，也能从 Git 中的归档恢复该份确切源码，而不依赖旧 HEAD 恰好包含这些字节。

验证同时检查归档和当前实现。当前实现不同仍返回 blocked，并提供 `restore_from`，要求先在隔离 checkout 恢复再验证。归档损坏或缺失也阻断。工具不会导入、运行或自动恢复归档源码；`.txt` 仅存原始字节。

旧包不修改正文或标识。本次从此前独立恢复目录找回四个旧包所需的全部匹配源码，在其目录新增 `implementation-companion.json`；companion 绑定旧包原始 SHA-256、完整源码路径/hash清单与内容寻址归档。无法找回全部字节时不得宣称可恢复，应登记开发期验收局限。本轮四个包全部找回，但在当前新实现上验证仍按预期阻断；`implementation_recoverable=true` 只证明源码可恢复，不等于当前环境验证通过。
