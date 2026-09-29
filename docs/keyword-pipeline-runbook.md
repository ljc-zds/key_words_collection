# 关键词采集与验证运行规范

本文件是本项目每日关键词任务的唯一运行规范。所有采集、筛选、补数、富化与飞书写入均以此为准。

## 目标与边界

Chrome 隔离：关键词任务固定 `127.0.0.1:9222`、`runtime/keyword-loop-profile`，使用 `zsh start_keyword_chrome.sh` 启动。不要使用 `start_cdp_chrome.sh`（现为 AITDK 兼容入口）。三任务映射见 [Chrome三任务隔离配置](Chrome三任务隔离配置.md)。

2026-09-09 起，discovery 入口默认添加前置查询过滤：两站搜索量均≥5,000；Similarweb KD 1–60、CPC≥0.01 美元；Semrush US KD 0–60、CPC≥0.01 美元。保留原搜索量/KD 分档，本地复核返回指标。2026-09-10 更新：Semrush 筛选结果缺少精确词时直接跳过，记录原因、不计入通过数；不取消 filter 补查，不再缺失默认放行。完整规则见 [关键词挖掘完整流程](关键词挖掘完整流程.md)。

- 每日目标：60 个通过硬筛的关键词。
- 写入目标：飞书关键词表 `e2e503`。
- 写入方式：按关键词更新已有行；新词追加到最后一个非空关键词行之后；不得清空、覆盖其他行。
- 目标市场：Google US。Similarweb 的全球词量只用于初筛；最终以 Semrush US 数据为准。

## 来源优先级与流式补数

候选来源按以下顺序取用：

1. Stripe 收入榜：`https://seo.web.cafe/referring/`
2. Toolify 趋势榜：`https://www.toolify.ai/Best-trending-AI-Tools`
3. 飞书词根库

每日期望来源配额为 Stripe 20、Toolify 20、词根 20。某榜单在当前月已没有新候选或无法产出时，缺口转给词根。

采用流式循环，而不是“先采满再验证”：

```text
Similarweb 初筛一小批 -> Semrush 验证 -> 记录淘汰/保留
                                      |
                         通过数 + 待验证数 < 60 ?
                                      |
                                      是
                                      v
                          立即从下一来源继续 Similarweb 初筛
```

只要“已通过硬筛数 + Semrush 待验证数”小于 60，就继续补 Similarweb 候选。不要等待一个大批次全部完成后才再次采词。

## 跨日断点续跑

断点保存在本地 SQLite 的 `pipeline_state`，按 `stripe`、`toolify`、`root` 三个来源独立保存。断点永远表示**下一项待处理的位置**，不是上一次已经完成的位置，因此重新开始时不会重复扫描或跳过未完成数据。

每个来源保存以下字段：

| 字段 | 含义 |
| --- | --- |
| `period` | Stripe/Toolify 榜单月份；词根使用词根库版本标识 |
| `source_position` | 下一条榜单产品或下一条词根的零基序号 |
| `product` | 当前榜单产品；词根来源写当前词根 |
| `root` | 当前传给 Similarweb 的通用词根 |
| `similarweb_page` | 当前词根下下一页待读取的页码，从 1 开始 |

推进规则：

1. 开始读取一个 Similarweb 页之前先保存该页断点。
2. 成功记录该页所有候选后，将 `similarweb_page` 增加 1。
3. 当前词根所有需要读取的页完成后，将页码重置为 1，并将 `source_position` 推进到下一个产品或词根。
4. Similarweb、Semrush、网络或浏览器中断时不得推进断点；第二天先恢复相同的来源、产品、词根和页码。
5. Semrush 的待验证词已在 `daily_run_keywords` 中持久化；跨日时优先完成这些待验证词，再读取断点指定的 Similarweb 页。

查看或更新断点：

```bash
python3 -m keyword_loop.checkpoint_cli show --source toolify
python3 -m keyword_loop.checkpoint_cli set --source toolify --period 2026-09 --position 17 --product Higgsfield --root "ai video generator" --similarweb-page 3
```

检查所有跨日待 Semrush 队列：

```bash
python3 -c 'from pathlib import Path; from keyword_loop.store import KeywordStore; print(KeywordStore(Path("output/keyword-loop.sqlite3")).unresolved_semrush_keywords())'
```

## 硬筛阶段

### 1. Similarweb 初筛

通过条件：

- Similarweb 按“搜索量-KD”分档初筛（全球口径）：

  | 搜索量 | KD 上限 |
  | --- | --- |
  | `>= 30,000` | `<= 60` |
  | `10,000-29,999` | `<= 45` |
  | `5,000-9,999` | `<= 30` |
  | `< 5,000` | 淘汰 |
- 明显的品牌导航、影视下载、实体商品、破解词不进入 Semrush。

将通过词记录到 SQLite `keywords` 与 `daily_run_keywords`，状态为“待 Semrush”。此时不得写飞书。

### 2. Semrush 交叉验证

在当前 Chrome 已登录的 Semrush Keyword Manager 中创建临时列表，批量导入 Similarweb 候选。把每行单元格按以下规则导入 SQLite `keyword_validation.stage = semrush`：

读取单词查询页时使用自适应等待，禁止固定等待 10 秒以上：导航后每 1 秒检查一次该词的精确结果行；一旦该行出现且不包含 `Loading`，立即解析并进入下一词。最长等待 20 秒。若 20 秒后页面仍显示 `Loading`，保留该词在待验证队列并重试，不得标记为“Semrush 未返回精确关键词”。只有页面已稳定且没有精确结果行时，才可使用“未返回精确关键词”的兜底规则。

| 字段 | Semrush Manager 单元格 |
| --- | --- |
| 关键词 | 第 2 列，去除“添加标签” |
| 意图 | 第 3 列，`I/C/N/T` 转完整文字 |
| 搜索量 | 第 5 列 |
| KD | 第 8 列 |
| CPC | 第 9 列 |
| 广告竞争度 | 第 10 列 |
| SERP 特征数 | 第 11 列 |

通过条件：Semrush US 数据应用同一“搜索量-KD”分档。其市场口径优先于 Similarweb；不通过时，记录具体原因并立即回到 Similarweb 补数循环。若 Semrush 未返回**精确关键词行**，不得用近似词替代；该词沿用已通过的 Similarweb 分档并标记为“Semrush US 未返回精确关键词”。

### 3. 工具页意图门槛

只保留可由单页工具、计算器、编辑器、转换器、生成器、检查器、模板或规划器承接的查询。淘汰品牌纯导航、影视/下载/破解、本地导航和实体商品主词。

通过前三阶段的词才是“可发布关键词”。

## 注释阶段，不参与自动淘汰

以下阶段只补充决策信息，绝不删除或淘汰已通过硬筛的关键词。

### 4. 哥飞 KD

脚本：

```bash
python3 run_keyword_enrichment_batch.py
```

补跑未完成的历史批次时，必须显式传入该批次日期，避免脚本默认取当天：

```bash
python3 run_keyword_enrichment_batch.py --run-date 2026-09-01
```

- 频率：至少 7 秒一次，账号限制为每分钟 10 次。
- 429 时脚本停止并保留已完成结果；下次执行从未完成词继续。
- 写入：哥飞 KD、趋势、链接预算、竞争详情、判断依据。

### 5. Serper Google SERP

脚本：

```bash
python3 run_serper_batch.py
```

历史批次使用同一参数：

```bash
python3 run_serper_batch.py --run-date 2026-09-01
```

写入：Google 自然搜索前十、People Also Ask、相关搜索、强站数量。


### 6. AI 二筛

脚本：

```bash
python3 run_ai_screen_batch.py
```

```bash
python3 run_ai_screen_batch.py --run-date 2026-09-01
```

模型输出为注释字段：AI机会评分、工具页适配度、关键词域名适配度、推荐页面类型、AI判断原因。模型不得淘汰已通过硬筛的词。

默认模型名为 `gpt-5.5`；可用 `AI_SCREEN_MODEL` 覆盖。需要一个兼容 OpenAI Responses API 的接口。当前配置使用 `https://cubapi.codemao.cn` 作为 base URL。

## 飞书字段状态

空值不再用于表示进度：

- `待Semrush补采`：早期记录未保存完整 Semrush 字段。
- `待AI二筛`：硬筛通过但尚未调用模型。
- `待Serper采集`：硬筛通过但尚未调用 Serper。

## 所需环境变量

```dotenv
SERPER_API_KEY=
SEO_WEBCAFE_TOKEN=
FEISHU_APP_ID=
FEISHU_APP_SECRET=
OPENAI_API_KEY=
AI_SCREEN_MODEL=gpt-5.5
AI_SCREEN_BASE_URL=https://cubapi.codemao.cn
```

现有 Similarweb 与 Semrush 使用 Chrome 已登录会话，不在 `.env` 存放登录信息。

## 每日执行顺序

1. 先执行待验证的 Semrush 队列；无待验证词时，用 `checkpoint_cli show` 读取每个来源的断点。
2. 在 Chrome 从断点指定的 Stripe、Toolify 或词根位置恢复，并在 Similarweb 读取该页；每完成一页立即推进 checkpoint。
3. 立即将本批 Similarweb 通过词导入 Semrush，解析完整字段并写入 SQLite。
4. 对 Semrush 或意图淘汰的词记录原因；若通过数加待验证数不足 60，立刻回到第 1 步补词。
5. 对新增硬筛通过词依次执行哥飞、Serper、AI 二筛脚本。
6. 任一富化脚本完成后均会按关键词 upsert 飞书。
7. 检查状态：

```bash
python3 -c 'from datetime import date; from pathlib import Path; from keyword_loop.store import KeywordStore; s=KeywordStore(Path("output/keyword-loop.sqlite3")); print(s.daily_run_status(date.today()))'
```

8. 当 `accepted == 60` 时停止新增采集；未完成的注释阶段可继续补齐，但不影响硬筛通过数量。

## 验证与故障恢复

```bash
python3 -m pytest -q
```

- Similarweb 或 Semrush 页面超时：保留 SQLite 队列，刷新或重新打开已登录页面后从待验证词继续。
- 哥飞 429：至少等待一分钟后重新运行富化脚本；脚本会跳过已有结果。
- Serper 或 AI 请求失败：脚本停止而不写半批飞书；修复凭据/网络后重跑，已保存注释会被跳过。
- 绝不运行清空飞书表的命令；发布脚本只更新目标关键词行或追加新行。
