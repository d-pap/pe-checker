# PE Checker: live-data research prototype

Search a veterinary practice, HVAC contractor, or national brand. The app fetches public datasets, indexes them in SQLite, and shows the chain and source links it can actually support. It never treats a missing row as proof of independent ownership.

## Run

Requires Python 3.9 or newer. No paid API, account, package install, or manually edited business list is required.

```bash
npm start
```

Open <http://localhost:4173>. The first run downloads two datasets in the background; the header shows when they are ready. `npm test` runs the offline matching and import checks. `PORT=4180 npm start` uses another port.

The database is generated at `pe-checker.sqlite3`. The server checks for updated downloads every hour and refreshes each source after 24 hours. It retains the last successful data when a source is temporarily unavailable. Wikipedia and Wikidata lookups are cached for seven days.

## Sources and what the app claims

| Source | Pulled from | What a match means |
| --- | --- | --- |
| Private Equity Vet | [Published XLSX](https://privateequityvet.org/vet-list/) | The publisher lists a specific veterinary practice, group, and investor/backer. The spreadsheet does not itself classify every investor or document current control. Match name **and location**. |
| hvacrollups | [Published deal CSV](https://hvacrollups.com/data) | A source-linked historical transaction was reported. The row may name a sponsor and may be marked verified by the publisher. A deal does not establish current ownership. The CSV has no location field. |
| Wikipedia | [Open MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page) | An infobox suggests a brand → parent → owner chain or lists a public ticker. This is a research lead until primary evidence confirms it. Article content is CC BY-SA and linked in results. |
| Wikidata | [Open Wikidata API](https://www.wikidata.org/wiki/Wikidata:Data_access) | Exact-name entity identity clue, never an ownership verdict by itself. Structured data is CC0. |

The veterinary file contains 15,211 rows and the HVAC export 1,168 deals as downloaded on 2026-09-29. Counts will change when source files change. The project stores the published data locally to support personal research. **Before publishing this as a public service, obtain permission or a suitable license for the veterinary compilation:** [their terms](https://privateequityvet.org/terms-of-use/) allow intentionally provided downloads and reasonable attributed portions, and restrict republishing a material part of the dataset. The HVAC publisher asks for attribution and its [legal and methodology notes](https://hvacrollups.com/legal) to accompany reused data.

## How a full service should work

1. **Resolve the exact business.** Search name plus city, address, website, and phone. Keep brand, operating company, local practice/franchisee, and investor as distinct entities. If multiple places match, ask the visitor to select one.
2. **Collect dated evidence.** Import licensed sector datasets and open corporate data; monitor acquisition announcements, filings, and company disclosures. Store each claimed relationship with its source URL, publication date, observed date, transaction status, and effective start/end date.
3. **Build the chain.** Follow practice → operating group → platform → sponsor. Distinguish equity control, minority investment, franchising, licensing, and business support relationships. Never infer practice ownership solely from a brand-level sponsor.
4. **Classify as of a date.** `Currently PE-backed`, `formerly PE-backed`, `possible/indirect`, and `unresolved` require different evidence. An announced deal is not a closed deal. A later sale or IPO may change the answer; an IPO does not necessarily end PE voting control.
5. **Recheck and correct.** Refresh sources, detect conflicting or newer claims, queue uncertain changes for review, and show the last checked date. Let businesses and consumers submit source-linked corrections. Keep previous findings for an audit trail.

This prototype implements the source downloads, local matching, historical HVAC deal records, a limited open encyclopedia chain, source dates, and an explicit unresolved state. It does **not** have a complete, automated national acquisition feed or a reliable way to classify every local business. Free public data is fragmented, and many private transactions are undisclosed. A public launch needs more licensed sources or a research and verification operation, plus a persistent dated ownership graph and a correction process.

For the Macomb-area examples, a search for **Creekside Animal Hospital, Macomb, MI** currently returns unresolved in the connected datasets. Several other Creekside clinics in other states are listed; their ownership must not be applied to the Macomb practice. Searches for **Patterson Veterinary Hospital, Clinton Township, MI** and **Snider Veterinary Services, Clinton Township, MI** return named groups and backers from the veterinary download. **C&C** is not in the connected HVAC deal export; that absence proves nothing about its ownership.
