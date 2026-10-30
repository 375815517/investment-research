# 项目级宿主适配工具

`investment_ai.HostManager` 是 CLI 的宿主文件适配实现，仅处理工作区内的投影。权威方法仍在 ai/skills，根入口不由本工具覆盖。

`inspect/verify` 只读；`plan/sync/repair/uninstall` 默认只返回计划，`save=true` 才将计划保存在 `.research-local/hosts/plans/`；apply 根据 plan_id 检查源、目标、回执和计划摘要后执行。CLI 的 `--save` 映射为该参数。

回执记录生成文件及摘要；用户修改、未知归属文件和符号链接目标受到保护。安装中断保存 pending 计划，重复同一 apply 可以接续。卸载仅处理回执拥有且内容未改变的文件。Markdown 相对链接按实际投影位置重写到仓库权威资源。

Codex 和 CodeBuddy 均有项目文件 profile；CodeBuddy 明确为实验性文件投影。verify 的 filesystem、source_current、discovery、invocation、hooks 分开报告。目前未进行真实宿主发现/调用验证，Hook 禁用。文件级通过不能被解释为完整平台支持。
