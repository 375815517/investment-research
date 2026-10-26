# 项目化整理记录

## 2026-10-22：迁入独立 Git 仓库

当前唯一项目根为 `/Users/zhuqiang/Dev/investment-research`。从 Default/projects/investment-research 整体迁入，保留新仓库原有 .git；原有目录层级、报告、PDF、CSV与计算记录不变。更新 README、AGENTS、候选 APP.yaml 的路径及项目归属说明。旧 Default 仅保留项目导航，不保留研究副本；历史任务仍归原空间。本次为跨目录文件迁移，未在新仓库建立 Oriel Workspace 或复制旧任务，未执行 Git 暂存、提交或推送。

验证：迁移前106份文件逐一核对；仅修改上述5份作者文件并重新生成候选打包配置，其余文件摘要不变，Git元数据保持原样。新位置9项Web测试、4项DuckDB数据测试通过，项目内打包成功。迁移前完整目录暂存于 `/tmp/investment-research-before-git-move-20261022`，仅供短期恢复，系统清理后不保证保留。

下文及 migration-files.csv 是2026-10-21历史迁移记录，其中目标路径去掉 projects/investment-research/ 前缀即可在当前仓库定位。

---


日期：2026-10-21。用户决定：继续在Default空间组织，项目优先，停止旧应用托管；项目与应用引用关系后续转交Oriel升级。

## 唯一作者位置

`projects/investment-research/` 是业务项目目录，不是新Oriel Workspace，不是Git仓库，也不冒充已登记Project实体。任务仍由Default管理。

| 原位置（Default相对） | 新位置（项目相对） |
|---|---|
| investment-research下公共规则、方法、模板、调研 | framework/ |
| investment-research/playbooks/行业.md | industries/行业/methodology.md |
| companies/公司/shared/ | companies/公司/knowledge/ |
| companies/公司/analyses/ | 原样保留 |
| companies/xiaomi/sources/historical-competitors.md | companies/xiaomi/analyses/2026-10-21-initial/background.md |
| investment-research/web/ | apps/research-web/ |
| Default/apps/investment-research/ | 退出旧生成副本，不再作为作者入口 |
| Default/research/旧小米跳转文件 | 退出重复导航，以项目README为入口 |

详见[逐文件迁移映射](migration-files.csv)。映射保留迁移前后摘要；README等当前组织说明有意修订，报告、PDF、行情与计算记录保持字节不变。旧上下文内的路径属于当时快照，不改写；阅读器兼容rules、playbooks和shared的旧相对路径，新创建内容使用新路径。历次分析内部的inputs、runs、事实与报告不做纯改名，保留证据链。

## 恢复边界

原文件及旧生成副本通过文件移动保存到本机临时恢复目录 `/tmp/investment-project-recovery-20261021`，未销毁；它不是项目权威副本，系统清理临时文件后不保证仍存在。恢复前先检查新项目是否已有后续修改，不能直接覆盖。

## 验证与托管

隔离副本完成9项Web测试、4项DuckDB数据测试，验证新目录、旧链接、创建分析快照、可选项目内打包，以及真实浏览器的行业方法、公司知识、研究报告和PDF读取。正式迁移后再次验证：84份迁移文件与隔离稿一致，其中37份研究、原始资料和数据文件保持原摘要；9项Web测试、4项DuckDB数据测试通过。正式路径的临时服务成功读取目录、报告和PDF原件（HTTP 200，PDF文件头有效），验证后已停止。项目内可选打包产出18份文件，与源码一致；三个旧入口目录已移走，token-stats保留。

旧应用先停止，再经安装版Core的app.hosting.uninstall退出托管，未直接编辑运行状态。Oriel可能仍保留旧App预览条目，预览不是已安装实例；当前不重新安装或启动。运行安装包和机器回执由Oriel管理，不当作项目作者内容移动。

## 任务历史

Default中的既有任务与验收记录保持原归属，历史交付路径不回写Kernel。查看旧路径时按migration-files.csv定位新文件；本次迁移以新任务记录，不复制旧Claim、Evidence或Closure。

## 后续Oriel诉求

参见[项目与应用引用关系](oriel-project-app-proposal.md)。仅记录待转交；没有向其他项目发消息，也没有修改Oriel源码。
