# Product Hunt Search Resolver Design

## Objective

Produce an Obsidian candidate table equivalent to the supplied Product Hunt
screen: product metadata, official website/domain, AITDK traffic/keyword data,
filter status, and source links.

## Website Resolution

Product Hunt's official API supplies products but not a directly usable official
website URL. For each Product Hunt candidate, a browser-driven web search uses
the product name and tagline to identify the official website result. The
resolver rejects Product Hunt, app stores, social networks, and directory sites.
Uncertain matches are recorded with a failure reason rather than silently used.

## Enrichment And Filter

Resolved domains use the existing isolated AITDK extension flow. The report
stores available traffic metrics, domain age/registration data when exposed by
AITDK, and top keywords. Candidate status uses: age under 365 days, monthly
visits above 3,000, organic share above 20%, direct share above 20%, and at
least one non-brand keyword.

## Report

Each dated Markdown report in the Obsidian Product Hunt directory contains a
compact table: Site, description, domain, source date, registration/age,
search/total visits, traffic shares, keywords, status, error, Product Hunt
source, and resolved website link. It contains no credentials or raw tracking
URLs.

## Validation

Unit tests cover search-result domain rejection, field mapping, filters, and
Markdown rendering. A small manual batch of five Product Hunt posts verifies
that the report creates structured rows with either successful AITDK data or a
specific sanitized failure reason.
