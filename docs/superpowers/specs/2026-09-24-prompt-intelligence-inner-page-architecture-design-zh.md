# Prompt Intelligence 网站内页架构设计

## 1. 目标

基于已采集的 Similarweb Global 与 Semrush US 关键词数据，建设一个面向英语市场的 Prompt Intelligence 网站。每个可索引内页只对应一个主关键词和一个独立搜索意图。全站共用用户账户、支付、模型路由、文件存储和生成服务，不同工具与内容体验通过专门设计的落地页呈现。

网站不能按照每一种关键词拼写机械地创建页面。搜索意图相同的近义词应合并到同一个规范页面。只有在具备独立工具流程，或者拥有足够丰富的公开 Prompt 内容时，才发布新的可索引页面。

## 2. 产品边界

网站包含五个明确分离的功能区域：

1. **分析与转换工具**：处理用户已有的图片、视频或 Prompt。
2. **Prompt 生成器**：根据用户选择的结构化条件创建新 Prompt。
3. **公开 Prompt Library**：供访客发现经过验证的 Prompt 及其生成效果。
4. **My Library**：保存登录用户自己的私人 Prompt 和收藏内容。
5. **Generation History**：保存用户尚未主动收藏的近期生成记录。

Prompt Manager 不属于首发产品范围。未来可以使用 `/prompt-manager` 页面验证需求并收集候补用户，但完整的版本管理、效果评测和团队协作属于另一个独立的 B2B 产品。

## 3. 网站信息架构

```text
首页 (/)
├── AI 工具 (/tools)
│   ├── Video to Prompt (/tools/video-to-prompt)
│   ├── Image to Prompt Generator (/tools/image-to-prompt-generator)
│   ├── Prompt Optimizer (/tools/prompt-optimizer)
│   └── JSON Prompt Generator (/tools/json-prompt-generator)
├── Prompt 生成器 (/generators)
│   ├── ChatGPT Prompt Generator (/generators/chatgpt-prompt-generator)
│   ├── Claude Prompt Generator (/generators/claude-prompt-generator)
│   ├── Art Prompt Generator (/generators/art-prompt-generator)
│   ├── Writing Prompt Generator (/generators/writing-prompt-generator)
│   ├── Story Prompt Generator (/generators/story-prompt-generator)
│   ├── Drawing Prompt Generator (/generators/drawing-prompt-generator)
│   ├── Character Prompt Generator (/generators/character-prompt-generator)
│   ├── Veo 3 Prompt Generator (/generators/veo-3-prompt-generator)
│   ├── Suno Prompt Generator (/generators/suno-prompt-generator)
│   └── Flux Prompt Generator (/generators/flux-prompt-generator)
├── Prompt Library (/prompt-library)
│   ├── Image Prompt Library (/prompt-library/image)
│   ├── Video Prompt Library (/prompt-library/video)
│   ├── ChatGPT Prompt Library (/prompt-library/chatgpt)
│   ├── Claude Prompt Library (/prompt-library/claude)
│   └── Nano Banana Prompt Library (/prompt-library/nano-banana)
├── 公开 Prompt 详情页 (/prompts/{slug})
├── 使用指南 (/guides)
├── 价格页 (/pricing)
└── 私人应用区 (/app) [noindex]
    ├── 工作台 (/app/workspace)
    ├── 生成历史 (/app/history)
    ├── My Library (/app/library)
    ├── 收藏 (/app/favorites)
    └── 账户与账单 (/app/settings)
```

## 4. 关键词与页面映射

Similarweb 与 Semrush 的指标保持独立，不进行相加。

### 4.1 核心工具页

| 优先级 | URL | 主关键词 | Similarweb Global | Semrush US | 合并覆盖的次级关键词 |
|---|---|---|---:|---:|---|
| P0 | `/tools/prompt-optimizer` | `prompt optimizer` | 36,155 / KD 32 | 1,900 / KD 46 | `prompt enhancer`、`prompt improver`、`ai prompt optimizer` |
| P0 | `/tools/image-to-prompt-generator` | `image to prompt generator` | 36,575 / KD 55 | 1,600 / KD 50 | `image to prompt`、`prompt generator from image`、`image prompt extractor` |
| P0 | `/tools/video-to-prompt` | `video to prompt` | 23,637 / KD 39 | 2,400 / KD 21 | `video to prompt generator`、`videotoprompt`、`video prompt generator` |
| P1 | `/tools/json-prompt-generator` | `json prompt generator` | 4,314 / KD 4 | 尚未确认 | `image to json prompt generator`、`text to json prompt generator` |

最新版 Similarweb 数据中，`image to prompt` 精确词出现异常值，因此规范页面选择数据更稳定的 `image to prompt generator` 作为主关键词，同时自然覆盖较短的关键词变体。

### 4.2 Prompt 生成器页面

| 优先级 | URL | 主关键词 | Similarweb Global | Semrush US | 独立生成流程 |
|---|---|---|---:|---:|---|
| P0 | `/generators/chatgpt-prompt-generator` | `chatgpt prompt generator` | 20,670 / KD 27 | 2,400 / KD 44 | 目标、背景、受众、限制条件和输出格式 |
| P0 | `/generators/claude-prompt-generator` | `claude prompt generator` | 11,222 / KD 31 | 尚未确认 | XML 区块、长上下文、Projects、Artifacts 和 Claude Code |
| P1 | `/generators/writing-prompt-generator` | `writing prompt generator` | 8,667 / KD 60 | 尚未确认 | 写作类型、主题、受众、语气和长度 |
| P1 | `/generators/art-prompt-generator` | `art prompt generator` | 5,097 / KD 23 | 尚未确认 | 主体、媒介、风格、构图、光线和色彩 |
| P1 | `/generators/suno-prompt-generator` | `suno prompt generator` | 3,837 / KD 45 | 尚未确认 | 音乐类型、情绪、乐器、结构、人声和歌词 |
| P1 | `/generators/drawing-prompt-generator` | `drawing prompt generator` | 3,654 / KD 23 | 尚未确认 | 绘画主体、媒介、难度、风格和挑战条件 |
| P1 | `/generators/veo-3-prompt-generator` | `veo 3 prompt generator` | 3,458 / KD 0 | 尚未确认 | 镜头、主体、动作、运镜、音频和时间安排 |
| P1 | `/generators/story-prompt-generator` | `story prompt generator` | 3,161 / KD 32 | 尚未确认 | 类型、背景、人物、冲突、基调和开场场景 |
| P2 | `/generators/character-prompt-generator` | `character prompt generator` | 1,788 / KD 28 | 尚未确认 | 外貌、性格、背景、动机和能力 |
| P2 | `/generators/flux-prompt-generator` | `flux prompt generator` | 1,329 / KD 25 | 尚未确认 | Flux 专属视觉结构和参数 |

模型品牌专属页面必须输出符合对应模型特点的 Prompt，不能只替换通用页面的标题。产品域名中不应直接使用第三方品牌名称。

### 4.3 公开 Prompt Library 页面

| 优先级 | URL | 主关键词 | Similarweb Global | Semrush US | 发布条件 |
|---|---|---|---:|---:|---|
| P0 | `/prompt-library` | `prompt library` | 31,352 / KD 46 | 1,600 / KD 41 | 包含真实生成效果的综合可搜索 Prompt 库 |
| P1 | `/prompt-library/claude` | `claude prompt library` | 3,213 / KD 42 | 尚未确认 | 至少 30 条经过审核的 Claude Prompt |
| P1 | `/prompt-library/image` | `image prompt library` | 3,112 / KD 22 | 30 / KD 缺失 | 至少 50 条包含真实生成图片的 Prompt |
| P1 | `/prompt-library/nano-banana` | `nano banana prompt library` | 2,542 / KD 29 | 尚未确认 | 至少 30 条模型专属 Prompt 及生成结果 |
| P2 | `/prompt-library/chatgpt` | `chatgpt prompt library` | 1,146 / KD 35 | 210 / KD 46 | 至少 30 条经过审核的任务型 Prompt |
| P2 | `/prompt-library/video` | `video prompt library` | 694 / KD 0 | 尚未确认 | 至少 30 条带可播放视频或封面帧的 Prompt |

Art、Writing、Story、Drawing 和 Character 可以作为 Library 内的用户筛选条件存在，但在搜索需求和内容库存达到要求之前保持 `noindex`。对应的 Generator 页面从首发阶段即可索引。

## 5. 页面模板

### 5.1 分析与转换工具模板

适用于 Video to Prompt、Image to Prompt Generator、Prompt Optimizer 和 JSON Prompt Generator。

1. 使用精确搜索意图的 H1，并在首屏直接提供可操作工具。
2. 根据任务提供上传、粘贴或结构化文本输入区域。
3. 当不同模型的 Prompt 语法存在差异时，提供目标模型选择器。
4. 结果编辑器支持复制、重新生成和保存。
5. 展示真实输入与输出案例。
6. 展示与当前任务相关的隐私、文件安全和处理说明。
7. 链接到相关 Generator 和 Library 页面。
8. FAQ 只回答当前页面主搜索意图相关的问题。

### 5.2 引导式 Prompt 生成器模板

适用于 Art、Writing、Story、Drawing、Character、ChatGPT、Claude、Veo、Suno 和 Flux 页面。

1. H1 对应唯一主关键词。
2. 结构化表单字段必须符合当前使用场景。
3. 实时展示 Prompt 预览。
4. 输出符合目标模型格式的 Prompt。
5. 支持生成、随机、复制和保存操作。
6. 示例必须由当前生成器实际生成。
7. 存在对应公开 Library 分类时，提供明确入口。

只修改标题和介绍文案不足以构成独立页面。每个可索引 Generator 页面都必须具备不同的输入控件、输出结构、案例和说明内容。

### 5.3 公开 Prompt Library 模板

适用于 Prompt Library 首页以及可索引的模型和媒介分类页。

1. 提供搜索和有实际意义的分类筛选。
2. Prompt 卡片展示真实生成结果预览。
3. 展示模型、使用场景、风格和质量元数据。
4. 公开详情页展示完整 Prompt、参数和生成结果。
5. 支持复制、收藏和 Remix。
6. 提供针对当前分类的精选集合。

筛选组合、排序参数、搜索结果页和空分类统一设置为 `noindex`。只有经过策划且拥有足够内容库存的分类才能拥有规范的可索引 URL。

### 5.4 公开 Prompt 详情页模板

每个 `/prompts/{slug}` 页面只展示一条有实际价值且经过审核的 Prompt，并包含其生成图片、视频或文本结果、模型和参数、可编辑变量，以及进入对应 Generator 进行 Remix 的入口。低质量、重复、私人或未经审核的 Prompt 不允许索引。

### 5.5 私人应用区模板

`/app/*` 区域需要登录并统一设置为 `noindex`。其中包含工作台、生成历史、私人 Library、收藏和账单。每次生成会自动进入 History；只有用户主动点击保存后才进入 My Library。私人内容绝不自动公开。

## 6. 导航设计

### 顶部导航

1. Logo
2. Tools
3. Generators
4. Prompt Library
5. Pricing
6. Sign in
7. 主行动按钮：`Create Prompt`

Tools 下拉菜单重点展示 Video to Prompt、Image to Prompt 和 Prompt Optimizer。Generators 下拉菜单将模型生成器与创意场景生成器分组展示。Library 菜单只展示允许索引的分类。

### 页脚导航

- **Tools：**核心分析与转换工具。
- **Generators：**高优先级模型和场景生成器。
- **Library：**主 Library 和可索引分类。
- **Resources：**指南、价格和帮助。
- **Legal：**服务条款、隐私、版权和使用规范。

### 面包屑

```text
Home > Tools > Video to Prompt
Home > Generators > Art Prompt Generator
Home > Prompt Library > Claude Prompt Library
Home > Prompt Library > Prompt Detail
```

## 7. 内链设计

全站围绕“创造与发现”的闭环建立内链：

```text
Generator -> 对应 Library 分类 -> Prompt 详情 -> 返回 Generator Remix
```

具体关系：

- Image to Prompt 链接到 Image Prompt Library 和 Flux Prompt Generator。
- Video to Prompt 链接到 Video Prompt Library 和 Veo 3 Prompt Generator。
- Art Prompt Generator 在 Art Library 具备足够关键词验证和内容库存前，先链接到 Image Prompt Library。
- ChatGPT 和 Claude Generator 链接到各自 Library 分类以及 Prompt Optimizer。
- 每个公开 Prompt 详情页都链接回所属 Library 分类和对应 Generator。

每个页面配置 3 至 5 个高度相关的上下文链接。禁止在全站所有页面放置包含全部关键词页的链接区块。

## 8. 规范页与关键词竞争规则

- `prompt optimizer`、`prompt enhancer` 和 `prompt improver` 合并到一个规范工具页。
- `video to prompt` 和 `video to prompt generator` 合并到一个规范工具页。
- `image to prompt generator`、`image to prompt` 和 `prompt generator from image` 合并到一个规范工具页。
- `prompt library`、`ai prompt library` 和 `prompts library` 合并到 Prompt Library 首页。
- 单复数、`free`、`AI` 和词序变化不能自动获得独立页面。
- 新建独立页面必须同时满足：用户任务不同、输入控件不同、输出结构不同并且拥有足够原创案例。
- URL 参数不能生成可索引页面。

## 9. 上线顺序

### 第一阶段：核心产品

- `/tools/video-to-prompt`
- `/tools/image-to-prompt-generator`
- `/tools/prompt-optimizer`
- `/tools/json-prompt-generator`
- `/generators/chatgpt-prompt-generator`
- `/generators/claude-prompt-generator`
- `/generators/art-prompt-generator`
- `/generators/writing-prompt-generator`
- `/generators/story-prompt-generator`
- `/prompt-library`
- `/prompt-library/image`
- `/prompt-library/claude`
- `/pricing`
- 私人 `/app/*` 页面

### 第二阶段：验证后扩展

- Drawing 和 Character Prompt Generator。
- Veo 3、Suno 和 Flux Prompt Generator。
- Nano Banana、ChatGPT 和 Video Prompt Library 页面。
- 经过审核的公开 Prompt 详情页。

### 第三阶段：需求驱动扩展

- 新模型生成器和 Library 分类必须经过关键词与内容库存审核后才能上线。
- 增加 Prompt Manager 需求验证页；没有产品需求证据时不开发完整 Prompt Manager。
- 英语站完成收录并验证转化后，才考虑国际化版本。

## 10. 验收标准

- 每个可索引内页都有且只有一个明确记录的主关键词。
- 不存在两个可索引页面争夺同一搜索意图。
- 每个 Generator 都有符合其使用场景的输入项和输出格式。
- 每个可索引 Library 分类都达到最低审核内容数量。
- 每个公开 Prompt 详情页都包含真实生成结果和模型元数据。
- 私人页面、参数页、空页面、搜索结果页和重复页面全部设置为 `noindex`。
- 所有重要页面都可以从首页三次点击以内到达。
- 每个可索引页面至少拥有一个有效的站内入口，不存在孤立页面。
- Similarweb 与 Semrush 指标在规划和报告中始终分开呈现。
- 没有进行实时 SERP 验证的页面，不得声称已经确认其 SERP 竞争情况。
