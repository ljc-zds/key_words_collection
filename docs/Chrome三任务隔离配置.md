# Chrome 三任务隔离配置

所有地址明确使用 IPv4 `127.0.0.1`，禁止将 `localhost` 或 `::1` 当作自动备用地址。

| 任务 | CDP 地址 | 项目 runtime 下的 profile | 启动命令 |
| --- | --- | --- | --- |
| Similarweb / Semrush | http://127.0.0.1:9222 | keyword-loop-profile | zsh start_keyword_chrome.sh |
| Product Hunt / AITDK | http://127.0.0.1:9230 | aitdk-cdp-clean-20260909 | zsh start_product_hunt_chrome.sh |
| Google Trends / trend_radar | http://127.0.0.1:9228 | google-trends-background-profile | zsh start_google_trends_background.sh |

统一启动器为 `browser_sessions.py`，沿用原目录，不复制或清空登录资料。关键词与 Trends 禁用扩展，AITDK 只加载指定 AITDK 扩展。Trends 采用 headless，其他使用 no-startup-window；查询自身创建后台 Target。

启动器检查 IPv4/IPv6 所有监听者的 profile 路径和端口。端口被其他 profile 占用时直接报错，不接管、不终止其他进程、不尝试换地址。已有正确会话时直接复用。

旧 `start_cdp_chrome.sh` 保留为 Product Hunt/AITDK 的兼容入口；不能用它启动关键词浏览器。`run_trend_radar_v6_background.sh` 固定连接 9228。Product Hunt 定时入口应委托项目 `run_product_hunt_daily.sh`，由后者准备 AITDK 独立浏览器。

仅查看启动参数（不启动 Chrome）：`.venv/bin/python browser_sessions.py keywords --dry-run`。只检查状态：`.venv/bin/python browser_sessions.py keywords --check`，也可将 keywords 换成 product-hunt 或 google-trends。

更改前已经加载的 MCP 进程需重新加载才会使用新默认值。手动命令不要继续传入旧地址；显式传参和环境变量可以覆盖客户端默认值。关键词采集断点和数据不受本次配置调整影响。
