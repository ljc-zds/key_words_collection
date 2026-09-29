# Product Hunt Demand Radar Design

## Objective

Build the Product Hunt branch of the demand-discovery workflow. It retrieves
recent Product Hunt launches through the official API, enriches their official
websites through the already-validated AITDK browser adapter, applies the
bounty-derived screening rules, and writes a daily Markdown report into the
Obsidian vault.

## Sources And Credentials

Product Hunt is the source of launch candidates. The collector sends GraphQL
requests only to Product Hunt's official API with a developer token read from
the project-local `.env` file. The environment file is ignored by Git and never
appears in diagnostics, output JSON, or Obsidian reports.

AITDK remains the traffic and keyword enrichment provider. Each site is queried
through the normal extension flow in a dedicated Playwright profile. The
pipeline does not extract or replay AITDK signing material.

## Pipeline

1. Request newest Product Hunt posts, including name, tagline, launch URL,
   website URL, creation time, vote count, and topics when present.
2. Normalize website URLs to registrable hostnames, reject marketplace/social
   links, and deduplicate domains across the current batch and prior reports.
3. Enrich each remaining domain through AITDK, with bounded sequential retries
   and a per-domain result that contains either traffic data or a non-sensitive
   failure reason.
4. Apply the candidate filter: domain age under one year, monthly visits above
   3,000, organic search share above 20%, and direct traffic share above 20%.
5. Identify obvious brand terms from the Product Hunt name and hostname; flag
   terms containing those tokens as branded. Retain only domains with at least
   one remaining non-brand keyword, and leave borderline terms for human review.
6. Write one dated Obsidian Markdown note with: batch summary, opportunity
   shortlist, excluded candidates with reasons, and a data-source section.

## Output Location And Format

Reports are written to:

`/Users/am/Documents/openclaw/oclaw/obsidian-vault/01-个人输出/刷榜单目录/Product Hunt/`

The filename is `YYYY-MM-DD【Product Hunt 找词】.md`. Front matter stores the
run date, source, candidate count, shortlisted count, and tags. The report keeps
Product Hunt links and website links, but no credentials or raw signed requests.

## Failure Handling

The daily report is still created when Product Hunt returns no candidates or a
subset of AITDK lookups fails. It records counts and sanitized reasons, allowing
the next scheduled run to retry failed domains. An API authentication error
stops candidate collection with a clear local error and does not write the
token to output.

## Testing And Acceptance

Tests are written before production code. Unit tests cover Product Hunt GraphQL
response normalization, URL/domain selection, threshold filtering, brand-keyword
classification, and Markdown rendering. A manually enabled integration test
uses the local Product Hunt token to fetch a small page of posts and then runs
one AITDK enrichment through the existing `deno.com` smoke mechanism.

Acceptance requires a dated Obsidian note containing at least one structured
candidate row or an explicit no-candidate summary, with no secret values in the
note or local diagnostic output.
