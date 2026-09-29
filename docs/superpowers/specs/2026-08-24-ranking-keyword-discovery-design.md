# Ranking Keyword Discovery Design

## Objective

Create the second keyword-discovery route: collect publicly accessible product
ranking pages, resolve listed products to official domains, use Similarweb to
find their search keywords, and rank filtered opportunities by the number of
independent products that surface them.

## Sources

The collector accepts public Toolify ranking pages and public third-party
Stripe-revenue ranking pages. Stripe itself is not treated as a source of
official product revenue rankings. Every imported product retains its source
URL, page title, capture date, and a `revenue_estimate` label when the source
reports an estimate rather than verified revenue.

Pages requiring authentication, rate-limit bypasses, or anti-bot circumvention
are skipped and recorded with a sanitized reason.

## Pipeline

1. A source adapter downloads and parses a ranking page into product name,
   product URL, displayed rank, and displayed revenue text where available.
2. The resolver identifies an official domain from a direct link or existing
   search-resolution rules. Directory, social, app-store, and ranking hosts are
   rejected.
3. The existing Similarweb CDP collector reads keyword, average volume, KD,
   and intent for each resolved domain or product-derived query.
4. SQLite merges the keyword observations with root-library observations.
   Provenance records source kind, ranking URL, ranked product/domain, and
   collection time.
5. The review query retains volume >= 30000 and KD <= 60, then adds
   `consensus_count`: the number of distinct ranked products contributing that
   keyword. Results are ordered by consensus count, average volume, and KD.

## Output

The existing Feishu review sheet receives all qualifying candidates. New
columns identify the number of ranking products, their names/domains, and the
ranking source URLs. This makes a keyword supported by several independent
successful products visibly distinct from one found only through a root.

## Reliability

Each source page and product is independently recoverable. SQLite stores
source and resolver failures with a timestamp and sanitized reason. A failed
ranking source or a product with no resolvable official domain cannot block the
rest of the run.

## Validation

Unit tests cover source-page parsing fixtures, rejected non-official links,
ranking provenance aggregation, consensus ranking, and Feishu row rendering.
One manual public Toolify page validates the live parser; a public Stripe
third-party page validates that estimate metadata is preserved.
