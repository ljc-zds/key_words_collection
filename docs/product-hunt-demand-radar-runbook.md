# Product Hunt 找需求词运行手册

Chrome 独立配置：`127.0.0.1:9230` + `runtime/aitdk-cdp-clean-20260909`，只加载 AITDK 扩展。`run_product_hunt_daily.sh` 自动检查/准备专用浏览器，系统定时入口已委托该脚本；不再检测或启动关键词任务的 9222。详见 [Chrome三任务隔离配置](Chrome三任务隔离配置.md)。

本文档描述当前正在运行的本地 Mac 自动化方案。结果写入飞书，域名、流量与关键词数据统一通过本地 AITDK Chrome CDP MCP 获取。

## 目标

每天获取前一天在 Product Hunt 发布的产品，筛出对新站友好的非品牌需求词机会，并将所有采集结果保留在飞书中供后续筛选和复盘。

## 当前流程

```text
Product Hunt 前一天全量产品
  -> 读取飞书存量，按“发布日期 + Product Hunt 链接”去重
  -> 仅对未出现过的产品调用 AITDK MCP
  -> 解析真实官网
  -> AITDK 返回 Whois、流量来源和核心关键词
  -> 根据域名年龄、流量和来源占比筛选
  -> 提取非品牌关键词、计算筛选结果
  -> 飞书追加写入，并再次去重
```

Product Hunt API 负责取得产品列表。AITDK MCP 复用本机已登录 Chrome 中的 AITDK 扩展，返回注册日期（若扩展提供）、最新月访问量、流量来源和核心关键词；不会导出 Cookie、请求签名或响应原文。

## 筛选规则

每个条件均为包含边界：

| 条件 | 通过标准 |
| --- | --- |
| 域名年龄 | 注册至今不超过 365 天 |
| 最新月自然搜索访问 | 不少于 3,000 |
| 自然搜索流量占比 | 不低于 20% |
| 直接访问占比 | 不低于 20% |

通过流量条件的产品会提取关键词，并按产品名和域名前缀排除明显品牌词。是否存在非品牌词目前只影响报告内容，不作为额外的硬性淘汰条件。

## 飞书数据与去重

目标是已授权的 Product Hunt 飞书表格，表头共 20 列，包括产品、域名、发布日期、注册日期、搜索访问量、总访问量、三个月趋势、搜索占比、直接占比、非品牌关键词、状态和来源链接。

唯一键为：

```text
发布日期（第 7 列） + Product Hunt 来源链接（第 18 列）
```

每日运行在调用 AITDK MCP **之前**先读取该表：已有键的产品直接跳过。写入阶段会再次去重，且能识别飞书 API 返回的富文本链接格式。若历史表中已经存在重复键，保留最早一条并清除后续重复行。

因此：

- 不同发布日期的产品会追加到表格底部。
- 同一天重复运行不会重复写入，也不会为已有产品消耗 AITDK 查询额度。
- `--retry-errors` 用于重试本地报告中的错误行，并可更新同一产品的已有记录。

## AITDK 查询与前置条件

每个未去重产品最多调用一次 `domain_enrich`。筛选使用 AITDK 的最新月访问量；当前 MCP 不承诺三个月趋势，表中的趋势列会留空。

只有满足以下前置条件的未去重产品才会发起 AITDK 查询：

1. 成功解析到独立官网；
2. Chrome CDP 已在本机 `127.0.0.1:9222` 启动；
3. AITDK 扩展已在该 profile 中登录。

如果 AITDK 未返回 Whois 注册日期，产品会记为 `error`，可在浏览器/扩展恢复后用 `--retry-errors` 重试。实际额度按 AITDK 当前套餐计费规则为准。

## 定时任务

macOS LaunchAgent：

```text
标签：com.producthunt.demand-radar
配置：/Users/am/Library/LaunchAgents/com.producthunt.demand-radar.plist
时间：每天 08:30（本机时区）
启动脚本：/Users/am/Library/Application Support/ProductHuntRadar/run.sh
```

启动脚本进入项目目录后执行：

```bash
.venv/bin/python product_hunt_daily.py
```

`RunAtLoad` 为 `false`，因此安装或登录时不会额外运行；只有每日时间点触发。

Product Hunt GraphQL 按应用的查询复杂度执行 15 分钟窗口限流。收到 `429` 时，脚本读取响应头 `X-Rate-Limit-Reset` 自动等待对应秒数后重试同一页，最多等待并重试 3 个限流窗口；响应头缺失或异常时按 60 秒等待。等待期间不会调用 AITDK MCP，也不会写入飞书。

## 日常检查与手动命令

在项目目录执行：

```bash
# 查看当天任务进度与最终统计
tail -n 50 runtime/product_hunt_daily.log

# 查看 LaunchAgent 是否正在运行
launchctl print gui/$(id -u)/com.producthunt.demand-radar

# 手动跑前一天；会读飞书去重并写入飞书
.venv/bin/python product_hunt_daily.py

# 仅测试一条，不写飞书
.venv/bin/python product_hunt_daily.py --limit 1 --skip-feishu

# 仅重试本地报告中的 error 行
.venv/bin/python product_hunt_daily.py --retry-errors
```

本地报告位于 `runtime/product_hunt_daily.json`，当天 Product Hunt 原始列表缓存位于 `runtime/product-hunt-cache/YYYY-MM-DD.json`。运行日志以 `runtime/product_hunt_daily.log` 为准；LaunchAgent 的标准输出日志通常为空，因为启动脚本会将 Python 输出重定向到项目运行日志。

每完成一条产品处理，脚本都会原子写入 `runtime/product-hunt-checkpoints/YYYY-MM-DD.json`。任务因网络、关机或进程中断而停止时，下次运行会加载该检查点，并跳过其中已经完成的产品，不会再次调用其域名或 Traffic 接口。只有飞书写入成功后，才会删除当天检查点。早于该机制的中断任务没有中间检查点，无法据此恢复已消费的接口请求。

## 状态含义

| 状态 | 含义 |
| --- | --- |
| `Success` | 满足全部硬性筛选条件 |
| `excluded` | 拿到数据，但未通过域名年龄或流量条件 |
| `no_website` | 未能获得独立官网，或仅为应用商店 / Product Hunt 页面 |
| `no_data` | AITDK 未返回可用访问量 |
| `error` | Chrome CDP、AITDK 扩展、注册日期或其他采集过程异常；可用 `--retry-errors` 重试 |

## 凭据与安全

`.env` 只保存 Product Hunt 和飞书凭据，受 Git 忽略规则保护。不要把 `.env`、Bearer Token、飞书 App Secret 或完整请求头写入飞书、日志、文档或 Git。AITDK 登录态保存在指定 Chrome profile 中，不由脚本读取。

需要的环境变量为：

```text
PRODUCT_HUNT_DEVELOPER_TOKEN
FEISHU_APP_ID
FEISHU_APP_SECRET
```

若密钥曾在聊天记录、截图或提交中暴露，应在对应服务控制台轮换后更新 `.env`。

## 已知限制

- 当前按域名顺序串行采集，以降低 AITDK 查询额度消耗和 Chrome 并发冲突风险。
- Chrome CDP 未运行、扩展未安装或登录失效时，当天记录会标记为 `error`，待恢复后重试。
- Product Hunt 的同日产品列表可能自身含重复项，前置去重会将其排除。
- 飞书写入发生在整批采集完成后；任务中断时本地报告可能已生成，但飞书尚未更新。修复后可使用该本地报告重新执行写入或按错误重试。
