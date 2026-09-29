# Local Keyword Site Analysis Design

## Goal

Analyze the existing Similarweb and Semrush keyword records without making any external requests. Keep only keywords that can support a realistic English-language site, rank them, export an auditable Excel workbook, and generate a self-contained HTML analysis page from the same result set.

## Data Sources

- `output/keyword-loop.sqlite3::keywords`: Similarweb observations with global volume, KD, intent, retrieval time, and provenance roots.
- `output/keyword-loop.sqlite3::keyword_validation(stage='semrush')`: Semrush exact-match validation for Similarweb keywords.
- `output/keyword-loop.sqlite3::semrush_related_candidates`: Semrush US related keywords with volume, KD, CPC, intent, competition density, SERP features, and parent keyword.

Metrics from the two providers remain in separate columns. They are never added together because the markets and measurement methods differ.

## Qualification

Normalize and deduplicate keywords, then apply conservative hard exclusions. Reject missing metrics, volume below 5,000, KD above 60, pure navigation, piracy/adult/gambling/local-navigation queries, bare identifiers, transient dates, and queries without a clear tool, reference, learning, comparison, or reusable content job.

Score surviving keywords on demand (20), SEO feasibility (25), product fit (20), monetization (15), expansion potential (10), and data confidence (10). Apply explicit risk deductions. Keep only scores of at least 60: P0 is 80+, P1 is 70-79.9, and P2 is 60-69.9. Because no live SERP is used, every record is labeled `未进行实时 SERP 验证`.

## Project Clustering

Assign each accepted keyword a site type and a normalized topic key. Group related keywords into site opportunities. Rank projects by the best member score, supporting-keyword count, and combined demand signal. Do not treat every keyword as a separate website.

## Outputs

Generate a canonical JSON result first. The Excel workbook and HTML page must both consume that JSON.

The workbook contains `建站项目排名`, `关键词明细`, and `评分口径`. It contains no rejected keyword text. The HTML contains overview metrics, distribution summaries, a project ranking table, keyword filters, and an expandable detail view. It is self-contained and works as a local file.

## Verification

- Unit tests cover normalization, source separation, hard exclusions, site classification, scoring, priority, and clustering.
- Workbook counts reconcile to canonical JSON, key ranges inspect correctly, formula-error scan is clean, and every sheet is rendered for visual review.
- HTML counts reconcile to canonical JSON and responsive screenshots show no overlap at desktop and mobile widths.
- No external network request, browser SERP request, or scheduled task is created.
