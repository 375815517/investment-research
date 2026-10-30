# 研习公共 Web 模块

作者源码唯一位于本项目 apps/research-web/；资料在项目 companies/。本轮停止旧应用托管，保留源码供后续项目应用入口复用。tools/build-web.mjs 只生成项目内 .build/research-web/，不写Default/apps。

沿用 Node 22 标准库服务器。正式托管由清单launch.args中的 --library-root 指定资料绝对路径；开发环境仍支持 INVESTMENT_LIBRARY_ROOT。1.1.1移除当前运行器尚不支持的configuration环境引用，权限与资料位置保持不变。页面支持公共/行业方法、公司、研究正文、证据表、原始PDF、计算结果、参数、复现清单、复盘与小米行情事件。

页面只读取已保存行情；更新由项目 tools/pipeline.py refresh 完成。JSON/CSV/Markdown为持久文件，DuckDB负责分析并生成可重建视图；浏览器不联网获取行情。没有研究结果时明确为空，不冒充已计算。

## 验证

在本目录运行 node --test test.js；在项目根运行 python tools/test_pipeline.py。真实浏览器测试使用隔离资料副本。构建部署包：node tools/build-web.mjs（从项目根执行）。开发预览使用 node apps/research-web/server.js --library-root "$PWD"（项目根运行）；可选打包不触发正式托管。重新接入时需要按届时Oriel项目入口能力核对源路径、权限和资料目录。

## 边界

仅回环访问，写入要求同源与校验令牌，拒绝路径越界/符号链接与陈旧覆盖。Web只支持已归档公司PDF附件，原始HTML不执行。历史正文只读，验证追加，复盘可更新。CSV支持引号字段；大型原件保留文件形式，不导入搜索索引。没有交易、账户或外部发布功能。

## PDF原件阅读（1.1.0）

原件链接进入本地PDF.js阅读器，可翻页、按实际页码跳转、缩放、读取本页文字和下载原件。PDF实际页序与印刷页码区别保留提示。三份归档财报在内嵌浏览器验证，不再依赖原生PDF插件。错误与密码保护会明确显示，不显示无说明空白。

Mozilla pdfjs-dist 6.4.299固定资源随应用打包；vendor/manifest.json记录npm原始包完整性与各资源SHA-256，LICENSE保留。字体、字符映射和WASM以assets.json保存，服务只返回已登记资源；无外网请求，不执行PDF脚本或XFA。PDF.js使用同源Worker与WASM，CSP未开放任意JavaScript求值。
