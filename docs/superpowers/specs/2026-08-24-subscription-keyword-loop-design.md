# Subscription Keyword Discovery Loop Design

## Objective

Turn a maintained subscription-business root-keyword library into a daily,
reviewable stream of high-demand keyword candidates. The workflow queries the
Similarweb Keyword Generator, retains keywords with average monthly volume of
at least 30,000 and KD no greater than 60, learns candidate roots from accepted
keywords, and publishes a maximum of 300 records per run to the supplied
Feishu destination.

## Scope

The first delivery automates the root-keyword route. Revenue ranking sources
are represented as imported root keywords; scraping Stripe or Toolify rankings
is deliberately outside this delivery. The existing AITDK browser setup is
reused to drive Similarweb while logged into the user's account.

## Inputs And Configuration

- A Feishu root library supplied as either a wiki-backed table or a local CSV.
  Its required column is `root`; optional columns include `source` and `active`.
- Runtime environment variables `FEISHU_APP_ID` and `FEISHU_APP_SECRET`.
  Credentials never appear in source code, logs, reports, tests, or generated
  configuration files.
- CLI options for market, search engine, minimum volume (default 30000),
  maximum KD (default 60), per-root result cap, and daily review cap (default
  300).

## Collection

For each active root, browser automation opens Similarweb's Keyword Generator
with the root pre-filled. It reads the phrase-match, related-keyword, trending,
and question tabs. For each result it records keyword, average monthly volume,
KD, search intent, result type, source root, market, and retrieval time.

The collector paginates until it reaches the configured cap or finds no next
page. A failed root becomes a per-root error record and does not cancel the
remaining batch. Authentication, changed page structure, unreadable metric
cells, and rate limits result in actionable sanitized errors without exposing
page data or credentials.

## Storage And Selection

SQLite is the local run history. A normalized keyword is unique per market;
multiple source roots and result types are merged into its provenance. The
daily candidate query retains only volume >= 30000 and KD <= 60, then orders by
volume descending, KD ascending, and number of independent roots descending.

Accepted candidates produce proposed roots by tokenizing their keyword and
removing generic stop words. These proposals are stored separately for manual
approval; the automation never silently adds roots to the active library.

## Feishu Publication

The supplied wiki URL is resolved through the Feishu API before every publish.
If it targets a spreadsheet, publication uses the Sheets API; if it targets a
Bitable, publication uses the Bitable records API. The destination requires
columns equivalent to: keyword, average volume, KD, intent, source roots,
result types, market, retrieved at, review status, and explanation.

Each run upserts the dated review batch rather than clearing prior history.
The explanation field is a deterministic Chinese template answering: what the
keyword is, its likely search intent, and its possible subscription-business
value. This provides the requested daily manual review without an additional
LLM dependency in the first release.

## CLI

`python -m keyword_loop run --roots-feishu-url <url> --results-feishu-url <url>`
collects, filters, stores, and publishes one batch. `import-roots`,
`propose-roots`, and `publish` are available separately for recovery and
inspection. A dry-run writes local SQLite only.

## Validation

Unit tests cover metric parsing, threshold boundaries, normalization and
provenance merging, root proposal, deterministic explanation generation, and
Feishu payload selection. Browser smoke tests use a stable saved Similarweb
HTML fixture and verify table extraction without making live requests. A final
manual run against one root checks that the current Similarweb page and the
authorized Feishu destination are accessible.
