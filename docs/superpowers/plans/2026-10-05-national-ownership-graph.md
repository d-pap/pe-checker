# PE Checker Phase 1: National Ownership Graph — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vet/HVAC prototype with a nightly-built, source-attributed ownership graph for national brands, published as a static, verdict-first search site on GitHub Pages.

**Architecture:** One collector per free source turns raw data into dated *claims* ("X is controlled by Y, from, to, source"). Each night `run.py` folds the claims into NDJSON state on a `data` branch, merges records about the same entity (`resolve.py`), labels owners (`classify.py`), walks each ownership chain into a verdict (`verdict.py`), checks safety gates (`checks.py`), and writes sharded JSON plus a plain HTML/JS site (`publish.py`, `site/`).

**Tech Stack:** Python 3.12 (stdlib + `mwparserfromhell` 0.7.2), `unittest`, plain HTML/CSS/JS (ES modules, no build step), Playwright 1.63 for browser tests, GitHub Actions + GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-10-05-national-ownership-graph-design.md`. Read its "Revisions made during planning" section first; this plan implements the revised spec.

**Provenance:** Every code and test block below was run as a prototype on 2026-10-05: 109 unit tests and 5 browser tests passed. The Wikipedia, Wikidata, SEC, and USDA collectors were also smoke-tested against the live services. Copy the blocks exactly. If a test fails, the bug is in the copy or in an environment difference, not in the design.

## Global Constraints

- Python 3.12 in CI (3.12+ locally). The only third-party Python package is `mwparserfromhell==0.7.2` (`requirements.txt`).
- Everything else is the Python standard library. Tests use `unittest` and run offline: no test touches the network.
- Site: plain HTML/CSS/JS, no framework, no build step. Every value inserted into HTML goes through `esc()`, and every URL goes through `safeUrl()`.
- The Wikipedia/Wikimedia User-Agent is exactly `PECheckerBot/1.0 (+https://github.com/d-pap/pe-checker)` (`pipeline/config.py`).
  - Pacing is ≥0.35 s between requests (~170/min, under the 200/min limit), one request at a time.
  - Wikipedia requests send `maxlag=5` and honor `429 Retry-After`.
  - Wikidata requests must **not** send `maxlag`: Wikidata ties it to its query-service lag and refuses reads.
- SEC: User-Agent `PECheckerBot/1.0 <email>`, with the email from the `SEC_CONTACT_EMAIL` env var/secret, at ≤4 requests/s. The email is never committed, logged, or published.
- FTC: the api.data.gov key comes from `FTC_API_KEY`, is sent only as an `X-Api-Key` header, and never appears in a URL, error, or log.
- A missing record is never shown as independent ownership.
- Same-name entities never merge without corroboration.
- A deal (FTC notice) never establishes current control.
- Claims are never deleted (they become `retracted`).
- Verdicts are computed only, never hand-edited.
- Confidence:
  - **confirmed**: an official filing (sources `adv`, `ftc`, `sec_ex21`), or two independent source groups.
  - `wikipedia`, `wikipedia_history`, and `wikidata` are **one** group.
  - Links joined only by the corporate-family rule are at most **reported**.
- Gates:
  - Per-source active-claim count within ±20% of the previous run (`wikipedia_history` exempt).
  - At most 2% of verdict tiers may change in one run.
  - Known answers must always hold, even on `--override-gates` runs.
- The known answers in `pipeline/checks.py` are test expectations only and never feed site data.
- Size limits: published `data/` ≤ 300 MB, and every NDJSON state file < 95 MB.
- Pages state ownership facts only. Never claim that an owner caused a change.
- All commands assume the repo root and an activated virtualenv (`source .venv/bin/activate`, created in Task 1).
- Every commit message ends with the attribution lines your session requires.

## Review Focus

These are inputs and conditions the spec implies but doesn't spell out, most likely to bite first. Each one is pinned by a test in the task that owns the code:

1. **A user types a curly apostrophe or accent ("Rao’s").** They must find the same brand as "Raos". The JS `normalize()` mirrors Python's. → Task 19, Playwright test "curly apostrophes and nicknames find the same brand".
2. **A Wikipedia `owner` field links to a person's article (a founder).** The brand must not become "corporate-owned by" that person, and the person gets no page. → Task 5, `test_an_owner_who_is_a_person_is_not_a_parent_company`.
3. **The FTC API ignores paging.** The first backfill must still terminate (repeat detection plus a page cap). → Task 9, `test_an_api_that_ignores_paging_cannot_loop_forever`.
4. **An owner's end date is this year** (`(2010–2026)` read in 2026). That period is history, not a rival "conflicting" parent. → Task 15, `test_owner_that_ended_earlier_this_year_is_history_not_a_rival`.
5. **A page uses an infobox other than `Infobox company`** (restaurant chains, brands). It must still be parsed when fetched through an NSI/Wikidata link. → Task 4, `test_any_infobox_template_is_read`.

## File map

| Path | Responsibility |
|---|---|
| `pipeline/model.py` | Records (`Entity`, `Claim`, `Classification`, `CollectorResult`), name keys, date padding |
| `pipeline/config.py` | User-Agents, source cadences, download cache location |
| `pipeline/store.py` | NDJSON state on the `data` branch; applies collector runs without deleting claims |
| `pipeline/http.py` | `Fetcher`: pacing, retries, `Retry-After`, MediaWiki `maxlag`, no secrets in errors |
| `pipeline/collectors/wikitext.py` | Pure infobox parsing (owners, brands, tickers, classification, people) |
| `pipeline/collectors/wikipedia.py` | Bulk/incremental infobox collection, redirect resolution |
| `pipeline/collectors/nsi.py` | Name Suggestion Index brands |
| `pipeline/collectors/wikidata.py` | Secondary ownership links, CIKs, PE-firm class |
| `pipeline/collectors/adv.py` | SEC Form ADV advisers, funds, websites; PE classification |
| `pipeline/collectors/ftc.py` | FTC early-termination deals (buyer = deal, seller = ended control) |
| `pipeline/collectors/usda.py` | USDA branded foods brand → owner, streamed with range requests |
| `pipeline/collectors/sec_ex21.py` | 10-K Exhibit 21 subsidiaries, SEC registrant tickers |
| `pipeline/collectors/wikipedia_history.py` | One-time yearly revision backfill of past owners |
| `pipeline/resolve.py` | Union of records into nodes (strong IDs, exact names, corporate family) |
| `pipeline/classify.py` | Owner kind per node; Form ADV matching that never upgrades an operating company |
| `pipeline/verdict.py` | Chain walk, tiers, flags, history, owner cards |
| `pipeline/checks.py` | Safety gates and the gate report |
| `pipeline/publish.py` | Slugs, entity/search shards, `meta.json`, size budget |
| `pipeline/sample.py` | Built-in sample graph for `--sample` builds and end-to-end tests |
| `pipeline/run.py` | Orchestrator CLI |
| `site/` | `index.html`, `app.js`, `style.css`, `about.html` |
| `tests/` | `unittest` modules, `helpers.py` test doubles, `site/search.spec.js` |
| `.github/workflows/` | `test.yml` (push/PR), `nightly.yml` (cron + manual) |

---

### Task 1: Scaffold, records, and name keys

**Files:**
- Create: `requirements.txt`, `pipeline/__init__.py`, `pipeline/collectors/__init__.py`, `tests/__init__.py`, `pipeline/model.py`, `pipeline/config.py`
- Modify: `package.json` (test script), `.gitignore`
- Test: `tests/test_model.py`

**Interfaces:**
- Produces:
  - `normalize(str|None) -> str`, `exact_key`, `family_key`, `adviser_core`, `name_ref(name) -> "name:<normalized>"`, `slugify`, `smart_title`, `website_domain`, `pad_start`, `pad_end`, `year_of`, `chunks(items, size)`.
  - Constants `CONTROL_RELATIONS`, `SOURCE_GROUPS`, `SOURCE_PRIORITY`, `SOCIAL_DOMAINS`.
  - Dataclasses `Entity(id, kind, name, source, aliases=[], ids={}, category="")`, `Claim(source, subject, relation, object, start=None, end=None, source_url="", source_record="", excerpt="", official=False, observed=False, first_seen="", last_seen="", status="active", via_family=False)` with `.key`, `Classification(entity, kind, source, evidence, source_url="", official=False)` with `.key`, and `CollectorResult(entities, claims, classifications, scope=None, progress=None, unchanged=False)`.
  - `config.USER_AGENT`, `config.CADENCE_DAYS`, `config.sec_user_agent(email)`, `config.cache_dir()`.

- [ ] **Step 1: Create the virtualenv and package skeleton**

```bash
printf 'mwparserfromhell==0.7.2\n' > requirements.txt
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
mkdir -p pipeline/collectors tests/site
printf '"""PE Checker nightly pipeline: collect sources, resolve entities, compute verdicts, publish."""\n' > pipeline/__init__.py
printf '"""One module per source. Each exposes collect(fetcher, store, run_date) -> CollectorResult."""\n' > pipeline/collectors/__init__.py
: > tests/__init__.py
printf '.venv/\nstate/\nbuild/\n.cache/\nnode_modules/\ntest-results/\nplaywright-report/\n.playwright-mcp/\n' >> .gitignore
```

In `package.json`, replace the `"test"` script with:

```json
"test": "python3 -m unittest discover -s tests -t . -p 'test_*.py'"
```

- [ ] **Step 2: Write the failing test**

`tests/test_model.py`:

```python
import unittest

from pipeline.model import (Claim, adviser_core, exact_key, family_key, name_ref, normalize, pad_end, pad_start,
                            slugify, smart_title, website_domain, year_of)


class NameKeys(unittest.TestCase):
    def test_normalize_folds_case_accents_apostrophes_and_initialisms(self):
        self.assertEqual(normalize("Rao's Homemade, L.L.C."), "raos homemade llc")
        self.assertEqual(normalize("Café Rio & Co."), "cafe rio and co")
        self.assertEqual(normalize("Jersey Mike’s"), "jersey mikes")
        self.assertEqual(normalize(None), "")

    def test_exact_key_drops_legal_form_only(self):
        self.assertEqual(exact_key("Sovos Brands Intermediate, Inc."), "sovos brands intermediate")
        self.assertEqual(exact_key("Sovos Brands Limited Partnership"), "sovos brands")
        self.assertEqual(exact_key("KKR & Co. Inc."), "kkr")
        self.assertEqual(exact_key("The Campbell's Company"), "campbells")
        self.assertEqual(exact_key("Company"), "company")  # never empties a name

    def test_family_key_also_drops_holding_words(self):
        self.assertEqual(family_key("Sovos Brands Intermediate, Inc."), "sovos brands")
        self.assertEqual(family_key("Noosa Holdco, L.P."), "noosa")
        self.assertEqual(family_key("Noosa Holdings, Inc."), "noosa")
        self.assertEqual(family_key("Inspire Brands"), "inspire brands")

    def test_adviser_core_matches_firm_and_its_management_company(self):
        self.assertEqual(adviser_core("Roark Capital Management, LLC"), "roark")
        self.assertEqual(adviser_core("Roark Capital Group"), "roark")
        self.assertEqual(adviser_core("BLACKSTONE MANAGEMENT PARTNERS L.L.C."), "blackstone")
        self.assertEqual(adviser_core("Blackstone Inc."), "blackstone")
        self.assertEqual(adviser_core("Advent International, L.P."), "advent international")

    def test_refs_slugs_and_titles(self):
        self.assertEqual(name_ref("RAO'S HOMEMADE"), "name:raos homemade")
        self.assertEqual(slugify("Jersey Mike's Subs"), "jersey-mikes-subs")
        self.assertEqual(smart_title("RAO'S HOMEMADE"), "Rao's Homemade")
        self.assertEqual(smart_title("ROARK CAPITAL PARTNERS VI (T) LP"), "Roark Capital Partners VI (T) LP")
        self.assertEqual(smart_title("Sovos Brands"), "Sovos Brands")

    def test_website_domain(self):
        self.assertEqual(website_domain("HTTP://WWW.ROARKCAPITAL.COM"), "roarkcapital.com")
        self.assertEqual(website_domain("{{URL|https://www.subway.com/en-us|subway.com}}"), "subway.com")
        self.assertEqual(website_domain("https://blackstone.podbean.com/"), "podbean.com")
        self.assertEqual(website_domain("https://www.bbc.co.uk/news"), "bbc.co.uk")
        self.assertEqual(website_domain(""), "")


class Dates(unittest.TestCase):
    def test_partial_dates_pad_to_the_widest_meaning(self):
        self.assertEqual(pad_start("2018"), "2018-01-01")
        self.assertEqual(pad_start("2018-03"), "2018-03-01")
        self.assertEqual(pad_end("2018"), "2018-12-31")
        self.assertEqual(pad_end("2018-03"), "2018-03-31")
        self.assertEqual(pad_start(None), "")
        self.assertEqual(year_of("2024-03-19"), 2024)
        self.assertIsNone(year_of(None))


class ClaimKeys(unittest.TestCase):
    def test_key_ignores_dates_but_deals_keep_their_record(self):
        a = Claim(source="wikipedia", subject="Q1", relation="controlled_by", object="Q2", start="2018")
        b = Claim(source="wikipedia", subject="Q1", relation="controlled_by", object="Q2", start="2019")
        self.assertEqual(a.key, b.key)
        d1 = Claim(source="ftc", subject="name:x", relation="deal", object="name:y", source_record="1")
        d2 = Claim(source="ftc", subject="name:x", relation="deal", object="name:y", source_record="2")
        self.assertNotEqual(d1.key, d2.key)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run it to verify it fails**

Run: `python3 -m unittest tests.test_model -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'pipeline.model'`

- [ ] **Step 4: Write the implementation**

`pipeline/model.py`:

```python
"""Records and name keys shared by every pipeline stage."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field

CONTROL_RELATIONS = ("brand_of", "controlled_by", "fund_of")
RELATIONS = CONTROL_RELATIONS + ("minority_stake", "deal")
OWNER_KINDS = ("pe_firm", "investment_firm", "public_company", "private_company")
# Wikipedia, its page history, and Wikidata come from one editing community,
# so agreement among them counts as a single source.
SOURCE_GROUPS = {"wikipedia": "wiki", "wikipedia_history": "wiki", "wikidata": "wiki"}
# Which source's spelling of a name wins when records merge.
SOURCE_PRIORITY = ("wikipedia", "wikidata", "nsi", "sec_ex21", "adv", "ftc", "usda", "wikipedia_history", "stub")
SOCIAL_DOMAINS = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com", "youtu.be",
    "tiktok.com", "threads.net", "pinterest.com", "podbean.com", "soundcloud.com", "spotify.com", "spoti.fi",
    "apple.co", "apple.com", "qq.com", "medium.com", "bit.ly", "linktr.ee", "glassdoor.com", "crunchbase.com",
    "wikipedia.org", "google.com", "sec.gov", "vimeo.com", "substack.com",
}

_LEGAL_ONE = {"inc", "incorporated", "llc", "lp", "llp", "lllp", "pllc", "co", "corp", "corporation", "company",
              "ltd", "limited", "plc", "sa", "ag", "nv", "bv", "gmbh", "sarl"}
_LEGAL_TWO = {("limited", "partnership"), ("and", "co"), ("and", "company")}
_HOLDING_WORDS = {"holdings", "holding", "intermediate", "midco", "topco", "holdco", "parent", "acquisition",
                  "acquisitions", "buyer", "opco", "group"}
_ADVISER_WORDS = {"management", "partners", "group", "holdings", "capital", "advisors", "advisers"}
_UPPER_WORDS = {"llc", "lp", "llp", "lllp", "plc", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi",
                "xii", "usa", "us", "uk"}


def normalize(value: str | None) -> str:
    """Lowercase ASCII words: "Rao's Homemade, L.L.C." -> "raos homemade llc"."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"[’'`]", "", text)
    text = re.sub(r"\b([a-z])\.", r"\1", text)
    text = text.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _strip_legal(tokens: list[str]) -> list[str]:
    if len(tokens) > 1 and tokens[0] == "the":
        tokens = tokens[1:]
    while len(tokens) > 1:
        if len(tokens) > 2 and tuple(tokens[-2:]) in _LEGAL_TWO:
            tokens = tokens[:-2]
        elif tokens[-1] in _LEGAL_ONE:
            tokens = tokens[:-1]
        else:
            break
    return tokens


def _reduce(name: str | None, words: set[str]) -> str:
    tokens = _strip_legal(normalize(name).split())
    while len(tokens) > 1 and tokens[-1] in words:
        tokens = _strip_legal(tokens[:-1])
    return " ".join(tokens)


def exact_key(name: str | None) -> str:
    """Name without legal-form words: "Sovos Brands Intermediate, Inc." -> "sovos brands intermediate"."""
    return " ".join(_strip_legal(normalize(name).split()))


def family_key(name: str | None) -> str:
    """Corporate family: also drops holding-structure words -> "sovos brands"."""
    return _reduce(name, _HOLDING_WORDS)


def adviser_core(name: str | None) -> str:
    """Investment-firm core: "Roark Capital Management, LLC" and "Roark Capital Group" -> "roark"."""
    return _reduce(name, _ADVISER_WORDS)


def name_ref(name: str) -> str:
    """Reference for an entity known only by its name."""
    return "name:" + normalize(name)


def slugify(name: str) -> str:
    return normalize(name).replace(" ", "-") or "entity"


def smart_title(name: str) -> str:
    """Title-case ALL-CAPS names ("RAO'S HOMEMADE" -> "Rao's Homemade"); leave mixed case alone."""
    if not name or name != name.upper():
        return name
    def fix(match: re.Match) -> str:
        word = match.group(0)
        return word.upper() if word in _UPPER_WORDS else word.capitalize()
    return re.sub(r"[a-z0-9]+(?:'[a-z]+)?", fix, name.lower())


def website_domain(value: str | None) -> str:
    """Registrable domain of a URL or bare host: "HTTP://WWW.ROARKCAPITAL.COM" -> "roarkcapital.com"."""
    match = re.search(r"(?:https?://)?(?:www\d?\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)", (value or "").lower())
    if not match:
        return ""
    labels = match.group(1).split(".")
    keep = 3 if len(labels) >= 3 and labels[-2] in {"co", "com", "org", "net"} and len(labels[-1]) == 2 else 2
    return ".".join(labels[-keep:])


def pad_start(value: str | None) -> str:
    """Earliest day a partial date can mean: "2018" -> "2018-01-01"."""
    if not value:
        return ""
    return value[:10] if len(value) >= 10 else value + "-01-01"[len(value) - 4:]


def pad_end(value: str | None) -> str:
    """Latest day a partial date can mean: "2018" -> "2018-12-31"."""
    if not value:
        return ""
    return value[:10] if len(value) >= 10 else value + "-12-31"[len(value) - 4:]


def year_of(value: str | None) -> int | None:
    return int(value[:4]) if value and value[:4].isdigit() else None


@dataclass
class Entity:
    id: str
    kind: str  # brand | company | adviser | fund
    name: str
    source: str
    aliases: list[str] = field(default_factory=list)
    ids: dict[str, str] = field(default_factory=dict)
    category: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Claim:
    source: str
    subject: str
    relation: str
    object: str
    start: str | None = None
    end: str | None = None
    source_url: str = ""
    source_record: str = ""
    excerpt: str = ""
    official: bool = False
    observed: bool = False
    first_seen: str = ""
    last_seen: str = ""
    status: str = "active"
    via_family: bool = False

    @property
    def key(self) -> str:
        extra = self.source_record if self.relation == "deal" else ""
        raw = "|".join((self.source, self.subject, self.relation, self.object, extra))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Classification:
    entity: str
    kind: str
    source: str
    evidence: str
    source_url: str = ""
    official: bool = False

    @property
    def key(self) -> str:
        return f"{self.source}|{self.entity}|{self.kind}"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CollectorResult:
    entities: list[Entity] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    classifications: list[Classification] = field(default_factory=list)
    # None: a full refresh, so anything this source no longer asserts is retracted.
    # A set of source_url values: only claims from those pages may be retracted.
    scope: set[str] | None = None
    progress: dict | None = None  # collector state to persist (cursors, versions)
    unchanged: bool = False  # no new release: keep every stored record as-is


def chunks(items, size: int):
    items = list(items)
    for start in range(0, len(items), size):
        yield items[start:start + size]
```

`pipeline/config.py`:

```python
"""Settings shared by the pipeline: identification, schedules, and where downloads are cached."""

from __future__ import annotations

import os
from pathlib import Path

REPO_URL = "https://github.com/d-pap/pe-checker"
USER_AGENT = f"PECheckerBot/1.0 (+{REPO_URL})"

# Days between successful runs of each source.
CADENCE_DAYS = {"nsi": 7, "wikipedia": 1, "wikidata": 7, "adv": 30, "ftc": 1, "usda": 30, "sec_ex21": 7,
                "wikipedia_history": 1}


def sec_user_agent(email: str) -> str:
    """The SEC asks automated clients to identify themselves as "Name contact@email"."""
    return f"PECheckerBot/1.0 {email}"


def cache_dir() -> Path:
    return Path(os.environ.get("PE_CACHE_DIR", ".cache"))
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_model -v`
Expected: 8 tests, OK

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore package.json pipeline tests
git commit -m "Add pipeline skeleton, records, and name keys"
```

---

### Task 2: State store (NDJSON on the data branch)

**Files:**
- Create: `pipeline/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `Claim`, `Classification`, `CollectorResult`, `Entity` from Task 1.
- Produces: `Store(root)` with:
  - `.load() -> Store`
  - `.apply(source, result, run_date)`
  - `.mark(source, run_date, ok, error="")`
  - `.all_claims()`, `.all_entities()`, `.all_classifications()`
  - `.save()`
  - attributes `claims`, `entities`, `classifications` (each `source -> key -> record`), `sources`, `progress`, `slugs`, `tiers` (`slug -> tier`), and `changes` (`date -> list`)
  - module constant `MAX_FILE_BYTES`
- Retraction rules:
  - `scope=None` means full refresh: everything not re-asserted is retracted.
  - `scope=set_of_urls` retracts only claims whose `source_url` is in the set. `set()` means append-only.
  - `unchanged=True` touches nothing except progress.

- [ ] **Step 1: Write the failing test**

`tests/test_store.py`:

```python
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import store as store_module
from pipeline.model import Claim, Classification, CollectorResult, Entity
from pipeline.store import Store


def claim(obj="Q2", url="https://a", source="wikipedia"):
    return Claim(source=source, subject="Q1", relation="controlled_by", object=obj, source_url=url)


class Apply(unittest.TestCase):
    def setUp(self):
        self.store = Store(Path(tempfile.mkdtemp()))

    def test_new_claims_get_first_and_last_seen(self):
        self.store.apply("wikipedia", CollectorResult(claims=[claim()]), "2026-10-05")
        stored = next(iter(self.store.claims["wikipedia"].values()))
        self.assertEqual((stored.first_seen, stored.last_seen, stored.status), ("2026-10-05", "2026-10-05", "active"))

    def test_full_refresh_retracts_missing_claims_but_keeps_them(self):
        self.store.apply("wikipedia", CollectorResult(claims=[claim("Q2"), claim("Q3")]), "2026-10-05")
        self.store.apply("wikipedia", CollectorResult(claims=[claim("Q2")]), "2026-10-06")
        statuses = {c.object: (c.status, c.first_seen, c.last_seen) for c in self.store.claims["wikipedia"].values()}
        self.assertEqual(statuses["Q2"], ("active", "2026-10-05", "2026-10-06"))
        self.assertEqual(statuses["Q3"], ("retracted", "2026-10-05", "2026-10-05"))

    def test_scoped_refresh_only_retracts_claims_from_rechecked_pages(self):
        self.store.apply("wikipedia", CollectorResult(claims=[claim("Q2", "https://a"), claim("Q3", "https://b")]), "2026-10-05")
        self.store.apply("wikipedia", CollectorResult(claims=[], scope={"https://a"}), "2026-10-06")
        statuses = {c.object: c.status for c in self.store.claims["wikipedia"].values()}
        self.assertEqual(statuses, {"Q2": "retracted", "Q3": "active"})

    def test_append_only_never_retracts(self):
        self.store.apply("ftc", CollectorResult(claims=[claim(source="ftc")], scope=set()), "2026-10-05")
        self.store.apply("ftc", CollectorResult(claims=[], scope=set()), "2026-10-06")
        self.assertEqual(next(iter(self.store.claims["ftc"].values())).status, "active")

    def test_reasserted_claim_reactivates(self):
        self.store.apply("wikipedia", CollectorResult(claims=[claim()]), "2026-10-05")
        self.store.apply("wikipedia", CollectorResult(claims=[]), "2026-10-06")
        self.store.apply("wikipedia", CollectorResult(claims=[claim()]), "2026-10-07")
        stored = next(iter(self.store.claims["wikipedia"].values()))
        self.assertEqual((stored.status, stored.first_seen), ("active", "2026-10-05"))

    def test_unchanged_keeps_everything_and_saves_progress(self):
        self.store.apply("usda", CollectorResult(claims=[claim(source="usda")], entities=[Entity("Q1", "brand", "A", "usda")]), "2026-10-05")
        self.store.apply("usda", CollectorResult(unchanged=True, progress={"release": "x"}), "2026-10-06")
        self.assertEqual(len(self.store.entities["usda"]), 1)
        self.assertEqual(next(iter(self.store.claims["usda"].values())).last_seen, "2026-10-05")
        self.assertEqual(self.store.progress["usda"], {"release": "x"})

    def test_scoped_refresh_drops_classifications_a_page_no_longer_makes(self):
        kind = Classification(entity="Q1", kind="pe_firm", source="wikipedia", evidence="x", source_url="https://a")
        self.store.apply("wikipedia", CollectorResult(classifications=[kind]), "2026-10-05")
        self.store.apply("wikipedia", CollectorResult(scope={"https://a"}), "2026-10-06")
        self.assertEqual(self.store.classifications["wikipedia"], {})

    def test_mark_counts_active_claims_and_keeps_last_success_on_failure(self):
        self.store.apply("wikipedia", CollectorResult(claims=[claim()]), "2026-10-05")
        self.store.mark("wikipedia", "2026-10-05", ok=True)
        self.store.mark("wikipedia", "2026-10-06", ok=False, error="HTTP 503")
        meta = self.store.sources["wikipedia"]
        self.assertEqual((meta["last_success"], meta["last_attempt"], meta["error"], meta["active_claims"]),
                         ("2026-10-05", "2026-10-06", "HTTP 503", 1))


class Persistence(unittest.TestCase):
    def test_round_trip_is_sorted_and_lossless(self):
        root = Path(tempfile.mkdtemp())
        first = Store(root)
        first.apply("wikipedia", CollectorResult(claims=[claim("Q3"), claim("Q2")], entities=[Entity("Q1", "company", "A", "wikipedia")],
                                                 classifications=[Classification("Q2", "pe_firm", "wikipedia", "x")]), "2026-10-05")
        first.slugs = {"Q1": "a"}
        first.changes["2026-10-05"] = [{"slug": "a"}]
        first.save()
        written = (root / "claims" / "wikipedia.ndjson").read_bytes()
        second = Store(root).load()
        by_key = lambda claims: sorted(claims, key=lambda c: c.key)
        self.assertEqual(by_key(second.all_claims()), by_key(first.all_claims()))
        self.assertEqual(second.all_entities(), first.all_entities())
        second.save()
        self.assertEqual((root / "claims" / "wikipedia.ndjson").read_bytes(), written)  # stable bytes, readable diffs
        self.assertEqual(second.slugs, {"Q1": "a"})
        self.assertTrue((root / "changes" / "2026-10-05.json").exists())

    def test_refuses_files_github_would_reject(self):
        store = Store(Path(tempfile.mkdtemp()))
        store.apply("wikipedia", CollectorResult(claims=[claim()]), "2026-10-05")
        with mock.patch.object(store_module, "MAX_FILE_BYTES", 10):
            with self.assertRaises(ValueError):
                store.save()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_store -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'pipeline.store'`

- [ ] **Step 3: Write the implementation**

`pipeline/store.py`:

```python
"""Persistent graph state: sorted NDJSON files on the `data` branch."""

from __future__ import annotations

import json
from pathlib import Path

from .model import Claim, Classification, CollectorResult, Entity

# GitHub rejects files over 100 MB.
MAX_FILE_BYTES = 95 * 1024 * 1024
_JSON_FILES = ("sources", "progress", "slugs", "tiers")


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.claims: dict[str, dict[str, Claim]] = {}  # source -> claim key -> claim
        self.entities: dict[str, dict[str, Entity]] = {}  # source -> entity id -> entity
        self.classifications: dict[str, dict[str, Classification]] = {}
        self.sources: dict[str, dict] = {}  # source -> last_success, last_attempt, error, active_claims
        self.progress: dict[str, dict] = {}  # source -> collector cursors and versions
        self.slugs: dict[str, str] = {}  # entity id -> published slug (never reassigned)
        self.tiers: dict[str, str] = {}  # slug -> tier at the last publish
        self.changes: dict[str, list] = {}  # run date -> tier changes, written by save()

    def load(self) -> "Store":
        for folder, target, cls in (("claims", self.claims, Claim), ("entities", self.entities, Entity),
                                    ("classifications", self.classifications, Classification)):
            for path in sorted((self.root / folder).glob("*.ndjson")):
                records = target.setdefault(path.stem, {})
                with path.open(encoding="utf-8") as handle:
                    for line in handle:
                        if line.strip():
                            record = cls(**json.loads(line))
                            records[record.id if cls is Entity else record.key] = record
        for name in _JSON_FILES:
            path = self.root / f"{name}.json"
            if path.exists():
                setattr(self, name, json.loads(path.read_text(encoding="utf-8")))
        return self

    def apply(self, source: str, result: CollectorResult, run_date: str) -> None:
        """Fold one collector run into the stored state; never deletes a claim."""
        if result.progress is not None:
            self.progress[source] = result.progress
        if result.unchanged:
            return
        stored = self.claims.setdefault(source, {})
        fresh = {claim.key: claim for claim in result.claims}
        for key, claim in fresh.items():
            previous = stored.get(key)
            claim.first_seen = previous.first_seen if previous else run_date
            claim.last_seen = run_date
            claim.status = "active"
            stored[key] = claim
        for key, claim in stored.items():
            if key not in fresh and claim.status == "active":
                if result.scope is None or claim.source_url in result.scope:
                    claim.status = "retracted"
        entities = self.entities.setdefault(source, {})
        classifications = self.classifications.setdefault(source, {})
        if result.scope is None:
            entities.clear()
            classifications.clear()
        else:
            emitted = {c.key for c in result.classifications}
            for key in [k for k, c in classifications.items() if c.source_url in result.scope and k not in emitted]:
                del classifications[key]
        for entity in result.entities:
            entities[entity.id] = entity
        for classification in result.classifications:
            classifications[classification.key] = classification

    def mark(self, source: str, run_date: str, ok: bool, error: str = "") -> None:
        meta = self.sources.setdefault(source, {})
        meta["last_attempt"] = run_date
        if ok:
            meta["last_success"] = run_date
            meta["error"] = ""
        else:
            meta["error"] = error[:500]
        meta["active_claims"] = sum(1 for c in self.claims.get(source, {}).values() if c.status == "active")

    def all_claims(self) -> list[Claim]:
        return [c for records in self.claims.values() for c in records.values()]

    def all_entities(self) -> list[Entity]:
        return [e for records in self.entities.values() for e in records.values()]

    def all_classifications(self) -> list[Classification]:
        return [c for records in self.classifications.values() for c in records.values()]

    def save(self) -> None:
        for folder, data in (("claims", self.claims), ("entities", self.entities),
                             ("classifications", self.classifications)):
            directory = self.root / folder
            directory.mkdir(parents=True, exist_ok=True)
            for source, records in data.items():
                lines = [json.dumps(records[key].to_dict(), sort_keys=True, ensure_ascii=False) for key in sorted(records)]
                payload = "".join(line + "\n" for line in lines)
                if len(payload.encode("utf-8")) > MAX_FILE_BYTES:
                    raise ValueError(f"{folder}/{source}.ndjson would exceed GitHub's 100 MB file limit")
                (directory / f"{source}.ndjson").write_text(payload, encoding="utf-8")
        for name in _JSON_FILES:
            (self.root / f"{name}.json").write_text(
                json.dumps(getattr(self, name), sort_keys=True, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        for run_date, changes in self.changes.items():
            directory = self.root / "changes"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{run_date}.json").write_text(json.dumps(changes, indent=1, ensure_ascii=False) + "\n",
                                                        encoding="utf-8")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_store -v`
Expected: 10 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/store.py tests/test_store.py
git commit -m "Add NDJSON state store that retracts but never deletes claims"
```

---

### Task 3: Polite HTTP fetcher

**Files:**
- Create: `pipeline/http.py`
- Test: `tests/test_http.py`

**Interfaces:**
- Produces: `Fetcher(user_agent, min_interval=0.25, max_retries=4, opener=None, sleep=time.sleep, clock=time.monotonic)`.
  - `.open(url, params=None, headers=None, timeout=60)` returns a response the caller closes.
  - `.get(...) -> bytes`
  - `.get_json(...) -> object`
  - `.requests` counter
  - `FetchError` for failures
- Behavior:
  - Retries 429/5xx and network errors, honoring `Retry-After`.
  - `get_json` retries a MediaWiki `maxlag` error and raises on any other API `error` object.
  - Errors never include the query string.

- [ ] **Step 1: Write the failing test**

`tests/test_http.py`:

```python
import io
import json
import unittest
import urllib.error

from pipeline.http import FetchError, Fetcher


class Clock:
    def __init__(self):
        self.now = 0.0
        self.slept = []

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds

    def time(self):
        return self.now


def fetcher_with(responses, clock=None):
    clock = clock or Clock()
    seen = []

    def opener(request, timeout):
        seen.append(request)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return io.BytesIO(item)

    fetcher = Fetcher("TestBot/1.0 (+https://example.org)", min_interval=1.0, opener=opener, sleep=clock.sleep, clock=clock.time)
    return fetcher, seen, clock


def http_error(code, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError("https://x.test/a?api_key=SECRET", code, "error", headers, None)


class FetcherTests(unittest.TestCase):
    def test_sends_user_agent_and_encodes_params(self):
        fetcher, seen, _ = fetcher_with([b"ok"])
        self.assertEqual(fetcher.get("https://x.test/a", {"q": "a b"}), b"ok")
        self.assertEqual(seen[0].full_url, "https://x.test/a?q=a+b")
        self.assertEqual(seen[0].get_header("User-agent"), "TestBot/1.0 (+https://example.org)")

    def test_paces_requests(self):
        fetcher, _, clock = fetcher_with([b"1", b"2"])
        fetcher.get("https://x.test/a")
        fetcher.get("https://x.test/b")
        self.assertEqual(clock.slept, [1.0])

    def test_retries_429_honoring_retry_after(self):
        fetcher, seen, clock = fetcher_with([http_error(429, "7"), b"ok"])
        self.assertEqual(fetcher.get("https://x.test/a"), b"ok")
        self.assertIn(7.0, clock.slept)
        self.assertEqual(len(seen), 2)

    def test_gives_up_without_leaking_the_query_string(self):
        fetcher, _, _ = fetcher_with([http_error(404)])
        with self.assertRaises(FetchError) as caught:
            fetcher.get("https://x.test/a", {"api_key": "SECRET"})
        self.assertNotIn("SECRET", str(caught.exception))

    def test_maxlag_is_retried_then_raises(self):
        lagged = json.dumps({"error": {"code": "maxlag", "info": "lagged"}}).encode()
        fetcher, _, _ = fetcher_with([lagged, json.dumps({"query": {}}).encode()])
        self.assertEqual(fetcher.get_json("https://x.test/api"), {"query": {}})
        fetcher, _, _ = fetcher_with([lagged] * 5)
        with self.assertRaises(FetchError):
            fetcher.get_json("https://x.test/api")

    def test_other_api_errors_raise_instead_of_looking_empty(self):
        fetcher, _, _ = fetcher_with([json.dumps({"error": {"code": "badvalue", "info": "nope"}}).encode()])
        with self.assertRaises(FetchError):
            fetcher.get_json("https://x.test/api")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_http -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'pipeline.http'`

- [ ] **Step 3: Write the implementation**

`pipeline/http.py`:

```python
"""Polite HTTP: an identified User-Agent, pacing between requests, and retries with backoff."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

RETRY_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


class Fetcher:
    def __init__(self, user_agent: str, min_interval: float = 0.25, max_retries: int = 4,
                 opener=None, sleep=time.sleep, clock=time.monotonic):
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._open = opener or (lambda request, timeout: urllib.request.urlopen(request, timeout=timeout))
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None
        self.requests = 0

    def _pace(self) -> None:
        if self._last is not None:
            wait = self.min_interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()

    def open(self, url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 60):
        """Open a response (caller closes it). Retries 429/5xx and network errors."""
        if params:
            url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
        request_headers = {"User-Agent": self.user_agent, "Accept-Encoding": "identity", **(headers or {})}
        shown = url.split("?")[0]  # never echo query strings (they can carry keys) into errors
        for attempt in range(self.max_retries + 1):
            self._pace()
            self.requests += 1
            try:
                return self._open(urllib.request.Request(url, headers=request_headers), timeout)
            except urllib.error.HTTPError as error:
                if error.code not in RETRY_STATUS or attempt == self.max_retries:
                    raise FetchError(f"HTTP {error.code} from {shown}") from None
                self._sleep(self._retry_after(error.headers, attempt))
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                if attempt == self.max_retries:
                    raise FetchError(f"{type(error).__name__} from {shown}") from None
                self._sleep(2 ** attempt)
        raise FetchError(f"gave up on {shown}")

    @staticmethod
    def _retry_after(headers, attempt: int) -> float:
        try:
            return min(float(headers.get("Retry-After")), 300.0)
        except (AttributeError, TypeError, ValueError):
            return float(2 ** attempt)

    def get(self, url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 60) -> bytes:
        with self.open(url, params, headers, timeout) as response:
            return response.read()

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 60):
        """GET and decode JSON, waiting and retrying when MediaWiki reports replication lag."""
        for attempt in range(self.max_retries + 1):
            data = json.loads(self.get(url, params, headers, timeout))
            error = data.get("error") if isinstance(data, dict) else None
            if not isinstance(error, dict):
                return data
            if error.get("code") != "maxlag" or attempt == self.max_retries:
                raise FetchError(f"API error {error.get('code')} from {url.split('?')[0]}: {str(error.get('info', ''))[:200]}")
            self._sleep(5.0 * (attempt + 1))
        raise FetchError(f"gave up on {url.split('?')[0]}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_http -v`
Expected: 6 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/http.py tests/test_http.py
git commit -m "Add paced, retrying fetcher that keeps secrets out of errors"
```

---

### Task 4: Infobox parsing

**Files:**
- Create: `pipeline/collectors/wikitext.py`
- Test: `tests/test_wikitext.py`

**Interfaces:**
- Produces:
  - `page_facts(wikitext) -> PageFacts(fields: dict, short_description: str, template: str)`
  - `parse_owners(value) -> list[OwnerRef(target, text, start, end, percent)]`
  - `parse_names(value) -> list[(target|None, text)]`
  - `parse_tickers(value) -> ["NYSE: BX", ...]`
  - `classify_page(facts) -> list[kind]`, with the most specific first
  - `is_person(facts) -> bool`
  - `plain(value) -> str`

- [ ] **Step 1: Write the failing test**

The fixtures are real lead sections Wikipedia served on 2026-10-05, trimmed to the fields we read. The last class pins Review Focus #5.

`tests/test_wikitext.py`:

```python
import unittest

from pipeline.collectors.wikitext import classify_page, is_person, page_facts, parse_names, parse_owners, parse_tickers

# Lead sections as Wikipedia served them on 2026-10-05 (trimmed to the fields we read).
SOVOS = """{{Short description|American food company}}
{{Infobox company
| name = Sovos Brands
| type = [[Subsidiary]]
| brands = {{ubl|Rao's Homemade|Michael Angelo's|Noosa Yoghurt|Birch Benders}}
| owner =
| parent = {{ubl|[[Campbell Soup Company|Campbell's]] {{smaller|(2024–present)}}}}
| website = {{url|thecampbellscompany.com/}}
| industry = [[Food processing]]
}}"""
ROARK = """{{Short description|American private equity firm}}
{{Infobox company
| type = [[Privately held company|Private]]
| industry = [[Private equity]]
| website = {{URL|https://roarkcapital.com}}
}}"""
BLACKSTONE = """{{Short description|American alternative investment company}}
{{Infobox company
| type = [[Public company|Public]]
| traded_as = {{unbulleted list|{{NYSE|BX}}|[[S&P 500]] component}}
| industry = [[Financial services]]
| products = {{Unbulleted list|[[Alternative investment]]|[[Private equity]]}}
}}"""
JPMORGAN = """{{Short description|American multinational bank}}
{{Infobox company
| type = [[Public company|Public]]
| traded_as = {{NYSE|JPM}}
| industry = [[Financial services]]
| products = {{hlist|[[Asset management]]|[[Private equity]]}}
}}"""


class Owners(unittest.TestCase):
    def test_link_target_text_and_date_range(self):
        [ref] = parse_owners("[[Inspire Brands]] (2018–present)")
        self.assertEqual((ref.target, ref.text, ref.start, ref.end), ("Inspire Brands", "Inspire Brands", "2018", None))

    def test_piped_redirect_link_inside_list_and_smaller_template(self):
        [ref] = parse_owners(page_facts(SOVOS).fields["parent"])
        self.assertEqual((ref.target, ref.text, ref.start, ref.end), ("Campbell Soup Company", "Campbell's", "2024", None))

    def test_former_and_current_owners_on_separate_lines(self):
        former, current = parse_owners("Advent International (2017–2024)<br>[[Campbell's]] (2024–present)")
        self.assertEqual((former.target, former.text, former.start, former.end), (None, "Advent International", "2017", "2024"))
        self.assertEqual((current.target, current.start, current.end), ("Campbell's", "2024", None))

    def test_two_links_on_one_line_with_percentages(self):
        a, b = parse_owners("[[A Corp]] (60%), [[B Fund]] (40%)")
        self.assertEqual((a.target, a.percent, b.target, b.percent), ("A Corp", 60.0, "B Fund", 40.0))

    def test_refs_comments_and_since(self):
        refs = parse_owners("{{plainlist|\n* [[Inspire Brands]] {{small|(since 2018)}}<ref>cite</ref>\n* <!-- x -->[[Roark]]\n}}")
        self.assertEqual([(r.target, r.start) for r in refs], [("Inspire Brands", "2018"), ("Roark", None)])

    def test_text_that_names_no_owner_is_ignored(self):
        self.assertEqual(parse_owners("Independent business"), [])
        self.assertEqual(parse_owners("The Cancro family"), [])
        self.assertEqual(parse_owners(""), [])


class Facts(unittest.TestCase):
    def test_brand_list_and_tickers(self):
        facts = page_facts(SOVOS)
        self.assertEqual(parse_names(facts.fields["brands"])[0], (None, "Rao's Homemade"))
        self.assertEqual(parse_tickers(page_facts(BLACKSTONE).fields["traded_as"]), ["NYSE: BX"])
        self.assertEqual(facts.short_description, "American food company")

    def test_classification_reads_description_and_industry_not_products(self):
        self.assertEqual(classify_page(page_facts(ROARK)), ["pe_firm", "private_company"])
        self.assertEqual(classify_page(page_facts(BLACKSTONE)), ["investment_firm", "public_company"])
        self.assertEqual(classify_page(page_facts(JPMORGAN)), ["public_company"])  # "Private equity" in products is not enough
        self.assertEqual(classify_page(page_facts(SOVOS)), ["private_company"])


class OtherTemplates(unittest.TestCase):
    def test_any_infobox_template_is_read(self):
        facts = page_facts("{{Infobox restaurant chain\n| owner = [[Inspire Brands]]\n}}")
        self.assertEqual((facts.template, parse_owners(facts.fields["owner"])[0].target), ("infobox restaurant chain", "Inspire Brands"))

    def test_people_are_recognized(self):
        self.assertTrue(is_person(page_facts("{{Short description|American businessman (born 1957)}}\n{{Infobox person\n| name = X\n}}")))
        self.assertTrue(is_person(page_facts("{{Short description|American entrepreneur}}")))
        self.assertFalse(is_person(page_facts("{{Short description|American family restaurant chain}}\n{{Infobox company\n}}")))
        self.assertFalse(is_person(page_facts("{{Short description|American family restaurant chain}}\n{{Infobox restaurant\n}}")))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_wikitext -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'pipeline.collectors.wikitext'`

- [ ] **Step 3: Write the implementation**

`pipeline/collectors/wikitext.py`:

```python
"""Read company facts out of Wikipedia wikitext (infobox fields and short description)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import mwparserfromhell as mwp

LIST_TEMPLATES = {"ubl", "unbulleted list", "ublist", "plainlist", "plain list", "flatlist", "flat list", "hlist",
                  "bulleted list", "collapsible list"}
FORMAT_TEMPLATES = {"smaller", "small", "nowrap", "nobr", "resize", "noitalic"}
EXCHANGES = {"nyse": "NYSE", "nasdaq": "Nasdaq", "nyse american": "NYSE American", "nyse arca": "NYSE Arca",
             "otc pink": "OTC Pink", "otcqx": "OTCQX", "otcqb": "OTCQB", "lse": "LSE", "tsx": "TSX", "asx": "ASX",
             "euronext": "Euronext", "fwb": "FWB", "sehk": "SEHK", "tyo": "TYO"}
INVESTMENT_WORDS = ("investment firm", "investment company", "investment management", "alternative investment",
                    "hedge fund", "venture capital", "investment holding", "growth equity")

_REF = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_BR = re.compile(r"<br\s*/?>", re.I)
_RANGE = re.compile(r"(\d{4})\s*(?:[–—-]|to)\s*(present|current|\d{4})?", re.I)
_SINCE = re.compile(r"\b(?:since|from)\s+(\d{4})\b", re.I)
_SINGLE_YEAR = re.compile(r"\((\d{4})\)")
_PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
# Unlinked owner text that names no owner ("Independent business", "Founders").
_NOT_OWNERS = re.compile(r"^(?:independent|independently owned|independent business|self|none|n/?a|public|"
                         r"publicly (?:traded|held)|private(?:ly held)?|employees?|founders?|management|various|"
                         r"(?:the )?\w+ family|family[- ]owned|shareholders?|stockholders?)$", re.I)


PERSON_INFOBOXES = {"infobox person", "infobox businessperson", "infobox officeholder", "infobox chef",
                    "infobox philanthropist", "infobox royalty", "infobox family"}
_PERSON_WORDS = re.compile(r"\b(?:born|businessman|businesswoman|businessperson|entrepreneur|philanthropist|"
                           r"restaurateur)\b", re.I)


@dataclass
class PageFacts:
    fields: dict[str, str]
    short_description: str
    template: str = ""  # infobox template name, lowercased


def is_person(facts: PageFacts) -> bool:
    """People and families can own businesses, but they are not parent companies."""
    if facts.template in PERSON_INFOBOXES:
        return True
    return not facts.template.startswith("infobox company") and bool(_PERSON_WORDS.search(facts.short_description))


@dataclass
class OwnerRef:
    target: str | None  # linked article title, if the item links one
    text: str  # plain name, without a trailing "(2018–present)"
    start: str | None
    end: str | None
    percent: float | None


def _name(template) -> str:
    return str(template.name).strip().lower().replace("_", " ")


def page_facts(wikitext: str) -> PageFacts:
    fields, short, infobox_name = {}, "", ""
    for template in mwp.parse(wikitext).filter_templates(recursive=False):
        name = _name(template)
        if not infobox_name and name.startswith("infobox"):
            infobox_name = name
            fields = {str(p.name).strip().lower(): str(p.value).strip() for p in template.params}
        elif name == "short description" and template.params and not short:
            short = str(template.params[0].value).strip()
    return PageFacts(fields, short, infobox_name)


def plain(value: str | None) -> str:
    return " ".join(mwp.parse(value or "").strip_code().split())


def _unwrap(value: str) -> str:
    """Replace list and formatting templates with their contents, one line per list item."""
    for _ in range(6):
        code = mwp.parse(value)
        changed = False
        for template in code.filter_templates(recursive=False):
            if _name(template) in LIST_TEMPLATES | FORMAT_TEMPLATES:
                items = [str(p.value) for p in template.params if not p.showkey]
                code.replace(template, "\n".join(items))
                changed = True
        value = str(code)
        if not changed:
            break
    return value


def split_items(value: str) -> list[str]:
    value = _COMMENT.sub("", _REF.sub("", value or ""))
    value = _BR.sub("\n", _unwrap(value))
    items = []
    for line in value.split("\n"):
        line = line.strip().lstrip("*#").strip().strip(",;").strip()
        if line:
            items.append(line)
    return items


def _owner_ref(segment: str) -> OwnerRef | None:
    code = mwp.parse(segment)
    links = code.filter_wikilinks()
    target = str(links[0].title).split("#")[0].strip() if links else None
    if target and ":" in target and target.split(":")[0].strip().lower() in {"file", "image", "category", "wikt", "wiktionary"}:
        target = None
    text = " ".join(code.strip_code().split()).strip(" ,;")
    if not text and not target:
        return None
    start = end = None
    if match := _RANGE.search(text):
        start = match.group(1)
        last = (match.group(2) or "present").lower()
        end = None if last in {"present", "current"} else last
    elif match := _SINCE.search(text) or _SINGLE_YEAR.search(text):
        start = match.group(1)
    percent = _PERCENT.search(text)
    name = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip() or text or target
    if not target and _NOT_OWNERS.match(name):
        return None
    return OwnerRef(target or None, name, start, end, float(percent.group(1)) if percent else None)


def parse_owners(value: str) -> list[OwnerRef]:
    """Owner/parent field -> one reference per owner, with any date range and percentage."""
    refs = []
    for item in split_items(value):
        segments = [s for s in re.split(r"(?=\[\[)", item) if s.strip()]
        if len(segments) > 1 and not segments[0].lstrip().startswith("[["):
            segments = [segments[0] + segments[1], *segments[2:]]
        for segment in segments:
            if ref := _owner_ref(segment):
                refs.append(ref)
    return refs


def parse_names(value: str) -> list[tuple[str | None, str]]:
    """List field (brands, subsidiaries) -> [(linked title or None, display name)]."""
    names = []
    for item in split_items(value):
        if ref := _owner_ref(item):
            names.append((ref.target, ref.text or ref.target))
    return names


def parse_tickers(value: str) -> list[str]:
    tickers = []
    for template in mwp.parse(value or "").filter_templates(recursive=True):
        exchange = EXCHANGES.get(_name(template))
        if exchange and template.params:
            symbol = str(template.params[0].value).strip()
            if symbol:
                tickers.append(f"{exchange}: {symbol}")
    return tickers


def classify_page(facts: PageFacts) -> list[str]:
    """Owner kinds a page describes itself as, most specific first."""
    described = f"{facts.short_description} {plain(facts.fields.get('industry'))}".lower()
    kinds = []
    if "private equity" in described:
        kinds.append("pe_firm")
    elif any(word in described for word in INVESTMENT_WORDS):
        kinds.append("investment_firm")
    company_type = plain(facts.fields.get("type")).lower()
    if parse_tickers(facts.fields.get("traded_as", "")) or "public" in company_type:
        kinds.append("public_company")
    elif "private" in company_type or "subsidiary" in company_type:
        kinds.append("private_company")
    return kinds
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_wikitext -v`
Expected: 10 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/collectors/wikitext.py tests/test_wikitext.py
git commit -m "Parse ownership, brands, tickers, and kind from Wikipedia infoboxes"
```

---

### Task 5: Wikipedia collector and shared test doubles

**Files:**
- Create: `pipeline/collectors/wikipedia.py`, `tests/helpers.py`
- Test: `tests/test_wikipedia.py`

**Interfaces:**
- Consumes: `Fetcher.get_json` (Task 3), `Store` (Task 2), and the Task 4 parsers.
- Produces:
  - `collect(fetcher, store, run_date) -> CollectorResult`. A full run every 7 days has `scope=None`; incremental runs are scoped to re-read article URLs. Progress is `{"revids": {title: revid}, "full_refresh": date}`.
  - Also exported for Task 12: `API`, `OWNER_FIELDS`, `article_url(title)`, `display_name(title)`, `resolve_titles(fetcher, titles) -> {title: (canonical, qid|None)}`.
- Test helpers used by every later collector test:
  - `FakeFetcher(routes)`, with `.calls` as `[(url, params, headers)]` and `.requests`
  - `FakeResponse`
  - `url_is(prefix)`
  - `serve_ranges(bytes)`
  - `FakeWiki(pages, redirects)`
- Entity IDs: a QID when the page has one, else `wp:<title>`. Unlinked names become `name:<normalized>`.

- [ ] **Step 1: Write the test doubles**

`tests/helpers.py`:

```python
"""Test doubles shared by the collector tests: no test touches the network."""

from __future__ import annotations

import io
import json


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, headers: dict | None = None):
        super().__init__(body)
        self.headers = headers or {}


class FakeFetcher:
    """Answers get/get_json/open from (predicate, answer) routes and records every request.

    An answer is a dict/list (JSON), bytes, a FakeResponse, or a callable
    (url, params, headers) -> one of those.
    """

    def __init__(self, routes):
        self.routes = list(routes)
        self.calls: list[tuple[str, dict, dict]] = []
        self.requests = 0

    def _answer(self, url, params, headers):
        params, headers = dict(params or {}), dict(headers or {})
        self.calls.append((url, params, headers))
        self.requests += 1
        for match, answer in self.routes:
            if match(url, params, headers):
                return answer(url, params, headers) if callable(answer) else answer
        raise AssertionError(f"unexpected request: {url} {params}")

    def get_json(self, url, params=None, headers=None, timeout=60):
        answer = self._answer(url, params, headers)
        if isinstance(answer, FakeResponse):
            return json.loads(answer.read())
        return json.loads(answer) if isinstance(answer, bytes) else answer

    def get(self, url, params=None, headers=None, timeout=60):
        return self.open(url, params, headers, timeout).read()

    def open(self, url, params=None, headers=None, timeout=60):
        answer = self._answer(url, params, headers)
        if isinstance(answer, FakeResponse):
            return answer
        return FakeResponse(answer if isinstance(answer, bytes) else json.dumps(answer).encode())


def url_is(prefix: str):
    return lambda url, params, headers: url.startswith(prefix)


def serve_ranges(payload: bytes):
    """Answer HTTP Range requests ("bytes=a-b" or "bytes=-n") against an in-memory file."""
    def answer(url, params, headers):
        spec = headers.get("Range", "").removeprefix("bytes=")
        if spec.startswith("-"):
            start, end = max(0, len(payload) - int(spec[1:])), len(payload) - 1
        elif spec:
            first, last = spec.split("-")
            start, end = int(first), min(int(last), len(payload) - 1)
        else:
            start, end = 0, len(payload) - 1
        return FakeResponse(payload[start:end + 1], {"Content-Range": f"bytes {start}-{end}/{len(payload)}"})
    return answer


class FakeWiki:
    """A tiny MediaWiki API over in-memory pages: {title: {"qid", "revid", "text", "redirects"}}."""

    def __init__(self, pages: dict[str, dict], redirects: dict[str, str] | None = None):
        self.pages = pages
        self.redirects = redirects or {}

    def _page(self, title: str, params: dict) -> dict:
        page = self.pages[title]
        record = {"pageid": abs(hash(title)) % 10_000_000, "ns": 0, "title": title}
        props = params.get("prop", "")
        if "revisions" in props:
            record["revisions"] = [{"revid": page["revid"], "timestamp": "2026-10-01T00:00:00Z",
                                    "slots": {"main": {"content": page["text"]}}}]
        if "pageprops" in props and page.get("qid"):
            record["pageprops"] = {"wikibase_item": page["qid"]}
        if "info" in props:
            record["lastrevid"] = page["revid"]
        if "redirects" in props:
            record["redirects"] = [{"ns": 0, "title": t} for t in page.get("redirects", [])]
        return record

    def __call__(self, url, params, headers):
        if params.get("generator") == "embeddedin":
            titles = [t for t, p in self.pages.items() if "{{infobox company" in p["text"].lower()]
            return {"batchcomplete": True, "query": {"pages": [self._page(t, params) for t in titles]}}
        steps, pages = [], []
        for title in params.get("titles", "").split("|"):
            final = self.redirects.get(title, title)
            if final != title:
                steps.append({"from": title, "to": final})
            pages.append(self._page(final, params) if final in self.pages else {"ns": 0, "title": final, "missing": True})
        return {"batchcomplete": True, "query": {"redirects": steps, "pages": pages}}
```

- [ ] **Step 2: Write the failing test**

`test_an_owner_who_is_a_person_is_not_a_parent_company` pins Review Focus #2.

`tests/test_wikipedia.py`:

```python
import tempfile
import unittest
from pathlib import Path

from pipeline.collectors import wikipedia
from pipeline.model import Entity
from pipeline.store import Store
from tests.helpers import FakeFetcher, FakeWiki, url_is

PAGES = {
    "Buffalo Wild Wings": {"qid": "Q509255", "revid": 11, "redirects": ["BWW"], "text":
        "{{Short description|American sports bar and restaurant chain}}\n{{Infobox company\n| type = [[Subsidiary]]\n"
        "| parent = [[Inspire Brands]] (2018–present)\n| website = {{url|buffalowildwings.com}}\n}}"},
    "Inspire Brands": {"qid": "Q55074808", "revid": 12, "text":
        "{{Infobox company\n| type = [[Privately held company|Private]]\n| owner = [[Roark Capital Group]]\n"
        "| subsidiaries = {{ubl|[[Arby's]]|[[Buffalo Wild Wings]]}}\n}}"},
    "Roark Capital Group": {"qid": "Q7339900", "revid": 13, "text":
        "{{Short description|American private equity firm}}\n{{Infobox company\n| industry = [[Private equity]]\n"
        "| website = {{URL|https://roarkcapital.com}}\n}}"},
    "Sovos Brands": {"qid": "Q121775110", "revid": 14, "text":
        "{{Infobox company\n| brands = {{ubl|Rao's Homemade|Noosa Yoghurt}}\n"
        "| parent = {{ubl|[[Campbell Soup Company|Campbell's]] {{smaller|(2024–present)}}}}\n}}"},
    # Linked from Sovos through a redirect; uses a different infobox, so the bulk pass misses it.
    "Campbell's": {"qid": "Q1030544", "revid": 15, "text": "{{Infobox dummy\n| traded_as = {{Nasdaq|CPB}}\n}}"},
    "Arby's": {"qid": "Q630866", "revid": 16, "text": "{{Infobox dummy\n| type = Subsidiary\n}}"},
    "Jersey Mike's Subs": {"qid": "Q6184897", "revid": 17, "text": "{{Infobox company\n| owner = [[Peter Cancro]]\n}}"},
    "Peter Cancro": {"qid": "Q7175091", "revid": 18, "text":
        "{{Short description|American businessman (born 1957)}}\n{{Infobox person\n| name = Peter Cancro\n}}"},
}


def wiki_fetcher(pages=PAGES):
    return FakeFetcher([(url_is(wikipedia.API), FakeWiki(pages, {"Campbell Soup Company": "Campbell's"}))])


def empty_store():
    return Store(Path(tempfile.mkdtemp()))


class FullRun(unittest.TestCase):
    def setUp(self):
        self.result = wikipedia.collect(wiki_fetcher(), empty_store(), "2026-10-05")
        self.links = {(c.subject, c.relation, c.object, c.start) for c in self.result.claims}
        self.entities = {e.id: e for e in self.result.entities}

    def test_parent_owner_and_dates(self):
        self.assertIn(("Q509255", "controlled_by", "Q55074808", "2018"), self.links)
        self.assertIn(("Q55074808", "controlled_by", "Q7339900", None), self.links)

    def test_redirected_link_resolves_to_the_canonical_page_and_its_qid(self):
        self.assertIn(("Q121775110", "controlled_by", "Q1030544", "2024"), self.links)
        self.assertIn("Campbell Soup Company", self.entities["Q1030544"].aliases + [self.entities["Q1030544"].name])

    def test_brands_and_subsidiaries_point_up_to_the_page(self):
        self.assertIn(("name:raos homemade", "brand_of", "Q121775110", None), self.links)
        self.assertIn(("Q630866", "controlled_by", "Q55074808", None), self.links)
        self.assertEqual(self.entities["name:raos homemade"].kind, "brand")

    def test_page_entity_identity_and_classification(self):
        bww = self.entities["Q509255"]
        self.assertEqual(bww.ids["website_domain"], "buffalowildwings.com")
        self.assertIn("BWW", bww.aliases)
        kinds = {(k.entity, k.kind) for k in self.result.classifications}
        self.assertIn(("Q7339900", "pe_firm"), kinds)
        self.assertIn(("Q1030544", "public_company"), kinds)  # fetched as a linked parent

    def test_an_owner_who_is_a_person_is_not_a_parent_company(self):
        self.assertFalse(any(c.object == "Q7175091" for c in self.result.claims))
        self.assertNotIn("Q7175091", self.entities)

    def test_full_run_replaces_everything_and_records_revisions(self):
        self.assertIsNone(self.result.scope)
        self.assertEqual(self.result.progress["full_refresh"], "2026-10-05")
        self.assertEqual(self.result.progress["revids"]["Sovos Brands"], 14)


class IncrementalRun(unittest.TestCase):
    def test_only_changed_pages_are_reparsed_and_scoped(self):
        store = empty_store()
        store.progress["wikipedia"] = {"full_refresh": "2026-10-04",
                                       "revids": {t: p["revid"] for t, p in PAGES.items()}}
        changed = {**PAGES, "Buffalo Wild Wings": {**PAGES["Buffalo Wild Wings"], "revid": 99}}
        fetcher = wiki_fetcher(changed)
        result = wikipedia.collect(fetcher, store, "2026-10-05")
        self.assertEqual(result.scope, {wikipedia.article_url("Buffalo Wild Wings")})
        self.assertEqual({c.subject for c in result.claims}, {"Q509255"})
        self.assertNotIn("embeddedin", str([params for _, params, _ in fetcher.calls]))

    def test_pages_known_from_other_sources_are_included(self):
        store = empty_store()
        store.progress["wikipedia"] = {"full_refresh": "2026-10-04", "revids": {}}
        store.entities["wikidata"] = {"Q630866": Entity("Q630866", "company", "Arby's", "wikidata", ids={"wikipedia": "Arby's"})}
        result = wikipedia.collect(wiki_fetcher(), store, "2026-10-05")
        self.assertIn(wikipedia.article_url("Arby's"), result.scope)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run it to verify it fails**

Run: `python3 -m unittest tests.test_wikipedia -v`
Expected: ERROR, `ImportError: cannot import name 'wikipedia' from 'pipeline.collectors'`

- [ ] **Step 4: Write the implementation**

`pipeline/collectors/wikipedia.py`:

```python
"""Wikipedia company infoboxes: the primary source of ownership links."""

from __future__ import annotations

import datetime
import re
import urllib.parse
from dataclasses import dataclass, field

from ..model import Claim, Classification, CollectorResult, Entity, chunks, name_ref, website_domain
from .wikitext import OwnerRef, PageFacts, classify_page, is_person, page_facts, parse_names, parse_owners, parse_tickers, plain

SOURCE = "wikipedia"
API = "https://en.wikipedia.org/w/api.php"
TEMPLATE = "Template:Infobox company"
OWNER_FIELDS = ("parent", "owner", "owners")
SUBSIDIARY_FIELDS = ("subsid", "subsidiaries")
FULL_REFRESH_DAYS = 7
LINK_HOPS = 3
_CONTENT = {"action": "query", "prop": "revisions|pageprops|redirects", "rvprop": "content|ids|timestamp",
            "rvslots": "main", "rvsection": "0", "ppprop": "wikibase_item", "rdprop": "title",
            "rdnamespace": "0", "rdlimit": "max", "format": "json", "formatversion": "2", "maxlag": "5"}


def article_url(title: str) -> str:
    return "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"), safe="()_,'!:")


def display_name(title: str) -> str:
    return re.sub(r"\s*\([^)]*\)$", "", title)


@dataclass
class ParsedPage:
    title: str
    qid: str | None
    revid: int
    facts: PageFacts
    redirects: list[str] = field(default_factory=list)

    @property
    def entity_id(self) -> str:
        return self.qid or f"wp:{self.title}"

    def owners(self) -> list[tuple[str, OwnerRef]]:
        return [(name, ref) for name in OWNER_FIELDS for ref in parse_owners(self.facts.fields.get(name, ""))]

    def listed(self, names: tuple[str, ...]) -> list[tuple[str, str | None, str]]:
        return [(name, target, text) for name in names for target, text in parse_names(self.facts.fields.get(name, ""))]

    def link_targets(self) -> set[str]:
        targets = {ref.target for _, ref in self.owners() if ref.target}
        targets |= {target for _, target, _ in self.listed(("brands",) + SUBSIDIARY_FIELDS) if target}
        return targets


def parse_page(page: dict) -> ParsedPage:
    revision = page["revisions"][0]
    return ParsedPage(title=page["title"], qid=page.get("pageprops", {}).get("wikibase_item"),
                      revid=revision.get("revid", 0), facts=page_facts(revision["slots"]["main"]["content"]),
                      redirects=[r["title"] for r in page.get("redirects", [])])


def iterate_pages(fetcher, params: dict):
    """Yield complete page records, merging prop continuations until each batch completes."""
    batch: dict[int, dict] = {}
    cont: dict = {}
    while True:
        data = fetcher.get_json(API, {**params, **cont})
        for page in data.get("query", {}).get("pages", []):
            if "pageid" not in page:
                continue
            merged = batch.setdefault(page["pageid"], {"redirects": []})
            for key, value in page.items():
                if key == "redirects":
                    merged["redirects"].extend(value)
                elif key not in merged or key == "revisions":
                    merged[key] = value
        if data.get("batchcomplete") or "continue" not in data:
            for page in batch.values():
                if page.get("revisions"):
                    yield page
            batch = {}
        if "continue" not in data:
            return
        cont = data["continue"]


def pages_by_title(fetcher, titles):
    for batch in chunks(sorted(titles), 50):
        yield from iterate_pages(fetcher, {**_CONTENT, "titles": "|".join(batch), "redirects": "1"})


def resolve_titles(fetcher, titles) -> dict[str, tuple[str, str | None]]:
    """Map each title (redirect or not) to (canonical title, QID or None). Missing pages are left out."""
    mapping: dict[str, tuple[str, str | None]] = {}
    for batch in chunks(sorted(set(titles)), 50):
        data = fetcher.get_json(API, {"action": "query", "titles": "|".join(batch), "redirects": "1",
                                      "prop": "pageprops", "ppprop": "wikibase_item", "format": "json",
                                      "formatversion": "2", "maxlag": "5"})
        query = data.get("query", {})
        steps = {s["from"]: s["to"] for s in query.get("normalized", []) + query.get("redirects", [])}
        pages = {p["title"]: p for p in query.get("pages", []) if not p.get("missing") and not p.get("invalid")}
        for title in batch:
            final = title
            for _ in range(3):
                final = steps.get(final, final)
            if final in pages:
                mapping[title] = (final, pages[final].get("pageprops", {}).get("wikibase_item"))
    return mapping


def changed_titles(fetcher, titles, revids: dict[str, int]) -> set[str]:
    changed = set()
    for batch in chunks(sorted(titles), 50):
        data = fetcher.get_json(API, {"action": "query", "prop": "info", "titles": "|".join(batch), "redirects": "1",
                                      "format": "json", "formatversion": "2", "maxlag": "5"})
        for page in data.get("query", {}).get("pages", []):
            if not page.get("missing") and revids.get(page["title"]) != page.get("lastrevid"):
                changed.add(page["title"])
    return changed


def _full_due(progress: dict, run_date: str) -> bool:
    last = progress.get("full_refresh")
    if not last:
        return True
    return (datetime.date.fromisoformat(run_date) - datetime.date.fromisoformat(last)).days >= FULL_REFRESH_DAYS


def collect(fetcher, store, run_date: str) -> CollectorResult:
    progress = dict(store.progress.get(SOURCE, {}))
    revids: dict[str, int] = dict(progress.get("revids", {}))
    linked = {e.ids["wikipedia"] for records in store.entities.values() for e in records.values()
              if e.ids.get("wikipedia") and e.source != SOURCE}
    full = _full_due(progress, run_date)
    parsed: dict[str, ParsedPage] = {}
    if full:
        params = {**_CONTENT, "generator": "embeddedin", "geititle": TEMPLATE, "geinamespace": "0", "geilimit": "50"}
        for page in iterate_pages(fetcher, params):
            parsed[page["title"]] = parse_page(page)
        to_fetch = linked - set(parsed)
    else:
        to_fetch = changed_titles(fetcher, set(revids) | linked, revids)
    # Unchanged pages keep their stored claims during an incremental run, so only a
    # full run must re-read every linked parent page.
    unchanged = set() if full else set(revids)
    for _ in range(LINK_HOPS + 1):
        for page in pages_by_title(fetcher, to_fetch):
            parsed[page["title"]] = parse_page(page)
        targets = {t for p in parsed.values() for t in p.link_targets()}
        resolved = resolve_titles(fetcher, targets - set(parsed))
        to_fetch = {canonical for canonical, _ in resolved.values()} - set(parsed) - unchanged
        if not to_fetch:
            break
    resolved = resolve_titles(fetcher, {t for p in parsed.values() for t in p.link_targets()} - set(parsed))
    result = build_result(parsed, resolved)
    for page in parsed.values():
        revids[page.title] = page.revid
    progress["revids"] = revids
    if full:
        progress["full_refresh"] = run_date
    result.scope = None if full else {article_url(t) for t in parsed}
    result.progress = progress
    return result


def build_result(parsed: dict[str, ParsedPage], resolved: dict[str, tuple[str, str | None]]) -> CollectorResult:
    entities: dict[str, Entity] = {}
    claims: list[Claim] = []
    kinds: list[Classification] = []
    people = {title for title, page in parsed.items() if is_person(page.facts)}
    parsed = {title: page for title, page in parsed.items() if title not in people}
    for page in parsed.values():
        fields = page.facts.fields
        ids = {"wikipedia": page.title}
        if page.qid:
            ids["wikidata"] = page.qid
        if domain := website_domain(fields.get("website") or fields.get("url") or ""):
            ids["website_domain"] = domain
        tickers = parse_tickers(fields.get("traded_as", ""))
        if tickers:
            ids["ticker"] = tickers[0]
        entities[page.entity_id] = Entity(id=page.entity_id, kind="company", name=display_name(page.title),
                                          source=SOURCE, aliases=page.redirects[:20], ids=ids)
        for kind in classify_page(page.facts):
            if kind == "public_company" and tickers:
                evidence = f"traded_as = {', '.join(tickers)}"
            elif kind in ("pe_firm", "investment_firm"):
                evidence = f"Short description: {page.facts.short_description}; industry: {plain(fields.get('industry'))}"
            else:
                evidence = f"type = {plain(fields.get('type'))}"
            kinds.append(Classification(entity=page.entity_id, kind=kind, source=SOURCE, evidence=evidence[:200],
                                        source_url=article_url(page.title)))

    def target_id(title: str | None, text: str) -> str:
        """Entity id for a linked title (following redirects) or, failing that, for plain text."""
        canonical, qid = resolved.get(title, (title, None)) if title else (None, None)
        if canonical in parsed:
            entity = entities[parsed[canonical].entity_id]
        elif title in resolved:
            entity_id = qid or f"wp:{canonical}"
            entity = entities.setdefault(entity_id, Entity(
                id=entity_id, kind="company", name=display_name(canonical), source=SOURCE,
                ids={k: v for k, v in (("wikipedia", canonical), ("wikidata", qid)) if v}))
        else:
            ref = name_ref(text or title or "")
            return entities.setdefault(ref, Entity(id=ref, kind="company", name=text or title or "", source=SOURCE)).id
        if title != canonical and title not in entity.aliases:
            entity.aliases.append(title)  # e.g. "Campbell Soup Company" for Campbell's
        return entity.id

    for page in parsed.values():
        url, record, fields = article_url(page.title), str(page.revid), page.facts.fields
        for field_name, ref in page.owners():
            if ref.target and resolved.get(ref.target, (ref.target, None))[0] in people:
                continue  # an owner who is a person is not a parent company
            obj = target_id(ref.target, ref.text)
            if obj == page.entity_id:
                continue
            relation = "minority_stake" if ref.percent is not None and ref.percent < 50 else "controlled_by"
            claims.append(Claim(source=SOURCE, subject=page.entity_id, relation=relation, object=obj, start=ref.start,
                                end=ref.end, source_url=url, source_record=record,
                                excerpt=f"{field_name} = {fields.get(field_name, '')}"[:200]))
        for field_name, target, text in page.listed(("brands",) + SUBSIDIARY_FIELDS):
            subject = target_id(target, text)
            if subject == page.entity_id:
                continue
            if field_name == "brands" and subject.startswith("name:"):
                entities[subject].kind = "brand"
            claims.append(Claim(source=SOURCE, subject=subject,
                                relation="brand_of" if field_name == "brands" else "controlled_by",
                                object=page.entity_id, source_url=url, source_record=record,
                                excerpt=f"{field_name} = {fields.get(field_name, '')}"[:200]))
    return CollectorResult(entities=list(entities.values()), claims=claims, classifications=kinds)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_wikipedia -v`
Expected: 8 tests, OK

- [ ] **Step 6: Commit**

```bash
git add pipeline/collectors/wikipedia.py tests/helpers.py tests/test_wikipedia.py
git commit -m "Collect ownership links from Wikipedia infoboxes"
```

---

### Task 6: Name Suggestion Index collector

**Files:**
- Create: `pipeline/collectors/nsi.py`
- Test: `tests/test_nsi.py`

**Interfaces:**
- Produces:
  - `parse_brands(document, wikidata) -> list[Entity]`: US and worldwide (`001`) brands only. The ID is the QID or `nsi:<id>`. `kind="brand"`, the category comes from the NSI path, and the aliases are matchNames, short_name, brand, and name.
  - `collect(...)` returns `unchanged=True` when the npm version is the same.

- [ ] **Step 1: Write the failing test**

`tests/test_nsi.py`:

```python
import tempfile
import unittest
from pathlib import Path

from pipeline.collectors import nsi
from pipeline.model import Entity
from pipeline.store import Store
from tests.helpers import FakeFetcher, url_is

DOCUMENT = {"nsi": {
    "brands/amenity/restaurant": {"items": [
        {"displayName": "Buffalo Wild Wings", "id": "buffalowildwings-96af40", "locationSet": {"include": ["us"]},
         "matchNames": ["bww"], "tags": {"brand": "Buffalo Wild Wings", "brand:wikidata": "Q509255", "short_name": "BW3"}},
        {"displayName": "Wagamama", "id": "wagamama-1", "locationSet": {"include": ["gb"]},
         "tags": {"brand:wikidata": "Q2577474"}},
    ]},
    "brands/amenity/fast_food": {"items": [
        {"displayName": "Buffalo Wild Wings GO", "id": "bwwgo-1", "locationSet": {"include": ["us-mn"]},
         "tags": {"brand": "Buffalo Wild Wings GO", "brand:wikidata": "Q509255"}},
        {"displayName": "Local Chain", "id": "localchain-1", "locationSet": {"include": ["001"]}, "tags": {}},
    ]},
    "transit/route/bus": {"items": [{"displayName": "Metro", "id": "metro", "locationSet": {"include": ["us"]}, "tags": {}}]},
}}
WIKIDATA = {"Q509255": {"officialWebsites": ["https://www.buffalowildwings.com/"]}}


class ParseBrands(unittest.TestCase):
    def setUp(self):
        self.entities = {e.id: e for e in nsi.parse_brands(DOCUMENT, WIKIDATA)}

    def test_us_and_worldwide_brands_only(self):
        self.assertEqual(set(self.entities), {"Q509255", "nsi:localchain-1"})

    def test_items_sharing_a_qid_merge_their_names(self):
        bww = self.entities["Q509255"]
        self.assertEqual((bww.kind, bww.category, bww.ids["website_domain"]), ("brand", "restaurant", "buffalowildwings.com"))
        self.assertEqual(bww.aliases, ["bww", "BW3", "Buffalo Wild Wings GO"])


class Collect(unittest.TestCase):
    def fetcher(self, version):
        return FakeFetcher([(url_is(nsi.REGISTRY), {"version": version}),
                            (url_is("https://cdn.jsdelivr.net/npm/name-suggestion-index@8.1/dist/json"), DOCUMENT),
                            (url_is("https://cdn.jsdelivr.net/npm/name-suggestion-index@8.1/dist/wikidata"), {"wikidata": WIKIDATA})])

    def test_new_version_is_downloaded(self):
        result = nsi.collect(self.fetcher("8.1"), Store(Path(tempfile.mkdtemp())), "2026-10-05")
        self.assertEqual((result.progress["version"], len(result.entities), result.scope), ("8.1", 2, None))

    def test_same_version_is_unchanged(self):
        store = Store(Path(tempfile.mkdtemp()))
        store.progress["nsi"] = {"version": "8.1"}
        store.entities["nsi"] = {"Q1": Entity("Q1", "brand", "A", "nsi")}
        self.assertTrue(nsi.collect(self.fetcher("8.1"), store, "2026-10-05").unchanged)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_nsi -v`
Expected: ERROR, `ImportError: cannot import name 'nsi'`

- [ ] **Step 3: Write the implementation**

`pipeline/collectors/nsi.py`:

```python
"""OpenStreetMap Name Suggestion Index: the list of storefront brands and their nicknames."""

from __future__ import annotations

from ..model import CollectorResult, Entity, website_domain

SOURCE = "nsi"
REGISTRY = "https://registry.npmjs.org/name-suggestion-index/latest"
CDN = "https://cdn.jsdelivr.net/npm/name-suggestion-index@{version}/dist/{path}"
FALLBACK_VERSION = "8.0.20260918"


def _in_us(location_set: dict) -> bool:
    return any(str(code) in ("us", "001") or str(code).startswith("us-") for code in location_set.get("include", []))


def parse_brands(document: dict, wikidata: dict) -> list[Entity]:
    merged: dict[str, Entity] = {}
    for path, group in document.get("nsi", {}).items():
        if not path.startswith("brands/"):
            continue
        category = path.rsplit("/", 1)[-1].replace("_", " ")
        for item in group.get("items", []):
            if not _in_us(item.get("locationSet", {})):
                continue
            tags = item.get("tags", {})
            qid = tags.get("brand:wikidata")
            entity_id = qid or f"nsi:{item['id']}"
            entity = merged.get(entity_id)
            if entity is None:
                ids = {"nsi": item["id"]}
                if qid:
                    ids["wikidata"] = qid
                sites = (wikidata.get(qid) or {}).get("officialWebsites") or [""]
                if domain := website_domain(sites[0]):
                    ids["website_domain"] = domain
                name = item.get("displayName") or tags.get("brand") or tags.get("name") or entity_id
                entity = merged[entity_id] = Entity(id=entity_id, kind="brand", name=name, source=SOURCE,
                                                    ids=ids, category=category)
            for alias in (*item.get("matchNames", []), tags.get("short_name"), tags.get("brand"), tags.get("name")):
                if alias and alias != entity.name and alias not in entity.aliases:
                    entity.aliases.append(alias)
    return list(merged.values())


def collect(fetcher, store, run_date: str) -> CollectorResult:
    progress = dict(store.progress.get(SOURCE, {}))
    try:
        version = fetcher.get_json(REGISTRY)["version"]
    except Exception:
        version = progress.get("version", FALLBACK_VERSION)
    if version == progress.get("version") and store.entities.get(SOURCE):
        return CollectorResult(unchanged=True, progress=progress)
    document = fetcher.get_json(CDN.format(version=version, path="json/nsi.min.json"))
    wikidata = fetcher.get_json(CDN.format(version=version, path="wikidata/wikidata.min.json")).get("wikidata", {})
    progress["version"] = version
    return CollectorResult(entities=parse_brands(document, wikidata), scope=None, progress=progress)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_nsi -v`
Expected: 4 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/collectors/nsi.py tests/test_nsi.py
git commit -m "Collect US storefront brands from the Name Suggestion Index"
```

---

### Task 7: Wikidata collector

**Files:**
- Create: `pipeline/collectors/wikidata.py`
- Test: `tests/test_wikidata.py`

**Interfaces:**
- Consumes: store entities from `nsi` and `wikipedia`, plus active `wikipedia` claims.
- Produces:
  - `build_result(documents, objects) -> CollectorResult`:
    - P127/P749 become `controlled_by`, and P355 becomes a reverse `controlled_by`, with P580/P582 dates.
    - Human owners are dropped.
    - P5531 is stored as `ids["cik"]`.
    - P31 = Q5418962 means `pe_firm`; P414 means `public_company`.
  - `collect` targets NSI QIDs plus Wikipedia chain members and returns `scope=None`. No `maxlag` parameter is sent.

- [ ] **Step 1: Write the failing test**

`tests/test_wikidata.py`:

```python
import tempfile
import unittest
from pathlib import Path

from pipeline.collectors import wikidata
from pipeline.model import Claim, Entity
from pipeline.store import Store
from tests.helpers import FakeFetcher, url_is


def item(qid, label, claims=None, title=None):
    doc = {"id": qid, "labels": {"en": {"value": label}}, "claims": claims or {}, "aliases": {"en": [{"value": label + " Inc."}]}}
    if title:
        doc["sitelinks"] = {"enwiki": {"title": title}}
    return doc


def statement(value, start=None, end=None, rank="normal"):
    qualifiers = {}
    if start:
        qualifiers["P580"] = [{"datavalue": {"value": {"time": f"+{start}-00-00T00:00:00Z", "precision": 9}}}]
    if end:
        qualifiers["P582"] = [{"datavalue": {"value": {"time": f"+{end}-00-00T00:00:00Z", "precision": 9}}}]
    return {"id": f"s-{value}", "rank": rank, "qualifiers": qualifiers,
            "mainsnak": {"snaktype": "value", "datavalue": {"value": {"id": value} if str(value).startswith("Q") else value}}}


DOCS = {
    "Q630866": item("Q630866", "Arby's", {"P127": [statement("Q7339900")], "P749": [statement("Q55074808", start="2018")]}, "Arby's"),
    "Q6184897": item("Q6184897", "Jersey Mike's Subs", {"P127": [statement("Q99999")]}, "Jersey Mike's Subs"),
    "Q1030544": item("Q1030544", "Campbell's", {"P5531": [statement("0000016732")], "P414": [statement("Q82059")],
                                                 "P355": [statement("Q121775110", start="2024")]}),
    "Q7339900": item("Q7339900", "Roark Capital", {"P31": [statement("Q5418962")], "P127": [statement("Q1", rank="deprecated")]}),
}
OBJECTS = {"Q99999": item("Q99999", "Peter Cancro", {"P31": [statement("Q5")]}),
           "Q55074808": item("Q55074808", "Inspire Brands"),
           "Q121775110": item("Q121775110", "Sovos Brands")}


class BuildResult(unittest.TestCase):
    def setUp(self):
        self.result = wikidata.build_result(DOCS, OBJECTS)
        self.links = {(c.subject, c.object, c.start, c.end) for c in self.result.claims}

    def test_owned_by_parent_and_subsidiary_with_dates(self):
        self.assertIn(("Q630866", "Q7339900", None, None), self.links)
        self.assertIn(("Q630866", "Q55074808", "2018", None), self.links)
        self.assertIn(("Q121775110", "Q1030544", "2024", None), self.links)

    def test_people_and_deprecated_statements_are_skipped(self):
        self.assertFalse(any(c.object in ("Q99999", "Q1") for c in self.result.claims))
        self.assertNotIn("Q99999", {e.id for e in self.result.entities})

    def test_identifiers_and_classifications(self):
        entities = {e.id: e for e in self.result.entities}
        self.assertEqual(entities["Q1030544"].ids["cik"], "16732")
        self.assertEqual(entities["Q630866"].ids["wikipedia"], "Arby's")
        kinds = {(k.entity, k.kind) for k in self.result.classifications}
        self.assertEqual(kinds, {("Q7339900", "pe_firm"), ("Q1030544", "public_company")})


class Collect(unittest.TestCase):
    def test_targets_nsi_brands_and_wikipedia_chain_members_without_maxlag(self):
        store = Store(Path(tempfile.mkdtemp()))
        store.entities["nsi"] = {"Q630866": Entity("Q630866", "brand", "Arby's", "nsi", ids={"wikidata": "Q630866"})}
        store.entities["wikipedia"] = {"Q1030544": Entity("Q1030544", "company", "Campbell's", "wikipedia", ids={"wikidata": "Q1030544"})}
        store.claims["wikipedia"] = {"k": Claim("wikipedia", "wp:x", "controlled_by", "Q1030544")}
        fetcher = FakeFetcher([(url_is(wikidata.API), lambda url, params, headers: {"entities": {
            q: (DOCS.get(q) or OBJECTS.get(q) or {"missing": ""}) for q in params["ids"].split("|")}})])
        result = wikidata.collect(fetcher, store, "2026-10-05")
        first_ids = set(fetcher.calls[0][1]["ids"].split("|"))
        self.assertEqual(first_ids, {"Q630866", "Q1030544"})
        self.assertTrue(all("maxlag" not in params for _, params, _ in fetcher.calls))
        self.assertIsNone(result.scope)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_wikidata -v`
Expected: ERROR, `ImportError: cannot import name 'wikidata'`

- [ ] **Step 3: Write the implementation**

`pipeline/collectors/wikidata.py`:

```python
"""Wikidata: a secondary cross-check of ownership, plus SEC identifiers (CIKs)."""

from __future__ import annotations

from ..model import Claim, Classification, CollectorResult, Entity, chunks

SOURCE = "wikidata"
API = "https://www.wikidata.org/w/api.php"
PE_FIRM = "Q5418962"
HUMAN = "Q5"
OWNERSHIP = {"P127": "owned by", "P749": "parent organization"}


def fetch_entities(fetcher, qids, props: str) -> dict[str, dict]:
    found = {}
    for batch in chunks(sorted(set(qids)), 50):
        data = fetcher.get_json(API, {"action": "wbgetentities", "ids": "|".join(batch), "props": props,
                                      "languages": "en", "sitefilter": "enwiki", "format": "json"})
        for qid, document in data.get("entities", {}).items():
            if "missing" not in document:
                found[qid] = document
    return found


def statements(document: dict, prop: str):
    for statement in document.get("claims", {}).get(prop, []):
        if statement.get("rank") == "deprecated":
            continue
        snak = statement.get("mainsnak", {})
        if snak.get("snaktype") == "value":
            yield statement, snak["datavalue"]["value"]


def qualifier_date(statement: dict, prop: str) -> str | None:
    for qualifier in statement.get("qualifiers", {}).get(prop, []):
        value = (qualifier.get("datavalue") or {}).get("value") or {}
        if time := value.get("time"):
            date = time.lstrip("+")[:10]
            precision = value.get("precision", 9)
            return date if precision >= 11 else date[:7] if precision == 10 else date[:4]
    return None


def _instance_of(document: dict) -> set[str]:
    return {value.get("id") for _, value in statements(document, "P31") if isinstance(value, dict)}


def target_qids(store) -> set[str]:
    """NSI brands plus every entity already on a Wikipedia ownership chain."""
    qids = {e.ids["wikidata"] for e in store.entities.get("nsi", {}).values() if e.ids.get("wikidata")}
    wiki = store.entities.get("wikipedia", {})
    for claim in store.claims.get("wikipedia", {}).values():
        if claim.status == "active":
            for ref in (claim.subject, claim.object):
                entity = wiki.get(ref)
                if entity and entity.ids.get("wikidata"):
                    qids.add(entity.ids["wikidata"])
    return qids


def build_result(documents: dict[str, dict], objects: dict[str, dict]) -> CollectorResult:
    entities, claims, kinds = {}, [], []
    known = {**objects, **documents}
    for qid, document in documents.items():
        label = document.get("labels", {}).get("en", {}).get("value", qid)
        ids = {"wikidata": qid}
        if title := document.get("sitelinks", {}).get("enwiki", {}).get("title"):
            ids["wikipedia"] = title
        for _, value in statements(document, "P5531"):
            if str(value).strip().isdigit():
                ids["cik"] = str(int(value))
                break
        aliases = [a["value"] for a in document.get("aliases", {}).get("en", [])][:15]
        entities[qid] = Entity(id=qid, kind="company", name=label, source=SOURCE, aliases=aliases, ids=ids)
        url = f"https://www.wikidata.org/wiki/{qid}"
        if PE_FIRM in _instance_of(document):
            kinds.append(Classification(entity=qid, kind="pe_firm", source=SOURCE, source_url=url,
                                        evidence="Wikidata: instance of private equity firm"))
        if any(True for _ in statements(document, "P414")):
            kinds.append(Classification(entity=qid, kind="public_company", source=SOURCE, source_url=url,
                                        evidence="Wikidata: listed on a stock exchange"))
        for prop, words in OWNERSHIP.items():
            for statement, value in statements(document, prop):
                owner = value.get("id") if isinstance(value, dict) else None
                if not owner or HUMAN in _instance_of(known.get(owner, {})):
                    continue  # people (founders, families) are not parent companies
                claims.append(Claim(source=SOURCE, subject=qid, relation="controlled_by", object=owner,
                                    start=qualifier_date(statement, "P580"), end=qualifier_date(statement, "P582"),
                                    source_url=f"{url}#{prop}", source_record=statement.get("id", ""),
                                    excerpt=f"{words}: {owner}"))
        for statement, value in statements(document, "P355"):
            if isinstance(value, dict) and value.get("id"):
                claims.append(Claim(source=SOURCE, subject=value["id"], relation="controlled_by", object=qid,
                                    start=qualifier_date(statement, "P580"), end=qualifier_date(statement, "P582"),
                                    source_url=f"{url}#P355", source_record=statement.get("id", ""),
                                    excerpt=f"has subsidiary: {value['id']}"))
    for qid, document in objects.items():
        if qid not in entities and HUMAN not in _instance_of(document):
            label = document.get("labels", {}).get("en", {}).get("value", qid)
            entities[qid] = Entity(id=qid, kind="company", name=label, source=SOURCE, ids={"wikidata": qid})
    return CollectorResult(entities=list(entities.values()), claims=claims, classifications=kinds)


def collect(fetcher, store, run_date: str) -> CollectorResult:
    documents = fetch_entities(fetcher, target_qids(store), "labels|aliases|claims|sitelinks")
    owners = {value.get("id") for document in documents.values() for prop in (*OWNERSHIP, "P355")
              for _, value in statements(document, prop) if isinstance(value, dict)} - set(documents) - {None}
    objects = fetch_entities(fetcher, owners, "labels|claims")
    result = build_result(documents, objects)
    result.scope = None
    return result
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_wikidata -v`
Expected: 4 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/collectors/wikidata.py tests/test_wikidata.py
git commit -m "Add Wikidata as a secondary ownership and CIK source"
```

---

### Task 8: SEC Form ADV collector

**Files:**
- Create: `pipeline/collectors/adv.py`
- Test: `tests/test_adv.py`

**Interfaces:**
- Consumes: `config.cache_dir()`; `Fetcher.open` for zip downloads.
- Produces:
  - `recent_files(manifest, run_date, months=13)`
  - `read_filings(zip_path) -> [{"crd", "legal", "business", "date", "funds": [(id, name, type)], "sites": [...]}]`
  - `build_result(filings)`:
    - Keeps the latest filing per CRD.
    - Entities are `crd:<n>` (kind `adviser`, with `ids["website_domains"]` as a space-separated list of non-social domains) and `fund:<id>` (kind `fund`).
    - Each fund has a `fund_of` claim (official) to its adviser.
    - An adviser with ≥1 "Private Equity Fund" is `pe_firm`. An adviser with funds but none labeled PE is `investment_firm`. Advisers without funds are unclassified.
  - `collect` downloads into `<cache>/adv/` and returns `unchanged` when the manifest fingerprint is the same.

- [ ] **Step 1: Write the failing test**

`tests/test_adv.py`:

```python
import csv
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from pipeline.collectors import adv
from pipeline.store import Store
from tests.helpers import FakeFetcher, url_is


def csv_bytes(header, rows):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue().encode()


def monthly_zip(path: Path, suffix: str, filings):
    """filings: [(filing_id, crd, name, submitted, [(fund_id, fund_name, type)], [website])]"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"IA_ADV_Base_A_{suffix}.csv", csv_bytes(
            ["FilingID", "DateSubmitted", "1A", "1B1", "1E1"], [(f, d, n.upper(), n.upper(), crd) for f, crd, n, d, _, _ in filings]))
        archive.writestr(f"IA_Schedule_D_7B1_{suffix}.csv", csv_bytes(
            ["FilingID", "Fund Name", "Fund ID", "Fund Type"], [(f, fn, fid, ft) for f, *_, funds, _ in filings for fid, fn, ft in funds]))
        archive.writestr(f"IA_Schedule_D_7B1A17b_{suffix}.csv", csv_bytes(["FilingID", "x"], [("1", "ignored")]))
        archive.writestr(f"IA_Schedule_D_1I_{suffix}.csv", csv_bytes(
            ["FilingID", "Website"], [(f, site) for f, *_, sites in filings for site in sites]))


class Filings(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        monthly_zip(self.dir / "old.zip", "20260101_20260131", [
            ("1", "160368", "Roark Capital Management, LLC", "01/05/2026 10:00:00 AM",
             [("805-1", "ROARK CAPITAL PARTNERS V LP", "Private Equity Fund")], ["HTTP://WWW.ROARKCAPITAL.COM"]),
        ])
        monthly_zip(self.dir / "new.zip", "20260301_20260331", [
            ("2", "160368", "Roark Capital Management, LLC", "03/31/2026 03:57:13 PM",
             [("805-2", "ROARK CAPITAL PARTNERS VI (T) LP", "Private Equity Fund"), ("805-3", "ROARK CREDIT LP", "Hedge Fund")],
             ["HTTP://WWW.ROARKCAPITAL.COM", "https://www.linkedin.com/company/roark-capital/"]),
            ("3", "999", "Quiet Hedge Advisors", "03/02/2026 09:00:00 AM", [("805-9", "QUIET FUND", "Hedge Fund")], []),
            ("4", "1000", "Advice Only LLC", "03/02/2026 09:00:00 AM", [], []),
        ])

    def test_latest_filing_per_adviser_wins(self):
        result = adv.build_result(adv.read_filings(self.dir / "old.zip") + adv.read_filings(self.dir / "new.zip"))
        funds = {e.id for e in result.entities if e.kind == "fund"}
        self.assertEqual(funds, {"fund:805-2", "fund:805-3", "fund:805-9"})  # the January-only fund is gone

    def test_adviser_identity_kind_and_fund_links(self):
        result = adv.build_result(adv.read_filings(self.dir / "new.zip"))
        roark = next(e for e in result.entities if e.id == "crd:160368")
        self.assertEqual((roark.name, roark.ids["website_domains"]), ("Roark Capital Management, LLC", "roarkcapital.com"))
        kinds = {(k.entity, k.kind) for k in result.classifications}
        self.assertEqual(kinds, {("crd:160368", "pe_firm"), ("crd:999", "investment_firm")})  # no funds: unclassified
        self.assertIn(("fund:805-2", "fund_of", "crd:160368"), {(c.subject, c.relation, c.object) for c in result.claims})
        self.assertTrue(all(c.official for c in result.claims))

    def test_recent_files_window(self):
        manifest = {"advFilingData": {"sectionDisplayName": "x", "2025": {"files": [
            {"fileName": "ADV_Filing_Data_20250801_20250831.zip", "year": "2025", "size": 1},
            {"fileName": "ADV_Filing_Data_20250901_20250930.zip", "year": "2025", "size": 1}]},
            "2026": {"files": [{"fileName": "ADV_Filing_Data_20260901_20260930.zip", "year": "2026", "size": 1}]}}}
        names = [f["fileName"] for f in adv.recent_files(manifest, "2026-10-05")]
        self.assertEqual(names, ["ADV_Filing_Data_20250901_20250930.zip", "ADV_Filing_Data_20260901_20260930.zip"])

    def test_collect_downloads_into_the_cache_and_skips_unchanged_manifests(self):
        payload = (self.dir / "new.zip").read_bytes()
        manifest = {"advFilingData": {"2026": {"files": [
            {"fileName": "ADV_Filing_Data_20260301_20260331.zip", "year": "2026", "size": len(payload), "uploadedOn": "x"}]}}}
        fetcher = FakeFetcher([(url_is(adv.MANIFEST), manifest), (url_is("https://reports.adviserinfo.sec.gov/reports/foia/advFilingData/"), payload)])
        store = Store(self.dir / "state")
        with mock.patch.dict(os.environ, {"PE_CACHE_DIR": str(self.dir / "cache")}):
            result = adv.collect(fetcher, store, "2026-10-05")
            self.assertTrue((self.dir / "cache" / "adv" / "ADV_Filing_Data_20260301_20260331.zip").exists())
            store.apply("adv", result, "2026-10-05")
            self.assertTrue(adv.collect(fetcher, store, "2026-10-06").unchanged)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_adv -v`
Expected: ERROR, `ImportError: cannot import name 'adv'`

- [ ] **Step 3: Write the implementation**

`pipeline/collectors/adv.py`:

```python
"""SEC Form ADV: which investment advisers manage private equity funds."""

from __future__ import annotations

import csv
import datetime
import io
import re
import shutil
import zipfile
from pathlib import Path

from ..config import cache_dir
from ..model import SOCIAL_DOMAINS, Claim, Classification, CollectorResult, Entity, smart_title, website_domain

SOURCE = "adv"
MANIFEST = "https://reports.adviserinfo.sec.gov/reports/foia/reports_metadata.json"
FILE_URL = "https://reports.adviserinfo.sec.gov/reports/foia/advFilingData/{year}/{name}"
ADVISER_PAGE = "https://adviserinfo.sec.gov/firm/summary/{crd}"
MONTHS = 13  # monthly files are deltas; every adviser files an annual update within a year
PE_FUND = "Private Equity Fund"
_BASE = re.compile(r"(?:IA_ADV_Base_A|ERA_ADV_Base)_\d")
_FUNDS = re.compile(r"(?:IA|ERA)_Schedule_D_7B1_\d")
_SITES = re.compile(r"(?:IA|ERA)_Schedule_D_1I_\d")


def recent_files(manifest: dict, run_date: str, months: int = MONTHS) -> list[dict]:
    year, month = int(run_date[:4]), int(run_date[5:7])
    total = year * 12 + (month - 1) - months
    cutoff = f"{total // 12:04d}{total % 12 + 1:02d}01"
    files = [f for value in manifest.get("advFilingData", {}).values() if isinstance(value, dict)
             for f in value.get("files", [])]
    chosen = [f for f in files if re.search(r"_(\d{8})_\d{8}\.zip$", f["fileName"]).group(1) >= cutoff]
    return sorted(chosen, key=lambda f: f["fileName"])


def _submitted(value: str) -> str:
    try:
        return datetime.datetime.strptime(value.strip(), "%m/%d/%Y %I:%M:%S %p").isoformat()
    except ValueError:
        return ""


def _rows(archive: zipfile.ZipFile, member: str):
    with archive.open(member) as handle:
        yield from csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8", errors="replace"))


def read_filings(path: Path) -> list[dict]:
    """One dict per filing in a monthly zip: adviser identity, its funds, and its websites."""
    advisers, funds, sites = {}, {}, {}
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            base = member.rsplit("/", 1)[-1]
            if _BASE.match(base):
                for row in _rows(archive, member):
                    if crd := (row.get("1E1") or "").strip():
                        advisers[row["FilingID"]] = {"crd": crd, "legal": (row.get("1A") or "").strip(),
                                                     "business": (row.get("1B1") or "").strip(),
                                                     "date": _submitted(row.get("DateSubmitted") or "")}
            elif _FUNDS.match(base):
                for row in _rows(archive, member):
                    funds.setdefault(row["FilingID"], []).append(
                        ((row.get("Fund ID") or "").strip(), (row.get("Fund Name") or "").strip(), (row.get("Fund Type") or "").strip()))
            elif _SITES.match(base):
                for row in _rows(archive, member):
                    sites.setdefault(row["FilingID"], []).append((row.get("Website") or "").strip())
    return [{**adviser, "funds": funds.get(fid, []), "sites": sites.get(fid, [])} for fid, adviser in advisers.items()]


def build_result(filings: list[dict]) -> CollectorResult:
    latest: dict[str, dict] = {}
    for filing in filings:
        if filing["date"] >= latest.get(filing["crd"], {}).get("date", ""):
            latest[filing["crd"]] = filing
    entities, claims, kinds = [], [], []
    for crd, filing in sorted(latest.items()):
        adviser_id, url = f"crd:{crd}", ADVISER_PAGE.format(crd=crd)
        domains = []
        for site in filing["sites"]:
            domain = website_domain(site)
            if domain and domain not in SOCIAL_DOMAINS and domain not in domains:
                domains.append(domain)
        ids = {"crd": crd}
        if domains:
            ids["website_domains"] = " ".join(domains)
        name = smart_title(filing["business"] or filing["legal"])
        aliases = [smart_title(filing["legal"])] if filing["legal"] and smart_title(filing["legal"]) != name else []
        entities.append(Entity(id=adviser_id, kind="adviser", name=name, source=SOURCE, aliases=aliases, ids=ids))
        funds = [f for f in filing["funds"] if f[0]]
        if not funds:
            continue
        pe = [f for f in funds if f[2] == PE_FUND]
        kinds.append(Classification(
            entity=adviser_id, kind="pe_firm" if pe else "investment_firm", source=SOURCE, official=True,
            source_url=url, evidence=f"Form ADV filed {filing['date'][:10]}: {len(pe)} of {len(funds)} private funds are private equity funds"))
        for fund_id, fund_name, fund_type in funds:
            fund_ref = f"fund:{fund_id}"
            entities.append(Entity(id=fund_ref, kind="fund", name=fund_name, source=SOURCE, ids={"fund": fund_id}))
            claims.append(Claim(source=SOURCE, subject=fund_ref, relation="fund_of", object=adviser_id, official=True,
                                source_url=url, source_record=fund_id, excerpt=f"{fund_name} ({fund_type})"[:200]))
    return CollectorResult(entities=entities, claims=claims, classifications=kinds)


def download(fetcher, url: str, dest: Path, size: int) -> Path:
    if dest.exists() and dest.stat().st_size == size:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    with fetcher.open(url, timeout=600) as response, partial.open("wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)
    partial.replace(dest)
    return dest


def collect(fetcher, store, run_date: str) -> CollectorResult:
    progress = dict(store.progress.get(SOURCE, {}))
    files = recent_files(fetcher.get_json(MANIFEST), run_date)
    if not files:
        raise RuntimeError("Form ADV manifest listed no recent filing files")
    fingerprint = [f"{f['fileName']}:{f['size']}:{f.get('uploadedOn', '')}" for f in files]
    if fingerprint == progress.get("fingerprint") and store.entities.get(SOURCE):
        return CollectorResult(unchanged=True, progress=progress)
    filings = []
    for f in files:
        path = download(fetcher, FILE_URL.format(year=f["year"], name=f["fileName"]),
                        cache_dir() / "adv" / f["fileName"], int(f["size"]))
        filings.extend(read_filings(path))
    result = build_result(filings)
    progress["fingerprint"] = fingerprint
    result.scope, result.progress = None, progress
    return result
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_adv -v`
Expected: 4 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/collectors/adv.py tests/test_adv.py
git commit -m "Classify investment advisers from SEC Form ADV fund types"
```

---

### Task 9: FTC early-termination collector

**Files:**
- Create: `pipeline/collectors/ftc.py`
- Test: `tests/test_ftc.py`

**Interfaces:**
- Produces:
  - `parse_notice(attributes) -> (entities, claims)`. For each acquired entity there is a `deal` claim to the **buyer** (dated `start`), and a `controlled_by` claim to the **seller** that *ended* on that date. The seller is skipped when it is the target itself. Everything is official.
  - `collect` sends the key as `X-Api-Key`, stops at `progress["latest_created"]` or at a repeated notice, caps at `MAX_PAGES`, and returns `scope=set()`.

- [ ] **Step 1: Write the failing test**

`test_an_api_that_ignores_paging_cannot_loop_forever` pins Review Focus #3.

`tests/test_ftc.py`:

```python
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline.collectors import ftc
from pipeline.store import Store
from tests.helpers import FakeFetcher, url_is


def notice(number, created, buyer, seller, targets, date="2026-09-15"):
    return {"attributes": {"transaction-number": number, "created": created, "date": date, "title": f"{number}: {buyer}; {seller}",
                           "acquiring-party": buyer, "acquired-party": seller, "acquired-entities": targets}}


class ParseNotice(unittest.TestCase):
    def test_buyer_makes_a_deal_and_seller_an_ended_control_period(self):
        entities, claims = ftc.parse_notice(notice("20262236", "x", "Roark Capital Partners VI (T) LP", "SSC Partners II-A LP", ["C3 TopCo, LLC"])["attributes"])
        found = {(c.relation, c.subject, c.object, c.start, c.end) for c in claims}
        self.assertEqual(found, {("deal", "name:c3 topco llc", "name:roark capital partners vi t lp", "2026-09-15", None),
                                 ("controlled_by", "name:c3 topco llc", "name:ssc partners ii a lp", None, "2026-09-15")})
        self.assertTrue(all(c.official and c.source_url.endswith("/20262236") for c in claims))
        self.assertEqual(len(entities), 3)

    def test_seller_that_is_the_target_itself_is_not_an_owner(self):
        _, claims = ftc.parse_notice(notice("1", "x", "Sovos Brands Limited Partnership", "Rao's Specialty Foods, Inc.", ["Rao's Specialty Foods, Inc."])["attributes"])
        self.assertEqual([c.relation for c in claims], ["deal"])


class Collect(unittest.TestCase):
    def setUp(self):
        self.pages = [[notice(str(n), f"2026-09-{30 - n:02d}T00:00:00+00:00", "Buyer LP", "Seller LP", [f"Target {n}"]) for n in range(3)]]

    def run_collect(self, store, page_size=50):
        fetcher = FakeFetcher([(url_is(ftc.API), lambda url, params, headers: {"data": self.pages[int(params["page[offset]"]) // page_size]
                                                                               if int(params["page[offset]"]) // page_size < len(self.pages) else []})])
        with mock.patch.dict(os.environ, {"FTC_API_KEY": "KEY"}), mock.patch.object(ftc, "PAGE_SIZE", page_size):
            return ftc.collect(fetcher, store, "2026-10-05"), fetcher

    def test_key_goes_in_a_header_never_the_url(self):
        result, fetcher = self.run_collect(Store(Path(tempfile.mkdtemp())))
        url, params, headers = fetcher.calls[0]
        self.assertEqual(headers, {"X-Api-Key": "KEY"})
        self.assertNotIn("KEY", url + str(params))
        self.assertEqual(result.scope, set())
        self.assertEqual(result.progress["latest_created"], "2026-09-30T00:00:00+00:00")

    def test_incremental_run_stops_at_notices_already_seen(self):
        store = Store(Path(tempfile.mkdtemp()))
        store.progress["ftc"] = {"latest_created": "2026-09-29T00:00:00+00:00"}
        result, _ = self.run_collect(store)
        self.assertEqual({c.subject for c in result.claims}, {"name:target 0"})

    def test_an_api_that_ignores_paging_cannot_loop_forever(self):
        page = [notice(str(n), f"2026-09-{20 + n:02d}T00:00:00+00:00", "Buyer LP", "Seller LP", [f"Target {n}"]) for n in range(2)]
        fetcher = FakeFetcher([(url_is(ftc.API), {"data": page})])
        with mock.patch.dict(os.environ, {"FTC_API_KEY": "KEY"}), mock.patch.object(ftc, "PAGE_SIZE", 2):
            result = ftc.collect(fetcher, Store(Path(tempfile.mkdtemp())), "2026-10-05")
        self.assertEqual((len(fetcher.calls), {c.subject for c in result.claims}), (2, {"name:target 0", "name:target 1"}))

    def test_missing_key_fails_the_source(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            ftc.collect(FakeFetcher([]), Store(Path(tempfile.mkdtemp())), "2026-10-05")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_ftc -v`
Expected: ERROR, `ImportError: cannot import name 'ftc'`

- [ ] **Step 3: Write the implementation**

`pipeline/collectors/ftc.py`:

```python
"""FTC early termination notices: dated deals, including PE funds buying and selling."""

from __future__ import annotations

import os

from ..model import Claim, CollectorResult, Entity, name_ref, normalize

SOURCE = "ftc"
API = "https://api.ftc.gov/v0/hsr-early-termination-notices"
NOTICE = "https://www.ftc.gov/legal-library/browse/early-termination-notices/{number}"
PAGE_SIZE = 50
MAX_PAGES = 1000  # about 50,000 notices; the full history is ~28,000


def parse_notice(attributes: dict) -> tuple[list[Entity], list[Claim]]:
    """In HSR terms the "acquired party" is the seller (the target's former ultimate parent)."""
    number = str(attributes.get("transaction-number") or "").strip()
    date = (attributes.get("date") or "")[:10] or None
    buyer = (attributes.get("acquiring-party") or "").strip()
    seller = (attributes.get("acquired-party") or "").strip()
    targets = [t.strip() for t in attributes.get("acquired-entities") or [] if t and t.strip()] or ([seller] if seller else [])
    url = NOTICE.format(number=number)
    title = (attributes.get("title") or "").strip()
    entities = [Entity(id=name_ref(n), kind="company", name=n, source=SOURCE) for n in dict.fromkeys([buyer, seller, *targets]) if n]
    claims = []
    for target in targets:
        if buyer and normalize(buyer) != normalize(target):
            claims.append(Claim(source=SOURCE, subject=name_ref(target), relation="deal", object=name_ref(buyer),
                                start=date, source_url=url, source_record=number, official=True,
                                excerpt=f"Early termination granted {date}: {title}"[:200]))
        if seller and normalize(seller) != normalize(target):
            claims.append(Claim(source=SOURCE, subject=name_ref(target), relation="controlled_by", object=name_ref(seller),
                                end=date, source_url=url, source_record=number, official=True,
                                excerpt=f"Seller in early termination {date}: {title}"[:200]))
    return entities, claims


def collect(fetcher, store, run_date: str) -> CollectorResult:
    key = os.environ.get("FTC_API_KEY")
    if not key:
        raise RuntimeError("FTC_API_KEY is not set")
    progress = dict(store.progress.get(SOURCE, {}))
    seen = progress.get("latest_created", "")
    newest = seen
    entities: dict[str, Entity] = {}
    claims: list[Claim] = []
    offset = 0
    numbers: set[str] = set()
    for _ in range(MAX_PAGES):
        data = fetcher.get_json(API, {"page[limit]": str(PAGE_SIZE), "page[offset]": str(offset),
                                      "sort[sort-created][path]": "created",
                                      "sort[sort-created][direction]": "DESC"},
                                headers={"X-Api-Key": key})
        records = data.get("data", [])
        reached_seen = False
        for record in records:
            attributes = record.get("attributes", {})
            created = attributes.get("created", "")
            number = str(attributes.get("transaction-number", ""))
            if (seen and created <= seen) or number in numbers:  # caught up, or the API repeated a page
                reached_seen = True
                break
            numbers.add(number)
            newest = max(newest, created)
            notice_entities, notice_claims = parse_notice(attributes)
            for entity in notice_entities:
                entities.setdefault(entity.id, entity)
            claims.extend(notice_claims)
        if reached_seen or len(records) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    progress["latest_created"] = newest
    # Notices are never withdrawn, so this source only ever adds claims.
    return CollectorResult(entities=list(entities.values()), claims=claims, scope=set(), progress=progress)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_ftc -v`
Expected: 6 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/collectors/ftc.py tests/test_ftc.py
git commit -m "Collect FTC early-termination deals, including PE exits"
```

---

### Task 10: USDA branded-foods collector

**Files:**
- Create: `pipeline/collectors/usda.py`
- Test: `tests/test_usda.py`

**Interfaces:**
- Produces:
  - `latest_release(html) -> "YYYY-MM-DD"|None`
  - `zip_member_lines(fetcher, url, suffix)` streams one zip member with HTTP Range requests.
  - `aggregate(rows, release) -> CollectorResult`:
    - `brand_of` claims from `name:<brand>` to `name:<owner>`, `observed=True`, with `start` = first label date.
    - `end` = last label date unless the pair appears on a product's newest label.
    - Brand names typed into the owner field are skipped.
  - `collect` returns `unchanged` for an already-processed release.

- [ ] **Step 1: Write the failing test**

`tests/test_usda.py`:

```python
import csv
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from pipeline.collectors import usda
from pipeline.store import Store
from tests.helpers import FakeFetcher, serve_ranges, url_is

HEADER = ["fdc_id", "brand_owner", "brand_name", "gtin_upc", "ingredients", "branded_food_category", "modified_date"]
ROWS = [
    ("1", "RAO'S HOMEMADE", "RAO'S HOMEMADE", "0747479000017", "TOMATOES", "Pasta Sauces", "2018-06-14"),
    ("2", "Sovos Brands Intermediate, Inc.", "RAO'S HOMEMADE", "0747479000017", "TOMATOES,\nBASIL", "Pasta Sauces", "2020-02-03"),
    ("3", "Sovos Brands Intermediate, Inc.", "RAO'S HOMEMADE", "0747479000017", "TOMATOES", "Pasta Sauces", "2023-06-23"),
    ("4", "Old Owner Co", "OLDBRAND", "0001", "X", "Snacks", "2019-01-01"),
    ("5", "New Owner Co", "OLDBRAND", "0001", "X", "Snacks", "2022-01-01"),
    ("6", "", "NO OWNER", "0002", "X", "Snacks", "2022-01-01"),
]


def branded_zip() -> bytes:
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(HEADER)
    writer.writerows(ROWS)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("food.csv", "fdc_id\n1\n")
        archive.writestr("FoodData_Central_branded_food_csv_2026-04-30/branded_food.csv", text.getvalue())
    return buffer.getvalue()


class Aggregate(unittest.TestCase):
    def setUp(self):
        rows = [dict(zip(HEADER, row)) for row in ROWS]
        self.result = usda.aggregate(rows, "2026-04-30")
        self.claims = {(c.subject, c.object): c for c in self.result.claims}

    def test_brand_name_in_the_owner_field_is_not_an_owner(self):
        self.assertNotIn(("name:raos homemade", "name:raos homemade"), self.claims)

    def test_current_owner_open_and_former_owner_ended(self):
        rao = self.claims[("name:raos homemade", "name:sovos brands intermediate inc")]
        self.assertEqual((rao.start, rao.end, rao.observed, rao.relation), ("2020-02-03", None, True, "brand_of"))
        old = self.claims[("name:oldbrand", "name:old owner co")]
        self.assertEqual(old.end, "2019-01-01")
        self.assertIsNone(self.claims[("name:oldbrand", "name:new owner co")].end)

    def test_names_are_title_cased_with_categories(self):
        entities = {e.id: e for e in self.result.entities}
        self.assertEqual((entities["name:raos homemade"].name, entities["name:raos homemade"].category), ("Rao's Homemade", "Pasta Sauces"))


class Collect(unittest.TestCase):
    def test_streams_only_the_branded_member_and_records_the_release(self):
        page = b'<a href="/fdc-datasets/FoodData_Central_branded_food_csv_2025-12-18.zip">old</a>' \
               b'<a href="/fdc-datasets/FoodData_Central_branded_food_csv_2026-04-30.zip">new</a>'
        fetcher = FakeFetcher([(url_is(usda.PAGE), page), (url_is(usda.FILE.format(release="2026-04-30")), serve_ranges(branded_zip()))])
        store = Store(Path(tempfile.mkdtemp()))
        result = usda.collect(fetcher, store, "2026-10-05")
        self.assertEqual(result.progress["release"], "2026-04-30")
        self.assertEqual(len(result.claims), 3)
        self.assertTrue(all("Range" in headers for url, _, headers in fetcher.calls if url != usda.PAGE))
        store.apply("usda", result, "2026-10-05")
        self.assertTrue(usda.collect(fetcher, store, "2026-11-05").unchanged)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_usda -v`
Expected: ERROR, `ImportError: cannot import name 'usda'`

- [ ] **Step 3: Write the implementation**

`pipeline/collectors/usda.py`:

```python
"""USDA FoodData Central branded foods: which company owns each grocery brand."""

from __future__ import annotations

import csv
import re
import struct
import urllib.parse
import zlib

from ..model import Claim, CollectorResult, Entity, exact_key, name_ref, normalize, smart_title

SOURCE = "usda"
PAGE = "https://fdc.nal.usda.gov/download-datasets/"
FILE = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_branded_food_csv_{release}.zip"
SEARCH = "https://fdc.nal.usda.gov/food-search?type=Branded&query={query}"
MEMBER = "branded_food.csv"
_RELEASE = re.compile(r"FoodData_Central_branded_food_csv_(\d{4}-\d{2}-\d{2})\.zip")


def latest_release(page_html: str) -> str | None:
    found = sorted(set(_RELEASE.findall(page_html)))
    return found[-1] if found else None


def zip_member_lines(fetcher, url: str, suffix: str):
    """Stream one member of a remote zip with HTTP range requests, without downloading the rest."""
    with fetcher.open(url, headers={"Range": "bytes=-65536"}) as response:
        tail = response.read()
        total = int(response.headers["Content-Range"].rsplit("/", 1)[1])
    tail_start = total - len(tail)
    end = tail.rfind(b"PK\x05\x06")
    if end < 0:
        raise ValueError("zip end-of-directory record not found")
    directory_size, directory_offset = struct.unpack("<II", tail[end + 12:end + 20])
    if directory_offset >= tail_start:
        directory = tail[directory_offset - tail_start:directory_offset - tail_start + directory_size]
    else:
        directory = fetcher.get(url, headers={"Range": f"bytes={directory_offset}-{directory_offset + directory_size - 1}"})
    position, member = 0, None
    while position + 46 <= len(directory) and directory[position:position + 4] == b"PK\x01\x02":
        method, = struct.unpack("<H", directory[position + 10:position + 12])
        compressed, = struct.unpack("<I", directory[position + 20:position + 24])
        name_length, extra_length, comment_length = struct.unpack("<HHH", directory[position + 28:position + 34])
        offset, = struct.unpack("<I", directory[position + 42:position + 46])
        name = directory[position + 46:position + 46 + name_length].decode("utf-8", "replace")
        if name.endswith(suffix):
            member = (method, compressed, offset)
        position += 46 + name_length + extra_length + comment_length
    if member is None:
        raise ValueError(f"{suffix} not found in {url}")
    method, compressed, offset = member
    header = fetcher.get(url, headers={"Range": f"bytes={offset}-{offset + 29}"})
    name_length, extra_length = struct.unpack("<HH", header[26:30])
    start = offset + 30 + name_length + extra_length
    inflater = zlib.decompressobj(-15) if method == 8 else None
    buffer = b""
    with fetcher.open(url, headers={"Range": f"bytes={start}-{start + compressed - 1}"}, timeout=600) as response:
        while chunk := response.read(1 << 20):
            buffer += inflater.decompress(chunk) if inflater else chunk
            *lines, buffer = buffer.split(b"\n")
            for line in lines:
                yield line.decode("utf-8", "replace") + "\n"
    if inflater:
        buffer += inflater.flush()
    if buffer:
        yield buffer.decode("utf-8", "replace")


def _same_name(brand: str, owner: str) -> bool:
    """A brand name typed into the owner field ("RAO'S" owning "RAO'S HOMEMADE") is not an owner."""
    a, b = exact_key(brand), exact_key(owner)
    return a == b or a.startswith(b + " ") or b.startswith(a + " ")


def aggregate(rows, release: str) -> CollectorResult:
    pairs: dict[tuple[str, str], dict] = {}
    latest: dict[str, tuple[str, str, str]] = {}  # barcode -> (date, brand key, owner key) of its newest label
    for row in rows:
        brand, owner = (row.get("brand_name") or "").strip(), (row.get("brand_owner") or "").strip()
        if not brand or not owner or _same_name(brand, owner):
            continue
        key = (normalize(brand), normalize(owner))
        if not all(key):
            continue
        date = (row.get("modified_date") or row.get("available_date") or "")[:10]
        pair = pairs.setdefault(key, {"brand": brand, "owner": owner, "first": date, "last": date,
                                      "category": (row.get("branded_food_category") or "").strip()})
        if date and (not pair["first"] or date < pair["first"]):
            pair["first"] = date
        pair["last"] = max(pair["last"], date)
        if (gtin := (row.get("gtin_upc") or "").strip().lstrip("0")) and date >= latest.get(gtin, ("",))[0]:
            latest[gtin] = (date, *key)
    current = {(brand_key, owner_key) for _, brand_key, owner_key in latest.values()}
    entities: dict[str, Entity] = {}
    claims = []
    for (brand_key, owner_key), pair in sorted(pairs.items()):
        brand_ref, owner_ref = name_ref(pair["brand"]), name_ref(pair["owner"])
        entities.setdefault(brand_ref, Entity(id=brand_ref, kind="brand", name=smart_title(pair["brand"]), source=SOURCE,
                                              category=pair["category"]))
        entities.setdefault(owner_ref, Entity(id=owner_ref, kind="company", name=smart_title(pair["owner"]), source=SOURCE))
        claims.append(Claim(
            source=SOURCE, subject=brand_ref, relation="brand_of", object=owner_ref, observed=True,
            start=pair["first"] or None, end=None if (brand_key, owner_key) in current else (pair["last"] or None),
            source_url=SEARCH.format(query=urllib.parse.quote(pair["brand"])), source_record=f"FoodData Central {release}",
            excerpt=f"brand_owner = {pair['owner']} (label records {pair['first']} to {pair['last']})"[:200]))
    return CollectorResult(entities=list(entities.values()), claims=claims)


def collect(fetcher, store, run_date: str) -> CollectorResult:
    progress = dict(store.progress.get(SOURCE, {}))
    release = latest_release(fetcher.get(PAGE).decode("utf-8", "replace"))
    if not release:
        raise RuntimeError("no branded-foods release link on the USDA download page")
    if release == progress.get("release") and store.entities.get(SOURCE):
        return CollectorResult(unchanged=True, progress=progress)
    rows = csv.DictReader(zip_member_lines(fetcher, FILE.format(release=release), MEMBER))
    result = aggregate(rows, release)
    progress["release"] = release
    result.scope, result.progress = None, progress
    return result
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_usda -v`
Expected: 4 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/collectors/usda.py tests/test_usda.py
git commit -m "Collect grocery brand owners from USDA FoodData Central"
```

---

### Task 11: SEC Exhibit 21 collector

**Files:**
- Create: `pipeline/collectors/sec_ex21.py`
- Test: `tests/test_sec_ex21.py`

**Interfaces:**
- Consumes: store entities' `ids["cik"]`/`ids["ticker"]`, active control claims, and `public_company` classifications.
- Produces:
  - `parse_ex21(raw_bytes) -> [subsidiary names]`
  - `target_companies(store, tickers) -> [(entity_id, cik)]`
  - `exhibit_documents(fetcher, cik, since_year)`
  - `collect`:
    - Processes ≤400 companies per run, rotating a cursor.
    - Skips documents in `progress["seen_docs"]`.
    - Emits official, observed `controlled_by` claims to the registrant, keeping the earliest stored `start`.
    - Emits `public_company` classifications.
    - Returns `scope=set()`.

- [ ] **Step 1: Write the failing test**

`tests/test_sec_ex21.py`:

```python
import tempfile
import unittest
from pathlib import Path

from pipeline.collectors import sec_ex21
from pipeline.model import Claim, Classification, Entity
from pipeline.store import Store
from tests.helpers import FakeFetcher, url_is

TABLE = b"""<html><body><p>EXHIBIT 21</p><table>
<tr><td><b>Name of Subsidiary</b></td><td>Jurisdiction</td></tr>
<tr><td>Sovos Brands Intermediate Inc.</td><td>Delaware</td></tr>
<tr><td>Rao&#8217;s Specialty Foods, Inc. (1)</td><td>New York</td></tr>
<tr><td>Delaware</td><td></td></tr>
</table></body></html>"""
TEXT = b"SUBSIDIARIES OF THE REGISTRANT\n\nPepperidge Farm, Incorporated        Connecticut\nCampbell Sales Company   New Jersey\n"


class Parse(unittest.TestCase):
    def test_html_table_first_column_without_headers_or_places(self):
        self.assertEqual(sec_ex21.parse_ex21(TABLE), ["Sovos Brands Intermediate Inc", "Rao’s Specialty Foods, Inc"])

    def test_plain_text_columns(self):
        self.assertEqual(sec_ex21.parse_ex21(TEXT), ["Pepperidge Farm, Incorporated", "Campbell Sales Company"])


class Collect(unittest.TestCase):
    def setUp(self):
        self.store = Store(Path(tempfile.mkdtemp()))
        self.store.entities["wikipedia"] = {"Q1030544": Entity("Q1030544", "company", "Campbell's", "wikipedia", ids={"ticker": "Nasdaq: CPB"})}
        self.store.claims["wikipedia"] = {"k": Claim("wikipedia", "Q121775110", "controlled_by", "Q1030544")}
        hits = {"hits": {"hits": [
            {"_id": "0000016732-24-000130:cpb-ex21.htm", "_source": {"file_type": "EX-21", "ciks": ["0000016732"], "file_date": "2024-09-19", "period_ending": "2024-07-28"}},
            {"_id": "0000016732-24-000130:cpb-10k.htm", "_source": {"file_type": "10-K", "ciks": ["0000016732"], "file_date": "2024-09-19"}},
            {"_id": "0000099999-12-000001:old-ex21.htm", "_source": {"file_type": "EX-21", "ciks": ["0000016732"], "file_date": "2012-09-19"}},
        ]}}
        self.fetcher = FakeFetcher([
            (url_is(sec_ex21.TICKERS), {"0": {"cik_str": 16732, "ticker": "CPB", "title": "CAMPBELL'S Co"}}),
            (url_is("https://data.sec.gov/submissions/CIK0000016732.json"),
             {"name": "CAMPBELL'S Co", "tickers": ["CPB"], "exchanges": ["Nasdaq"], "formerNames": [{"name": "CAMPBELL SOUP CO"}]}),
            (url_is(sec_ex21.SEARCH), hits),
            (url_is("https://www.sec.gov/Archives/edgar/data/16732/000001673224000130/cpb-ex21.htm"), TABLE),
        ])

    def test_subsidiaries_become_official_observed_control_claims(self):
        result = sec_ex21.collect(self.fetcher, self.store, "2026-10-05")
        claim = next(c for c in result.claims if c.subject == "name:sovos brands intermediate inc")
        self.assertEqual((claim.object, claim.official, claim.observed, claim.start), ("Q1030544", True, True, "2024-07-28"))
        self.assertEqual(result.scope, set())  # dropping off Exhibit 21 never retracts control
        kinds = {(k.entity, k.kind, k.official) for k in result.classifications}
        self.assertEqual(kinds, {("Q1030544", "public_company", True)})
        campbell = next(e for e in result.entities if e.id == "Q1030544")
        self.assertIn("CAMPBELL SOUP CO", campbell.aliases)

    def test_documents_already_read_are_skipped_next_time(self):
        first = sec_ex21.collect(self.fetcher, self.store, "2026-10-05")
        self.store.apply("sec_ex21", first, "2026-10-05")
        second = sec_ex21.collect(self.fetcher, self.store, "2026-10-12")
        self.assertEqual(second.claims, [])
        self.assertEqual(sum(1 for url, _, _ in self.fetcher.calls if url.endswith("cpb-ex21.htm")), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_sec_ex21 -v`
Expected: ERROR, `ImportError: cannot import name 'sec_ex21'`

- [ ] **Step 3: Write the implementation**

`pipeline/collectors/sec_ex21.py`:

```python
"""SEC 10-K Exhibit 21: the subsidiaries public companies list each year."""

from __future__ import annotations

import html
import re

from ..model import Claim, Classification, CollectorResult, Entity, name_ref, normalize, pad_start

SOURCE = "sec_ex21"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEARCH = "https://efts.sec.gov/LATEST/search-index"
TICKERS = "https://www.sec.gov/files/company_tickers.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{filename}"
COMPANIES_PER_RUN = 400
YEARS = 10
_HEADER_START = ("name", "subsidiar", "jurisdiction", "state of", "exhibit", "list of", "the following", "percent",
                 "entity", "company name", "organized", "incorporat", "country")
_PLACES = {"delaware", "new york", "new jersey", "california", "texas", "ohio", "illinois", "nevada", "florida",
           "georgia", "michigan", "pennsylvania", "massachusetts", "virginia", "maryland", "united states",
           "canada", "mexico", "united kingdom", "england", "ireland", "netherlands", "germany", "france",
           "luxembourg", "cayman islands", "bermuda", "australia", "japan", "china", "hong kong", "singapore"}


def _clean(fragment: str) -> str:
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())
    text = re.sub(r"\s*\(\d+\)$", "", re.sub(r"^\d+\.\s+", "", text))  # "1. Name (2)" -> "Name"
    return text.strip(" .*†‡")


def parse_ex21(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", "replace")
    candidates = []
    if re.search(r"<tr[\s>]", text, re.I):
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
            cells = [c for c in (_clean(cell) for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)) if c]
            if cells:
                candidates.append(cells[0])
    else:
        body = html.unescape(re.sub(r"<[^>]+>", "\n", text))
        for line in body.splitlines():
            parts = re.split(r"\s{2,}|\t", line.strip())
            if parts and parts[0]:
                candidates.append(_clean(parts[0]))
    names, seen = [], set()
    for name in candidates:
        lower = name.lower()
        if (3 <= len(name) <= 150 and sum(ch.isalpha() for ch in name) >= 2 and not lower.startswith(_HEADER_START)
                and normalize(name) not in _PLACES and normalize(name) not in seen):
            seen.add(normalize(name))
            names.append(name)
    return names


def target_companies(store, tickers: dict[str, int]) -> list[tuple[str, int]]:
    """(entity id, CIK) for public companies and for every parent on an ownership chain."""
    merged: dict[str, dict] = {}
    for records in store.entities.values():
        for entity in records.values():
            merged.setdefault(entity.id, {}).update({k: v for k, v in entity.ids.items() if k in ("cik", "ticker")})
    parents = {c.object for c in store.all_claims() if c.status == "active" and c.relation in ("controlled_by", "brand_of")}
    public = {c.entity for c in store.all_classifications() if c.kind == "public_company"}
    chosen = []
    for entity_id in sorted(parents | public):
        ids = merged.get(entity_id, {})
        cik = int(ids["cik"]) if ids.get("cik", "").isdigit() else None
        if cik is None and ids.get("ticker"):
            cik = tickers.get(ids["ticker"].split(":")[-1].strip().upper())
        if cik:
            chosen.append((entity_id, cik))
    return chosen


def exhibit_documents(fetcher, cik: int, since_year: int) -> list[dict]:
    hits = fetcher.get_json(SEARCH, {"q": "subsidiaries", "ciks": f"{cik:010d}", "forms": "10-K"}).get("hits", {}).get("hits", [])
    documents = {}
    for hit in hits:
        source = hit.get("_source", {})
        if not str(source.get("file_type", "")).upper().startswith("EX-21"):
            continue
        if f"{cik:010d}" not in source.get("ciks", [])[:1] or int((source.get("file_date") or "0")[:4]) < since_year:
            continue
        accession, filename = hit["_id"].split(":", 1)
        documents[accession] = {"url": ARCHIVE.format(cik=cik, folder=accession.replace("-", ""), filename=filename),
                                "accession": accession, "period": source.get("period_ending") or source.get("file_date")}
    return sorted(documents.values(), key=lambda d: d["period"] or "")


def collect(fetcher, store, run_date: str) -> CollectorResult:
    progress = dict(store.progress.get(SOURCE, {}))
    tickers = {row["ticker"].upper(): int(row["cik_str"]) for row in fetcher.get_json(TICKERS).values()}
    companies = target_companies(store, tickers)
    if not companies:
        return CollectorResult(scope=set(), progress=progress)
    cursor = progress.get("cursor", 0) % len(companies)
    batch = (companies[cursor:] + companies[:cursor])[:COMPANIES_PER_RUN]
    seen_docs = set(progress.get("seen_docs", []))
    stored = store.claims.get(SOURCE, {})
    entities, claims, kinds = {}, [], []
    since_year = int(run_date[:4]) - YEARS
    for entity_id, cik in batch:
        submissions = fetcher.get_json(SUBMISSIONS.format(cik=cik))
        ids = {"cik": str(cik)}
        listed = [f"{exchange}: {symbol}" for symbol, exchange in zip(submissions.get("tickers", []), submissions.get("exchanges", [])) if exchange]
        if listed:
            ids["ticker"] = listed[0]
            kinds.append(Classification(entity=entity_id, kind="public_company", source=SOURCE, official=True,
                                        source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}",
                                        evidence=f"SEC registrant {submissions.get('name', '')}, {', '.join(listed)}"))
        aliases = [submissions.get("name", "")] + [f.get("name", "") for f in submissions.get("formerNames", [])]
        entities[entity_id] = Entity(id=entity_id, kind="company", name=submissions.get("name", entity_id), source=SOURCE,
                                     aliases=[a for a in aliases if a][:10], ids=ids)
        for document in exhibit_documents(fetcher, cik, since_year):
            if document["url"] in seen_docs:
                continue
            for subsidiary in parse_ex21(fetcher.get(document["url"])):
                ref = name_ref(subsidiary)
                entities.setdefault(ref, Entity(id=ref, kind="company", name=subsidiary, source=SOURCE))
                claim = Claim(source=SOURCE, subject=ref, relation="controlled_by", object=entity_id, official=True,
                              observed=True, start=document["period"], source_url=document["url"],
                              source_record=document["accession"],
                              excerpt=f"Listed in {submissions.get('name', '')} Exhibit 21 for period ending {document['period']}")
                previous = stored.get(claim.key)
                if previous and previous.start and pad_start(previous.start) < pad_start(claim.start):
                    claim.start = previous.start  # keep the earliest year it was listed
                claims.append(claim)
            seen_docs.add(document["url"])
    progress["cursor"] = (cursor + len(batch)) % len(companies)
    progress["seen_docs"] = sorted(seen_docs)
    # Dropping out of Exhibit 21 ends the observation, never the control, so nothing is retracted.
    return CollectorResult(entities=list(entities.values()), claims=claims, classifications=kinds, scope=set(),
                           progress=progress)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_sec_ex21 -v`
Expected: 4 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/collectors/sec_ex21.py tests/test_sec_ex21.py
git commit -m "Collect public-company subsidiaries from 10-K Exhibit 21"
```

---

### Task 12: Wikipedia page-history backfill

**Files:**
- Create: `pipeline/collectors/wikipedia_history.py`
- Test: `tests/test_wikipedia_history.py`

**Interfaces:**
- Consumes from Task 5: `API`, `OWNER_FIELDS`, `display_name`, `resolve_titles`.
- Produces:
  - `chain_titles(store)`
  - `yearly_revisions(fetcher, title, first_year, last_year) -> [("YYYY-01-01", revid)]`
  - `revision_texts(fetcher, revids)`
  - `periods(observations) -> [(OwnerRef, first_date, first_revid, absent_date|None)]`. A one-sample gap is treated as present.
  - `collect` processes chain pages not in `progress["done"]` within a 6,000-request budget. It emits `controlled_by` claims with `observed=True` unless the infobox gave dates. Returns `scope=set()`.

- [ ] **Step 1: Write the failing test**

`tests/test_wikipedia_history.py`:

```python
import tempfile
import unittest
from pathlib import Path

from pipeline.collectors import wikipedia_history as history
from pipeline.collectors.wikitext import OwnerRef
from pipeline.model import Claim, Entity
from pipeline.store import Store
from tests.helpers import FakeFetcher, url_is


def ref(name):
    return OwnerRef(name, name, None, None, None)


class Periods(unittest.TestCase):
    def test_owner_changes_become_dated_periods(self):
        found = history.periods([("2016-01-01", 1, [ref("Advent")]), ("2017-01-01", 2, [ref("Advent")]),
                                 ("2018-01-01", 3, [ref("Campbell's")])])
        summary = {(r.target, first, revid, absent) for r, first, revid, absent in found}
        self.assertEqual(summary, {("Advent", "2016-01-01", 1, "2018-01-01"), ("Campbell's", "2018-01-01", 3, None)})

    def test_one_vandalized_sample_does_not_invent_a_change(self):
        found = history.periods([("2016-01-01", 1, [ref("A")]), ("2017-01-01", 2, []), ("2018-01-01", 3, [ref("A")])])
        self.assertEqual([(r.target, first, absent) for r, first, _, absent in found], [("A", "2016-01-01", None)])


REVISIONS = {"query": {"pages": [{"title": "Sovos Brands", "revisions": [
    {"revid": 100, "timestamp": "2021-06-01T00:00:00Z"}, {"revid": 200, "timestamp": "2024-03-19T00:00:00Z"}]}]}}
TEXTS = {100: "{{Infobox company\n| owner = [[Advent International]]\n}}",
         200: "{{Infobox company\n| parent = [[Campbell Soup Company|Campbell's]] (2024–present)\n}}"}


def api(url, params, headers):
    if params.get("rvprop") == "ids|timestamp":
        return REVISIONS
    if "revids" in params:
        return {"query": {"pages": [{"title": "Sovos Brands", "revisions": [
            {"revid": int(r), "slots": {"main": {"content": TEXTS[int(r)]}}} for r in params["revids"].split("|")]}]}}
    titles = params["titles"].split("|")
    steps = [{"from": "Campbell Soup Company", "to": "Campbell's"}] if "Campbell Soup Company" in titles else []
    qids = {"Advent International": "Q379801", "Campbell's": "Q1030544"}
    return {"query": {"redirects": steps, "pages": [{"title": t, "pageprops": {"wikibase_item": qids[t]}}
                                                    for t in {s["to"] for s in steps} | (set(titles) - {"Campbell Soup Company"})]}}


class Collect(unittest.TestCase):
    def test_backfills_chain_pages_once(self):
        store = Store(Path(tempfile.mkdtemp()))
        store.entities["wikipedia"] = {"Q121775110": Entity("Q121775110", "company", "Sovos Brands", "wikipedia", ids={"wikipedia": "Sovos Brands"})}
        store.claims["wikipedia"] = {"k": Claim("wikipedia", "Q121775110", "controlled_by", "Q1030544")}
        result = history.collect(FakeFetcher([(url_is(history.API), api)]), store, "2026-10-05")
        found = {(c.object, c.start, c.end, c.observed) for c in result.claims}
        self.assertIn(("Q379801", "2022-01-01", "2025-01-01", True), found)
        self.assertIn(("Q1030544", "2024", None, False), found)
        self.assertEqual((result.scope, result.progress["done"]), (set(), ["Sovos Brands"]))
        store.apply("wikipedia_history", result, "2026-10-05")
        again = history.collect(FakeFetcher([]), store, "2026-10-06")  # nothing left to fetch
        self.assertEqual(again.claims, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_wikipedia_history -v`
Expected: ERROR, `ImportError: cannot import name 'wikipedia_history'`

- [ ] **Step 3: Write the implementation**

`pipeline/collectors/wikipedia_history.py`:

```python
"""Wikipedia page history: past owners, observed from one infobox revision per year."""

from __future__ import annotations

from ..model import Claim, CollectorResult, Entity, chunks, name_ref
from .wikipedia import API, OWNER_FIELDS, display_name, resolve_titles
from .wikitext import OwnerRef, page_facts, parse_owners

SOURCE = "wikipedia_history"
FIRST_YEAR = 2010
REQUEST_BUDGET = 6000  # per run; the one-time backfill finishes over several nights


def chain_titles(store) -> set[str]:
    """Titles of Wikipedia pages that are on an ownership chain today."""
    pages = store.entities.get("wikipedia", {})
    refs = {r for c in store.claims.get("wikipedia", {}).values() if c.status == "active"
            and c.relation in ("controlled_by", "brand_of") for r in (c.subject, c.object)}
    return {pages[r].ids["wikipedia"] for r in refs if r in pages and pages[r].ids.get("wikipedia")}


def yearly_revisions(fetcher, title: str, first_year: int, last_year: int) -> list[tuple[str, int]]:
    """(1 January of each year, revision in effect that day), oldest first."""
    revisions: list[tuple[str, int]] = []
    params = {"action": "query", "prop": "revisions", "titles": title, "rvprop": "ids|timestamp", "rvlimit": "500",
              "rvdir": "newer", "rvstart": f"{first_year - 1}-01-01T00:00:00Z", "format": "json",
              "formatversion": "2", "maxlag": "5"}
    cont: dict = {}
    while True:
        data = fetcher.get_json(API, {**params, **cont})
        for page in data.get("query", {}).get("pages", []):
            revisions.extend((r["timestamp"], r["revid"]) for r in page.get("revisions", []))
        if "continue" not in data:
            break
        cont = data["continue"]
    samples = []
    for year in range(first_year, last_year + 1):
        before = [revid for timestamp, revid in revisions if timestamp < f"{year}-01-01T00:00:00Z"]
        if before:
            samples.append((f"{year}-01-01", before[-1]))
    return samples


def revision_texts(fetcher, revids) -> dict[int, str]:
    texts = {}
    for batch in chunks(sorted(set(revids)), 50):
        data = fetcher.get_json(API, {"action": "query", "prop": "revisions", "revids": "|".join(map(str, batch)),
                                      "rvprop": "content|ids", "rvslots": "main", "rvsection": "0",
                                      "format": "json", "formatversion": "2", "maxlag": "5"})
        for page in data.get("query", {}).get("pages", []):
            for revision in page.get("revisions", []):
                texts[revision["revid"]] = revision.get("slots", {}).get("main", {}).get("content", "")
    return texts


def periods(observations: list[tuple[str, int, list[OwnerRef]]]) -> list[tuple[OwnerRef, str, int, str | None]]:
    """(owner, first date seen, revision first seen, first date absent or None).

    An owner missing from a single sample but back in the next is treated as present,
    so one vandalized revision cannot invent a change of ownership.
    """
    present = [{(r.target or r.text): r for r in refs if r.target or r.text} for _, _, refs in observations]
    for index in range(1, len(present) - 1):
        for key, ref in present[index - 1].items():
            if key not in present[index] and key in present[index + 1]:
                present[index][key] = ref
    found, open_periods = [], {}
    for (date, revid, _), owners in zip(observations, present):
        for key in [k for k in open_periods if k not in owners]:
            ref, first_date, first_revid = open_periods.pop(key)
            found.append((ref, first_date, first_revid, date))
        for key, ref in owners.items():
            open_periods.setdefault(key, (ref, date, revid))
    found.extend((ref, first_date, first_revid, None) for ref, first_date, first_revid in open_periods.values())
    return found


def collect(fetcher, store, run_date: str) -> CollectorResult:
    progress = dict(store.progress.get(SOURCE, {}))
    done = set(progress.get("done", []))
    pages = {e.ids.get("wikipedia"): e for e in store.entities.get("wikipedia", {}).values()}
    entities: dict[str, Entity] = {}
    claims: list[Claim] = []
    start = fetcher.requests
    for title in sorted(chain_titles(store) - done):
        if fetcher.requests - start >= REQUEST_BUDGET:
            break
        samples = yearly_revisions(fetcher, title, FIRST_YEAR, int(run_date[:4]))
        texts = revision_texts(fetcher, [revid for _, revid in samples])
        observations = [(date, revid, [ref for name in OWNER_FIELDS
                                       for ref in parse_owners(page_facts(texts[revid]).fields.get(name, ""))])
                        for date, revid in samples if revid in texts]
        found = periods(observations)
        resolved = resolve_titles(fetcher, {ref.target for ref, *_ in found if ref.target})
        subject = pages[title].id
        for ref, first_date, first_revid, absent_date in found:
            if ref.target in resolved:
                canonical, qid = resolved[ref.target]
                obj = qid or f"wp:{canonical}"
                entities.setdefault(obj, Entity(id=obj, kind="company", name=display_name(canonical), source=SOURCE,
                                                ids={k: v for k, v in (("wikipedia", canonical), ("wikidata", qid)) if v}))
            else:
                obj = name_ref(ref.text)
                entities.setdefault(obj, Entity(id=obj, kind="company", name=ref.text, source=SOURCE))
            if obj == subject:
                continue
            claims.append(Claim(
                source=SOURCE, subject=subject, object=obj,
                relation="minority_stake" if ref.percent is not None and ref.percent < 50 else "controlled_by",
                start=ref.start or first_date, end=ref.end or absent_date,
                observed=not (ref.start or ref.end),
                source_url=f"https://en.wikipedia.org/w/index.php?oldid={first_revid}", source_record=str(first_revid),
                excerpt=f"Infobox listed {ref.text} from {first_date} until {absent_date or 'now'}"))
        done.add(title)
    progress["done"] = sorted(done)
    # Past revisions never change, so these observations are only ever added.
    return CollectorResult(entities=list(entities.values()), claims=claims, scope=set(), progress=progress)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_wikipedia_history -v`
Expected: 3 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/collectors/wikipedia_history.py tests/test_wikipedia_history.py
git commit -m "Backfill past owners from yearly Wikipedia revisions"
```

---

### Task 13: Entity resolution

**Files:**
- Create: `pipeline/resolve.py`
- Test: `tests/test_resolve.py`

**Interfaces:**
- Produces:
  - `resolve(entities, claims, classifications) -> Graph`, where `Graph` has:
    - `nodes: {id: Node(id, kind, name, aliases, ids, category, sources, members)}`
    - `canonical: {ref: node_id}`
    - `claims`, rewritten to node IDs, with self-loops dropped and `via_family` set
    - `classifications: {node_id: [Classification]}`
    - `possibly_same_as: [(ref, candidate, reason)]`, never used in verdicts
  - Node ID preference: QID, then `wp:`, `cik:`, `crd:`, `fund:`, `nsi:`, `name:`.
- Merge rules, in order:
  1. Shared strong IDs (`wikidata`, `wikipedia`, `cik`, `crd`, `nsi`, `fund`). Two different QIDs never merge.
  2. `name:` refs with the same `exact_key` merge. They then join a strong node only when that node is the **unique** owner of that exact name or alias. Otherwise the match goes to `possibly_same_as`.
  3. Remaining, non-ambiguous `name:` refs join by `family_key`, and their claims get `via_family=True`.

- [ ] **Step 1: Write the failing test**

`tests/test_resolve.py`:

```python
import unittest

from pipeline.model import Claim, Classification, Entity
from pipeline.resolve import resolve


def entity(id, name, source="wikipedia", kind="company", aliases=(), **ids):
    return Entity(id=id, kind=kind, name=name, source=source, aliases=list(aliases), ids=dict(ids))


def link(subject, obj, source="usda", relation="brand_of"):
    return Claim(source=source, subject=subject, relation=relation, object=obj)


class StrongIdentifiers(unittest.TestCase):
    def test_same_qid_across_sources_is_one_node_named_by_the_best_source(self):
        graph = resolve([entity("Q509255", "BWW brand", "nsi", "brand", ["bww"], wikidata="Q509255"),
                         entity("Q509255", "Buffalo Wild Wings", "wikipedia", wikidata="Q509255")], [], [])
        node = graph.nodes["Q509255"]
        self.assertEqual((node.name, node.kind, node.sources), ("Buffalo Wild Wings", "brand", ["nsi", "wikipedia"]))
        self.assertIn("bww", node.aliases)

    def test_shared_wikipedia_title_links_a_page_without_qid(self):
        graph = resolve([entity("wp:Foo", "Foo", wikipedia="Foo"), entity("Q9", "Foo", "wikidata", wikidata="Q9", wikipedia="Foo")], [], [])
        self.assertEqual(graph.canonical["wp:Foo"], "Q9")

    def test_two_wikidata_items_never_merge(self):
        graph = resolve([entity("Q1", "Foo", nsi="x"), entity("Q2", "Foo", "nsi", nsi="x")], [], [])
        self.assertNotEqual(graph.canonical["Q1"], graph.canonical["Q2"])
        self.assertTrue(graph.possibly_same_as)


class Names(unittest.TestCase):
    def test_name_reference_matches_a_unique_identity_name_or_redirect(self):
        graph = resolve([entity("Q1030544", "Campbell's", aliases=["Campbell Soup Company"]),
                         entity("name:campbell soup company", "CAMPBELL SOUP COMPANY", "usda")],
                        [link("name:pace", "name:campbell soup company")], [])
        self.assertEqual(graph.canonical["name:campbell soup company"], "Q1030544")
        self.assertEqual(graph.claims[0].object, "Q1030544")
        self.assertFalse(graph.claims[0].via_family)

    def test_same_legal_name_with_different_suffix_is_one_node(self):
        graph = resolve([entity("name:noosa yoghurt llc", "Noosa Yoghurt, LLC", "sec_ex21"),
                         entity("name:noosa yoghurt", "Noosa Yoghurt", "wikipedia", "brand")], [], [])
        self.assertEqual(graph.canonical["name:noosa yoghurt llc"], graph.canonical["name:noosa yoghurt"])

    def test_ambiguous_name_stays_separate(self):
        graph = resolve([entity("Q1", "Apollo"), entity("Q2", "Apollo", "wikipedia"), entity("name:apollo", "Apollo", "ftc")], [], [])
        self.assertEqual(graph.canonical["name:apollo"], "name:apollo")
        self.assertEqual(len([p for p in graph.possibly_same_as if p[0] == "name:apollo"]), 2)

    def test_corporate_family_rule_joins_holding_entities_and_marks_claims(self):
        graph = resolve([entity("Q121775110", "Sovos Brands"),
                         entity("name:sovos brands intermediate inc", "Sovos Brands Intermediate, Inc.", "usda")],
                        [link("name:raos homemade", "name:sovos brands intermediate inc")], [])
        self.assertEqual(graph.canonical["name:sovos brands intermediate inc"], "Q121775110")
        self.assertTrue(graph.claims[0].via_family)

    def test_self_loops_after_merging_are_dropped_and_classifications_follow(self):
        graph = resolve([entity("Q1", "Acme", aliases=["Acme Holdings"]), entity("name:acme holdings", "Acme Holdings", "ftc")],
                        [link("name:acme holdings", "Q1", relation="controlled_by")],
                        [Classification("name:acme holdings", "public_company", "sec_ex21", "x")])
        self.assertEqual(graph.claims, [])
        self.assertEqual([c.entity for c in graph.classifications["Q1"]], ["Q1"])

    def test_references_without_records_get_stub_nodes(self):
        graph = resolve([], [link("name:a", "name:b")], [])
        self.assertEqual((graph.nodes["name:b"].name, graph.nodes["name:b"].sources), ("b", []))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_resolve -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'pipeline.resolve'`

- [ ] **Step 3: Write the implementation**

`pipeline/resolve.py`:

```python
"""Merge records from every source into one node per real-world entity."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace

from .model import SOURCE_PRIORITY, Claim, Classification, Entity, exact_key, family_key, normalize, smart_title

STRONG_KEYS = ("wikidata", "wikipedia", "cik", "crd", "nsi", "fund")
_ID_RANK = ("Q", "wp:", "cik:", "crd:", "fund:", "nsi:", "name:")
_CATEGORY_PRIORITY = ("nsi", "usda")


@dataclass
class Node:
    id: str
    kind: str
    name: str
    aliases: list[str]
    ids: dict[str, str]
    category: str
    sources: list[str]
    members: list[str]


@dataclass
class Graph:
    nodes: dict[str, Node]
    canonical: dict[str, str]  # every reference -> node id
    claims: list[Claim]  # subject/object rewritten to node ids
    classifications: dict[str, list[Classification]]  # node id -> records
    possibly_same_as: list[tuple[str, str, str]] = field(default_factory=list)  # never used in verdicts


class _Groups:
    """Union-find that refuses to join two different Wikidata items."""

    def __init__(self):
        self.parent: dict[str, str] = {}
        self.qid: dict[str, str] = {}

    def find(self, ref: str) -> str:
        self.parent.setdefault(ref, ref)
        root = ref
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[ref] != root:
            self.parent[ref], ref = root, self.parent[ref]
        return root

    def union(self, a: str, b: str) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return True
        qa, qb = self.qid.get(ra), self.qid.get(rb)
        if qa and qb and qa != qb:
            return False
        self.parent[rb] = ra
        if qb and not qa:
            self.qid[ra] = qb
        return True


def _rank(ref: str) -> tuple:
    for index, prefix in enumerate(_ID_RANK):
        if ref.startswith(prefix) and (prefix != "Q" or ref[1:].isdigit()):
            return (index, ref)
    return (len(_ID_RANK), ref)


def _priority(source: str) -> int:
    return SOURCE_PRIORITY.index(source) if source in SOURCE_PRIORITY else len(SOURCE_PRIORITY)


def _stub_name(ref: str) -> str:
    return ref.split(":", 1)[1] if ref.startswith(("name:", "wp:")) else ref


def resolve(entities: list[Entity], claims: list[Claim], classifications: list[Classification]) -> Graph:
    records: dict[str, list[Entity]] = defaultdict(list)
    for entity in entities:
        records[entity.id].append(entity)
    for ref in [r for c in claims for r in (c.subject, c.object)] + [c.entity for c in classifications]:
        if ref not in records:
            records[ref].append(Entity(id=ref, kind="company", name=_stub_name(ref), source="stub"))

    groups = _Groups()
    for ref, recs in records.items():
        groups.find(ref)
        qid = ref if _rank(ref)[0] == 0 else next((r.ids["wikidata"] for r in recs if r.ids.get("wikidata")), None)
        if qid:
            groups.qid[ref] = qid
    possibly: list[tuple[str, str, str]] = []

    # 1. Strong identifiers.
    holder: dict[tuple[str, str], str] = {}
    for ref, recs in records.items():
        for record in recs:
            for key in STRONG_KEYS:
                value = record.ids.get(key)
                if not value:
                    continue
                if (key, value) in holder:
                    if not groups.union(holder[(key, value)], ref):
                        possibly.append((ref, holder[(key, value)], f"shared {key} but different Wikidata items"))
                else:
                    holder[(key, value)] = ref

    # 2. Name-only references: same legal name across sources, then an exact match
    #    to a name an identity source (Wikipedia title/redirect, Wikidata label, SEC, ADV) uses.
    name_refs = sorted(r for r in records if r.startswith("name:"))
    identity: dict[str, set[str]] = defaultdict(set)
    family_index: dict[str, set[str]] = defaultdict(set)
    for ref, recs in records.items():
        if ref.startswith("name:"):
            continue
        for record in recs:
            if record.source == "stub":
                continue
            for label in (record.name, *record.aliases):
                if key := exact_key(label):
                    identity[key].add(ref)
                if key := family_key(label):
                    family_index[key].add(ref)
    ambiguous: set[str] = set()  # left alone by the family rule too
    by_exact: dict[str, list[str]] = defaultdict(list)
    for ref in name_refs:
        by_exact[exact_key(_stub_name(ref))].append(ref)
    for key, refs in by_exact.items():
        for ref in refs[1:]:
            groups.union(refs[0], ref)
        candidates = {groups.find(r) for r in identity.get(key, ())}
        if len(candidates) == 1:
            groups.union(candidates.pop(), refs[0])
        elif len(candidates) > 1:
            ambiguous.update(refs)
            possibly.extend((refs[0], c, "same name as several entities") for c in sorted(candidates))

    # 3. Corporate-family rule ("Sovos Brands Intermediate, Inc." -> "Sovos Brands"), reported only.
    resolved_roots = {groups.find(r) for r in records if not r.startswith("name:")}
    family_merged: set[str] = set()
    by_family: dict[str, list[str]] = defaultdict(list)
    for ref in name_refs:
        if groups.find(ref) not in resolved_roots and ref not in ambiguous:
            by_family[family_key(_stub_name(ref))].append(ref)
    for key, refs in by_family.items():
        if len(key) < 3:
            continue
        candidates = {groups.find(r) for r in family_index.get(key, ())}
        if len(candidates) > 1:
            possibly.extend((refs[0], c, "same corporate family as several entities") for c in sorted(candidates))
            continue
        anchor = candidates.pop() if candidates else refs[0]
        for ref in refs:
            if groups.find(ref) != groups.find(anchor) and groups.union(anchor, ref):
                family_merged.add(ref)

    members: dict[str, list[str]] = defaultdict(list)
    for ref in records:
        members[groups.find(ref)].append(ref)
    canonical: dict[str, str] = {}
    nodes: dict[str, Node] = {}
    for group in members.values():
        node_id = min(group, key=_rank)
        recs = sorted((r for ref in group for r in records[ref]), key=lambda r: (_priority(r.source), r.id))
        named = [r for r in recs if r.source != "stub"] or recs
        name = smart_title(named[0].name)
        kinds = {r.kind for r in named}
        kind = next((k for k in ("adviser", "fund", "brand") if k in kinds), "company")
        seen = {normalize(name)}
        aliases = []
        for record in recs:
            for label in (record.name, *record.aliases):
                if label and normalize(label) not in seen:
                    seen.add(normalize(label))
                    aliases.append(smart_title(label))
        ids: dict[str, str] = {}
        for record in recs:
            for key, value in record.ids.items():
                ids.setdefault(key, value)
        category = next((r.category for source in _CATEGORY_PRIORITY for r in recs if r.source == source and r.category),
                        next((r.category for r in recs if r.category), ""))
        nodes[node_id] = Node(node_id, kind, name, aliases[:25], ids, category,
                              sorted({r.source for r in recs} - {"stub"}), sorted(group))
        for ref in group:
            canonical[ref] = node_id

    rewritten = []
    for claim in claims:
        subject, obj = canonical[claim.subject], canonical[claim.object]
        if subject != obj:
            rewritten.append(replace(claim, subject=subject, object=obj,
                                     via_family=claim.subject in family_merged or claim.object in family_merged))
    by_node: dict[str, list[Classification]] = defaultdict(list)
    for record in classifications:
        by_node[canonical[record.entity]].append(replace(record, entity=canonical[record.entity]))
    return Graph(nodes, canonical, rewritten, dict(by_node), possibly)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_resolve -v`
Expected: 9 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/resolve.py tests/test_resolve.py
git commit -m "Resolve records into entities without unsafe name merges"
```

---

### Task 14: Owner classification

**Files:**
- Create: `pipeline/classify.py`
- Test: `tests/test_classify.py`

**Interfaces:**
- Consumes: `Graph` (Task 13).
- Produces:
  - `classify(graph) -> {node_id: OwnerKind(kind, confidence, evidence)}`
  - `FINANCIAL = ("pe_firm", "investment_firm")`
  - `match_advisers(graph, records)`
- Rules:
  - Precedence: `pe_firm` > `investment_firm` > `public_company` > `private_company`.
  - Form ADV evidence transfers to a node **only if Wikipedia/Wikidata already describe it as an investment or PE firm**, matched by a shared website domain or an `adviser_core` name.
  - Unmatched hits go to `possibly_same_as`.

- [ ] **Step 1: Write the failing test**

`tests/test_classify.py`:

```python
import unittest

from pipeline.classify import classify
from pipeline.model import Classification, Entity
from pipeline.resolve import resolve


def kind(entity, kind, source="wikipedia", official=False):
    return Classification(entity=entity, kind=kind, source=source, evidence=f"{source} says {kind}", official=official)


ADVISERS = [Entity("crd:160368", "adviser", "Roark Capital Management, LLC", "adv", ids={"crd": "160368", "website_domains": "roarkcapital.com"}),
            Entity("crd:107038", "adviser", "J.P. Morgan Investment Management Inc.", "adv", ids={"crd": "107038", "website_domains": "jpmorganchase.com"}),
            Entity("crd:42", "adviser", "Summit Partners, L.P.", "adv", ids={"crd": "42"})]
ADV_KINDS = [kind("crd:160368", "pe_firm", "adv", True), kind("crd:107038", "pe_firm", "adv", True), kind("crd:42", "pe_firm", "adv", True)]


def run(entities, kinds):
    return classify(resolve(ADVISERS + entities, [], ADV_KINDS + kinds))


class Precedence(unittest.TestCase):
    def test_pe_beats_public_and_confidence_needs_official_or_two_groups(self):
        result = classify(resolve([Entity("Q1", "company", "X", "wikipedia")], [],
                                  [kind("Q1", "public_company"), kind("Q1", "pe_firm"), kind("Q1", "pe_firm", "wikidata")]))
        self.assertEqual((result["Q1"].kind, result["Q1"].confidence), ("pe_firm", "reported"))  # Wikipedia+Wikidata = one group


class AdviserMatching(unittest.TestCase):
    def test_described_firm_matched_by_domain_is_confirmed_pe(self):
        result = run([Entity("Q7339900", "company", "Roark Capital Group", "wikipedia", ids={"website_domain": "roarkcapital.com"})],
                     [kind("Q7339900", "investment_firm")])
        self.assertEqual((result["Q7339900"].kind, result["Q7339900"].confidence), ("pe_firm", "confirmed"))
        self.assertIn("Roark Capital Management", result["Q7339900"].evidence[0]["evidence"])

    def test_bank_with_pe_funds_is_not_turned_into_a_pe_firm(self):
        result = run([Entity("Q192314", "company", "JPMorgan Chase", "wikipedia", ids={"website_domain": "jpmorganchase.com"})],
                     [kind("Q192314", "public_company")])
        self.assertEqual(result["Q192314"].kind, "public_company")

    def test_name_match_needs_an_investment_description(self):
        result = run([Entity("Q5", "company", "Summit Group", "wikipedia")], [kind("Q5", "private_company")])
        self.assertEqual(result["Q5"].kind, "private_company")
        result = run([Entity("Q6", "company", "Summit Partners", "wikipedia")], [kind("Q6", "investment_firm")])
        self.assertEqual(result["Q6"].kind, "pe_firm")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_classify -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'pipeline.classify'`

- [ ] **Step 3: Write the implementation**

`pipeline/classify.py`:

```python
"""Decide what kind of owner each node is: PE firm, investment firm, public or private company."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .model import SOCIAL_DOMAINS, SOURCE_GROUPS, Classification, adviser_core
from .resolve import Graph, Node

PRECEDENCE = ("pe_firm", "investment_firm", "public_company", "private_company")
FINANCIAL = ("pe_firm", "investment_firm")
_DESCRIBING_SOURCES = ("wikipedia", "wikidata")


@dataclass
class OwnerKind:
    kind: str
    confidence: str  # confirmed | reported
    evidence: list[dict]


def _domains(node: Node) -> set[str]:
    values = [node.ids.get("website_domain", ""), *node.ids.get("website_domains", "").split()]
    return {d for d in values if d and d not in SOCIAL_DOMAINS}


def match_advisers(graph: Graph, records: dict[str, list[Classification]]) -> list[tuple[str, list[str], str]]:
    """Link SEC-registered advisers to the investment firms Wikipedia/Wikidata describe.

    Form ADV only upgrades and confirms a firm that an encyclopedia already describes as
    an investment or PE firm. It never turns an operating company (a bank, say) into a PE firm.
    """
    by_domain: dict[str, set[str]] = defaultdict(set)
    by_core: dict[str, set[str]] = defaultdict(set)
    for node in graph.nodes.values():
        if node.kind != "adviser":
            continue
        for domain in _domains(node):
            by_domain[domain].add(node.id)
        for label in (node.name, *node.aliases):
            if core := adviser_core(label):
                by_core[core].add(node.id)
    matches = []
    for node in graph.nodes.values():
        if node.kind in ("adviser", "fund"):
            continue
        described = any(r.kind in FINANCIAL and r.source in _DESCRIBING_SOURCES for r in records.get(node.id, []))
        domain_hits = set().union(*(by_domain.get(d, set()) for d in _domains(node)))
        core_hits = set().union(*(by_core.get(c, set()) for c in {adviser_core(l) for l in (node.name, *node.aliases)} if c))
        if described and domain_hits:
            matches.append((node.id, sorted(domain_hits), "website domain"))
        elif described and core_hits:
            matches.append((node.id, sorted(core_hits), "name"))
        else:
            graph.possibly_same_as.extend((node.id, a, "adviser match without corroboration")
                                          for a in sorted(domain_hits | core_hits))
    return matches


def classify(graph: Graph) -> dict[str, OwnerKind]:
    records = {node_id: list(items) for node_id, items in graph.classifications.items()}
    for node_id, adviser_ids, how in match_advisers(graph, records):
        for adviser_id in adviser_ids:
            for record in records.get(adviser_id, []):
                if record.source == "adv":
                    records.setdefault(node_id, []).append(Classification(
                        entity=node_id, kind=record.kind, source="adv", official=True, source_url=record.source_url,
                        evidence=f"Matched SEC Form ADV adviser {graph.nodes[adviser_id].name} by {how}. {record.evidence}"))
    result = {}
    for node_id, items in records.items():
        kinds = {r.kind for r in items}
        chosen = next((k for k in PRECEDENCE if k in kinds), None)
        if chosen is None:
            continue
        chosen_items = [r for r in items if r.kind == chosen]
        groups = {SOURCE_GROUPS.get(r.source, r.source) for r in chosen_items}
        confidence = "confirmed" if any(r.official for r in chosen_items) or len(groups) >= 2 else "reported"
        evidence = [{"source": r.source, "evidence": r.evidence, "url": r.source_url, "official": r.official}
                    for r in sorted(chosen_items, key=lambda r: (not r.official, r.source))]
        result[node_id] = OwnerKind(chosen, confidence, evidence[:6])
    return result
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_classify -v`
Expected: 4 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/classify.py tests/test_classify.py
git commit -m "Classify owners, confirming PE firms through Form ADV"
```

---

### Task 15: Verdicts

**Files:**
- Create: `pipeline/verdict.py`
- Test: `tests/test_verdict.py`

**Interfaces:**
- Consumes: `Graph`, `OwnerKind`.
- Produces: `build_verdicts(graph, kinds, as_of) -> {node_id: verdict}`, for nodes of kind `brand`/`company` only. Each verdict dict has:
  - `id`, `name`, `kind`, `category`, `aliases`, `sources`
  - `tier` (`pe_owned|investment_owned|corporate_owned|no_signals|owner`)
  - `owner` (`{id, name, kind}|None`), `since`, `since_observed`, `confidence`
  - `flags` (each with `type` of `formerly_pe|formerly_investment|changed_hands|flipped|rollup`)
  - `chain` (nodes with `owner_kind`, `relation`, `confidence`, `since`, `alternatives`, `evidence`)
  - `history`, `deals`, `minority`, `ticker`, `owner_kind`, `kind_evidence`
  - `controls` (+ `controls_count` on owner cards), `as_of`
- Also exported: `is_current`, `has_ended`, `edge_confidence`, `SOURCE_NAMES`, and the threshold constants.

- [ ] **Step 1: Write the failing test**

`test_owner_that_ended_earlier_this_year_is_history_not_a_rival` pins Review Focus #4.

`tests/test_verdict.py`:

```python
import unittest

from pipeline.classify import OwnerKind
from pipeline.model import Claim, Entity
from pipeline.resolve import resolve
from pipeline.verdict import build_verdicts

AS_OF = "2026-10-05"


def node(id, kind="company", category=""):
    return Entity(id=id, kind=kind, name=id.upper(), source="wikipedia", category=category)


def edge(subject, obj, source="wikipedia", start=None, end=None, relation="controlled_by", **extra):
    return Claim(source=source, subject=subject, relation=relation, object=obj, start=start, end=end,
                 source_url=f"https://example.org/{subject}", **extra)


def verdicts(entities, claims, kinds):
    graph = resolve(entities, claims, [])
    owner_kinds = {k: OwnerKind(v[0], v[1] if len(v) > 1 else "confirmed", []) for k, v in kinds.items()}
    return build_verdicts(graph, owner_kinds, AS_OF)


class Tiers(unittest.TestCase):
    def test_pe_anywhere_in_the_chain(self):
        v = verdicts([node("brand", "brand"), node("holdco"), node("pe")],
                     [edge("brand", "holdco", start="2018"), edge("holdco", "pe")], {"pe": ("pe_firm",)})["brand"]
        self.assertEqual((v["tier"], v["owner"]["id"], v["since"], v["confidence"]), ("pe_owned", "pe", "2018", "reported"))
        self.assertEqual([n["id"] for n in v["chain"]], ["brand", "holdco", "pe"])

    def test_public_listing_does_not_cancel_pe_control(self):
        v = verdicts([node("jm"), node("bx")], [edge("jm", "bx")], {"jm": ("public_company",), "bx": ("pe_firm",)})["jm"]
        self.assertEqual(v["tier"], "pe_owned")

    def test_investment_then_corporate_then_no_signals(self):
        result = verdicts([node("a"), node("jab"), node("b"), node("corp"), node("c")],
                          [edge("a", "jab"), edge("b", "corp")], {"jab": ("investment_firm",), "corp": ("public_company",)})
        self.assertEqual((result["a"]["tier"], result["b"]["tier"], result["c"]["tier"]),
                         ("investment_owned", "corporate_owned", "no_signals"))
        self.assertEqual(result["b"]["owner"]["id"], "corp")

    def test_minority_stake_is_shown_but_not_flagged(self):
        v = verdicts([node("a"), node("pe")], [edge("a", "pe", relation="minority_stake")], {"pe": ("pe_firm",)})["a"]
        self.assertEqual((v["tier"], v["minority"][0]["owner"]["id"]), ("no_signals", "pe"))

    def test_firms_get_owner_cards_listing_what_they_control(self):
        result = verdicts([node("pe"), node("x"), node("y")], [edge("x", "pe"), edge("y", "pe")], {"pe": ("pe_firm",)})
        self.assertEqual((result["pe"]["tier"], [c["id"] for c in result["pe"]["controls"]]), ("owner", ["x", "y"]))

    def test_advisers_and_funds_have_no_pages_but_count_in_chains(self):
        entities = [node("target"), Entity("fund:1", "fund", "Fund VI", "adv"), Entity("crd:1", "adviser", "Adviser", "adv")]
        result = verdicts(entities, [edge("target", "fund:1", "ftc", official=True), edge("fund:1", "crd:1", "adv", relation="fund_of", official=True)],
                          {"crd:1": ("pe_firm",)})
        self.assertEqual(set(result), {"target"})
        self.assertEqual((result["target"]["tier"], result["target"]["confidence"]), ("pe_owned", "confirmed"))


class Parents(unittest.TestCase):
    def test_grandparent_listed_as_parent_is_not_a_conflict(self):
        v = verdicts([node("raos"), node("sovos"), node("campbell")],
                     [edge("raos", "sovos", relation="brand_of"), edge("raos", "campbell", "usda", relation="brand_of"),
                      edge("sovos", "campbell", start="2024")], {"campbell": ("public_company",)})["raos"]
        self.assertEqual(([n["id"] for n in v["chain"]], v["confidence"]), (["raos", "sovos", "campbell"], "reported"))

    def test_rival_parents_are_conflicting_and_newest_dated_wins(self):
        v = verdicts([node("a"), node("old"), node("new")], [edge("a", "old", start="2010"), edge("a", "new", "wikidata", start="2022")], {})["a"]
        self.assertEqual((v["chain"][1]["id"], v["chain"][1]["confidence"], v["chain"][1]["alternatives"][0]["id"]), ("new", "conflicting", "old"))

    def test_owner_that_ended_earlier_this_year_is_history_not_a_rival(self):
        v = verdicts([node("a"), node("old"), node("new")], [edge("a", "old", start="2010", end="2026"), edge("a", "new", start="2026")], {})["a"]
        self.assertEqual((v["chain"][1]["id"], v["chain"][1]["confidence"]), ("new", "reported"))
        self.assertEqual((v["history"][0]["owner"]["id"], v["history"][0]["end"]), ("old", "2026"))

    def test_official_or_independent_sources_confirm_a_link(self):
        v = verdicts([node("a"), node("b")], [edge("a", "b"), edge("a", "b", "usda")], {})["a"]
        self.assertEqual(v["chain"][1]["confidence"], "confirmed")
        v = verdicts([node("a"), node("b")], [edge("a", "b"), edge("a", "b", "wikidata")], {})["a"]
        self.assertEqual(v["chain"][1]["confidence"], "reported")

    def test_cycles_and_depth_stop_the_walk(self):
        v = verdicts([node("a"), node("b")], [edge("a", "b"), edge("b", "a", "wikidata")], {})["a"]
        self.assertEqual([n["id"] for n in v["chain"]], ["a", "b"])
        ids = [f"n{i}" for i in range(12)]
        v = verdicts([node(i) for i in ids], [edge(a, b) for a, b in zip(ids, ids[1:])], {})["n0"]
        self.assertEqual(len(v["chain"]), 9)


class History(unittest.TestCase):
    def test_ended_pe_period_flags_formerly_pe_and_changed_hands(self):
        v = verdicts([node("sovos"), node("advent"), node("campbell")],
                     [edge("sovos", "advent", start="2017", end="2024"), edge("sovos", "campbell", start="2024")],
                     {"advent": ("pe_firm",), "campbell": ("public_company",)})["sovos"]
        flags = {f["type"]: f for f in v["flags"]}
        self.assertEqual(v["tier"], "corporate_owned")
        self.assertEqual((flags["formerly_pe"]["owner"]["id"], flags["formerly_pe"]["start"], flags["formerly_pe"]["end"]), ("advent", "2017", "2024"))
        self.assertEqual((flags["changed_hands"]["year"], flags["changed_hands"]["recent"]), (2024, True))
        self.assertEqual(flags["flipped"]["years"], [2017, 2024])  # sold to Advent, then to Campbell's

    def test_two_sales_within_ten_years_is_a_flip_and_observed_dates_do_not_count(self):
        v = verdicts([node("x"), node("p1"), node("p2"), node("p3")],
                     [edge("x", "p1", start="2017", end="2019"), edge("x", "p2", start="2019", end="2023"), edge("x", "p3", start="2023"),
                      edge("x", "p3", "usda", start="2025-01-01", observed=True)], {})["x"]
        flipped = next(f for f in v["flags"] if f["type"] == "flipped")
        self.assertEqual(flipped["years"], [2017, 2019, 2023])
        self.assertEqual(next(f for f in v["flags"] if f["type"] == "changed_hands")["year"], 2023)

    def test_retracted_claim_becomes_history_ending_when_last_seen(self):
        gone = edge("a", "old", last_seen="2026-06-01", status="retracted")
        v = verdicts([node("a"), node("old")], [gone], {})["a"]
        self.assertEqual((v["tier"], v["history"][0]["end"], v["history"][0]["end_observed"]), ("no_signals", "2026-06-01", True))

    def test_rollup_flag(self):
        brands = [node(f"b{i}", "brand", "fast food") for i in range(5)]
        result = verdicts(brands + [node("pe")], [edge(b.id, "pe") for b in brands], {"pe": ("pe_firm",)})
        rollup = next(f for f in result["b0"]["flags"] if f["type"] == "rollup")
        self.assertEqual((rollup["count"], rollup["category"]), (5, "fast food"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_verdict -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'pipeline.verdict'`

- [ ] **Step 3: Write the implementation**

`pipeline/verdict.py`:

```python
"""Turn the resolved graph into one verdict per entity, as of a date."""

from __future__ import annotations

from collections import Counter, defaultdict

from .classify import FINANCIAL, OwnerKind
from .model import CONTROL_RELATIONS, SOURCE_GROUPS, Claim, pad_end, pad_start, year_of
from .resolve import Graph

MAX_DEPTH = 8
RECENT_YEARS = 5  # "changed hands" is emphasized when this recent
FLIP_WINDOW_YEARS = 10
FLIP_MIN_CHANGES = 2
ROLLUP_MIN_BRANDS = 5
MAX_CONTROLS_LISTED = 200
CONFIDENCE_RANK = {"conflicting": 0, "reported": 1, "confirmed": 2}
SOURCE_NAMES = {
    "wikipedia": "Wikipedia", "wikipedia_history": "Wikipedia page history", "wikidata": "Wikidata",
    "nsi": "OpenStreetMap Name Suggestion Index", "usda": "USDA FoodData Central", "adv": "SEC Form ADV",
    "ftc": "FTC early termination notice", "sec_ex21": "SEC 10-K Exhibit 21",
}
PUBLISHED_KINDS = ("brand", "company")  # advisers and funds appear only inside chains


def has_ended(claim: Claim, as_of: str) -> bool:
    """A source that names an end year is saying it already ended: "2010–2026" is over in 2026."""
    return claim.status == "retracted" or (claim.end is not None and pad_start(claim.end) <= as_of)


def is_current(claim: Claim, as_of: str) -> bool:
    return not has_ended(claim, as_of) and (claim.start is None or pad_start(claim.start) <= as_of)


def edge_confidence(claims: list[Claim]) -> str:
    direct = [c for c in claims if not c.via_family]
    if any(c.official for c in direct) or len({SOURCE_GROUPS.get(c.source, c.source) for c in direct}) >= 2:
        return "confirmed"
    return "reported"


def edge_since(claims: list[Claim]) -> tuple[str | None, bool]:
    """Earliest start a source reports for this link; observed dates only when nothing is reported."""
    reported = sorted((c.start for c in claims if c.start and not c.observed), key=pad_start)
    if reported:
        return reported[0], False
    observed = sorted((c.start for c in claims if c.start), key=pad_start)
    return (observed[0], True) if observed else (None, False)


def evidence(claim: Claim) -> dict:
    return {"source": SOURCE_NAMES.get(claim.source, claim.source), "url": claim.source_url,
            "record": claim.source_record, "excerpt": claim.excerpt[:200], "relation": claim.relation,
            "start": claim.start, "end": claim.end, "official": claim.official, "observed": claim.observed,
            "first_seen": claim.first_seen, "last_seen": claim.last_seen}


def _clusters(years: list[int]) -> list[int]:
    """Collapse years one apart (an announced-then-closed deal) into one event each."""
    events: list[int] = []
    for year in sorted(set(years)):
        if not events or year - events[-1] > 1:
            events.append(year)
    return events


class VerdictBuilder:
    def __init__(self, graph: Graph, kinds: dict[str, OwnerKind], as_of: str):
        self.graph, self.kinds, self.as_of = graph, kinds, as_of
        self.as_of_year = int(as_of[:4])
        self.control: dict[str, list[Claim]] = defaultdict(list)
        self.deals: dict[str, list[Claim]] = defaultdict(list)
        self.minority: dict[str, list[Claim]] = defaultdict(list)
        for claim in graph.claims:
            if claim.relation in CONTROL_RELATIONS:
                self.control[claim.subject].append(claim)
            elif claim.relation == "deal":
                self.deals[claim.subject].append(claim)
            elif claim.relation == "minority_stake":
                self.minority[claim.subject].append(claim)
        self._parents: dict[str, tuple | None] = {}

    # ---- graph walking -------------------------------------------------
    def owner_kind(self, node_id: str) -> OwnerKind | None:
        if node_id in self.kinds:
            return self.kinds[node_id]
        for claim in self.control.get(node_id, []):  # a fund takes its adviser's kind
            if claim.relation == "fund_of" and claim.object in self.kinds:
                return self.kinds[claim.object]
        return None

    def _current_by_object(self, node_id: str) -> dict[str, list[Claim]]:
        by_object: dict[str, list[Claim]] = defaultdict(list)
        for claim in self.control.get(node_id, []):
            if is_current(claim, self.as_of):
                by_object[claim.object].append(claim)
        return by_object

    def _ancestors(self, node_id: str) -> set[str]:
        seen: set[str] = set()
        frontier = [node_id]
        for _ in range(MAX_DEPTH):
            frontier = [o for n in frontier for o in self._current_by_object(n) if o not in seen]
            seen.update(frontier)
        return seen

    def parent(self, node_id: str):
        """(parent id, claims, confidence, alternative parent ids) or None."""
        if node_id not in self._parents:
            by_object = self._current_by_object(node_id)
            pick = None
            if by_object:
                candidates = set(by_object)
                if len(candidates) > 1:  # a listed grandparent is not a rival parent
                    upper = set().union(*(self._ancestors(c) for c in candidates))
                    candidates = (candidates - upper) or candidates
                ranked = sorted(candidates, reverse=True, key=lambda o: (
                    CONFIDENCE_RANK[edge_confidence(by_object[o])],
                    max(pad_start(c.start) for c in by_object[o]),
                    len({c.source for c in by_object[o]}), o))
                best = ranked[0]
                confidence = "conflicting" if len(ranked) > 1 else edge_confidence(by_object[best])
                pick = (best, by_object[best], confidence, ranked[1:])
            self._parents[node_id] = pick
        return self._parents[node_id]

    def _ref(self, node_id: str) -> dict:
        node = self.graph.nodes.get(node_id)
        return {"id": node_id, "name": node.name if node else node_id}

    def _node(self, node_id: str) -> dict:
        kind = self.owner_kind(node_id)
        return {**self._ref(node_id), "owner_kind": kind.kind if kind else None,
                "kind_confidence": kind.confidence if kind else None}

    def chain(self, entity_id: str) -> list[dict]:
        nodes = [self._node(entity_id)]
        seen = {entity_id}
        current = entity_id
        for _ in range(MAX_DEPTH):
            pick = self.parent(current)
            if not pick:
                break
            parent_id, claims, confidence, alternatives = pick
            if parent_id in seen:
                nodes[-1]["cycle"] = True
                break
            since, observed = edge_since(claims)
            relation = Counter(c.relation for c in claims).most_common(1)[0][0]
            nodes.append({**self._node(parent_id), "relation": relation, "confidence": confidence,
                          "since": since, "since_observed": observed,
                          "alternatives": [self._ref(a) for a in alternatives[:5]],
                          "evidence": [evidence(c) for c in sorted(claims, key=lambda c: (c.source, c.key))][:8]})
            seen.add(parent_id)
            current = parent_id
        return nodes

    def history(self, chain_ids: list[str], current_edges: set[tuple[str, str]]) -> list[dict]:
        merged: dict[tuple[str, str], dict] = {}
        for node_id in chain_ids:
            for claim in self.control.get(node_id, []):
                if not has_ended(claim, self.as_of) or (node_id, claim.object) in current_edges:
                    continue
                kind = self.owner_kind(claim.object)
                end = claim.end or claim.last_seen
                period = merged.setdefault((node_id, claim.object), {
                    "subject": self._ref(node_id), "owner": {**self._ref(claim.object), "kind": kind.kind if kind else None},
                    "start": None, "start_observed": True, "end": None, "end_observed": True, "evidence": []})
                period["evidence"].append(evidence(claim))
                if claim.start and (not period["start"] or pad_start(claim.start) < pad_start(period["start"])):
                    period["start"], period["start_observed"] = claim.start, claim.observed
                if end and (not period["end"] or pad_end(end) > pad_end(period["end"])):
                    period["end"] = end
                    period["end_observed"] = claim.end is None or claim.observed
        return sorted(merged.values(), key=lambda p: (pad_start(p["start"]) or pad_end(p["end"]), p["owner"]["id"]))

    # ---- verdicts --------------------------------------------------------
    def verdict(self, entity_id: str) -> dict:
        node = self.graph.nodes[entity_id]
        chain = self.chain(entity_id)
        owners = chain[1:]
        own = self.owner_kind(entity_id)
        deciding = None
        if own and own.kind in FINANCIAL:
            tier = "owner"
        elif deciding := next((n for n in owners if n["owner_kind"] == "pe_firm"), None):
            tier = "pe_owned"
        elif deciding := next((n for n in owners if n["owner_kind"] == "investment_firm"), None):
            tier = "investment_owned"
        elif owners:
            tier, deciding = "corporate_owned", owners[-1]
        else:
            tier = "no_signals"

        since = confidence = None
        since_observed = False
        if deciding:
            path = chain[1:chain.index(deciding) + 1]
            dated = [n for n in path if n.get("since")]
            if dated:
                latest = max(dated, key=lambda n: pad_start(n["since"]))
                since, since_observed = latest["since"], latest["since_observed"]
            levels = [n["confidence"] for n in path]
            if tier in ("pe_owned", "investment_owned"):
                levels.append(deciding["kind_confidence"] or "reported")
            confidence = min(levels, key=CONFIDENCE_RANK.__getitem__)

        chain_ids = [n["id"] for n in chain]
        current_edges = set(zip(chain_ids, chain_ids[1:]))
        history = self.history(chain_ids, current_edges)
        deals = [{"date": c.start, "acquirer": self._ref(c.object), "url": c.source_url, "excerpt": c.excerpt[:200]}
                 for node_id in chain_ids for c in self.deals.get(node_id, [])]
        deals.sort(key=lambda d: d["date"] or "", reverse=True)

        flags = []
        for period in history:
            if period["owner"]["kind"] in FINANCIAL and period["owner"]["id"] not in chain_ids:
                flags.append({"type": "formerly_pe" if period["owner"]["kind"] == "pe_firm" else "formerly_investment",
                              "owner": {"id": period["owner"]["id"], "name": period["owner"]["name"]},
                              "start": period["start"], "end": period["end"], "observed": period["end_observed"]})
        # Only dates a source reports count as changes of hands; first-seen dates do not.
        change_dates = ([n["since"] for n in owners if n.get("since") and not n["since_observed"]]
                        + [p["start"] for p in history if p["start"] and not p["start_observed"]]
                        + [p["end"] for p in history if p["end"] and not p["end_observed"]]
                        + [d["date"] for d in deals if d["date"]])
        years = sorted({y for y in map(year_of, change_dates) if y and y <= self.as_of_year})
        if years:
            flags.append({"type": "changed_hands", "year": years[-1],
                          "recent": self.as_of_year - years[-1] <= RECENT_YEARS})
            events = _clusters([y for y in years if self.as_of_year - y < FLIP_WINDOW_YEARS])
            if len(events) >= FLIP_MIN_CHANGES:
                flags.append({"type": "flipped", "years": events})

        minority = []
        for claim in self.minority.get(entity_id, []):
            if is_current(claim, self.as_of):
                kind = self.owner_kind(claim.object)
                minority.append({"owner": {**self._ref(claim.object), "kind": kind.kind if kind else None},
                                 "evidence": [evidence(claim)]})
        return {
            "id": entity_id, "name": node.name, "kind": node.kind, "category": node.category,
            "aliases": node.aliases[:10], "sources": node.sources, "tier": tier,
            "owner": {"id": deciding["id"], "name": deciding["name"], "kind": deciding["owner_kind"]} if deciding else None,
            "since": since, "since_observed": since_observed, "confidence": confidence,
            "flags": flags, "chain": chain, "history": history, "deals": deals[:20], "minority": minority,
            "ticker": node.ids.get("ticker"), "owner_kind": own.kind if own else None,
            "kind_evidence": own.evidence if own else [], "controls": [], "as_of": self.as_of,
        }


def build_verdicts(graph: Graph, kinds: dict[str, OwnerKind], as_of: str) -> dict[str, dict]:
    builder = VerdictBuilder(graph, kinds, as_of)
    verdicts = {node_id: builder.verdict(node_id) for node_id, node in sorted(graph.nodes.items())
                if node.kind in PUBLISHED_KINDS}
    controls: dict[str, list[dict]] = defaultdict(list)
    rollups: Counter = Counter()
    for verdict in verdicts.values():
        for link in verdict["chain"][1:]:
            if verdicts.get(link["id"], {}).get("tier") == "owner":
                controls[link["id"]].append({"id": verdict["id"], "name": verdict["name"]})
        if verdict["owner"] and verdict["category"]:
            rollups[(verdict["owner"]["id"], verdict["category"])] += 1
    for owner_id, items in controls.items():
        verdicts[owner_id]["controls"] = sorted(items, key=lambda i: i["name"].lower())[:MAX_CONTROLS_LISTED]
        verdicts[owner_id]["controls_count"] = len(items)
    for verdict in verdicts.values():
        if verdict["owner"] and verdict["category"]:
            count = rollups[(verdict["owner"]["id"], verdict["category"])]
            if count >= ROLLUP_MIN_BRANDS:
                verdict["flags"].append({"type": "rollup", "owner": {"id": verdict["owner"]["id"], "name": verdict["owner"]["name"]},
                                         "count": count, "category": verdict["category"]})
    return verdicts
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_verdict -v`
Expected: 15 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/verdict.py tests/test_verdict.py
git commit -m "Compute tiered verdicts, chains, history, and flags"
```

---

### Task 16: Safety gates

**Files:**
- Create: `pipeline/checks.py`
- Test: `tests/test_checks.py`

**Interfaces:**
- Produces:
  - `KNOWN_ANSWERS`
  - `GateReport(failures, changes)` with `.ok` and `.markdown()`
  - `claim_count_failures(prev_sources, cur_sources)`
  - `tier_changes(prev_tiers, by_slug)`
  - `churn_failures(prev_tiers, changes)`
  - `known_answer_failures(by_slug)`
  - `run_gates(prev_sources, cur_sources, prev_tiers, by_slug, override=False)`

- [ ] **Step 1: Write the failing test**

`tests/test_checks.py`:

```python
import unittest

from pipeline import checks


def verdict(name, tier, owner=None, ticker=None, id="Q1"):
    return {"id": id, "name": name, "tier": tier, "owner": {"name": owner} if owner else None, "ticker": ticker, "sources": ["wikipedia"]}


GOOD = {
    "buffalo-wild-wings": verdict("Buffalo Wild Wings", "pe_owned", "Roark Capital Group"),
    "jersey-mikes-subs": verdict("Jersey Mike's Subs", "pe_owned", "Blackstone Inc."),
    "subway": verdict("Subway", "pe_owned", "Roark Capital Group"),
    "raos-homemade": verdict("Rao's Homemade", "corporate_owned", "Campbell's", id="name:raos homemade"),
    "chipotle-mexican-grill": verdict("Chipotle Mexican Grill", "no_signals", ticker="NYSE: CMG"),
}


class Gates(unittest.TestCase):
    def test_known_answers_pass_and_fail_with_reasons(self):
        self.assertEqual(checks.known_answer_failures(GOOD), [])
        broken = {**GOOD, "jersey-mikes-subs": verdict("Jersey Mike's Subs", "investment_owned", "Blackstone Inc.")}
        self.assertEqual(checks.known_answer_failures(broken), ["Known answer: Jersey Mike's Subs is investment_owned, expected pe_owned"])
        missing = {k: v for k, v in GOOD.items() if k != "subway"}
        self.assertIn("Known answer: Subway is missing", checks.known_answer_failures(missing))

    def test_claim_count_swing_beyond_twenty_percent_fails_except_history(self):
        previous = {"wikipedia": {"active_claims": 1000}, "wikipedia_history": {"active_claims": 10}}
        current = {"wikipedia": {"active_claims": 700}, "wikipedia_history": {"active_claims": 5000}}
        self.assertEqual(len(checks.claim_count_failures(previous, current)), 1)
        self.assertEqual(checks.claim_count_failures({}, current), [])  # first run has no baseline

    def test_tier_churn(self):
        previous = {f"s{i}": "no_signals" for i in range(100)}
        changed = {f"s{i}": verdict(f"S{i}", "pe_owned" if i < 3 else "no_signals") for i in range(100)}
        changes = checks.tier_changes(previous, changed)
        self.assertEqual(len(changes), 3)
        self.assertEqual(len(checks.churn_failures(previous, changes)), 1)

    def test_override_skips_counts_and_churn_but_never_known_answers(self):
        previous = {"wikipedia": {"active_claims": 1000}}
        current = {"wikipedia": {"active_claims": 1}}
        self.assertFalse(checks.run_gates(previous, current, {}, GOOD).ok)
        self.assertTrue(checks.run_gates(previous, current, {}, GOOD, override=True).ok)
        self.assertFalse(checks.run_gates({}, {}, {}, {}, override=True).ok)
        self.assertIn("Nightly gates failed", checks.run_gates(previous, current, {}, GOOD).markdown())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_checks -v`
Expected: ERROR, `ImportError: cannot import name 'checks'`

- [ ] **Step 3: Write the implementation**

`pipeline/checks.py`:

```python
"""Safety checks that run before anything is published."""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import normalize

COUNT_TOLERANCE = 0.20
CHURN_LIMIT = 0.02
COUNT_EXEMPT = {"wikipedia_history"}  # the history backfill grows by design
# Test expectations only: they check the automated pipeline, and never feed the site.
KNOWN_ANSWERS = (
    {"name": "Buffalo Wild Wings", "tier": "pe_owned", "owner": "Roark"},
    {"name": "Jersey Mike's Subs", "tier": "pe_owned", "owner": "Blackstone"},
    {"name": "Subway", "tier": "pe_owned", "owner": "Roark"},
    {"name": "Rao's Homemade", "tier": "corporate_owned", "owner": "Campbell"},
    {"name": "Chipotle Mexican Grill", "tier": "no_signals", "ticker": "CMG"},
)


@dataclass
class GateReport:
    failures: list[str] = field(default_factory=list)
    changes: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def markdown(self) -> str:
        lines = ["## Nightly gates failed", "", "Yesterday's site stays live. Nothing was committed.", ""]
        lines += [f"- {failure}" for failure in self.failures]
        if self.changes:
            lines += ["", f"### Tier changes ({len(self.changes)})", ""]
            lines += [f"- {c['name']} (`{c['slug']}`): {c['from']} → {c['to']}" for c in self.changes[:100]]
        return "\n".join(lines) + "\n"


def claim_count_failures(previous: dict[str, dict], current: dict[str, dict]) -> list[str]:
    failures = []
    for source, meta in sorted(current.items()):
        before = (previous.get(source) or {}).get("active_claims")
        after = meta.get("active_claims", 0)
        if source not in COUNT_EXEMPT and before and abs(after - before) / before > COUNT_TOLERANCE:
            failures.append(f"{source}: active claims went from {before} to {after} (limit ±{COUNT_TOLERANCE:.0%})")
    return failures


def tier_changes(previous_tiers: dict[str, str], by_slug: dict[str, dict]) -> list[dict]:
    return [{"slug": slug, "name": v["name"], "from": previous_tiers[slug], "to": v["tier"]}
            for slug, v in sorted(by_slug.items()) if slug in previous_tiers and previous_tiers[slug] != v["tier"]]


def churn_failures(previous_tiers: dict[str, str], changes: list[dict]) -> list[str]:
    if previous_tiers and len(changes) / len(previous_tiers) > CHURN_LIMIT:
        return [f"{len(changes)} of {len(previous_tiers)} verdict tiers changed in one run (limit {CHURN_LIMIT:.0%})"]
    return []


def known_answer_failures(by_slug: dict[str, dict]) -> list[str]:
    by_name: dict[str, dict] = {}
    for verdict in by_slug.values():
        key = normalize(verdict["name"])
        best = by_name.get(key)
        if best is None or (verdict["id"].startswith("Q"), len(verdict["sources"])) > (best["id"].startswith("Q"), len(best["sources"])):
            by_name[key] = verdict
    failures = []
    for expected in KNOWN_ANSWERS:
        verdict = by_name.get(normalize(expected["name"]))
        owner = ((verdict or {}).get("owner") or {}).get("name") or ""
        if verdict is None:
            failures.append(f"Known answer: {expected['name']} is missing")
        elif verdict["tier"] != expected["tier"]:
            failures.append(f"Known answer: {expected['name']} is {verdict['tier']}, expected {expected['tier']}")
        elif expected.get("owner") and expected["owner"].lower() not in owner.lower():
            failures.append(f"Known answer: {expected['name']} owner is {owner or 'none'}, expected {expected['owner']}")
        elif expected.get("ticker") and expected["ticker"] not in (verdict.get("ticker") or ""):
            failures.append(f"Known answer: {expected['name']} ticker is {verdict.get('ticker')}, expected {expected['ticker']}")
    return failures


def run_gates(previous_sources: dict, current_sources: dict, previous_tiers: dict[str, str],
              by_slug: dict[str, dict], override: bool = False) -> GateReport:
    changes = tier_changes(previous_tiers, by_slug)
    failures = known_answer_failures(by_slug)  # applies even to override runs
    if not override:
        failures = claim_count_failures(previous_sources, current_sources) + churn_failures(previous_tiers, changes) + failures
    return GateReport(failures, changes)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_checks -v`
Expected: 4 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/checks.py tests/test_checks.py
git commit -m "Add publish gates: known answers, claim counts, tier churn"
```

---

### Task 17: Publishing

**Files:**
- Create: `pipeline/publish.py`
- Test: `tests/test_publish.py`

**Interfaces:**
- Produces:
  - `assign_slugs(graph, verdicts, slugs) -> {node_id: slug}`. It reuses any member's earlier slug, never hands out a retired slug, and updates `slugs` in place.
  - `entity_shard(slug)` returns the first 3 hex characters of SHA-1.
  - `search_entry(verdict, slug) -> [name, slug, tier, kind, search_text, score]`
  - `write_site(out, site_dir, verdicts, slug_of, sources, changes, as_of)` writes:
    - `data/e/<shard>.json` (slug → verdict, with `slug` added next to linked IDs)
    - `data/search/<3-char prefix>.json`
    - `data/search/top.json`
    - `data/meta.json`
    - `data/changes/latest.json`
  - `PublishError` when the published data exceeds 300 MB.

- [ ] **Step 1: Write the failing test**

`tests/test_publish.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import publish
from pipeline.model import Entity
from pipeline.resolve import resolve


def verdict(id, name, tier="no_signals", kind="brand", aliases=()):
    return {"id": id, "name": name, "tier": tier, "kind": kind, "aliases": list(aliases), "chain": [{"id": id, "name": name}],
            "sources": [], "flags": [], "history": [], "deals": [], "controls": []}


class Slugs(unittest.TestCase):
    def test_stable_unique_slugs_that_survive_merges(self):
        graph = resolve([Entity("Q1", "brand", "Subway", "nsi"), Entity("name:subway", "brand", "Subway", "usda"),
                         Entity("Q2", "brand", "Subway", "wikipedia")], [], [])
        verdicts = {node_id: verdict(node_id, "Subway") for node_id in graph.nodes}
        slugs = {"name:subway": "subway"}  # an earlier run published the USDA record
        result = publish.assign_slugs(graph, verdicts, slugs)
        node_with_subway = graph.canonical["name:subway"]
        self.assertEqual(result[node_with_subway], "subway")
        self.assertEqual(len(set(result.values())), len(result))
        self.assertEqual(slugs[node_with_subway], "subway")


class WriteSite(unittest.TestCase):
    def setUp(self):
        self.site = Path(tempfile.mkdtemp())
        (self.site / "index.html").write_text("<!doctype html>")
        self.out = Path(tempfile.mkdtemp()) / "site"
        self.verdicts = {"Q509255": verdict("Q509255", "Buffalo Wild Wings", "pe_owned", aliases=["BW3"]),
                         "Q7339900": verdict("Q7339900", "Roark Capital Group", "owner", "company")}
        self.verdicts["Q509255"]["chain"].append({"id": "Q7339900", "name": "Roark Capital Group"})
        self.slugs = {"Q509255": "buffalo-wild-wings", "Q7339900": "roark-capital-group"}

    def test_writes_static_files_with_links_and_search_shards(self):
        publish.write_site(self.out, self.site, self.verdicts, self.slugs, {"wikipedia": {"last_success": "2026-10-05"}}, [], "2026-10-05")
        self.assertTrue((self.out / "index.html").exists())
        shard = json.loads((self.out / "data" / "e" / f"{publish.entity_shard('buffalo-wild-wings')}.json").read_text())
        self.assertEqual(shard["buffalo-wild-wings"]["chain"][1]["slug"], "roark-capital-group")
        for prefix in ("buf", "wil", "win", "bw3"):
            entries = json.loads((self.out / "data" / "search" / f"{prefix}.json").read_text())
            self.assertEqual(entries[0][1], "buffalo-wild-wings")
        top = json.loads((self.out / "data" / "search" / "top.json").read_text())
        self.assertEqual(top[0][0], "Buffalo Wild Wings")  # brands with a verdict rank first
        self.assertEqual(json.loads((self.out / "data" / "meta.json").read_text())["as_of"], "2026-10-05")

    def test_size_budget(self):
        with mock.patch.object(publish, "SIZE_BUDGET", 10), self.assertRaises(publish.PublishError):
            publish.write_site(self.out, self.site, self.verdicts, self.slugs, {}, [], "2026-10-05")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_publish -v`
Expected: ERROR, `ImportError: cannot import name 'publish'`

- [ ] **Step 3: Write the implementation**

`pipeline/publish.py`:

```python
"""Write the static site: search shards, entity shards, and metadata."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from .model import normalize, slugify

ENTITY_SHARD_CHARS = 3  # 4,096 shards keep each result-page download small on phones
SEARCH_PREFIX = 3
TOP_ENTRIES = 3000  # what two-letter queries search
SIZE_BUDGET = 300 * 1024 * 1024
TIER_SCORE = {"pe_owned": 4, "investment_owned": 4, "corporate_owned": 3, "owner": 3, "no_signals": 1}


class PublishError(RuntimeError):
    pass


def _priority(verdict: dict) -> tuple:
    return (not verdict["id"].startswith("Q"), -TIER_SCORE.get(verdict["tier"], 0), verdict["id"])


def assign_slugs(graph, verdicts: dict[str, dict], slugs: dict[str, str]) -> dict[str, str]:
    """Entity id -> slug. Reuses any member's earlier slug so shared links survive merges."""
    result: dict[str, str] = {}
    taken: set[str] = set()
    for node_id in sorted(verdicts, key=lambda i: _priority(verdicts[i])):
        previous = next((slugs[m] for m in [node_id, *graph.nodes[node_id].members] if m in slugs), None)
        if previous and previous not in taken:
            result[node_id] = previous
            taken.add(previous)
    reserved = set(slugs.values()) | taken
    for node_id in sorted(verdicts, key=lambda i: _priority(verdicts[i])):
        if node_id in result:
            continue
        base = slugify(verdicts[node_id]["name"])
        slug, number = base, 2
        while slug in reserved:
            slug, number = f"{base}-{number}", number + 1
        result[node_id] = slug
        reserved.add(slug)
    slugs.update(result)
    return result


def entity_shard(slug: str) -> str:
    return hashlib.sha1(slug.encode("utf-8")).hexdigest()[:ENTITY_SHARD_CHARS]


def search_entry(verdict: dict, slug: str) -> list:
    names = [normalize(n) for n in (verdict["name"], *verdict["aliases"])]
    text = " | ".join(dict.fromkeys(n for n in names if n))
    score = TIER_SCORE.get(verdict["tier"], 0) + (2 if verdict["kind"] == "brand" else 0) + (1 if verdict["id"].startswith("Q") else 0)
    return [verdict["name"], slug, verdict["tier"], verdict["kind"], text, score]


def _link(value, slug_of: dict[str, str]):
    """Copy a verdict, adding "slug" next to every entity id that has a page."""
    if isinstance(value, dict):
        out = {k: _link(v, slug_of) for k, v in value.items()}
        if isinstance(value.get("id"), str) and value["id"] in slug_of:
            out["slug"] = slug_of[value["id"]]
        return out
    if isinstance(value, list):
        return [_link(v, slug_of) for v in value]
    return value


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def write_site(out: Path, site_dir: Path, verdicts: dict[str, dict], slug_of: dict[str, str], sources: dict,
               changes: list[dict], as_of: str) -> None:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(site_dir, out)
    data = out / "data"
    shards: dict[str, dict] = defaultdict(dict)
    search: dict[str, dict[str, list]] = defaultdict(dict)
    entries = []
    for node_id, verdict in verdicts.items():
        slug = slug_of[node_id]
        shards[entity_shard(slug)][slug] = _link(verdict, slug_of)
        entry = search_entry(verdict, slug)
        entries.append(entry)
        for token in set(entry[4].replace("|", " ").split()):
            if len(token) >= SEARCH_PREFIX:
                search[token[:SEARCH_PREFIX]][slug] = entry
    for shard, records in shards.items():
        _write(data / "e" / f"{shard}.json", records)
    for prefix, records in search.items():
        _write(data / "search" / f"{prefix}.json", sorted(records.values(), key=lambda e: (-e[5], e[0])))
    _write(data / "search" / "top.json", sorted(entries, key=lambda e: (-e[5], e[0]))[:TOP_ENTRIES])
    _write(data / "meta.json", {"as_of": as_of, "sources": sources, "entities": len(verdicts),
                                "tiers": Counter(v["tier"] for v in verdicts.values())})
    _write(data / "changes" / "latest.json", changes)
    size = sum(p.stat().st_size for p in data.rglob("*") if p.is_file())
    if size > SIZE_BUDGET:
        raise PublishError(f"published data is {size / 1e6:.0f} MB, over the {SIZE_BUDGET / 1e6:.0f} MB budget")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_publish -v`
Expected: 3 tests, OK

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish.py tests/test_publish.py
git commit -m "Publish entity and search shards with stable slugs"
```

---

### Task 18: Orchestrator and sample graph

**Files:**
- Create: `pipeline/run.py`, `pipeline/sample.py`
- Modify: `package.json` (scripts)
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - CLI: `python -m pipeline.run [--state state] [--out build/site] [--site site] [--report build/gate-report.md] [--today YYYY-MM-DD] [--only a,b] [--override-gates] [--sample]`. Exit code `0` means published, `2` means a gate failed (report written, nothing saved), and anything else is a crash.
  - Module functions: `main(argv)`, `is_due(store, source, today)`, `collect_all(store, today, only)`, `COLLECTORS`.
  - `sample.sample_store(root) -> Store`, a deterministic graph mirroring the live records.
- The end-to-end test depends on `site/` existing. Create a minimal `site/index.html` now; Task 19 replaces it.

- [ ] **Step 1: Write the failing test**

`tests/test_run.py`:

```python
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import publish, run
from pipeline.model import CollectorResult
from pipeline.store import Store

ROOT = Path(__file__).resolve().parents[1]


class SampleBuild(unittest.TestCase):
    def test_sample_graph_passes_every_known_answer_and_publishes(self):
        out = Path(tempfile.mkdtemp()) / "site"
        code = run.main(["--sample", "--out", str(out), "--site", str(ROOT / "site"), "--today", "2026-10-05",
                         "--report", str(out.parent / "report.md")])
        self.assertEqual(code, 0, (out.parent / "report.md").read_text() if (out.parent / "report.md").exists() else "")
        meta = json.loads((out / "data" / "meta.json").read_text())
        self.assertEqual(meta["tiers"]["pe_owned"], 4)  # BWW, Subway, Jersey Mike's, Inspire Brands
        chase = json.loads((out / "data" / "e" / f"{publish.entity_shard('chase')}.json").read_text())["chase"]
        self.assertEqual(chase["tier"], "corporate_owned")  # its parent bank runs PE funds, but is not a PE firm


class Scheduling(unittest.TestCase):
    def test_due_by_cadence(self):
        store = Store(Path(tempfile.mkdtemp()))
        self.assertTrue(run.is_due(store, "adv", "2026-10-05"))
        store.sources["adv"] = {"last_success": "2026-09-20"}
        self.assertFalse(run.is_due(store, "adv", "2026-10-05"))
        self.assertTrue(run.is_due(store, "adv", "2026-10-20"))

    def test_a_failing_source_keeps_its_data_and_records_the_error(self):
        store = Store(Path(tempfile.mkdtemp()))
        def boom(fetcher, store, today):
            raise RuntimeError("HTTP 503")
        def fine(fetcher, store, today):
            return CollectorResult()
        collectors = (("nsi", boom, "web"), ("ftc", fine, "ftc"), ("sec_ex21", fine, "sec"))
        with mock.patch.object(run, "COLLECTORS", collectors), mock.patch.dict(os.environ, {}, clear=True):
            run.collect_all(store, "2026-10-05", set())
        self.assertEqual(store.sources["nsi"]["error"], "RuntimeError: HTTP 503")
        self.assertEqual(store.sources["ftc"]["last_success"], "2026-10-05")
        self.assertIn("SEC_CONTACT_EMAIL", store.sources["sec_ex21"]["error"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest tests.test_run -v`
Expected: ERROR, `ImportError: cannot import name 'run'`

- [ ] **Step 3: Write the sample graph and orchestrator**

`pipeline/sample.py`:

```python
"""A small graph shaped like real source records, for local builds and end-to-end tests.

Every record mirrors what a collector produced from live data on 2026-10-05. It is
test data only: the published site never reads it.
"""

from __future__ import annotations

from pathlib import Path

from .model import Claim, Classification, CollectorResult, Entity
from .store import Store

RUN_DATE = "2026-10-05"
WIKI = "https://en.wikipedia.org/wiki/"


def _wiki_page(qid: str, title: str, domain: str, ticker: str = "", aliases: tuple[str, ...] = ()) -> Entity:
    ids = {"wikipedia": title, "wikidata": qid, "website_domain": domain}
    if ticker:
        ids["ticker"] = ticker
    name = title.split(" (")[0]
    return Entity(id=qid, kind="company", name=name, source="wikipedia", aliases=list(aliases), ids=ids)


def _wiki_claim(subject: str, relation: str, obj: str, title: str, excerpt: str, start: str | None = None) -> Claim:
    return Claim(source="wikipedia", subject=subject, relation=relation, object=obj, start=start,
                 source_url=WIKI + title.replace(" ", "_"), source_record="1", excerpt=excerpt)


def _wiki_kind(entity: str, kind: str, title: str, evidence: str) -> Classification:
    return Classification(entity=entity, kind=kind, source="wikipedia", evidence=evidence,
                          source_url=WIKI + title.replace(" ", "_"))


def sample_results() -> dict[str, CollectorResult]:
    wikipedia = CollectorResult(
        entities=[
            _wiki_page("Q509255", "Buffalo Wild Wings", "buffalowildwings.com"),
            _wiki_page("Q55074808", "Inspire Brands", "inspirebrands.com"),
            _wiki_page("Q7339900", "Roark Capital Group", "roarkcapital.com"),
            _wiki_page("Q244457", "Subway (restaurant)", "subway.com"),
            _wiki_page("Q6184897", "Jersey Mike's Subs", "jerseymikes.com", "NYSE: JMKE", ("Jersey Mike's",)),
            _wiki_page("Q880942", "Blackstone Inc.", "blackstone.com", "NYSE: BX"),
            _wiki_page("Q121775110", "Sovos Brands", "thecampbellscompany.com"),
            _wiki_page("Q1030544", "Campbell's", "campbells.com", "Nasdaq: CPB", ("Campbell Soup Company",)),
            _wiki_page("Q465751", "Chipotle Mexican Grill", "chipotle.com", "NYSE: CMG"),
            _wiki_page("Q379801", "Advent International", "adventinternational.com"),
            _wiki_page("Q192314", "JPMorgan Chase", "jpmorganchase.com", "NYSE: JPM"),
            Entity(id="name:raos homemade", kind="brand", name="Rao's Homemade", source="wikipedia"),
        ],
        claims=[
            _wiki_claim("Q509255", "controlled_by", "Q55074808", "Buffalo Wild Wings",
                        "parent = [[Inspire Brands]] (2018–present)", start="2018"),
            _wiki_claim("Q55074808", "controlled_by", "Q7339900", "Inspire Brands", "owner = [[Roark Capital Group]]"),
            _wiki_claim("Q244457", "controlled_by", "Q7339900", "Subway (restaurant)", "owner = [[Roark Capital Group]]"),
            _wiki_claim("Q6184897", "controlled_by", "Q880942", "Jersey Mike's Subs", "parent = [[Blackstone Inc.]]"),
            _wiki_claim("Q121775110", "controlled_by", "Q1030544", "Sovos Brands",
                        "parent = {{ubl|[[Campbell Soup Company|Campbell's]] {{smaller|(2024–present)}}}}", start="2024"),
            _wiki_claim("name:raos homemade", "brand_of", "Q121775110", "Sovos Brands",
                        "brands = {{ubl|Rao's Homemade|Michael Angelo's|Noosa Yoghurt|Birch Benders}}"),
            # A bank brand whose parent runs PE funds must not read as PE-owned.
            _wiki_claim("Q524629", "brand_of", "Q192314", "Chase Bank", "parent = [[JPMorgan Chase]]"),
        ],
        classifications=[
            _wiki_kind("Q7339900", "pe_firm", "Roark Capital Group", "Short description: American private equity firm"),
            _wiki_kind("Q379801", "pe_firm", "Advent International", "Short description: Global private equity firm"),
            _wiki_kind("Q880942", "investment_firm", "Blackstone Inc.", "Short description: American alternative investment company"),
            _wiki_kind("Q880942", "public_company", "Blackstone Inc.", "traded_as = NYSE: BX"),
            _wiki_kind("Q6184897", "public_company", "Jersey Mike's Subs", "traded_as = NYSE: JMKE"),
            _wiki_kind("Q1030544", "public_company", "Campbell's", "traded_as = Nasdaq: CPB"),
            _wiki_kind("Q465751", "public_company", "Chipotle Mexican Grill", "traded_as = NYSE: CMG"),
            _wiki_kind("Q192314", "public_company", "JPMorgan Chase", "traded_as = NYSE: JPM"),
            _wiki_kind("Q55074808", "private_company", "Inspire Brands", "type = Private"),
        ],
    )
    nsi = CollectorResult(entities=[
        Entity(id="Q509255", kind="brand", name="Buffalo Wild Wings", source="nsi", aliases=["bww", "BW3"],
               ids={"wikidata": "Q509255", "nsi": "buffalowildwings-96af40"}, category="restaurant"),
        Entity(id="Q6184897", kind="brand", name="Jersey Mike's Subs", source="nsi", aliases=["Jersey Mike's"],
               ids={"wikidata": "Q6184897", "nsi": "jerseymikessubs-658eea"}, category="fast food"),
        Entity(id="Q244457", kind="brand", name="Subway", source="nsi",
               ids={"wikidata": "Q244457", "nsi": "subway-658eea"}, category="fast food"),
        Entity(id="Q465751", kind="brand", name="Chipotle", source="nsi",
               ids={"wikidata": "Q465751", "nsi": "chipotle-658eea"}, category="fast food"),
        Entity(id="Q524629", kind="brand", name="Chase", source="nsi",
               ids={"wikidata": "Q524629", "nsi": "chase-29fb3a"}, category="bank"),
    ])
    adviser_url = "https://adviserinfo.sec.gov/firm/summary/"
    adv = CollectorResult(
        entities=[
            Entity(id="crd:160368", kind="adviser", name="Roark Capital Management, LLC", source="adv",
                   ids={"crd": "160368", "website_domains": "roarkcapital.com"}),
            Entity(id="crd:155290", kind="adviser", name="Blackstone Management Partners L.L.C.", source="adv",
                   ids={"crd": "155290", "website_domains": "blackstone.com"}),
            Entity(id="crd:107038", kind="adviser", name="J.P. Morgan Investment Management Inc.", source="adv",
                   ids={"crd": "107038", "website_domains": "jpmorganchase.com"}),
            Entity(id="fund:805-9953320405", kind="fund", name="ROARK CAPITAL PARTNERS VI (T) LP", source="adv",
                   ids={"fund": "805-9953320405"}),
        ],
        claims=[Claim(source="adv", subject="fund:805-9953320405", relation="fund_of", object="crd:160368",
                      source_url=adviser_url + "160368", source_record="805-9953320405",
                      excerpt="ROARK CAPITAL PARTNERS VI (T) LP (Private Equity Fund)", official=True)],
        classifications=[
            Classification(entity="crd:160368", kind="pe_firm", source="adv", official=True,
                           evidence="Form ADV filed 2026-03-31: 14 of 14 private funds are private equity funds",
                           source_url=adviser_url + "160368"),
            Classification(entity="crd:155290", kind="pe_firm", source="adv", official=True,
                           evidence="Form ADV filed 2026-03-30: 36 of 40 private funds are private equity funds",
                           source_url=adviser_url + "155290"),
            Classification(entity="crd:107038", kind="pe_firm", source="adv", official=True,
                           evidence="Form ADV filed 2026-03-28: 12 of 90 private funds are private equity funds",
                           source_url=adviser_url + "107038"),
        ],
    )
    usda = CollectorResult(
        entities=[
            Entity(id="name:raos homemade", kind="brand", name="Rao's Homemade", source="usda", category="Pasta Sauces"),
            Entity(id="name:sovos brands intermediate inc", kind="company", name="Sovos Brands Intermediate, Inc.",
                   source="usda"),
        ],
        claims=[Claim(source="usda", subject="name:raos homemade", relation="brand_of",
                      object="name:sovos brands intermediate inc", start="2020-02-03", observed=True,
                      source_url="https://fdc.nal.usda.gov/food-search?type=Branded&query=RAO%27S%20HOMEMADE",
                      source_record="FoodData Central 2026-04-30",
                      excerpt="brand_owner = Sovos Brands Intermediate, Inc. (label records 2020-02-03 to 2023-06-23)")],
    )
    ftc_url = "https://www.ftc.gov/legal-library/browse/early-termination-notices/20262236"
    ftc = CollectorResult(
        entities=[Entity(id="name:c3 topco llc", kind="company", name="C3 TopCo, LLC", source="ftc"),
                  Entity(id="name:roark capital partners vi t lp", kind="company", name="Roark Capital Partners VI (T) LP", source="ftc"),
                  Entity(id="name:ssc partners ii a lp", kind="company", name="SSC Partners II-A LP", source="ftc")],
        claims=[
            Claim(source="ftc", subject="name:c3 topco llc", relation="deal", object="name:roark capital partners vi t lp",
                  start="2026-09-15", source_url=ftc_url, source_record="20262236", official=True,
                  excerpt="20262236: Roark Capital Partners VI (T) LP; SSC Partners II-A LP"),
            Claim(source="ftc", subject="name:c3 topco llc", relation="controlled_by", object="name:ssc partners ii a lp",
                  end="2026-09-15", source_url=ftc_url, source_record="20262236", official=True,
                  excerpt="Seller before early termination 2026-09-15"),
        ],
        scope=set(),
    )
    return {"wikipedia": wikipedia, "nsi": nsi, "adv": adv, "usda": usda, "ftc": ftc}


def sample_store(root: Path) -> Store:
    store = Store(root)
    for source, result in sample_results().items():
        store.apply(source, result, RUN_DATE)
        store.mark(source, RUN_DATE, ok=True)
    return store
```

`pipeline/run.py`:

```python
"""Nightly pipeline: collect → resolve → classify → verdicts → gates → publish → persist."""

from __future__ import annotations

import argparse
import copy
import datetime
import os
import sys
import tempfile
import traceback
from pathlib import Path

from . import checks, publish
from .classify import classify
from .collectors import adv, ftc, nsi, sec_ex21, usda, wikidata, wikipedia, wikipedia_history
from .config import CADENCE_DAYS, USER_AGENT, sec_user_agent
from .http import Fetcher
from .resolve import resolve
from .sample import sample_store
from .store import Store
from .verdict import build_verdicts

# Order matters: later collectors read what earlier ones stored this run.
COLLECTORS = (("nsi", nsi.collect, "web"), ("wikipedia", wikipedia.collect, "wiki"),
              ("wikidata", wikidata.collect, "wiki"), ("adv", adv.collect, "web"), ("ftc", ftc.collect, "ftc"),
              ("usda", usda.collect, "web"), ("sec_ex21", sec_ex21.collect, "sec"),
              ("wikipedia_history", wikipedia_history.collect, "wiki"))


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="state", help="data-branch checkout holding the graph")
    parser.add_argument("--out", default="build/site", help="where to write the static site")
    parser.add_argument("--site", default="site", help="static site sources to copy")
    parser.add_argument("--report", default="build/gate-report.md", help="where to write a failed-gate report")
    parser.add_argument("--today", default=datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    parser.add_argument("--only", default="", help="comma-separated sources to run now, due or not")
    parser.add_argument("--override-gates", action="store_true", help="skip count/churn gates (known answers still apply)")
    parser.add_argument("--sample", action="store_true", help="build from the built-in sample graph; no network")
    return parser.parse_args(argv)


def is_due(store: Store, source: str, today: str) -> bool:
    last = store.sources.get(source, {}).get("last_success")
    if not last:
        return True
    return (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(last)).days >= CADENCE_DAYS[source]


def fetchers() -> dict:
    email = os.environ.get("SEC_CONTACT_EMAIL", "").strip()
    return {"wiki": Fetcher(USER_AGENT, min_interval=0.35), "web": Fetcher(USER_AGENT, min_interval=0.25),
            "ftc": Fetcher(USER_AGENT, min_interval=1.0),
            "sec": Fetcher(sec_user_agent(email), min_interval=0.25) if email else None}


def collect_all(store: Store, today: str, only: set[str]) -> None:
    clients = fetchers()
    for source, collect, client in COLLECTORS:
        if (source not in only) if only else not is_due(store, source, today):
            continue
        try:
            if clients[client] is None:
                raise RuntimeError("SEC_CONTACT_EMAIL is not set")
            store.apply(source, collect(clients[client], store, today), today)
            store.mark(source, today, ok=True)
            print(f"{source}: ok ({store.sources[source]['active_claims']} active claims)", flush=True)
        except Exception as error:  # one failed source carries its previous claims forward
            store.mark(source, today, ok=False, error=f"{type(error).__name__}: {error}")
            print(f"{source}: FAILED, keeping previous data: {error}", file=sys.stderr, flush=True)
            traceback.print_exc()


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.sample:
        store = sample_store(Path(tempfile.mkdtemp(prefix="pe-sample-")))
        previous_sources = copy.deepcopy(store.sources)
    else:
        store = Store(Path(args.state)).load()
        previous_sources = copy.deepcopy(store.sources)
        collect_all(store, args.today, {s.strip() for s in args.only.split(",") if s.strip()})
    graph = resolve(store.all_entities(), store.all_claims(), store.all_classifications())
    verdicts = build_verdicts(graph, classify(graph), args.today)
    slug_of = publish.assign_slugs(graph, verdicts, store.slugs)
    by_slug = {slug_of[node_id]: verdict for node_id, verdict in verdicts.items()}
    report = checks.run_gates(previous_sources, store.sources, store.tiers, by_slug, args.override_gates)
    if not report.ok:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(report.markdown(), encoding="utf-8")
        print(report.markdown(), file=sys.stderr)
        return 2
    publish.write_site(Path(args.out), Path(args.site), verdicts, slug_of, store.sources, report.changes, args.today)
    store.tiers = {slug: verdict["tier"] for slug, verdict in by_slug.items()}
    store.changes[args.today] = report.changes
    if not args.sample:
        store.save()
    print(f"published {len(verdicts)} entities as of {args.today}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Create a placeholder site so the build can copy it:

```bash
mkdir -p site && printf '<!doctype html><title>PE Checker</title>\n' > site/index.html
```

Replace the `"scripts"` block in `package.json` with the following. Keep the existing `name`/`private`/`type` fields; set `"name": "pe-checker"` and `"version": "0.2.0"`.

```json
"scripts": {
  "test": "python3 -m unittest discover -s tests -t . -p 'test_*.py'",
  "build": "python3 -m pipeline.run",
  "build:sample": "python3 -m pipeline.run --sample --today 2026-10-05",
  "start": "python3 -m http.server 4173 --directory build/site"
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_run -v && npm test`
Expected: `test_run` 3 tests OK, then the full suite of 109 tests OK

- [ ] **Step 5: Run a sample build by hand**

Run: `npm run build:sample`
Expected: the last line is `published 15 entities as of 2026-10-05`, and `build/site/data/meta.json` exists

- [ ] **Step 6: Commit**

```bash
git add pipeline/run.py pipeline/sample.py tests/test_run.py package.json site/index.html
git commit -m "Add nightly orchestrator and offline sample build"
```

---

### Task 19: The website

**Files:**
- Create: `site/index.html` (replaces the placeholder), `site/app.js`, `site/style.css`, `site/about.html`, `playwright.config.js`
- Modify: `package.json` (adds the `test:site` script and the devDependency; adds `package-lock.json`)
- Test: `tests/site/search.spec.js`

**Interfaces:**
- Consumes: the published files from Task 17. The search entry shape is `[name, slug, tier, kind, search_text, score]`. Entity shards are at `data/e/<sha1(slug)[:3]>.json`.
- Produces: the routes `/?b=<slug>` (entity page) and `/?q=<text>` (not found). `app.js` exports `normalize`, `suggest`, `sentence`, and `renderVerdict`.
- Layout is verdict first: banner, then flags, then **Who owns it**, owner card list, **History**, **Deals**, and expandable **Sources**. Styling stays neutral; the visual theme is a separate design pass.

- [ ] **Step 1: Install Playwright**

```bash
npm install -D @playwright/test@1.63.0
npx playwright install chromium
npm pkg set scripts.test:site="playwright test"
```

- [ ] **Step 2: Write the failing browser test**

The "curly apostrophes" test pins Review Focus #1. The last test checks that page text is escaped.

`tests/site/search.spec.js`:

```javascript
import { expect, test } from '@playwright/test';

test('search leads to a verdict-first page with the ownership chain', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Search a brand or company' }).fill('bww');
  await page.getByRole('option', { name: /Buffalo Wild Wings/ }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Buffalo Wild Wings');
  const verdict = page.locator('.verdict');
  await expect(verdict).toContainText('PE-owned');
  await expect(verdict).toContainText('Controlled by Roark Capital Group, a private equity firm, since 2018.');
  await expect(page.locator('.chain')).toContainText('Inspire Brands');
  await page.locator('details.sources summary').click();
  await expect(page.locator('.evidence a').first()).toHaveAttribute('href', /^https:\/\//);
});

test('chain links move between entity pages', async ({ page }) => {
  await page.goto('/?b=raos-homemade');
  await expect(page.locator('.verdict')).toContainText("Owned by Campbell's since 2024.");
  await page.locator('.chain').getByRole('link', { name: 'Sovos Brands' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sovos Brands');
});

test('curly apostrophes and nicknames find the same brand', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Search a brand or company' }).fill('Rao’s');
  await expect(page.getByRole('option', { name: /Rao's Homemade/ })).toBeVisible();
});

test('a name we do not know says so without implying independence', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Search a brand or company' }).fill('zzqx corner shop');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Not in our data yet');
  await expect(page.locator('#result')).toContainText('says nothing about who owns it');
});

test('page text is escaped, never interpreted as markup', async ({ page }) => {
  await page.goto('/?q=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E');
  await expect(page.locator('#result img')).toHaveCount(0);
  await expect(page.locator('#result')).toContainText('<img src=x onerror=alert(1)>');
});
```

`playwright.config.js`:

```javascript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/site',
  use: { baseURL: 'http://localhost:4173' },
  projects: [{ name: 'phone', use: { ...devices['Pixel 7'] } }],
  webServer: {
    command: 'npm run build:sample && npm start',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `npm run test:site`
Expected: FAIL. The placeholder page has no search combobox: `getByRole('combobox', { name: 'Search a brand or company' })` times out.

- [ ] **Step 4: Write the site**

`site/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Look up whether private equity, an investment firm, or a big corporation owns a brand, with sources for every link.">
  <title>PE Checker</title>
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="style.css">
  <script type="module" src="app.js"></script>
</head>
<body>
  <header class="site-header">
    <a class="wordmark" href="./">PE Checker</a>
    <a href="about.html">How this works</a>
  </header>
  <main>
    <form id="search" class="search" role="search" autocomplete="off">
      <label for="query">Who really owns it?</label>
      <div class="combo">
        <input id="query" type="search" role="combobox" aria-label="Search a brand or company"
               aria-autocomplete="list" aria-expanded="false" aria-controls="suggestions"
               placeholder="Search a brand or company, e.g. Buffalo Wild Wings" spellcheck="false">
        <ul id="suggestions" role="listbox" aria-label="Matching brands and companies" hidden></ul>
      </div>
    </form>
    <section id="result" aria-live="polite">
      <div class="intro">
        <p>Private equity firms and big corporations often buy businesses and keep the name you know. Search a brand to see who controls it, since when, and the sources behind every link.</p>
        <p class="examples">Try <a href="?b=buffalo-wild-wings">Buffalo Wild Wings</a>, <a href="?b=jersey-mikes-subs">Jersey Mike's</a>, or <a href="?b=raos-homemade">Rao's Homemade</a>.</p>
      </div>
    </section>
  </main>
  <footer class="site-footer"><span id="freshness"></span> <a href="about.html">Sources and method</a></footer>
</body>
</html>
```

`site/app.js`:

```javascript
// Search and verdict pages for PE Checker. Data comes from static JSON built nightly.
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const safeUrl = (value) => { try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : ''; } catch { return ''; } };

// Mirrors pipeline/model.py normalize(): keep the two in sync.
export function normalize(value) {
  return String(value ?? '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/['’`]/g, '').replace(/\b([a-z])\./g, '$1').replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, ' ').trim();
}

const TIERS = {
  pe_owned: { symbol: '●', label: 'PE-owned' },
  investment_owned: { symbol: '●', label: 'Investment-firm owned' },
  corporate_owned: { symbol: '◆', label: 'Corporate-owned' },
  no_signals: { symbol: '○', label: 'No ownership signals found' },
  owner: { symbol: '◎', label: 'Owner' },
};
const KIND_LABELS = { pe_firm: 'private equity firm', investment_firm: 'investment firm', public_company: 'public company', private_company: 'private company' };

const cache = new Map();
function getJson(path) {
  if (!cache.has(path)) cache.set(path, fetch(path).then((r) => (r.ok ? r.json() : null)).catch(() => null));
  return cache.get(path);
}

async function shardOf(slug) {
  const digest = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(slug));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('').slice(0, 3);
}

// ---- search ---------------------------------------------------------------
export async function suggest(query) {
  const q = normalize(query);
  if (q.length < 2) return [];
  const tokens = q.split(' ');
  const longest = tokens.reduce((a, b) => (b.length > a.length ? b : a));
  const entries = (await getJson(`data/search/${longest.length >= 3 ? longest.slice(0, 3) : 'top'}.json`)) || [];
  const score = (entry) => {
    const names = entry[4].split(' | ');
    return (names.includes(q) ? 100 : 0) + (names.some((n) => n.startsWith(q)) ? 50 : 0) + entry[5];
  };
  return entries
    .filter((entry) => { const words = entry[4].split(/ \| | /); return tokens.every((t) => words.some((w) => w.startsWith(t))); })
    .sort((a, b) => score(b) - score(a) || a[0].localeCompare(b[0]))
    .slice(0, 8);
}

let active = -1;
let current = [];
function renderSuggestions(list) {
  const box = $('#suggestions');
  current = list;
  active = -1;
  box.innerHTML = list.map((entry, index) => `<li role="option" id="option-${index}" data-slug="${esc(entry[1])}" aria-selected="false">
      <span class="option-name">${esc(entry[0])}</span><span class="option-tier tier-${esc(entry[2])}">${esc(TIERS[entry[2]]?.label || '')}</span></li>`).join('');
  box.hidden = list.length === 0;
  $('#query').setAttribute('aria-expanded', String(list.length > 0));
}
function highlight(index) {
  const options = [...document.querySelectorAll('#suggestions [role=option]')];
  options.forEach((option, i) => option.setAttribute('aria-selected', String(i === index)));
  active = index;
  $('#query').setAttribute('aria-activedescendant', index >= 0 ? `option-${index}` : '');
}
function go(slug) { const url = new URL(location.href); url.search = `?b=${encodeURIComponent(slug)}`; history.pushState(null, '', url); route(); }

// ---- verdict page ---------------------------------------------------------
const year = (date) => (date ? String(date).slice(0, 4) : '');
const nameLink = (ref) => (ref?.slug ? `<a href="?b=${encodeURIComponent(ref.slug)}">${esc(ref.name)}</a>` : esc(ref?.name ?? 'Unknown'));

export function sentence(v) {
  const since = v.since ? ` since ${v.since_observed ? 'at least ' : ''}${year(v.since)}` : '';
  switch (v.tier) {
    case 'pe_owned': return `Controlled by ${nameLink(v.owner)}, a private equity firm${since && `,${since}`}.`;
    case 'investment_owned': return `Controlled by ${nameLink(v.owner)}, an investment firm${since && `,${since}`}.`;
    case 'corporate_owned': return `Owned by ${nameLink(v.owner)}${since}.`;
    case 'owner': return `${esc(v.name)} is ${v.owner_kind === 'pe_firm' ? 'a private equity firm' : 'an investment firm'}.`;
    default: return `We found no parent owner in our sources. That doesn't confirm it's independent.${v.ticker ? ` Publicly traded (${esc(v.ticker)}).` : ''}${v.deals?.length ? ' A recent deal is listed below.' : ''}`;
  }
}

function flagText(flag) {
  switch (flag.type) {
    case 'formerly_pe': return `◇ Formerly PE-owned: ${nameLink(flag.owner)}${flag.start || flag.end ? ` (${year(flag.start) || '?'}–${year(flag.end) || '?'})` : ''}`;
    case 'formerly_investment': return `◇ Formerly owned by investment firm ${nameLink(flag.owner)}${flag.end ? ` (until ${year(flag.end)})` : ''}`;
    case 'changed_hands': return `⟳ Changed hands in ${flag.year}`;
    case 'flipped': return `↻ Sold repeatedly: ${flag.years.join(', ')}`;
    case 'rollup': return `⧉ ${nameLink(flag.owner)} controls ${flag.count} ${esc(flag.category)} brands in our data`;
    default: return '';
  }
}

function evidenceList(items) {
  return `<ul class="evidence">${items.map((e) => `<li><a href="${esc(safeUrl(e.url))}" rel="noopener noreferrer" target="_blank">${esc(e.source)}</a>
    ${e.official ? '<span class="badge">official filing</span>' : ''}${e.observed ? '<span class="badge">date observed</span>' : ''}
    <q>${esc(e.excerpt)}</q> <span class="muted">checked ${esc(e.last_seen || '')}</span></li>`).join('')}</ul>`;
}

export function renderVerdict(v) {
  const tier = TIERS[v.tier] || TIERS.no_signals;
  const flags = v.flags.map(flagText).filter(Boolean);
  const nodeMeta = (node, i) => [KIND_LABELS[node.owner_kind],
    i && node.since ? `since ${node.since_observed ? 'at least ' : ''}${year(node.since)}` : '',
    i ? node.confidence : ''].filter(Boolean).map(esc).join(' · ');
  const chain = v.chain.length > 1 ? `<section class="chain"><h2>Who owns it</h2><ol>${v.chain.map((node, i) => `<li>
      <strong>${i ? nameLink(node) : esc(node.name)}</strong> <span class="muted">${nodeMeta(node, i)}</span>
      ${node.alternatives?.length ? `<p class="muted">Other sources name: ${node.alternatives.map(nameLink).join(', ')}</p>` : ''}</li>`).join('')}</ol></section>` : '';
  const history = v.history.length ? `<section><h2>History</h2><ul class="timeline">${v.history.map((p) => `<li>
      ${esc(year(p.start) || '?')}–${esc(year(p.end) || '?')}: ${esc(p.subject.name)} owned by ${nameLink(p.owner)}${p.owner.kind ? ` (${esc(KIND_LABELS[p.owner.kind] || '')})` : ''}</li>`).join('')}</ul></section>` : '';
  const deals = v.deals.length ? `<section><h2>Deals</h2><ul class="timeline">${v.deals.map((d) => `<li>${esc(d.date)}: acquired by ${nameLink(d.acquirer)} · <a href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener noreferrer">FTC notice</a></li>`).join('')}</ul></section>` : '';
  const controls = v.controls?.length ? `<section><h2>Brands it controls in our data (${v.controls_count})</h2><ul class="columns">${v.controls.map((c) => `<li>${nameLink(c)}</li>`).join('')}</ul></section>` : '';
  const sources = [...v.chain.slice(1).flatMap((n) => n.evidence || []), ...v.history.flatMap((p) => p.evidence), ...(v.kind_evidence || []).map((k) => ({ source: k.source, url: k.url, excerpt: k.evidence, official: k.official }))];
  return `<article class="verdict-page">
    <h1>${esc(v.name)}</h1>
    <div class="verdict tier-${esc(v.tier)}"><p class="tier"><span aria-hidden="true">${tier.symbol}</span> ${esc(v.tier === 'owner' ? (v.owner_kind === 'pe_firm' ? 'Private equity firm' : 'Investment firm') : tier.label)}</p>
      <p>${sentence(v)}</p>${v.confidence ? `<p class="muted">Confidence: ${esc(v.confidence)}</p>` : ''}</div>
    ${flags.length ? `<ul class="flags">${flags.map((f) => `<li>${f}</li>`).join('')}</ul>` : ''}
    ${chain}${controls}${history}${deals}
    ${sources.length ? `<details class="sources"><summary>Sources (${sources.length})</summary>${evidenceList(sources)}</details>` : ''}
    <p class="muted">Last checked ${esc(v.as_of)}. Ownership facts only: this page does not claim an owner changed the business.</p>
  </article>`;
}

function renderNotFound(query) {
  return `<article class="verdict-page"><h1>Not in our data yet</h1>
    <p>We don't have a record for “${esc(query)}”. That says nothing about who owns it: our sources cover national brands and their parent companies, and many businesses aren't listed yet.</p></article>`;
}

async function route() {
  const params = new URLSearchParams(location.search);
  const slug = params.get('b');
  const query = params.get('q');
  if (!slug && !query) return;
  if (slug) {
    const records = await getJson(`data/e/${await shardOf(slug)}.json`);
    const verdict = records?.[slug];
    $('#result').innerHTML = verdict ? renderVerdict(verdict) : renderNotFound(slug.replace(/-/g, ' '));
    document.title = verdict ? `${verdict.name} · PE Checker` : 'Not found · PE Checker';
  } else {
    $('#result').innerHTML = renderNotFound(query);
    document.title = 'Not found · PE Checker';
  }
}

function init() {
  const input = $('#query');
  let timer;
  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(async () => renderSuggestions(await suggest(input.value)), 120); });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown' && current.length) { event.preventDefault(); highlight(Math.min(active + 1, current.length - 1)); }
    if (event.key === 'ArrowUp' && current.length) { event.preventDefault(); highlight(Math.max(active - 1, 0)); }
    if (event.key === 'Escape') renderSuggestions([]);
  });
  $('#suggestions').addEventListener('click', (event) => { const option = event.target.closest('[role=option]'); if (option) { renderSuggestions([]); go(option.dataset.slug); } });
  $('#search').addEventListener('submit', async (event) => {
    event.preventDefault();
    const list = current.length ? current : await suggest(input.value);
    const choice = list[active >= 0 ? active : 0];
    renderSuggestions([]);
    if (choice) go(choice[1]);
    else if (input.value.trim()) { const url = new URL(location.href); url.search = `?q=${encodeURIComponent(input.value.trim())}`; history.pushState(null, '', url); route(); }
  });
  window.addEventListener('popstate', route);
  getJson('data/meta.json').then((meta) => { if (meta) $('#freshness').textContent = `Data as of ${meta.as_of}.`; });
  route();
}

if (typeof document !== 'undefined') init();
```

`site/style.css`:

```css
/* Neutral Phase 1 styling. The visual theme gets its own design pass later. */
:root {
  --bg: #ffffff; --text: #1d1d1f; --muted: #5c5c63; --line: #d9d9de; --surface: #f4f4f6;
  --pe: #b3122e; --inv: #9a4a00; --corp: #1f4f99; --none: #4a4a50; --link: #1f4f99;
  color-scheme: light dark;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #141416; --text: #f2f2f4; --muted: #a8a8b0; --line: #34343a; --surface: #1e1e22;
    --pe: #ff6b81; --inv: #ffb067; --corp: #8cb4ff; --none: #c4c4cc; --link: #8cb4ff;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
a { color: var(--link); }
main, .site-header, .site-footer { max-width: 44rem; margin: 0 auto; padding: 0 16px; }
.site-header { display: flex; justify-content: space-between; align-items: center; padding-top: 16px; padding-bottom: 16px; }
.wordmark { font-weight: 800; text-decoration: none; color: var(--text); font-size: 1.15rem; }
.search label { display: block; font-size: 1.6rem; font-weight: 750; margin: 24px 0 12px; }
.combo { position: relative; }
#query { width: 100%; font: inherit; font-size: 1.05rem; padding: 14px 16px; border: 2px solid var(--line); border-radius: 12px; background: var(--bg); color: var(--text); }
#query:focus { outline: 3px solid var(--link); outline-offset: 1px; }
#suggestions { position: absolute; z-index: 2; left: 0; right: 0; margin: 4px 0 0; padding: 4px; list-style: none; background: var(--bg); border: 1px solid var(--line); border-radius: 12px; box-shadow: 0 8px 24px rgb(0 0 0 / 0.12); }
#suggestions li { display: flex; justify-content: space-between; gap: 12px; padding: 10px 12px; border-radius: 8px; cursor: pointer; }
#suggestions li[aria-selected="true"], #suggestions li:hover { background: var(--surface); }
.option-tier { font-size: 0.85rem; color: var(--muted); white-space: nowrap; }
.intro { margin-top: 24px; color: var(--muted); }
.verdict-page h1 { font-size: 2rem; margin: 32px 0 12px; line-height: 1.15; }
.verdict { border-radius: 14px; padding: 16px 18px; background: var(--surface); border: 2px solid var(--line); }
.verdict .tier { font-weight: 800; letter-spacing: 0.02em; text-transform: uppercase; margin: 0 0 4px; }
.verdict p { margin: 4px 0; }
.tier-pe_owned { border-color: var(--pe); } .tier-pe_owned .tier, .option-tier.tier-pe_owned { color: var(--pe); }
.tier-investment_owned { border-color: var(--inv); } .tier-investment_owned .tier, .option-tier.tier-investment_owned { color: var(--inv); }
.tier-corporate_owned { border-color: var(--corp); } .tier-corporate_owned .tier, .option-tier.tier-corporate_owned { color: var(--corp); }
.tier-no_signals .tier { color: var(--none); }
.flags { list-style: none; padding: 0; margin: 12px 0; display: grid; gap: 6px; }
section h2 { font-size: 1.05rem; margin: 28px 0 8px; }
.chain ol { margin: 0; padding-left: 1.25rem; display: grid; gap: 10px; }
.timeline { padding-left: 1.25rem; }
.columns { columns: 2 12rem; padding-left: 1.25rem; }
.muted { color: var(--muted); font-size: 0.9rem; }
.sources { margin-top: 24px; } .sources summary { cursor: pointer; font-weight: 650; }
.evidence { padding-left: 1.25rem; display: grid; gap: 8px; overflow-wrap: anywhere; }
.badge { font-size: 0.75rem; border: 1px solid var(--line); border-radius: 999px; padding: 1px 8px; margin-left: 4px; color: var(--muted); }
.site-footer { padding-top: 32px; padding-bottom: 32px; color: var(--muted); font-size: 0.9rem; }
```

`site/about.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>How PE Checker works</title>
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="site-header"><a class="wordmark" href="./">PE Checker</a></header>
  <main class="verdict-page">
    <h1>How this works</h1>
    <p>Every night an automated job collects ownership facts from free public sources, links them into one ownership graph, and recomputes each verdict. Nobody edits verdicts by hand. A verdict changes only when a source changes.</p>
    <h2>What the labels mean</h2>
    <ul>
      <li><strong>● PE-owned</strong>: a private equity firm sits somewhere above the brand in its current ownership chain.</li>
      <li><strong>● Investment-firm owned</strong>: an investment firm that isn't classified as private equity sits in the chain.</li>
      <li><strong>◆ Corporate-owned</strong>: a parent company owns it, with no investment firm above.</li>
      <li><strong>○ No ownership signals found</strong>: our sources name no parent. That does not mean it's independent.</li>
      <li><strong>◇ Formerly PE-owned</strong>, <strong>⟳ Changed hands</strong>, <strong>↻ Sold repeatedly</strong>, <strong>⧉ Roll-up</strong>: history and pattern flags.</li>
    </ul>
    <h2>Confidence</h2>
    <p><strong>Confirmed</strong> means an official filing (SEC, FTC) supports the link, or two independent sources agree. Wikipedia and Wikidata together count as one. <strong>Reported</strong> means a single source. <strong>Conflicting</strong> means sources disagree; we show both.</p>
    <h2>Sources</h2>
    <ul id="sources">
      <li><a href="https://en.wikipedia.org/">Wikipedia</a> company infoboxes and page history, used under <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>. Each claim links to its article.</li>
      <li><a href="https://www.wikidata.org/">Wikidata</a> (CC0).</li>
      <li><a href="https://nsi.guide/">OpenStreetMap Name Suggestion Index</a> brand list (BSD-3-Clause).</li>
      <li><a href="https://fdc.nal.usda.gov/">USDA FoodData Central</a> branded foods (CC0). U.S. Department of Agriculture, Agricultural Research Service.</li>
      <li><a href="https://adviserinfo.sec.gov/">SEC Form ADV</a> private fund data (public domain).</li>
      <li><a href="https://www.sec.gov/edgar">SEC EDGAR</a> 10-K Exhibit 21 subsidiary lists (public domain).</li>
      <li><a href="https://www.ftc.gov/legal-library/browse/early-termination-notices">FTC early termination notices</a> (public domain).</li>
    </ul>
    <h2>Source freshness</h2>
    <ul id="freshness-list"><li>Loading…</li></ul>
    <h2>Limits</h2>
    <p>Many private deals are never disclosed. Phase 1 covers national brands and their parent companies, not individual local businesses. Pages state facts about ownership and do not claim that an owner changed a business.</p>
  </main>
  <script type="module">
    const list = document.querySelector('#freshness-list');
    fetch('data/meta.json').then((r) => r.json()).then((meta) => {
      list.replaceChildren(...Object.entries(meta.sources).map(([name, s]) => {
        const item = document.createElement('li');
        item.textContent = `${name}: last success ${s.last_success || 'never'}${s.error ? ` (stale since then: ${s.error})` : ''}`;
        return item;
      }));
    }).catch(() => { list.textContent = 'Freshness data unavailable.'; });
  </script>
</body>
</html>
```

- [ ] **Step 5: Run the browser tests to verify they pass**

Run: `npm run test:site`
Expected: `5 passed`

- [ ] **Step 6: Look at it on a phone-sized screen**

Run `npm run build:sample && npm start`, open `http://localhost:4173/?b=buffalo-wild-wings` at 390 px wide, and check:
- the banner reads "● PE-OWNED — Controlled by Roark Capital Group, a private equity firm, since 2018."
- the page doesn't scroll sideways
- Sources expands

- [ ] **Step 7: Commit**

```bash
git add site playwright.config.js tests/site package.json package-lock.json
git commit -m "Add verdict-first search site and browser tests"
```

---

### Task 20: GitHub Actions (tests, nightly build, Pages)

**Files:**
- Create: `.github/workflows/test.yml`, `.github/workflows/nightly.yml`

**Interfaces:**
- Consumes: `npm test`, `npm run test:site`, and `python -m pipeline.run` exit codes (0, 2, or other).
- Produces: a nightly run at 07:00 UTC plus a manual run with `override_gates` and `only` inputs.
  - On exit 0 it commits `state/` to the `data` branch and deploys `build/site` to Pages.
  - On exit 2 it opens an issue with `build/gate-report.md`.
- Workflow inputs reach the shell only through `env:` variables, never `${{ }}` inside `run:`.

- [ ] **Step 1: Write the workflows**

`.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: npm test
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - run: npm ci
      - run: npx playwright install --with-deps chromium
      - run: npm run test:site
```

`.github/workflows/nightly.yml`:

```yaml
name: Nightly build

on:
  schedule:
    - cron: "0 7 * * *"
  workflow_dispatch:
    inputs:
      override_gates:
        description: "Publish even if claim-count or churn gates fail (known answers still apply)"
        type: boolean
        default: false
      only:
        description: "Comma-separated sources to run now (blank = whatever is due)"
        type: string
        default: ""

permissions:
  contents: write
  pages: write
  id-token: write
  issues: write

concurrency:
  group: nightly
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 240
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4

      - name: Check out the data branch into state/
        run: |
          if git ls-remote --exit-code --heads origin data > /dev/null; then
            git fetch --depth=1 origin data:data
            git worktree add state data
          else
            git worktree add --orphan -b data state
          fi

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt

      - name: Restore large downloads
        uses: actions/cache@v4
        with:
          path: .cache
          key: downloads-${{ github.run_id }}
          restore-keys: downloads-

      - name: Run the pipeline
        id: pipeline
        env:
          SEC_CONTACT_EMAIL: ${{ secrets.SEC_CONTACT_EMAIL }}
          FTC_API_KEY: ${{ secrets.FTC_API_KEY }}
          PE_CACHE_DIR: .cache
          OVERRIDE: ${{ inputs.override_gates }}
          ONLY: ${{ inputs.only }}
        run: |
          set +e
          args=(--state state --out build/site --report build/gate-report.md)
          if [ "$OVERRIDE" = "true" ]; then args+=(--override-gates); fi
          if [ -n "$ONLY" ]; then args+=(--only "$ONLY"); fi
          python -m pipeline.run "${args[@]}"
          code=$?
          echo "code=$code" >> "$GITHUB_OUTPUT"
          # 2 means a safety gate failed: handled below, not a crash.
          if [ "$code" -ne 0 ] && [ "$code" -ne 2 ]; then exit "$code"; fi

      - name: Open an issue when a safety gate fails
        if: steps.pipeline.outputs.code == '2'
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh issue create --title "Nightly gates failed $(date -u +%F)" --body-file build/gate-report.md

      - name: Commit the graph to the data branch
        if: steps.pipeline.outputs.code == '0'
        working-directory: state
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A
          if ! git diff --cached --quiet; then git commit -q -m "data: $(date -u +%F)"; fi
          git push origin data

      - uses: actions/configure-pages@v5
        if: steps.pipeline.outputs.code == '0'
      - uses: actions/upload-pages-artifact@v3
        if: steps.pipeline.outputs.code == '0'
        with:
          path: build/site
      - id: deploy
        if: steps.pipeline.outputs.code == '0'
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Check that inputs never reach the shell directly**

Run: `grep -n '\${{ inputs' .github/workflows/nightly.yml`
Expected: exactly two lines, `OVERRIDE: ${{ inputs.override_gates }}` and `ONLY: ${{ inputs.only }}`, both under `env:`. GitHub validates the YAML itself when the workflow is pushed; any syntax error appears on the Actions tab.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows
git commit -m "Add CI tests and the nightly build-and-publish workflow"
```

- [ ] **Step 4: Manual setup (Derek; do not automate)**

Ask Derek before running any command that creates or pushes to a remote. The checklist:
1. Create the public repo `d-pap/pe-checker` (`gh repo create d-pap/pe-checker --public --source . --push`). If the name differs, update `REPO_URL` in `pipeline/config.py` first.
2. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
3. Get a free api.data.gov key at https://api.data.gov/signup/.
4. Settings → Secrets and variables → Actions: add `SEC_CONTACT_EMAIL` (Derek's SEC contact address) and `FTC_API_KEY`.
5. Actions → Nightly build → Run workflow (leave inputs blank). The first run takes 2–3 hours: the Wikipedia full pass, the FTC backfill, the ADV and USDA downloads, and the start of the SEC and history backfills. If it opens a "gates failed" issue, read the known-answer lines first.

---

### Task 21: Retire the prototype and rewrite the docs

**Files:**
- Delete: `core.py`, `server.py`, `live.html`, `live.js`, `live.css`, `styles.css`, `test_core.py`
- Modify: `README.md`, `AGENTS.md`

**Interfaces:** none (documentation only).

- [ ] **Step 1: Remove the prototype**

```bash
git rm -q core.py server.py live.html live.js live.css styles.css test_core.py
rm -rf __pycache__ pe-checker.sqlite3 pe-checker.sqlite3-shm pe-checker.sqlite3-wal
```

- [ ] **Step 2: Replace `README.md`**

````markdown
# PE Checker

Look up whether private equity, an investment firm, or a big corporation controls a brand, with a dated source for every link. An automated job rebuilds the ownership graph every night from free public data, and nobody maintains a list by hand.

## How it works

1. **Collect.** One collector per source turns raw data into dated claims ("Buffalo Wild Wings is controlled by Inspire Brands, 2018–present, per Wikipedia"). The sources are Wikipedia infoboxes and page history, Wikidata, OpenStreetMap's Name Suggestion Index, USDA FoodData Central, SEC Form ADV, SEC 10-K Exhibit 21, and FTC early-termination notices.
2. **Resolve.** Records about the same company merge only on strong identifiers or an unambiguous exact name. Fuzzy matches are never used.
3. **Classify.** Owners are labeled PE firm, investment firm, public company, or private company. Form ADV confirms PE firms.
4. **Verdict.** Each brand's current chain is walked up to its top owner: ● PE-owned, ● investment-firm owned, ◆ corporate-owned, or ○ no ownership signals found. Flags show former PE ownership, recent changes of hands, repeated sales, and roll-ups.
5. **Gate and publish.** Known answers, claim-count swings, and verdict churn are checked before anything goes live. The graph's history is committed to the `data` branch, and the static site deploys to GitHub Pages.

The design and roadmap are in `docs/superpowers/specs/2026-10-05-national-ownership-graph-design.md`.

## Develop

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
npm test                              # offline unit tests
npm run build:sample && npm start     # sample site at http://localhost:4173
npm ci && npx playwright install chromium && npm run test:site   # browser tests
```

Run one live source against a local copy of the data branch:

```bash
git fetch origin data:data && git worktree add state data
SEC_CONTACT_EMAIL=you@example.com FTC_API_KEY=... npm run build -- --only wikipedia
```

## Limits

Many private deals are never disclosed. Phase 1 covers national brands and their parent companies; local businesses come later. A missing record never means a business is independent. Pages report ownership facts and do not claim that an owner changed a business.

## Data and attribution

Wikipedia content is CC BY-SA 4.0, and each claim links to its article. Wikidata and USDA are CC0. The Name Suggestion Index is BSD-3-Clause. SEC and FTC records are public domain. Licenses for this repository's code and published data are pending (see the spec's open questions).
````

- [ ] **Step 3: Replace `AGENTS.md`**

```markdown
# PE Checker development notes

- Setup: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`. The only Python dependency is mwparserfromhell.
- `npm test` runs the offline unit tests (no network). `npm run test:site` builds the sample site and runs the Playwright tests (run `npm ci && npx playwright install chromium` once).
- `npm run build:sample && npm start` serves the built-in sample graph at http://localhost:4173. `npm run build -- --only <source>` runs one live collector against `state/` (a worktree of the `data` branch).
- Layout: `pipeline/collectors/*` (one module per source; each `collect(fetcher, store, run_date)` returns a `CollectorResult`), then `store.py`, `resolve.py`, `classify.py`, `verdict.py`, `checks.py`, `publish.py`, orchestrated by `run.py`. `site/` is the static front end, and its `normalize()` must stay identical to `pipeline/model.py`'s.
- Do not present a missing record as independent ownership. Do not merge same-name entities without corroboration. Do not let a deal establish current control. Never delete claims or hand-edit verdicts. The known answers in `checks.py` are test expectations, never site data.
- Secrets (`SEC_CONTACT_EMAIL`, `FTC_API_KEY`) live only in GitHub Actions secrets or your shell. Never commit or print them.
- Private Equity Vet's 2026-08-12 terms restrict republishing a material part of its compilation without written permission. It is not used in Phase 1; resolve data rights before any Phase 3 use.
```

- [ ] **Step 4: Verify nothing references the prototype**

Run: `grep -rn "core.py\|server.py\|live.js\|sqlite3" --include='*.py' --include='*.js' --include='*.json' --include='*.md' . | grep -v node_modules | grep -v docs/superpowers`
Expected: no output

Run: `npm test && npm run test:site`
Expected: 109 tests OK; 5 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Retire the vet/HVAC prototype and document the new pipeline"
```
