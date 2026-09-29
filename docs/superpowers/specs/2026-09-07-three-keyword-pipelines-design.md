# Three Keyword Pipelines Design

## Goal

Separate the subscription keyword workflow into three independently runnable
scripts without changing the existing SQLite schema, screening thresholds,
Feishu destinations, or browser/CDP authentication model.

## Scripts

1. `product_hunt_daily.py` remains the Product Hunt and AITDK pipeline. It
   retrieves Product Hunt launches, resolves official sites, enriches them via
   AITDK CDP MCP, applies the new-site traffic filter, and writes only to the
   Product Hunt sheet.
2. `run_keyword_discovery.py` becomes the Similarweb and Semrush discovery
   pipeline. It gathers Stripe, Toolify, and root terms; records Similarweb
   observations; verifies exact terms in Semrush; and writes only to SQLite.
3. `run_keyword_validation_publish.py` becomes the downstream validation
   pipeline. It reads the SQLite candidate queue, runs AI initial screening,
   Serper, Web.Cafe KD, AI final screening, and writes only complete accepted
   records to the keyword-results Feishu sheet.

## Code Boundaries

`keyword_loop/workflows/discovery.py` owns Similarweb/Semrush orchestration;
the command script owns argument parsing only. `keyword_loop/workflows/validation_publish.py`
owns downstream validation and publication; its command script owns argument
parsing only. Product Hunt code stays in `aitdk_enrichment` plus its existing
thin command entry point.

The legacy `run_discovery_semrush_only.py` and `run_daily_gates.py` remain as
compatibility wrappers that delegate to the new command modules. The current
`run_keyword_enrichment_batch.py` remains unchanged because it is a separate
maintenance/backfill command, not the new daily workflow.

## Failure Handling

Each pipeline preserves its current checkpoint behavior: Product Hunt uses its
JSON checkpoint, discovery uses SQLite source offsets and validation records,
and validation uses SQLite stage records. A failed external call records a
failure and leaves unfinished work available to a later run. No script publishes
partial keyword rows.

## Documentation

Keep `docs/关键词挖掘完整流程.md` unchanged. Create a new Chinese operating guide
describing the three scripts, their input/output boundaries, CDP requirements,
daily order, and retry commands.
