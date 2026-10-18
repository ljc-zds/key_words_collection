# Trends 采集通道

默认使用当前登录的普通 Chrome（`browser_sessions.py` 中的 Google Trends 专用 profile，端口 9229）。不会复制 Cookie、启动无头浏览器或重建 profile。

本机 CDP 控制连接（`127.0.0.0/8`、`::1`、`localhost`）通过 `cdp_transport.py` 直接连接，避免 macOS 系统 HTTP 代理把 `/json/version` 或浏览器 WebSocket 发往代理服务器。此处理仅作用于本机控制通道；Chrome 访问 Google Trends 仍遵循 Shadowrocket 配置，远程 CDP 与普通公网 HTTP 请求保留原有代理行为。本机 HTTP 重定向到公网会被拒绝。

每次操作依次尝试：

1. 新版 Explore：创建 `background=true` 标签页，先启用网络监听，再导航到携带 `q` 和 `date` 参数的新版 `/explore` 地址。由页面自行加载关键词与时间范围，不模拟点击、填词，也不加随机缓存参数。对本次需要的 RPC 单独等待：Rising 返回不代表 Interest over time 已成功，反之亦然。60 秒仍无有效数据则刷新当前页一次，再等待最多 60 秒；仍无数据才回退旧版。收到明确 429/403 立即停止，不刷新。成功取数后额外停留 10 秒再关闭该页。后端标记为 `new_url`。
2. 新版失败或没有有效数据：使用同一 Chrome profile，在页面内请求旧版 Explore 和 widgetdata。临时 widget token 只在该页面内使用。
3. 新版只要返回有效 Rising 或完整走势图，即视为至少部分成功；两类数据分别判断，不把一种当成另一种。缺少的部分继续用旧版补齐；补齐失败则记录待重试并跳过，不立即逐词或逐时间范围重试，不停止整轮。
4. 任一通道出现明确的 HTTP 429/403，或新版两种数据均没有且旧版也失败/无有效数据：保存已有结果及待重试父词，抛出 `CollectionStopped`，CLI 退出码为 2，并输出停止原因。明确限制不再尝试另一个通道。

有 Rising 数据但全部低于筛选门槛，属于正常完成，不触发停机。成功对比允许数值为 0，但不允许缺少时间序列；缺失不会记作零值或成功。有效新版 RPC 数据保存在 `output/trends-new-url-cache/`，按 Chrome 端点、关键词组及时间范围复用，跨重启保留；不保存请求头、Cookie 或登录令牌。v6 中已保存的 Rising 列表也会复用，以便只重试缺失的对比。

检查点仍使用 `output/trend-radar-dfs-20-unbounded-v6.json`。恢复后跳过已成功候选词；停止不会自动启动下一轮。MCP 客户端也会保持停止状态，重新开始需重新创建客户端/重启 MCP 进程。

后台标签页不会主动激活；Chrome 没有窗口时，创建标签页仍可能出现专用窗口。测试页用完会关闭，用户已有页面保留。

每次操作结束并清理页面后，冷却 5 秒再开始下一次操作；新版失败回退旧版也执行相同间隔。一次四候选词与 gpts 的对比算一组操作，Rising 查询也算一次操作。新版成功后留页 10 秒与此冷却叠加，成功取数至下一组开始共等待约 15 秒。最后一组仍会完成页面停留，但无需等待下一组冷却。

CLI、MCP 及通过 `build_client` 创建的诊断客户端共用同一 CDP 地址对应的文件锁和冷却时间戳，跨客户端、跨进程保持串行，不因重建客户端跳过间隔。状态保存在项目 `runtime/google-trends-pacing/`，不包含关键词或登录凭据。直接调用底层客户端不经过该调度层，诊断脚本应使用 `build_client`。

操作间隔默认为 `GOOGLE_TRENDS_OPERATION_MIN_WAIT=5`、`GOOGLE_TRENDS_OPERATION_MAX_WAIT=5`。旧版一次操作内部的两个请求仍保留默认 10–15 秒间隔，由 `GOOGLE_TRENDS_MIN_INTERVAL`、`GOOGLE_TRENDS_JITTER` 控制。较低频率不能保证免于限流。

验证命令：

```sh
PYTHONPATH=. .venv/bin/pytest -q tests/test_trends_pacing.py tests/test_trends_fallback.py tests/test_browser_trends_api.py tests/test_trend_radar.py tests/test_google_trends_mcp.py tests/test_browser_sessions.py
```
