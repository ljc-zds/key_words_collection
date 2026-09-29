# Flaq-related Site Keyword Architecture Summary

**Generated:** 2026-09-24
**Scope:** Fylia, SeaImagine, and AI Try-On rendered public pages

## Homepage Link Comparison

These counts cover unique internal paths exposed by each rendered homepage, not total indexed URLs.

| Site | Internal paths | Model paths | Blog paths | Free paths | Localized paths | Other paths |
|---|---:|---:|---:|---:|---:|---:|
| Fylia | 150 | 50 | 13 | 7 | 15 | 65 |
| SeaImagine | 75 | 16 | 13 | 7 | 15 | 24 |
| AI Try-On | 102 | 31 | 1 | 8 | 15 | 47 |

## Shared Architecture

```text
Shared generation, account, credit, history, payment, and storage platform
├── Brand homepage and default creation mode
├── Generic capability pages
├── Model and model-version pages
├── Scenario and outcome pages
├── Free acquisition tools
├── Blog, guide, comparison, and launch pages
└── Localized versions
```

## How many keywords are handled

1. A single backend capability is exposed through multiple search-intent entry pages.
2. Generic pages, model pages, and scenario pages use different URL families and page templates.
3. The actual working tool is embedded high on the landing page; the page is not merely keyword text.
4. Repeated supporting sections include examples, features, advantages, use cases, instructions, FAQ, related tools, and articles.
5. Mega menus, footers, and related-tool blocks distribute internal links to pages that do not fit in the primary navigation.
6. Free tools acquire visitors; shared credits and paid models monetize them inside the same account system.
7. Localization is applied after a page template exists, multiplying coverage without building a separate product.

## Important inference

The current sites prove that many pages can coexist on one shared platform. Public pages do not prove that all pages launched at the same time. A new site should copy the architecture and release gates, not assume that publishing the full catalog on day one is required.

## Implication for Prompt Intelligence

Prompt Intelligence can use the same pattern:

- Shared workspace and billing backend.
- Separate tool, model, scenario-generator, Library, and guide templates.
- Keyword-specific controls and examples on every indexable page.
- Related links and grouped navigation instead of placing every page in the header.
- Phased release based on tool readiness, unique content, and Library inventory.

