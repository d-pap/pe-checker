"""Live, source-attributed research index for the local PE Checker prototype."""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import unicodedata
import urllib.request
import urllib.parse
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).parent
DB_PATH = ROOT / "pe-checker.sqlite3"
VET_URL = "https://privateequityvet.org/files/vet-list.xlsx"
VET_PAGE = "https://privateequityvet.org/vet-list/"
HVAC_URL = "https://hvacrollups.com/deals/export.csv?sector=service_contractor"
HVAC_PAGE = "https://hvacrollups.com/data"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "PECheckerPrototype/0.2 (local ownership research; low-volume requests)"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
STATE_CODES = dict(zip(
    "alabama alaska arizona arkansas california colorado connecticut delaware florida georgia hawaii idaho illinois indiana iowa kansas kentucky louisiana maine maryland massachusetts michigan minnesota mississippi missouri montana nebraska nevada newhampshire newjersey newmexico newyork northcarolina northdakota ohio oklahoma oregon pennsylvania rhodeisland southcarolina southdakota tennessee texas utah vermont virginia washington westvirginia wisconsin wyoming".split(),
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
))


def normalize(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "").casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def fetch(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def excel_date(value: str) -> str:
    if not value:
        return ""
    try:
        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date().isoformat()
    except ValueError:
        return value


def xlsx_rows(payload: bytes):
    """Read the publisher's simple XLSX sheet with only Python's standard library."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.itertext()) for node in shared_root.findall(f"{NS}si")]
        with archive.open("xl/worksheets/sheet1.xml") as sheet:
            for _, element in ET.iterparse(sheet, events=("end",)):
                if element.tag != f"{NS}row":
                    continue
                cells = [""] * 13
                for cell in element.findall(f"{NS}c"):
                    column = re.match(r"[A-Z]+", cell.attrib.get("r", ""))
                    if not column:
                        continue
                    index = 0
                    for letter in column.group():
                        index = index * 26 + ord(letter) - 64
                    index -= 1
                    if index >= len(cells):
                        continue
                    raw = cell.findtext(f"{NS}v") or ""
                    if cell.attrib.get("t") == "s" and raw:
                        raw = shared[int(raw)]
                    if cell.attrib.get("t") == "inlineStr":
                        raw = "".join(cell.find(f"{NS}is").itertext())
                    cells[index] = raw
                if element.attrib.get("r") != "1":
                    cells[10] = excel_date(cells[10])
                    cells[11] = excel_date(cells[11])
                    yield cells
                element.clear()


def hvac_rows(payload: bytes):
    text = payload.decode("utf-8-sig")
    return csv.DictReader(line for line in io.StringIO(text) if not line.startswith("#"))


def connect(path: Path = DB_PATH):
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.executescript("""
        PRAGMA journal_mode = WAL;
        CREATE TABLE IF NOT EXISTS source_sync (
            source TEXT PRIMARY KEY, fetched_at TEXT NOT NULL, row_count INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS vet_practices (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL,
            address TEXT, city TEXT, state TEXT, postal_code TEXT, country TEXT,
            phone TEXT, consolidator TEXT, investor TEXT, website TEXT,
            acquired TEXT, updated TEXT, operating_status TEXT
        );
        CREATE INDEX IF NOT EXISTS vet_name ON vet_practices(name_key);
        CREATE INDEX IF NOT EXISTS vet_place ON vet_practices(city, state);
        CREATE TABLE IF NOT EXISTS hvac_deals (
            slug TEXT PRIMARY KEY, target TEXT NOT NULL, target_key TEXT NOT NULL,
            acquirer TEXT, sponsor TEXT, announced_date TEXT, closed_date TEXT,
            deal_type TEXT, status TEXT, verified INTEGER, verification_status TEXT,
            source_url TEXT
        );
        CREATE INDEX IF NOT EXISTS hvac_target ON hvac_deals(target_key);
        CREATE TABLE IF NOT EXISTS wikidata_cache (
            name_key TEXT PRIMARY KEY, payload TEXT NOT NULL, fetched_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS wikipedia_cache (
            name_key TEXT PRIMARY KEY, payload TEXT NOT NULL, fetched_at TEXT NOT NULL
        );
    """)
    return db


def source_age_hours(db, source: str) -> float | None:
    row = db.execute("SELECT fetched_at FROM source_sync WHERE source=?", (source,)).fetchone()
    if row is None:
        return None
    return (datetime.now(timezone.utc) - datetime.fromisoformat(row[0])).total_seconds() / 3600


def sync_vets(db, payload: bytes):
    rows = list(xlsx_rows(payload))
    if len(rows) < 5000:
        raise ValueError("Veterinary download is unexpectedly small")
    with db:
        db.execute("DELETE FROM vet_practices")
        db.executemany("""INSERT INTO vet_practices
            (name,name_key,address,city,state,postal_code,country,phone,consolidator,investor,website,acquired,updated,operating_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [
                (r[0], normalize(r[0]), *r[1:13]) for r in rows if r[0]
            ])
        db.execute("INSERT OR REPLACE INTO source_sync VALUES (?,?,?)",
                   ("vet", datetime.now(timezone.utc).isoformat(), len(rows)))
    return len(rows)


def sync_hvac(db, payload: bytes):
    rows = list(hvac_rows(payload))
    if len(rows) < 500:
        raise ValueError("HVAC download is unexpectedly small")
    with db:
        db.execute("DELETE FROM hvac_deals")
        db.executemany("""INSERT INTO hvac_deals
            (slug,target,target_key,acquirer,sponsor,announced_date,closed_date,deal_type,status,verified,verification_status,source_url)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", [
                (r["slug"], r["target"], normalize(r["target"]), r["acquirer"], r["sponsor"],
                 r["announced_date"], r["closed_date"], r["deal_type"], r["status"],
                 int(r["verified_badge"].lower() == "true"), r["verification_status"], r["source_url"])
                for r in rows if r["target"] and r["slug"]
            ])
        db.execute("INSERT OR REPLACE INTO source_sync VALUES (?,?,?)",
                   ("hvac", datetime.now(timezone.utc).isoformat(), len(rows)))
    return len(rows)


def refresh(db, force=False):
    outcome = {}
    for name, url, importer in (("vet", VET_URL, sync_vets), ("hvac", HVAC_URL, sync_hvac)):
        age = source_age_hours(db, name)
        if not force and age is not None and age < 24:
            outcome[name] = {"status": "cached", "age_hours": round(age, 1)}
            continue
        try:
            outcome[name] = {"status": "updated", "rows": importer(db, fetch(url))}
        except Exception as error:
            outcome[name] = {"status": "error", "message": str(error), "cached_age_hours": age}
    return outcome


def score_name(query: str, candidate: str):
    if query == candidate:
        return 100
    if len(query) >= 5 and candidate.startswith(query):
        return 70
    if len(query) >= 5 and query in candidate:
        return 45
    return 0


def place_tokens(place: str):
    tokens = normalize(place).split()
    for width in (2, 1):
        if len(tokens) >= width:
            state = "".join(tokens[-width:])
            if state in STATE_CODES:
                return tokens[:-width] + [STATE_CODES[state].lower()]
    return tokens


def vet_matches(db, name: str, place: str = "", limit=12):
    key = normalize(name)
    wanted_place = place_tokens(place)
    if not key and not wanted_place:
        return []
    rows = db.execute("SELECT * FROM vet_practices").fetchall()
    ranked = []
    for row in rows:
        name_score = score_name(key, row["name_key"]) if key else 30
        if not name_score:
            continue
        location = normalize(" ".join((row["city"] or "", row["state"] or "", row["postal_code"] or "", row["address"] or "")))
        if wanted_place and not all(token in location.split() for token in wanted_place):
            continue
        ranked.append((name_score, row))
    ranked.sort(key=lambda item: (-item[0], item[1]["name"], item[1]["city"] or ""))
    return [dict(row) for _, row in ranked[:limit]]


def hvac_matches(db, name: str, limit=12):
    key = normalize(name)
    if len(key) < 3:
        return []
    rows = db.execute("SELECT * FROM hvac_deals").fetchall()
    ranked = [(score_name(key, row["target_key"]), row) for row in rows]
    ranked = [(score, row) for score, row in ranked if score]
    ranked.sort(key=lambda item: (item[0], item[1]["closed_date"] or item[1]["announced_date"] or ""), reverse=True)
    return [dict(row) for _, row in ranked[:limit]]


def wikidata_lookup(db, name: str):
    """Wikidata is a clue source. Its ownership claims never become a verified PE verdict."""
    key = normalize(name)
    if len(key) < 3:
        return []
    cached = db.execute("SELECT payload,fetched_at FROM wikidata_cache WHERE name_key=?", (key,)).fetchone()
    if cached and datetime.now(timezone.utc) - datetime.fromisoformat(cached["fetched_at"]) < timedelta(days=7):
        return json.loads(cached["payload"])
    params = urllib.parse.urlencode({"action": "wbsearchentities", "search": name,
                                     "language": "en", "format": "json", "limit": "5", "maxlag": "5"})
    try:
        result = json.loads(fetch(f"{WIKIDATA_API}?{params}", timeout=10))
        items = [
            {"name": item["label"], "description": item.get("description", ""),
             "url": f"https://www.wikidata.org/wiki/{item['id']}", "id": item["id"]}
            for item in result.get("search", []) if normalize(item.get("label")) == key
        ]
        with db:
            db.execute("INSERT OR REPLACE INTO wikidata_cache VALUES (?,?,?)",
                       (key, json.dumps(items), datetime.now(timezone.utc).isoformat()))
        return items
    except Exception:
        return []


def wikipedia_article(name: str):
    params = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "content",
                                     "rvslots": "main", "titles": name, "redirects": "1", "format": "json",
                                     "maxlag": "5"})
    result = json.loads(fetch(f"{WIKIPEDIA_API}?{params}", timeout=10))
    page = next(iter(result.get("query", {}).get("pages", {}).values()), {})
    if "missing" in page or not page.get("revisions"):
        return None
    return {"title": page["title"], "text": page["revisions"][0]["slots"]["main"]["*"],
            "url": "https://en.wikipedia.org/wiki/" + page["title"].replace(" ", "_")}


def wikipedia_search_title(name: str):
    params = urllib.parse.urlencode({"action": "opensearch", "search": name,
                                     "limit": "5", "format": "json", "maxlag": "5"})
    result = json.loads(fetch(f"{WIKIPEDIA_API}?{params}", timeout=10))
    key = normalize(name)
    return next((title for title in result[1]
                 if normalize(title) == key or normalize(title).startswith(key + " ")), None)


def wikipedia_brand_owner(name: str):
    """Find a company whose infobox explicitly includes a brand without its own article."""
    params = urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": name,
                                     "srlimit": "3", "format": "json", "maxlag": "5"})
    result = json.loads(fetch(f"{WIKIPEDIA_API}?{params}", timeout=10))
    key = normalize(name)
    for hit in result.get("query", {}).get("search", []):
        article = wikipedia_article(hit["title"])
        if not article:
            continue
        brands = normalize(infobox_facts(article["text"]).get("brands", ""))
        if key in brands:
            return article
    return None


def infobox_facts(text: str):
    match = re.search(r"(?im)^\{\{Infobox\s+(?:company|brand|restaurant)\b", text)
    if not match:
        return {}
    start = match.start()
    depth = 0
    end = start
    while end < min(len(text), start + 25000):
        if text.startswith("{{", end):
            depth += 1
            end += 2
        elif text.startswith("}}", end):
            depth -= 1
            end += 2
            if depth == 0:
                break
        else:
            end += 1
    facts = {}
    for line in text[match.end():end - 2].splitlines():
        field = re.match(r"^\|\s*([a-z_]+)\s*=\s*(.*)$", line.strip())
        if field:
            facts[field.group(1)] = field.group(2).strip()
    return facts


def wiki_link(value: str):
    match = re.search(r"\[\[([^]|]+)(?:\|[^]]+)?\]\]", value or "")
    return match.group(1).strip() if match else None


def wikipedia_chain(db, name: str):
    normalized_name = normalize(name)
    if len(normalized_name) < 3:
        return []
    key = "v3:" + normalized_name
    cached = db.execute("SELECT payload,fetched_at FROM wikipedia_cache WHERE name_key=?", (key,)).fetchone()
    if cached and datetime.now(timezone.utc) - datetime.fromisoformat(cached["fetched_at"]) < timedelta(days=7):
        return json.loads(cached["payload"])
    chain = []
    seen = set()
    title = name
    try:
        for depth in range(4):
            article = wikipedia_article(title)
            if not article and depth == 0:
                suggested = wikipedia_search_title(name)
                article = wikipedia_article(suggested) if suggested else None
            if not article and depth == 0:
                article = wikipedia_brand_owner(name)
                if article:
                    chain.append({"name": name, "url": article["url"],
                                  "reported_parent": article["title"],
                                  "pe_firm_description": False, "pe_activity": False,
                                  "public_listing": False})
            if not article or article["title"] in seen:
                break
            seen.add(article["title"])
            facts = infobox_facts(article["text"])
            description = re.search(r"\{\{[Ss]hort description\|([^}]+)\}\}", article["text"])
            is_pe = "private equity" in normalize((description.group(1) if description else "") + " " + facts.get("industry", ""))
            pe_activity = is_pe or "private equity" in normalize(facts.get("products", ""))
            owner = wiki_link(facts.get("parent", "")) or wiki_link(facts.get("owner", ""))
            chain.append({"name": article["title"], "url": article["url"],
                          "reported_parent": owner, "pe_firm_description": is_pe,
                          "pe_activity": pe_activity,
                          "public_listing": bool(facts.get("traded_as"))})
            if is_pe or not owner:
                break
            title = owner
    except Exception:
        pass
    with db:
        db.execute("INSERT OR REPLACE INTO wikipedia_cache VALUES (?,?,?)",
                   (key, json.dumps(chain), datetime.now(timezone.utc).isoformat()))
    return chain


def lookup(db, name: str, place: str = "", include_wikidata=True):
    vets = vet_matches(db, name, place)
    hvac = hvac_matches(db, name)
    exact_vets = [row for row in vets if normalize(row["name"]) == normalize(name)]
    exact_hvac = [row for row in hvac if normalize(row["target"]) == normalize(name)]
    return {
        "query": {"name": name, "place": place},
        "vets": vets,
        "hvac": hvac,
        "identity_ambiguous": len(exact_vets) > 1 and not place,
        "exact_vet_count": len(exact_vets),
        "exact_hvac_count": len(exact_hvac),
        "wikidata": wikidata_lookup(db, name) if include_wikidata and name and not vets and not hvac else [],
        "wikipedia_chain": wikipedia_chain(db, name) if name and not vets and not hvac else [],
        "sources": {
            "vet": {"name": "Private Equity Vet", "url": VET_PAGE, "download": VET_URL,
                    "synced": (db.execute("SELECT fetched_at FROM source_sync WHERE source='vet'").fetchone() or [None])[0]},
            "hvac": {"name": "hvacrollups", "url": HVAC_PAGE, "download": HVAC_URL,
                     "synced": (db.execute("SELECT fetched_at FROM source_sync WHERE source='hvac'").fetchone() or [None])[0]},
        },
    }
