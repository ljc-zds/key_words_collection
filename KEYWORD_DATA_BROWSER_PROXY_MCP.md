# Similarweb 与 Semrush 浏览器代理 MCP

本文档规定关键词采集器如何通过 OpenCLI 浏览器代理复用当前 Chrome 登录态，从 Similarweb 和 Semrush 获取结构化关键词数据。默认只读取页面触发的 JSON 网络响应，不读取整页 DOM、不依赖截图，也不导出 Cookie 或认证 header。

本地 stdio MCP 保留为 API Key 或私密请求头已配置时的备用方案：

```text
POST https://sim.3ue.co/api/KeywordGenerator/google/suggest
```

## 浏览器代理 MCP（推荐）

当 Similarweb 或 Semrush 账号只有网页登录额度时，使用 OpenCLI 浏览器代理复用当前 Chrome 登录态。该模式不读取 Cookie，也不依赖页面表格或截图，而是监听页面发出的 JSON 响应。

## Similarweb

### 调用流程

1. 确认桥接状态：`opencli doctor` 应显示 daemon 和 Extension 均为 `OK`。
2. 为每个并行任务使用独立会话名，例如 `similarweb-keyword-<日期>`。
3. 打开关键词生成器 URL，等待网络请求完成，不等待页面的 `Preparing insights` 遮罩消失。
4. 执行 `opencli browser <session> network`，定位以下请求：

   ```text
   POST /api/KeywordGenerator/google/suggest
   ```

5. 只读取该请求的 JSON body，解析 `records`、`totalRecords`、`totalClicks` 和 `totalVolume`。
6. 完成后执行 `opencli browser <session> close` 释放会话。

### 请求参数

查询参数由页面自动生成，关键字段如下：

| 参数 | 含义 |
| --- | --- |
| `keyword` | 词根或关键词 |
| `country=999` | 数据库国家，999 表示美国 |
| `type=Broad` | Broad 扩展 |
| `type=Related` | Related 扩展 |
| `rowsPerPage=100` | 每次最多返回 100 条 |
| `latest=28d` | 最近 28 天窗口 |

单次测试 `final grade calculator` 已验证：Broad 返回 44 条，Related 返回 100 条，状态均为 HTTP 200。

### 响应字段

每条 `records[]` 记录可直接映射为关键词数据：

```text
keyword, averageVolume, windowVolume, difficulty,
primaryIntent, secondaryIntent, cpc, clicks,
volumeTrend, leadingSite
```

筛选建议使用 `averageVolume`（搜索量）和 `difficulty`（Similarweb KD），默认条件为搜索量 >= 30000 且 KD <= 60。`volumeTrend` 保留为 JSON，供趋势判断使用。

### 失败处理

- 页面可以卡在 `Preparing insights for your company`，只要网络请求已返回 200，就视为成功，不重试页面 DOM。
- 没有 `/api/KeywordGenerator/google/suggest` 请求时，等待 10 秒后刷新一次；仍无请求再记录失败并保留断点。
- HTTP 401/403 表示登录态或权限失效，需要用户在 Chrome 中重新登录。
- 不要把网络响应中的认证 headers、Cookie 或 token 写入日志、数据库或 Git。

## Semrush

Semrush 使用 Keyword Magic Tool 页面触发查询。浏览器代理打开带有 `q=<keyword>` 与 `db=us` 的页面，等待关键词查询对应的 JSON-RPC 响应后解析，不读取导航、侧边栏或整页 DOM。

### 查询入口

```text
https://sem.3ue.co/analytics/keywordmagic/?q=<keyword>&db=us&type=all&mode=0
```

页面会调用 Keyword Magic Tool 的数据服务：

```text
POST /kmtgw/v2/webapi
method: ideas.GetKeywords
```

### 响应字段

从返回结果的关键词数组中提取：

```text
keyword, volume, difficulty, cpc, competitive_density,
intent, serp_features
```

测试词 `final grade calculator` 已验证能返回关键词数据：主词搜索量为 165000、KD 为 49，同时包含 CPC、竞争程度和 SERP 字段。

### Semrush 规则

- 如果 Semrush 未返回精确关键词，按现有流程默认通过，并记录 `Semrush未返回精确关键词`。
- Semrush 返回数据时，使用相同的分档搜索量/KD 规则进行交叉验证。
- 页面首次出现“出错了”时，可点击一次“重试”；重试成功后直接读取网络响应。
- 若仍然无 JSON 响应，记录失败原因和断点，不使用截图或整页 DOM 作为回退。

## 配置认证

认证值不写入代码。优先配置 Similarweb 官方 API key（如果账号已开通 API）：

```bash
export SIMILARWEB_AUTHORIZATION='Bearer <your-api-key>'
```

也可以使用本地私密 headers 文件（不要提交到 Git）：

```bash
export SIMILARWEB_HEADERS_JSON=/absolute/path/similarweb-headers.json
```

文件内容示例：

```json
{"Authorization":"Bearer ..."}
```

若账号只能使用网页登录会话，可将当前请求所需的会话认证放入同一私密文件；MCP 不会从 Chrome 配置目录读取 cookie，也不会把认证值打印到 stdout。

## Agent 配置

以 Claude Desktop 为例：

```json
{
  "mcpServers": {
    "similarweb-local": {
      "command": "/Users/am/Documents/代码/key_words_collection/.venv/bin/python",
      "args": ["/Users/am/Documents/代码/key_words_collection/mcp_tool/similarweb_mcp.py"],
      "env": {
        "SIMILARWEB_AUTHORIZATION": "Bearer <your-api-key>"
      }
    }
  }
}
```

工具 `keyword_suggest` 默认返回 `平均搜索量 >= 30000` 且 `KD <= 60` 的记录，可传 `result_type=Broad` 或 `Related`。`health` 只检查本地配置，不消耗 Similarweb 额度。

## Semrush MCP

Semrush 同样提供独立的 stdio MCP：[semrush_mcp.py](/Users/am/Documents/代码/key_words_collection/mcp_tool/semrush_mcp.py)。它调用已确认的 Keyword Magic Tool JSON-RPC 接口 `/kmtgw/v2/webapi`，暴露同名 `keyword_suggest` 和 `health` 工具。

配置变量对应为 `SEMRUSH_BASE_URL`、`SEMRUSH_AUTHORIZATION`、`SEMRUSH_COOKIE` 或 `SEMRUSH_HEADERS_JSON`。例如：

```json
{
  "mcpServers": {
    "semrush-local": {
      "command": "/Users/am/Documents/代码/key_words_collection/.venv/bin/python",
      "args": ["/Users/am/Documents/代码/key_words_collection/mcp_tool/semrush_mcp.py"],
      "env": {"SEMRUSH_HEADERS_JSON": "/absolute/path/semrush-headers.json"}
    }
  }
}
```
