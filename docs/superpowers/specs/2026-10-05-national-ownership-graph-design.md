# PE Checker — Phase 1: National Ownership Graph

**Date:** 2026-10-05 · **Status:** Draft for Derek's review · **Replaces:** the vet/HVAC live-data prototype

## 1. Purpose

PE Checker is a public website where anyone can look up a business or brand and see whether a new owner bought it who is likely to cut quality, shrink portions, or raise prices. Private equity is the headline signal. Investment firms and large corporate parents count too.

The problem is "keep the name, change the owner." A sub shop, sauce brand, vet, or HVAC company keeps its familiar name after it is sold, so customers cannot see the change. The site makes ownership visible and sources every claim, so people can choose where to spend their money.

### What Derek asked for

- Any type of business, not a site built around one sector. The vet and HVAC framing was the prototype's main flaw.
- National brands across the US from the start. Local businesses come later, starting with Macomb and Metro Detroit and expanding by region.
- Data pulled automatically from real sources. Derek never maintains a list by hand.
- Free data sources and free hosting only. No paid APIs.
- Searching for a brand or business is the core experience. Barcode scanning is a nice-to-have.
- Before/after evidence of what changed after a sale is wanted. It is now its own phase (Phase 2).

### Agreed during brainstorming

- Ownership is the risk signal; measured change is the evidence. Phase 1 builds the risk layer, plus the acquisition dates that any before/after comparison needs.
- Verdicts are tiered: PE-owned, investment-firm owned, corporate-owned, or no signals found. Secondary flags mark former PE ownership, recent changes of hands, flips, and roll-ups.
- The site shows dated, sourced facts. It never claims that an owner caused a decline.
- A missing record never means "independent." A same-name business in another place never inherits another entity's ownership. These rules carry over from the prototype.

### Phase 1 is done when

1. Anyone can visit a public GitHub Pages URL, on a phone or desktop, and search a national brand or company. Suggestions appear as they type.
2. The result page shows the verdict first, then the ownership chain, the history timeline, and the evidence. Each piece of evidence includes its source, date, and confidence.
3. A nightly GitHub Actions run refreshes everything with no manual data entry. Bad nights are caught before they are published.
4. These known answers come out right from the automated pipeline:
   - Buffalo Wild Wings → PE (Roark Capital, through Inspire Brands)
   - Jersey Mike's → PE (Blackstone, even though it is publicly traded)
   - Subway → PE (Roark Capital)
   - Rao's → corporate (Campbell's). Its former Advent ownership needs a source Phase 1 doesn't have; see Revisions.
   - A public company with no parent → no signals found, noted as publicly traded

## 2. Roadmap

| Phase | Scope |
|---|---|
| **1 — National ownership graph** (this spec) | Graph, sources, verdicts, search and result pages, nightly pipeline, GitHub Pages |
| 2 — Evidence layer | USDA product-label versions (shrinkflation, ingredient swaps); chain-restaurant nutrition disclosures and menu prices from Wayback Machine snapshots; FDA/USDA recalls, OSHA and Wage & Hour violations, state WARN layoff notices, CMS ratings; owner track record (bankruptcies of other companies the owner bought). Every item is compared before vs. after the acquisition date. |
| 3 — Local, Metro Detroit first | Overture Maps Places, website fingerprints (footer "family of companies," legal entity named in the privacy policy, shared analytics IDs), Michigan business registry, CMS ownership files, franchise locations. The prototype's vet/HVAC sources are reconsidered here. |
| 4 — Freshness | Press-release feeds (deal announcements); a live lookup when a search misses, feeding the graph (the hybrid); "request this brand" queue |
| 5 — Launch | Correction submissions, legal review, pre-rendered pages for link previews and SEO, barcode scanner, browse-an-owner pages, non-PE alternatives |
| Design pass (any time after Phase 1) | Visual theme. Derek wants something as memorable as a nutrition label that works for any business. Ideas so far: an itemized "ownership receipt," or a vehicle-history-report style "ownership history." |

## 3. Out of scope for Phase 1

- Local businesses and franchise locations
- Before/after evidence
- Reviews
- Barcode scanning
- Owner portfolio pages (beyond the minimal owner card in §8.4)
- Alternatives
- Correction submissions
- Link-preview cards
- Press-release ingestion
- Live lookups when a search misses
- The final visual theme. Phase 1 ships clean, neutral styling.

## 4. Architecture

```
NIGHTLY — GitHub Actions (public repo, free)
  collectors/  one module per source → claims (subject, relation, object, dates, source, evidence)
      nsi · wikipedia · wikidata · usda · adv · ftc · sec_ex21
  resolve      merge claims about the same real-world entity (strong identifiers only)
  classify     label each owner: pe_firm / investment_firm / public_company / private_company / unknown
  verdict      walk each chain as of today; apply flag rules
  checks       sanity checks; on failure keep yesterday's site live and open a GitHub issue
  publish      search index shards + entity data shards → GitHub Pages
  persist      commit claims and entities to the `data` branch (git history = audit trail)

BROWSER — static site on GitHub Pages
  search box → prefix shard → suggestions → result page (?b=<slug>) → entity shard → render
```

### Repository layout

```
pipeline/
  run.py              orchestrator CLI (full run, single source, --sample for local dev)
  store.py            read/write sorted NDJSON claim, entity, and classification files
  http.py             polite fetcher: User-Agent, rate limits, retries/backoff, response cache
  collectors/         nsi.py wikipedia.py wikidata.py usda.py adv.py ftc.py sec_ex21.py
  resolve.py          entity resolution and stable slugs
  classify.py         owner classification
  verdict.py          verdict rules
  checks.py           sanity gates and change log
  publish.py          site data files
site/                 index.html app.js style.css about.html (no framework, no build step)
tests/                unit tests per module; fixtures/ holds saved real responses
.github/workflows/    nightly.yml (pipeline + Pages deploy), test.yml (on push)
```

- Python 3.12. The only third-party dependency is `mwparserfromhell`, for parsing Wikipedia templates. HTTP uses the standard library, as the prototype does.
- `package.json` scripts stay as the familiar entry points: `npm test`, `npm run build` (the pipeline), and `npm start` (serves `site/` locally with built data).
- The prototype (`core.py`, `server.py`, `live.*`, `styles.css`, `test_core.py`) is removed from the working tree once Phase 1 replaces it. It stays in git history. `AGENTS.md` and `README.md` are rewritten for the new structure.

## 5. Data model

All persistent state lives as sorted NDJSON on the `data` branch, so the nightly diff is human-readable. During a run, the pipeline loads these files into an in-memory SQLite database for joins.

### 5.1 `entities`

| Field | Notes |
|---|---|
| `id` | Stable ID: Wikidata QID if known (`Q509255`), else `wp:<title>`, `cik:<n>`, `crd:<n>`, `usda:<normalized owner>`, or `nsi:<id>` |
| `kind` | `brand` · `company` · `adviser` (an SEC-registered fund manager) · `fund` |
| `name`, `aliases[]` | Display name; aliases from NSI `matchNames`/`short_name`, Wikipedia redirects, legal names |
| `ids{}` | `wikidata`, `wikipedia`, `nsi`, `cik`, `crd`, `usda_owner`, `website_domain` |
| `category` | From NSI tags or the USDA food category, where available |
| `slug` | URL slug. Assigned once and never changed, so shared links keep working. |

### 5.2 `claims`

One source asserting one relationship.

| Field | Notes |
|---|---|
| `id` | Hash of (source, subject reference, relation, object reference) |
| `subject`, `object` | Entity IDs |
| `relation` | `brand_of` · `controlled_by` (parent or majority owner) · `minority_stake` · `fund_of` (fund → adviser) · `deal` (dated transaction event) |
| `start`, `end` | ISO date or year, plus precision. `end` is `null` for "present." |
| `source`, `source_url`, `source_record` | Collector name, a link a person can open, and the record ID (Wikipedia revision ID, ADV filing ID, FTC transaction number, SEC accession number) |
| `excerpt` | Raw field text the claim came from, e.g. `parent = [[Inspire Brands]] (2018–present)` |
| `first_seen`, `last_seen` | Dates of the pipeline runs that first and most recently observed the claim |
| `status` | `active` (the source still asserts it) · `retracted` (the source stopped asserting it; the claim is kept for history) |

Claims are never deleted. When a source stops asserting something, the claim becomes `retracted` with its `last_seen` date. That turns our nightly runs into dated "change observed" evidence, even when the source gave no date.

### 5.3 `classifications`

For each entity: `kind ∈ {pe_firm, investment_firm, public_company, private_company, unknown}`, a list of evidence (source, record, excerpt), and a confidence. Precedence is `pe_firm` > `investment_firm` > `public_company` > `private_company`. A publicly traded PE firm such as KKR or Blackstone is a `pe_firm`.

### 5.4 `verdicts` (rebuilt nightly, never edited by hand)

Per entity:
- `tier`
- `flags[]`
- `chain[]`: nodes plus the claims supporting each link, with confidence
- `history[]`: control periods with owner, owner kind, start, end, confidence
- `last_changed`
- `confidence`: the weakest link in the current chain
- `as_of`: the build date

The only way to change a verdict is to change, add, or outrank a claim.

## 6. Sources

Every collector outputs claims and entities in the formats above, has offline tests against saved real responses, and runs on its own schedule. All were feasibility-tested live on 2026-10-05.

### 6.1 Name Suggestion Index (OpenStreetMap brand list)

- **What:** storefront brands such as restaurants, retail, banks, and services, with Wikidata QIDs and aliases. About 2,700 US brand QIDs.
- **Where:** `https://cdn.jsdelivr.net/npm/name-suggestion-index@<version>/dist/json/nsi.min.json` and `.../dist/wikidata/wikidata.min.json`. Pin a version and check npm weekly for a new one. The GitHub raw `dist` path returns 404.
- **License:** BSD-3-Clause.
- **Produces:** brand entities (QID, aliases, category, official website). It contains no ownership data.

### 6.2 Wikipedia (primary source for ownership links)

- **Coverage:** about 79,000 articles use `Template:Infobox company`. Articles linked from NSI and Wikidata QIDs are added even if they use another infobox.
- **Bulk fetch:** weekly. `action=query&generator=embeddedin&geititle=Template:Infobox company&geinamespace=0&geilimit=50&prop=revisions|pageprops&rvprop=content|timestamp&rvslots=main&rvsection=0&ppprop=wikibase_item&maxlag=5&formatversion=2` takes about 1,600 requests, roughly 10 minutes.
- **Nightly refresh:** check `lastrevid` for tracked pages in batches of 50. Re-parse only the pages that changed.
- **Fields parsed with `mwparserfromhell`:** `parent`, `owner`, `owners`, `traded_as`, `industry`, `type`, `website`, `brands`, `products`, `subsid`, `defunct`, `fate`. Date ranges like `(2018–present)` and `{{ubl}}` lists are parsed into separate dated claims. A company's `brands` field produces `brand_of` claims for brands listed there.
- **Revision-history backfill:** for every entity on an ownership chain, plus its parents, fetch one revision per year back to 2010. Changes in parent or owner fields become dated `controlled_by` periods, labeled "observed in Wikipedia as of <revision date>." (Planning found this cannot supply Rao's former Advent ownership; see Revisions.)
  - It is a one-time backfill, resumable, with a budget of about 2,000 requests per night.
  - After that, nightly observation takes over.
- **Etiquette:** User-Agent `PECheckerBot/1.0 (+https://github.com/d-pap/pe-checker)` (a project URL is enough; no email). No more than 3 concurrent requests, ≤200 requests per minute, honor `maxlag` and `429 Retry-After`.
- **License:** CC BY-SA 4.0. Every claim links to its article, and the About page carries attribution.

### 6.3 Wikidata (secondary)

- **What:** `wbgetentities` in batches of 50 QIDs.
- **Properties used:** P127 (owned by), P749 (parent organization), P355 (subsidiary), P414 (stock exchange), P5531 (SEC CIK), P31 (instance of; Q5418962 means "private equity firm"), with qualifiers P580 and P582 (start and end time).
- **Coverage:** about 25% of NSI US brands have P127 or P749, and some statements are stale.
- **Rules:**
  - Wikidata is never used alone for a current verdict when Wikipedia disagrees.
  - Wikidata and Wikipedia agreeing does **not** count as two independent sources, because Wikidata is often imported from Wikipedia.
- **Avoid:** the public SPARQL endpoint (WDQS), which rate-limits and has had outages. `https://qlever.dev/api/wikidata` is an optional mirror for one-off queries.
- **License:** CC0.

### 6.4 USDA FoodData Central — Branded Foods

- **What:** grocery brands and the manufacturer that owns each one. There are 36,750 distinct `brand_owner` strings.
- **Where:** `https://fdc.nal.usda.gov/download-datasets/`. The CSV zip is about 450 MB and is released roughly twice a year.
  - Stream only the `branded_food.csv` member using HTTP range requests (the server supports them).
  - Check monthly for a new release.
- **Produces:**
  - Brand entities and `brand_of` claims, aggregated per (brand_name, brand_owner) pair with first and last `modified_date`. The 2 million raw rows are not stored.
  - Owner changes across versions become dated observations. Example: Rao's owner changes from "RAO'S HOMEMADE" to "Sovos Brands Intermediate, Inc." in 2020.
- **Gotchas:**
  - Owner names lag reality; Rao's still shows Sovos. These claims are always `reported` and are outranked by newer claims from other sources.
  - Brand names sometimes appear in the owner field.
  - Retailer private labels (Walmart, Target) are `brand_of` the retailer.
- **License:** CC0. A citation is requested.

### 6.5 SEC Form ADV — who is a PE firm

- **Where:** manifest at `https://reports.adviserinfo.sec.gov/reports/foia/reports_metadata.json` (section `advFilingData`). Files are at `.../advFilingData/{YYYY}/ADV_Filing_Data_{start}_{end}.zip`. Data from before 2025 is at `https://www.sec.gov/foia/docs/form-adv-archive-data`.
- **Join:** `IA_ADV_Base_A`/`ERA_ADV_Base` (adviser: legal name 1A, business name 1B1, CRD 1E1) to `IA_/ERA_Schedule_D_7B1` (funds: name, ID, **Fund Type**, gross assets) on FilingID.
- **Cadence:** files are monthly deltas, not snapshots. Keep a rolling 13 months, take the latest filing per CRD, and detect re-uploads by size or ETag.
- **Produces:**
  - adviser entities
  - fund entities with `fund_of` claims
  - classifications:
    - an adviser with ≥1 "Private Equity Fund" → `pe_firm`
    - an adviser with private funds but none labeled PE → `investment_firm`
- **Test results** (March 2026 filings):
  - 3,598 advisers reported PE funds.
  - Roark has 14 funds, all PE. Advent has 133 PE funds. KKR has 495 PE funds.
  - Blackstone is spread across about 25 filers, several of them with PE funds.
  - Fund types are self-reported. Some Blackstone funds are labeled "Hedge Fund," which is harmless under the "≥1 PE fund" rule.
- **Matching an adviser to a company entity:** Wikipedia's "Roark Capital Group" vs. ADV's "Roark Capital Management, LLC."
  - Compare core names: casefold, then strip legal suffixes and holding words (LLC, L.P., Inc., Co., Management, Partners, Group, Holdings, Capital, Advisors, Advisers).
  - The match is `confirmed` only when core names are equal **and** a second signal agrees: the same website domain (the ADV websites schedule, Schedule D 1.I, if present in the bulk data — verify during implementation), or Wikipedia describing the company as a private equity or investment firm.
  - A core-name match alone is not used (see Revisions: Form ADV only confirms firms an encyclopedia already describes as investment firms).
- **License:** US government, public domain.

### 6.6 FTC HSR early termination notices

- **Where:** `https://api.ftc.gov/v0/hsr-early-termination-notices` (JSON:API). It needs a free api.data.gov key, stored as the `FTC_API_KEY` secret. The RSS feed `https://www.ftc.gov/feeds/hsr-early-termination-notices.xml` is a fallback.
- **Volume:** 28,145 records.
  - Early termination was suspended from 2021 and resumed on 2025-04-25: 381 notices in 2025, 609 in 2026 through 2026-09-29.
  - Backfill once, then fetch increments nightly.
- **Produces:** `deal` claims from the acquiring party to the acquired party and acquired entities, dated.
  - Acquiring parties are joined to ADV fund names by exact normalized match. In testing, 22 of the 50 most recent notices matched, e.g. "Roark Capital Partners VI (T) LP."
  - Targets are often holding companies ("C3 TopCo, LLC"). A deal links to a brand only by exact normalized match to an existing entity name or alias. Unmatched deals are stored for Phase 4 and later.
- **Meaning:** a deal claim marks a change of hands and supports a `controlled_by` claim. A deal alone **never** establishes current control.
- **License:** public domain.

### 6.7 SEC EDGAR Exhibit 21 (subsidiary lists)

- **Access:** `www.sec.gov` requires a User-Agent with contact email. The email is stored as the `SEC_CONTACT_EMAIL` GitHub secret (Derek's SEC contact address) and never committed to the public repo. `data.sec.gov` and `efts.sec.gov` also accept it. Requests stay at ≤5 per second (the SEC limit is 10).
- **Scope:** public companies that appear as parents in the graph, found by CIK from Wikidata P5531 or `https://www.sec.gov/files/company_tickers.json`.
- **Steps:**
  1. Read the filing list from `https://data.sec.gov/submissions/CIK##########.json`.
  2. Find the 10-K's EX-21 through the filing index or full-text search (`efts.sec.gov/LATEST/search-index?...&forms=10-K`, `file_type: "EX-21"`).
  3. Parse the subsidiary names.
- **Produces:** `controlled_by` claims marked `confirmed` (official filing) for subsidiaries that exactly match an existing entity. Example: FY2024 Campbell's EX-21 lists Sovos Brands Holdings, Sovos Brands Intermediate, and Rao's Specialty Foods.
- **History:** the past 10 years of EX-21s give dated periods.
- **Gotchas:**
  - Acquired subsidiaries often disappear from EX-21 within a year as they are merged. Campbell's FY2025 list omits Sovos, and its FY2026 10-K has no EX-21 at all. Disappearing from EX-21 ends the *observation*, never the control.
  - EX-21 lists legal entities, not brands.
- **License:** public domain.

## 7. Entity resolution

The most dangerous error is a false merge, because it moves an owner onto the wrong brand.

- **Strong identifiers merge automatically:** Wikidata QID, Wikipedia title (after redirects), SEC CIK, ADV CRD, NSI ID. NSI brand Q509255 and the Wikipedia article "Buffalo Wild Wings" are the same entity through the QID.
- **Name-only matches** need an exact normalized name **plus** corroboration: the same website domain, or a second source using the identical legal name string. Otherwise the match is stored as `possibly_same_as` and **never used in verdicts**.
- **Corporate-family rule:** legal names that differ only by holding-structure words (Holdings, Intermediate, Midco, TopCo, Holdco, Parent, Acquisition, Buyer, Opco) are grouped as one corporate family for walking the chain. The grouping is `reported`. Example: "Sovos Brands Intermediate, Inc." and "Sovos Brands." If family members claim different parents, the result is `conflicting`.
- **Normalization:** NFKD, casefold, strip accents and punctuation, "&" → "and". Legal suffixes are stripped only when comparing company names.
- **Slugs:** generated from the display name with a collision suffix. Once assigned, a slug is persisted on the entity and never regenerated.

## 8. Verdict rules

### 8.1 Chain walk

From the entity, follow active `brand_of` and `controlled_by` links that are current as of the build date (`end` is null or in the future).

- **Several parent claims:** prefer `confirmed` claims, then the most recent dated evidence. If sources name different current controllers, mark the link `conflicting` and keep both.
- **Depth and loops:** stop at depth 8, and stop if a cycle is detected.
- **Top owner:** the last node whose classification is known.

### 8.2 Tiers (one per entity)

| Tier | Rule | Example copy |
|---|---|---|
| **● PE-owned** | Any node in the current chain is classified `pe_firm`, or is a fund whose adviser is one | "Controlled by Roark Capital, a private equity firm, since 2018." |
| **● Investment-firm owned** | Otherwise, any node is `investment_firm` | "Controlled by JAB Holding, an investment firm, since 2019." |
| **◆ Corporate-owned** | Otherwise, the entity has a current parent | "Owned by Campbell's since 2024." |
| **○ No ownership signals found** | Known entity, no current parent claims | "We found no parent owner in our sources. That doesn't confirm it's independent." If it is publicly traded, add "Publicly traded (NYSE: X)." |
| **Not in our data yet** | Search miss | Explain that this says nothing about ownership. |

A public listing never cancels a PE tier. Jersey Mike's is publicly traded and remains Blackstone-controlled.

### 8.3 Secondary flags

| Flag | Rule |
|---|---|
| **◇ Formerly PE-owned / formerly investment-firm owned** | Any ended control period whose owner is classified PE or investment firm. Show the firm and years; when a date is observed rather than reported, show "observed until 2024." |
| **⟳ Changed hands YEAR** | The most recent change of control on the chain. Emphasized when within 5 years. |
| **↻ Flipped** | ≥2 changes of control within 10 years |
| **⧉ Roll-up** | The top owner controls ≥5 brands in the same category in our data |

Thresholds are named constants in `verdict.py`.

### 8.4 Searching for an owner

When the searched entity is itself a PE or investment firm, show a minimal owner card. It states the firm type with its evidence, and gives a count and plain list of the brands it currently controls in our data. Full portfolio pages are Phase 5.

### 8.5 Confidence

| Level | Meaning |
|---|---|
| **Confirmed** | An official filing (SEC EX-21, Form ADV, FTC), or two *independent* sources agree. Wikipedia and Wikidata together count as one. |
| **Reported** | A single non-official source |
| **Conflicting** | Sources disagree about the current controller. Both are shown, and the verdict leans toward the most recent dated evidence. |

Most ownership links in Phase 1 will honestly read "Reported." PE classifications will mostly be "Confirmed," because they come from Form ADV.

## 9. Website

### Pages

- **Home:** one search box with instant suggestions that match names and aliases ("BWW," "Raos"), a few example searches, and a one-line explanation.
- **Result page** (`/?b=<slug>`, verdict first, from mockup direction A):
  1. verdict banner with the tier symbol, color, and plain sentence
  2. secondary flags
  3. **Who owns it** (chain)
  4. **History** (timeline of control periods)
  5. **Sources**, expandable: each claim with source name, link, date, confidence, and excerpt
  6. "Last checked" date
- **Not found:** "Not in our data yet," with the explanation.
- **About / Method:** sources, licenses, and attribution (CC BY-SA for Wikipedia); how verdicts and confidence work; tier definitions; known limitations; per-source freshness from `meta.json`.

### Published data files

| File | Contents |
|---|---|
| `data/search/<prefix>.json` | The prefix is the first three normalized characters of each name or alias token; `top.json` holds the top 3,000 entries for two-letter queries. Each entry: display name, slug, tier, kind, search text, score. |
| `data/e/<xxx>.json` | 4,096 shards keyed by the first three hex characters of sha1(slug). Each holds the full verdict objects for its entities. |
| `data/meta.json` | Build time, per-source last success and staleness, counts |
| `data/changes/latest.json` | Verdict changes from the latest run |

- **Search ranking:** exact match > prefix match. NSI/USDA consumer brands rank above generic companies. Ties go to the entity with more sources.
- **Size budget:** keep the published `data/` under 300 MB (GitHub Pages allows 1 GB). The publish step fails the run if the budget is exceeded.
- **Styling:** clean and neutral, mobile-first. Color is never the only signal; symbols and text always accompany it. The visual theme is a separate design pass.
- **URLs:** `/?b=<slug>` returns a real HTTP 200 on GitHub Pages. Pretty pre-rendered `/brand/<slug>/` pages with link-preview tags come in Phase 5.

## 10. Pipeline operations

### Schedule

GitHub Actions cron runs nightly at about 07:00 UTC, plus manual `workflow_dispatch`. Source cadences inside the run:

| Cadence | Sources |
|---|---|
| Nightly | Wikipedia (changed pages), FTC (incremental), revision backfill budget |
| Weekly | Wikipedia full pass, NSI, Wikidata, SEC EX-21 |
| Monthly | Form ADV, USDA new-release check |

### Secrets and state

- **Secrets:** `SEC_CONTACT_EMAIL` and `FTC_API_KEY`. Neither appears in code or logs.
- **State:**
  - The `data` branch holds claims, entities, classifications, slugs, and backfill progress. Large first-time backfills resume across nights.
  - Raw HTTP responses go in the Actions cache. Losing the cache only costs re-fetching.
- **Budget:** a normal nightly run takes under 60 minutes. The first runs may take several nights to finish the backfills.

### Failure handling

- **A source fails:** its previous claims carry forward unchanged, and `meta.json` marks the source stale since its last success. A failed fetch never produces "no signals found."
- **Sanity gates run before publishing:**
  - Each source's active claim count must stay within ±20% of the previous successful run. Claims added by the revision-history backfill are excluded from this count, because they grow by design.
  - Tier changes must not exceed 2% of entities in one night.
  - Known-answer checks must pass (§11).
  - On failure: don't publish, don't commit data, keep yesterday's site live, and open a GitHub issue with the gate report.
  - The first run has no baseline. It, and any run with an intended big change such as a new source, is started manually with `override_gates=true`. Known-answer checks still apply to override runs.
- **Change log:** each run writes `data/changes/YYYY-MM-DD.json` (tier changes, new and retracted claims) to the data branch.

### Local development

- `npm run build:sample` runs the whole pipeline on a built-in sample graph (no network); `npm run build -- --only <source>` runs one live source.
- `npm start` serves `site/` with the built data.

## 11. Testing

- **Collector tests** use saved real responses under `tests/fixtures/` and run fully offline with `npm test`. They cover:
  - Wikipedia infobox variants: date ranges, `{{ubl}}`, `<br>`, references, empty fields
  - Wikipedia revision-history diffs
  - the ADV join and fund-type rules
  - the FTC deal ↔ ADV fund join
  - USDA aggregation and owner-change observation
  - EX-21 parsing
- **Resolution tests:**
  - Strong-identifier merges.
  - Name-only non-merges, such as two different companies with the same name.
  - The corporate-family rule.
  - ADV name matching, including a negative case: an operating company whose core name equals an adviser's must not be classified PE without corroboration.
- **Verdict tests** use small hand-built graphs: PE in the chain, investment firm, corporate only, ended PE period, minority stake (not flagged), IPO with a PE parent, conflicting parents, cycle, depth limit, flip and roll-up thresholds.
- **Known-answer gate:** runs against the real nightly build. The expected answers live in test code and **are never published as site data**; they only check that the automated pipeline still reaches them.
  - Buffalo Wild Wings → PE (Roark)
  - Jersey Mike's → PE (Blackstone)
  - Subway → PE (Roark)
  - Rao's → corporate (Campbell's)
  - A public company with no parent → no signals found
- **Site test:** one Playwright test loads the home page, searches, and opens a result page using sample data.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Wikipedia template or format changes break parsing | Collector tests, ±20% claim-count gate, known-answer gate |
| A false merge puts an owner on the wrong brand | Strong-identifier rule, `possibly_same_as` never used in verdicts, negative tests |
| An ADV ↔ company name match is wrong | Corroboration required for `confirmed`; core-name-only is `reported` |
| Stale sources (USDA, Wikidata, EX-21 drop-offs) | Recency-based precedence; disappearance ends observation, not control |
| Published data too large for Pages | 300 MB budget check in publish |
| Legal: a wrong claim about a company | Every claim sourced and dated with a confidence level; facts only, no causal claims. Correction flow and legal review in Phase 5. National, publicly documented brands are the lowest-risk starting point. |
| Wikipedia CC BY-SA obligations | Link every claim, attribute on the About page, license published data compatibly (see §13) |

## 13. Open questions

- **Licenses for the public repo.** Recommendation: MIT for code, CC BY-SA 4.0 for published data (compatible with the Wikipedia-derived facts). Derek to confirm before the first public deploy.
- **Visual theme.** Separate design pass. Candidates: ownership receipt, vehicle-history-report style.
- **Investment-firm detection beyond ADV.** Holding companies like JAB may not file Form ADV, so the Wikipedia industry and description fields are the fallback. Quality will be measured in Phase 1 and revisited.
- **Flip and roll-up thresholds.** Starting values are in §8.3. Tune after seeing real distributions.
- **The prototype's vet/HVAC sources.** Not used in Phase 1; reconsider in Phase 3. Private Equity Vet's terms restrict republishing a material part of its compilation without written permission.

## 14. Revisions made during planning (2026-10-05)

Implementation planning prototyped the whole pipeline against live data. These changes supersede the sections above where they conflict.

1. **Rao's "formerly PE (Advent)" is out of Phase 1.**
   - Wikipedia's Sovos Brands page was created in 2023 and never listed Advent as owner.
   - The 2017 FTC notice names "Sovos Brands Limited Partnership" as buyer, not an Advent fund.
   - The Phase 1 known answer for Rao's is corporate-owned (Campbell's) only.
   - The likely source for the missing history is SEC beneficial-ownership filings (Schedule 13D/13G), which also reveal PE control of publicly traded brands. Candidate for a later phase.
2. **Form ADV never turns an operating company into a PE firm.**
   - Big banks run PE funds, so a domain or name match alone would label Chase "PE-owned."
   - ADV evidence now only upgrades and confirms a company that Wikipedia or Wikidata already describes as an investment or PE firm. The match is by shared website domain (ADV Schedule D 1.I is in the bulk data) or by core name.
   - Other matches are recorded as "possibly the same" and not used.
3. **FTC "acquired party" is the seller.** In HSR terms it is the target's former ultimate parent. Each notice therefore yields a dated `deal` to the buyer and an *ended* `controlled_by` period for the seller (when the seller isn't the target itself). This is how a PE exit becomes "formerly PE." Deals still never establish current control.
4. **People are not parent companies.** Owner links to people's articles (a person infobox, or a short description such as "businessman" or "entrepreneur") are dropped, and Wikidata owners that are humans are skipped. Unlinked owner text that names no one ("Independent business", "The X family") is ignored.
5. **An end year means it ended.** `(2010–2026)` read in 2026 is history, not a rival current owner.
6. **Wikidata requests send no `maxlag`.** Wikidata ties it to query-service lag and refused reads during testing. Any API error now fails the source, so yesterday's data carries forward instead of silently publishing empty results.
7. **Sharding and sample builds.**
   - Entity data uses 4,096 shards and search uses 3-character prefixes, to keep phone downloads small.
   - `--sample` builds from a built-in graph rather than fixtures plus a live sample.
8. **Expected volume and run time.**
   - The weekly Wikipedia pass takes about 4,000 requests (~25 minutes) because it also collects redirect names, which let USDA, FTC, and SEC names match companies.
   - The first nightly run takes 2–3 hours; normal nights take well under an hour. The workflow timeout is 4 hours.
