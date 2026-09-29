# Prompt Intelligence Inner Page Architecture

## 1. Goal

Build one English-language Prompt Intelligence website from the collected Similarweb Global and Semrush US keyword set. Each indexable inner page owns one primary keyword and one distinct search intent. The site shares one account, billing, model-routing, storage, and generation backend, while exposing different tools and content experiences through purpose-built landing pages.

The site must not create one page for every exact keyword spelling. Close variants with the same intent belong to one canonical page. New pages are published only when they provide a distinct tool workflow or a sufficiently deep public library category.

## 2. Product Boundaries

The site contains five clearly separated surfaces:

1. **Analysis tools** transform an existing image, video, or prompt.
2. **Prompt generators** create a new prompt from structured user choices.
3. **Public Prompt Library** lets visitors discover proven prompts and their outputs.
4. **My Library** stores a signed-in user's private prompts and favorites.
5. **Generation History** stores recent runs before the user deliberately saves them.

Prompt Manager is not part of the initial product. A future `/prompt-manager` validation page may collect demand, but the full versioning, evaluation, and team workflow is a separate B2B product.

## 3. Information Architecture

```text
Homepage (/)
├── AI Tools (/tools)
│   ├── Video to Prompt (/tools/video-to-prompt)
│   ├── Image to Prompt Generator (/tools/image-to-prompt-generator)
│   ├── Prompt Optimizer (/tools/prompt-optimizer)
│   └── JSON Prompt Generator (/tools/json-prompt-generator)
├── Prompt Generators (/generators)
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
├── Public Prompt Detail (/prompts/{slug})
├── Guides (/guides)
├── Pricing (/pricing)
└── Private Application (/app) [noindex]
    ├── Workspace (/app/workspace)
    ├── Generation History (/app/history)
    ├── My Library (/app/library)
    ├── Favorites (/app/favorites)
    └── Account and Billing (/app/settings)
```

## 4. Keyword-to-Page Map

Metrics remain source-specific and are not added together.

### 4.1 Core Tool Pages

| Priority | URL | Primary keyword | Similarweb Global | Semrush US | Secondary variants consolidated here |
|---|---|---|---:|---:|---|
| P0 | `/tools/prompt-optimizer` | `prompt optimizer` | 36,155 / KD 32 | 1,900 / KD 46 | `prompt enhancer`, `prompt improver`, `ai prompt optimizer` |
| P0 | `/tools/image-to-prompt-generator` | `image to prompt generator` | 36,575 / KD 55 | 1,600 / KD 50 | `image to prompt`, `prompt generator from image`, `image prompt extractor` |
| P0 | `/tools/video-to-prompt` | `video to prompt` | 23,637 / KD 39 | 2,400 / KD 21 | `video to prompt generator`, `videotoprompt`, `video prompt generator` |
| P1 | `/tools/json-prompt-generator` | `json prompt generator` | 4,314 / KD 4 | Not confirmed | `image to json prompt generator`, `text to json prompt generator` |

`image to prompt` has an anomalous Similarweb exact-match value in the latest run, so the canonical page targets the more stable `image to prompt generator` phrase while naturally covering the shorter variant.

### 4.2 Generator Pages

| Priority | URL | Primary keyword | Similarweb Global | Semrush US | Distinct workflow |
|---|---|---|---:|---:|---|
| P0 | `/generators/chatgpt-prompt-generator` | `chatgpt prompt generator` | 20,670 / KD 27 | 2,400 / KD 44 | Goal, context, audience, constraints, and output format |
| P0 | `/generators/claude-prompt-generator` | `claude prompt generator` | 11,222 / KD 31 | Not confirmed | XML sections, long context, Projects, Artifacts, and Claude Code |
| P1 | `/generators/writing-prompt-generator` | `writing prompt generator` | 8,667 / KD 60 | Not confirmed | Writing type, topic, audience, tone, and length |
| P1 | `/generators/art-prompt-generator` | `art prompt generator` | 5,097 / KD 23 | Not confirmed | Subject, medium, style, composition, lighting, and palette |
| P1 | `/generators/suno-prompt-generator` | `suno prompt generator` | 3,837 / KD 45 | Not confirmed | Genre, mood, instruments, structure, vocals, and lyrics |
| P1 | `/generators/drawing-prompt-generator` | `drawing prompt generator` | 3,654 / KD 23 | Not confirmed | Subject, medium, difficulty, style, and challenge constraints |
| P1 | `/generators/veo-3-prompt-generator` | `veo 3 prompt generator` | 3,458 / KD 0 | Not confirmed | Shot, subject, action, camera, audio, and timing |
| P1 | `/generators/story-prompt-generator` | `story prompt generator` | 3,161 / KD 32 | Not confirmed | Genre, setting, character, conflict, tone, and opening scene |
| P2 | `/generators/character-prompt-generator` | `character prompt generator` | 1,788 / KD 28 | Not confirmed | Appearance, personality, history, motivation, and abilities |
| P2 | `/generators/flux-prompt-generator` | `flux prompt generator` | 1,329 / KD 25 | Not confirmed | Flux-specific visual structure and parameters |

Brand-specific pages must provide model-specific output rather than reuse a generic prompt with a different heading. Brand names should not be used in the product's domain name.

### 4.3 Public Library Pages

| Priority | URL | Primary keyword | Similarweb Global | Semrush US | Publication requirement |
|---|---|---|---:|---:|---|
| P0 | `/prompt-library` | `prompt library` | 31,352 / KD 46 | 1,600 / KD 41 | Broad, searchable collection with real outputs |
| P1 | `/prompt-library/claude` | `claude prompt library` | 3,213 / KD 42 | Not confirmed | At least 30 reviewed Claude prompts |
| P1 | `/prompt-library/image` | `image prompt library` | 3,112 / KD 22 | 30 / KD unavailable | At least 50 image prompts with generated images |
| P1 | `/prompt-library/nano-banana` | `nano banana prompt library` | 2,542 / KD 29 | Not confirmed | At least 30 model-specific prompts and outputs |
| P2 | `/prompt-library/chatgpt` | `chatgpt prompt library` | 1,146 / KD 35 | 210 / KD 46 | At least 30 reviewed task prompts |
| P2 | `/prompt-library/video` | `video prompt library` | 694 / KD 0 | Not confirmed | At least 30 prompts with playable or poster-frame examples |

Art, writing, story, drawing, and character Library filters may exist for users, but they remain `noindex` until keyword demand and inventory quality justify dedicated landing pages. Their Generator pages are indexable from launch.

## 5. Page Templates

### 5.1 Analysis Tool Template

Used by Video to Prompt, Image to Prompt Generator, Prompt Optimizer, and JSON Prompt Generator.

1. Exact-intent H1 and usable tool above the fold.
2. Input area tailored to the task: upload, paste, or structured text.
3. Target-model selector when model syntax changes the result.
4. Result editor with copy, regenerate, and save actions.
5. Real input-output examples.
6. Task-specific trust, privacy, and processing notes.
7. Related Generator and Library links.
8. Focused FAQ based on the page's primary intent.

### 5.2 Guided Generator Template

Used by art, writing, story, drawing, character, ChatGPT, Claude, Veo, Suno, and Flux pages.

1. H1 targeting the single primary keyword.
2. A structured form whose fields match that use case.
3. Live prompt preview.
4. Model-formatted output.
5. Generate, randomize, copy, and save actions.
6. Examples produced by this exact generator.
7. Link to the matching Public Library collection when one exists.

Changing only the title and introductory paragraph is not sufficient. Each indexable Generator page requires different input controls, output structure, examples, and explanatory content.

### 5.3 Public Library Template

Used by the main Prompt Library and indexable model/media categories.

1. Search and meaningful category filters.
2. Prompt cards with actual output previews.
3. Model, use-case, style, and quality metadata.
4. Public detail pages with full prompt, settings, and output.
5. Copy, favorite, and Remix actions.
6. Category-specific curated collections.

Filter combinations, sort parameters, search results, and empty collections are `noindex`. Only curated categories with sufficient inventory receive canonical indexable URLs.

### 5.4 Public Prompt Detail Template

Each `/prompts/{slug}` page contains one useful, reviewed prompt; its generated image, video, or text result; model and parameters; editable variables; and links to Remix in the correct Generator. Low-value, duplicate, private, or unreviewed prompt records are not indexable.

### 5.5 Private Application Template

The `/app/*` area is authenticated and `noindex`. It contains the workspace, generation history, private library, favorites, and billing. A generation enters History automatically; it enters My Library only when the user explicitly saves it. Private content is never published automatically.

## 6. Navigation

### Header

1. Logo
2. Tools
3. Generators
4. Prompt Library
5. Pricing
6. Sign in
7. Primary CTA: `Create Prompt`

The Tools mega menu highlights Video to Prompt, Image to Prompt, and Prompt Optimizer. The Generators mega menu groups model generators separately from creative generators. The Library menu exposes only indexable categories.

### Footer

- **Tools:** core transformation tools.
- **Generators:** high-priority model and scenario generators.
- **Library:** main library and indexable collections.
- **Resources:** guides, pricing, and support.
- **Legal:** terms, privacy, copyright, and acceptable use.

### Breadcrumbs

```text
Home > Tools > Video to Prompt
Home > Generators > Art Prompt Generator
Home > Prompt Library > Claude Prompt Library
Home > Prompt Library > Prompt Detail
```

## 7. Internal Linking

The site uses paired creation-discovery loops:

```text
Generator -> matching Library category -> Prompt detail -> Remix in Generator
```

Examples:

- Image to Prompt links to Image Prompt Library and Flux Prompt Generator.
- Video to Prompt links to Video Prompt Library and Veo 3 Prompt Generator.
- Art Prompt Generator links to Image Prompt Library until an Art Library page has sufficient validated demand and inventory.
- ChatGPT and Claude Generator pages link to their respective Library collections and Prompt Optimizer.
- Every public prompt detail links back to its Library category and its matching Generator.

Each page should have three to five strongly related contextual links. Avoid sitewide blocks that link every keyword page to every other keyword page.

## 8. Canonical and Cannibalization Rules

- `prompt optimizer`, `prompt enhancer`, and `prompt improver` resolve to one canonical tool page.
- `video to prompt` and `video to prompt generator` resolve to one canonical tool page.
- `image to prompt generator`, `image to prompt`, and `prompt generator from image` resolve to one canonical tool page.
- `prompt library`, `ai prompt library`, and `prompts library` resolve to the main Library page.
- Singular/plural, free, AI, and word-order variants do not automatically receive separate pages.
- A separate page requires a distinct job, different controls, different output structure, and enough original examples.
- URL parameters never create indexable pages.

## 9. Launch Sequence

### Phase 1: Product Core

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
- Private `/app/*` pages

### Phase 2: Validated Expansion

- Drawing and Character Prompt Generators
- Veo 3, Suno, and Flux Prompt Generators
- Nano Banana, ChatGPT, and Video Library pages
- Reviewed public prompt detail pages

### Phase 3: Demand-Led Expansion

- New model generators and Library categories only after keyword and inventory review.
- Prompt Manager validation page; no full Prompt Manager implementation without product-demand evidence.
- International versions only after the English site has indexed and converted.

## 10. Acceptance Criteria

- Every indexable inner page has exactly one documented primary keyword.
- No two indexable pages target the same search intent.
- Every Generator has task-specific inputs and output formatting.
- Every indexable Library category meets its minimum reviewed inventory threshold.
- Every public prompt detail contains a real output and model metadata.
- Private, parameterized, empty, search-result, and duplicate pages are `noindex`.
- Important pages are reachable within three clicks from the homepage.
- Every indexable page has at least one inbound contextual link and no orphan pages exist.
- Similarweb and Semrush metrics remain separate in planning and reporting.
- No SERP claim is made for pages that have not received live SERP validation.
